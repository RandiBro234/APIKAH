"""Utilitas bersama: bulan, retry, download dengan resume, manifest, logging."""
from __future__ import annotations

import errno
import hashlib
import json
import logging
import math
import os
import threading
import time
from calendar import monthrange
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Iterator

from . import config

log = logging.getLogger("crawler")
_THREAD_LOCKS: dict[str, threading.RLock] = {}
_THREAD_LOCKS_GUARD = threading.Lock()


def setup_logging(name: str) -> None:
    config.LOGS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(config.LOGS / f"{name}.log")],
    )


def iter_months(start: date = config.START, end: date = config.END) -> Iterator[tuple[int, int]]:
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m == 13:
            y, m = y + 1, 1


def days_in_month(year: int, month: int) -> list[str]:
    return [f"{d:02d}" for d in range(1, monthrange(year, month)[1] + 1)]


def months_from_end(year: int, month: int, end: date = config.END) -> int:
    return (end.year - year) * 12 + (end.month - month)


def with_retry(fn: Callable, *args, retries: int = config.RETRIES,
               backoff: int = config.BACKOFF_SECONDS, **kwargs):
    last = None
    for attempt in range(1, retries + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - sengaja luas, lalu dicatat
            last = exc
            log.warning("percobaan %d/%d gagal: %s", attempt, retries, str(exc)[:300])
            if attempt < retries:
                time.sleep(backoff * attempt)
    raise last  # type: ignore[misc]


def done(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def _thread_lock(path: Path) -> threading.RLock:
    key = os.path.normcase(str(path.resolve()))
    with _THREAD_LOCKS_GUARD:
        return _THREAD_LOCKS.setdefault(key, threading.RLock())


@contextmanager
def _file_lock(lock_path: Path):
    """Lock one path across threads and processes on Windows/POSIX."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with _thread_lock(lock_path), lock_path.open("a+b") as stream:
        if os.name == "nt":
            import msvcrt

            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            while True:
                stream.seek(0)
                try:
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError as exc:
                    if exc.errno not in (errno.EACCES, errno.EDEADLK) and getattr(exc, "winerror", None) != 33:
                        raise
                    time.sleep(0.02)
            try:
                yield
            finally:
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def target_lock(path: Path):
    """Prevent concurrent writes; keep persistent lock files out of data folders."""
    key = os.path.normcase(str(Path(path).resolve())).encode("utf-8")
    lock_name = hashlib.sha256(key).hexdigest() + ".lock"
    return _file_lock(config.METADATA / "locks" / lock_name)


def finalize_download(part: Path, dest: Path) -> bool:
    """Publish a completed part without replacing an existing destination.

    Returns False if another process has already completed the destination.
    The part and destination must be on the same filesystem (they are siblings).
    """
    try:
        os.link(part, dest)
    except FileExistsError:
        if done(dest):
            part.unlink(missing_ok=True)
            return False
        raise
    part.unlink()
    return True


def download_file(url: str, dest: Path, timeout: int = config.HTTP_TIMEOUT) -> str:
    """Unduh dengan resume (.part). Return 'ok' | 'skipped' | 'missing' (404)."""
    import requests

    dest = Path(dest)
    with target_lock(dest):
        if done(dest):
            return "skipped"
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(dest.suffix + ".part")
        pos = part.stat().st_size if part.exists() else 0
        headers = {"Range": f"bytes={pos}-"} if pos else {}
        with requests.get(url, stream=True, headers=headers, timeout=timeout) as r:
            if r.status_code == 404:
                return "missing"
            if r.status_code == 416:      # part dianggap lengkap oleh server
                return "ok" if finalize_download(part, dest) else "skipped"
            r.raise_for_status()
            mode = "ab" if (pos and r.status_code == 206) else "wb"
            with open(part, mode) as f:
                for chunk in r.iter_content(1024 * 1024):
                    f.write(chunk)
        return "ok" if finalize_download(part, dest) else "skipped"


# ---------------------------------------------------------------- manifest
def manifest_path(name: str) -> Path:
    return config.METADATA / "manifests" / f"manifest_{name}.json"


def _manifest_lock(path: Path):
    """Serialize manifest read-modify-write across threads and processes."""
    return _file_lock(path.with_suffix(".lock"))


def manifest_load(name: str) -> dict:
    p = manifest_path(name)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        # Bisa terjadi kalau proses lain sedang menulis berkas yang sama (crawl paralel).
        # Manifest hanya untuk PELAPORAN -- jangan sampai menjatuhkan crawl karenanya.
        log.warning("manifest %s tidak terbaca (mungkin ditulis proses lain); dianggap kosong", name)
        return {}


def manifest_update(name: str, key: str, status: str, note: str = "") -> None:
    path = manifest_path(name)
    with _manifest_lock(path):
        m = manifest_load(name)
        m[key] = {"status": status, "note": note[:300], "ts": datetime.now().isoformat(timespec="seconds")}
        tmp = path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(m, indent=1, ensure_ascii=False))
        os.replace(tmp, path)


# ---------------------------------------------------------------- tile helper
def floor_to(x: float, step: int) -> int:
    return int(math.floor(x / step) * step)


def tile_origins(north: float, west: float, south: float, east: float, step: int) -> list[tuple[int, int]]:
    """Daftar (lat_sw, lon_sw) tile bertepi `step` derajat yang menutupi bbox."""
    lats = range(floor_to(south, step), math.ceil(north / step) * step, step)
    lons = range(floor_to(west, step), math.ceil(east / step) * step, step)
    return [(la, lo) for la in lats for lo in lons]


def ns_ew(lat: int, lon: int) -> tuple[str, int, str, int]:
    return ("N" if lat >= 0 else "S"), abs(lat), ("E" if lon >= 0 else "W"), abs(lon)

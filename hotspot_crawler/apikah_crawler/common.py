"""Utilitas bersama: bulan, retry, download dengan resume, manifest, logging."""
from __future__ import annotations

import errno
import hashlib
import json
import logging
import math
import os
import re
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
    if dest.is_file() and dest.stat().st_size > 0:
        part.unlink(missing_ok=True)
        return False
    if dest.exists():
        if dest.is_file() and dest.stat().st_size == 0:
            dest.unlink()
        else:
            raise FileExistsError(f"download destination is not a regular file: {dest}")
    if not part.is_file() or part.stat().st_size == 0:
        raise ValueError(f"refusing to finalize empty or missing partial file: {part}")
    try:
        os.link(part, dest)
    except FileExistsError:
        if dest.is_file() and dest.stat().st_size > 0:
            part.unlink(missing_ok=True)
            return False
        raise
    part.unlink()
    return True


def _resume_metadata_path(part: Path) -> Path:
    return part.with_name(part.name + ".meta.json")


def _read_resume_metadata(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_resume_metadata(path: Path, value: dict) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    os.replace(temporary, path)


def _clear_partial(part: Path, metadata: Path) -> None:
    part.unlink(missing_ok=True)
    metadata.unlink(missing_ok=True)


def _parse_content_range(value: str | None) -> tuple[int, int, int] | None:
    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", value or "")
    return tuple(map(int, match.groups())) if match else None


def _publish_partial(part: Path, dest: Path, metadata: Path) -> str:
    status = "ok" if finalize_download(part, dest) else "skipped"
    metadata.unlink(missing_ok=True)
    return status


def download_file(url: str, dest: Path, timeout: int = config.HTTP_TIMEOUT) -> str:
    """Unduh dengan resume (.part). Return 'ok' | 'skipped' | 'missing' (404)."""
    import requests

    dest = Path(dest)
    with target_lock(dest):
        if done(dest):
            return "skipped"
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(dest.suffix + ".part")
        metadata_path = _resume_metadata_path(part)
        metadata = _read_resume_metadata(metadata_path) if part.exists() else None
        source_fingerprint = hashlib.sha256(url.encode("utf-8")).hexdigest()
        validator = (metadata or {}).get("etag") or (metadata or {}).get("last_modified")
        total = (metadata or {}).get("total_length")
        pos = part.stat().st_size if part.exists() else 0

        # Legacy or unvalidated partials cannot be safely appended to.
        if part.exists() and ((metadata or {}).get("url_sha256") != source_fingerprint or not validator
                              or not isinstance(total, int) or total <= 0 or pos > total):
            _clear_partial(part, metadata_path)
            metadata, validator, total, pos = None, None, None, 0
        if part.exists() and pos == total:
            return _publish_partial(part, dest, metadata_path)

        for attempt in range(2):
            headers = {}
            if pos:
                headers["Range"] = f"bytes={pos}-"
                headers["If-Range"] = validator
            with requests.get(url, stream=True, headers=headers, timeout=timeout) as response:
                if response.status_code == 404:
                    return "missing"

                if response.status_code == 416:
                    if attempt == 0:
                        _clear_partial(part, metadata_path)
                        metadata, validator, total, pos = None, None, None, 0
                        continue
                    response.raise_for_status()
                    raise IOError("server rejected the full restart with HTTP 416")

                if response.status_code == 206:
                    content_range = _parse_content_range(response.headers.get("Content-Range"))
                    etag = response.headers.get("ETag")
                    last_modified = response.headers.get("Last-Modified")
                    valid_range = bool(pos and content_range and content_range[0] == pos)
                    if content_range:
                        start, end, received_total = content_range
                        valid_range = valid_range and end >= start and received_total > end
                        valid_range = valid_range and (total is None or received_total == total)
                        content_length = response.headers.get("Content-Length")
                        if content_length is not None:
                            valid_range = valid_range and int(content_length) == end - start + 1
                    if metadata and metadata.get("etag"):
                        valid_range = valid_range and etag == metadata["etag"]
                    elif metadata and metadata.get("last_modified"):
                        valid_range = valid_range and last_modified == metadata["last_modified"]
                    if not valid_range:
                        if attempt == 0:
                            _clear_partial(part, metadata_path)
                            metadata, validator, total, pos = None, None, None, 0
                            continue
                        raise IOError("server returned an invalid or mismatched Content-Range")
                    new_total = content_range[2]
                    mode = "ab"
                elif response.status_code == 200:
                    if pos:
                        _clear_partial(part, metadata_path)
                        metadata, pos = None, 0
                    response.raise_for_status()
                    content_length = response.headers.get("Content-Length")
                    new_total = int(content_length) if content_length is not None else None
                    mode = "wb"
                    etag = response.headers.get("ETag")
                    last_modified = response.headers.get("Last-Modified")
                else:
                    response.raise_for_status()
                    raise IOError(f"unexpected HTTP status {response.status_code}")

                new_metadata = {
                    "url_sha256": source_fingerprint,
                    "etag": etag or (metadata or {}).get("etag"),
                    "last_modified": last_modified or (metadata or {}).get("last_modified"),
                    "total_length": new_total,
                }
                _write_resume_metadata(metadata_path, new_metadata)
                with part.open(mode) as stream:
                    for chunk in response.iter_content(1024 * 1024):
                        if chunk:
                            stream.write(chunk)

            size = part.stat().st_size if part.exists() else 0
            if not size:
                _clear_partial(part, metadata_path)
                raise IOError("download returned an empty file")
            if new_total is not None and size != new_total:
                if size > new_total:
                    _clear_partial(part, metadata_path)
                raise IOError(f"download size {size} does not match expected length {new_total}")
            return _publish_partial(part, dest, metadata_path)

        raise IOError("download restart exhausted without a response")


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

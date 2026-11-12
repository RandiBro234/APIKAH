"""Cocokkan isi data mentah dengan manifest checksum.

    python verify_data.py                    # default: data/MANIFEST_raw.csv
    python verify_data.py --manifest lain.csv --root data/features_raw

Dipakai saat menerima salinan data dari rekan/tim: pastikan berkas yang
diterima identik dengan yang tercatat, tanpa perlu mengunduh ulang.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path

from . import config


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(manifest: Path, root: Path) -> dict:
    """Return hitungan ok/mismatch/missing/invalid dan exit code yang sesuai."""
    result = {"ok": 0, "mismatch": 0, "missing": 0, "invalid": 0, "exit_code": 0}
    with Path(manifest).open(newline="", encoding="utf-8") as stream:
        for row in csv.reader(stream):
            if not row or row[0] == "path":
                continue
            if len(row) != 3:
                result["invalid"] += 1
                continue
            relative, size_text, expected = row
            try:
                size = int(size_text)
            except ValueError:
                result["invalid"] += 1
                continue
            path = Path(manifest).parent / relative
            if not path.is_file():
                result["missing"] += 1
                continue
            if path.stat().st_size != size or _sha256(path) != expected:
                result["mismatch"] += 1
                continue
            result["ok"] += 1

    result["exit_code"] = 0 if result["ok"] and not (
        result["mismatch"] or result["missing"] or result["invalid"]) else 1
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path,
                        default=config.DATA_DIR / "MANIFEST_raw.csv")
    parser.add_argument("--root", type=Path, default=config.FEATURES_RAW,
                        help="folder data mentah (default: data/features_raw)")
    args = parser.parse_args(argv)

    if not args.manifest.is_file():
        print(f"manifest tidak ditemukan: {args.manifest}")
        return 2

    result = verify(args.manifest, args.root)
    print(f"ok       : {result['ok']}")
    print(f"mismatch : {result['mismatch']}")
    print(f"missing  : {result['missing']}")
    print(f"invalid  : {result['invalid']}")
    if result["exit_code"]:
        print("\nTIDAK COCOK: jangan pakai data ini sebelum diperbaiki.")
    else:
        print("\nSEMUA COCOK dengan manifest.")
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())

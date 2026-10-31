"""Copy legacy crawler outputs into APIKAH/data without deleting originals.

Run a read-only inventory first; use --apply only after confirming the plan.
Every copied file is SHA-256 checked. Conflicts are never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import tempfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_plan(project_root: Path, legacy_root: Path | None = None) -> list[tuple[Path, Path]]:
    project_root = Path(project_root).resolve()
    legacy_root = Path(legacy_root or project_root / "hotspot_crawler" / "hotspot_crawler" / "data")
    data_root = project_root / "data"

    partials = sorted(legacy_root.rglob("*.part")) if legacy_root.exists() else []
    if partials:
        raise RuntimeError(f"partial files must finish before migration: {partials[0]}")

    plan: list[tuple[Path, Path]] = []

    def add_tree(source: Path, destination: Path) -> None:
        if source.is_file():
            plan.append((source, destination / source.name))
        elif source.is_dir():
            for file in sorted(source.rglob("*")):
                if file.is_file():
                    plan.append((file, destination / file.relative_to(source)))

    raw = legacy_root / "raw"
    if raw.exists():
        for source in sorted(p for p in raw.iterdir() if p.is_dir()):
            add_tree(source, data_root / "features_raw" / "copernicus" / source.name)

    static = legacy_root / "static"
    if static.exists():
        for source in sorted(static.iterdir()):
            if source.name == "mcd64a1":
                target = data_root / "features_raw" / "nasa" / "mcd64a1"
            else:
                target = data_root / "features_raw" / "static" / source.name
            add_tree(source, target)

    add_tree(legacy_root / "processed", data_root / "features_processed")

    logs = legacy_root / "logs"
    if logs.exists():
        for source in sorted(p for p in logs.iterdir() if p.is_file()):
            category = "manifests" if source.name.startswith("manifest_") and source.suffix == ".json" else "logs"
            plan.append((source, data_root / "metadata" / category / source.name))

    return plan


def apply_plan(plan: list[tuple[Path, Path]], *, dry_run: bool) -> dict[str, int]:
    result = {"planned": 0, "copied": 0, "skipped": 0}
    for source, destination in plan:
        if not source.is_file():
            raise FileNotFoundError(f"source disappeared during migration: {source}")

        if destination.exists():
            if destination.is_file() and source.stat().st_size == destination.stat().st_size \
                    and sha256(source) == sha256(destination):
                result["skipped"] += 1
                continue
            raise FileExistsError(f"destination exists with different content: {destination}")

        if dry_run:
            result["planned"] += 1
            continue

        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            prefix=f"{destination.name}.", suffix=".migrate.part",
            dir=destination.parent, delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
        try:
            shutil.copyfile(source, temp_path)
            shutil.copystat(source, temp_path)
            if source.stat().st_size != temp_path.stat().st_size or sha256(source) != sha256(temp_path):
                raise IOError(f"copy verification failed: {source}")
            # rename (not replace) refuses to overwrite a destination created concurrently.
            os.rename(temp_path, destination)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
        result["copied"] += 1

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path,
                        default=Path(__file__).resolve().parents[2],
                        help="APIKAH repository root")
    parser.add_argument("--apply", action="store_true",
                        help="copy and verify; default only prints a dry-run inventory")
    args = parser.parse_args()

    try:
        plan = build_plan(args.repo_root)
        totals = apply_plan(plan, dry_run=not args.apply)
    except (FileExistsError, FileNotFoundError, OSError, RuntimeError) as exc:
        parser.error(str(exc))

    size = sum(source.stat().st_size for source, _ in plan)
    print(f"files: {len(plan)} | {size / (1024 ** 3):.2f} GiB")
    print(f"mode: {'COPY + SHA-256 VERIFY' if args.apply else 'DRY RUN (no writes)'}")
    print(f"planned: {totals['planned']} | copied: {totals['copied']} | already identical: {totals['skipped']}")
    print("source files are retained; no deletion performed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Kontrak path data project. Tanpa jaringan dan tanpa membaca dataset."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import traceback
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import config
import crawl_static
from common import manifest_path

TESTS = []


def test(fn):
    TESTS.append((fn.__name__, fn))
    return fn


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = PROJECT_ROOT / "data"


@test
def test_data_root_abs_and_di_bawah_root_project():
    assert config.DATA_DIR.is_absolute(), f"DATA_DIR harus absolut: {config.DATA_DIR}"
    assert config.DATA_DIR == DATA_ROOT, f"expected {DATA_ROOT}, got {config.DATA_DIR}"


@test
def test_kategori_data_mengikuti_struktur_baru():
    assert config.RAW == DATA_ROOT / "features_raw" / "copernicus"
    assert config.STATIC == DATA_ROOT / "features_raw" / "static"
    assert config.PROCESSED == DATA_ROOT / "features_processed"
    assert config.LOGS == DATA_ROOT / "metadata" / "logs"


@test
def test_label_gabungan_mengarah_ke_kategori_hotspot():
    assert config.HOTSPOT_LABELS == (
        DATA_ROOT / "hotspot_indonesia" / "combined" /
        "hotspot_indonesia_2012_2026-09.parquet"
    )


@test
def test_manifest_terpisah_dari_log_runtime():
    assert manifest_path("era5land") == DATA_ROOT / "metadata" / "manifests" / "manifest_era5land.json"


@test
def test_mcd64a1_disimpan_di_nasa_raw():
    assert config.MCD64A1_DIR == DATA_ROOT / "features_raw" / "nasa" / "mcd64a1"


@test
def test_burned_crawler_mengarah_ke_nasa_raw():
    output = StringIO()
    with redirect_stdout(output):
        crawl_static.do_burned(dry=True)
    assert str(config.MCD64A1_DIR) in output.getvalue()


@test
def test_path_sama_saat_diimport_dari_cwd_lain():
    config_dir = Path(config.__file__).resolve().parent
    script = (
        "import sys; "
        f"sys.path.insert(0, {str(config_dir)!r}); "
        "import config; print(config.DATA_DIR.resolve())"
    )
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=tmp, check=True,
            capture_output=True, text=True,
        )
    got = Path(result.stdout.strip())
    assert got == DATA_ROOT, f"CWD temp menghasilkan {got}, expected {DATA_ROOT}"


def main() -> int:
    passed = failed = 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"[OK  ] {name}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] {name}: {type(exc).__name__}: {exc}")
            traceback.print_exc(limit=2)
            failed += 1
    print(f"\nRingkasan: {passed} OK, {failed} FAIL")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Skeleton pipeline harian.

Fase 0: hanya memvalidasi kontrak dan menampilkan rencana langkah.
Belum mengambil data, belum menjalankan model, belum menulis ke database.

Contoh:
    python backend/pipeline/run_daily.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "feature_contract.json"

REQUIRED_ENV = [
    "FIRMS_MAP_KEY",
    "DATABASE_URL",
]

STEPS = [
    "Ambil hotspot FIRMS NRT 72 jam dan agregasi label tanggal lokal",
    "Ambil forecast cuaca (Open-Meteo/GFS) untuk horizon pendek",
    "Ambil indeks iklim NOAA bulanan",
    "Bangun fitur kanonik dengan build_features_live(as_of_date)",
    "Muat artefak model per horizon dan validasi feature_list",
    "Jalankan inference, kalibrasi, level 1-4, dan top-3 drivers",
    "Tulis predictions_latest, hotspots_recent, model_runs ke Supabase",
    "Tulis GeoJSON harian ke R2",
    "Verifikasi prediksi kemarin terhadap hotspot aktual",
]


def load_contract() -> dict:
    with CONTRACT.open(encoding="utf-8") as handle:
        return json.load(handle)


def check_env() -> list[str]:
    missing = [name for name in REQUIRED_ENV if not os.getenv(name)]
    return missing


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", dest="dry_run", action="store_true", default=True)
    parser.add_argument("--execute", dest="dry_run", action="store_false")
    args = parser.parse_args(argv)

    contract = load_contract()
    features = contract.get("feature_columns", [])
    grid = contract.get("grid", {})

    print("Kontrak:", contract.get("contract_version"), contract.get("status"))
    print("Pipeline kanonik:", contract.get("canonical_pipeline"))
    print("Fitur:", len(features))
    print("Grid step:", grid.get("step_degrees"))
    print("cell_id:", grid.get("cell_id_formula"))

    missing = check_env()
    if missing:
        print("Env belum diset:", ", ".join(missing))
    else:
        print("Env wajib tersedia.")

    if args.dry_run:
        print("\nRencana langkah harian:")
        for index, step in enumerate(STEPS, start=1):
            print(f"{index}. {step}")
        print("\nDry-run selesai. Tidak ada data yang diambil atau ditulis.")
        return 0

    raise SystemExit("Mode non-dry-run belum diimplementasikan pada Fase 0.")


if __name__ == "__main__":
    raise SystemExit(main())

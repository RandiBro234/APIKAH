"""Laporan kelengkapan crawl dari manifest (TODO #7).

    python report_manifest.py              # ringkasan semua manifest
    python report_manifest.py --missing 40 # tampilkan 40 bulan bermasalah (default 20)
    python report_manifest.py --quiet      # hanya baris ringkasan

Membaca `data/logs/manifest_*.json` yang ditulis `common.manifest_update()`, lalu
membandingkannya dengan daftar yang SEHARUSNYA ada (dihitung dari config.START..END)
dan dengan berkas yang benar-benar ada di disk.

Tiga jenis masalah yang dibedakan, karena penanganannya berbeda:

  - `belum`   : belum pernah dicoba  -> jalankan crawler, ia akan mengerjakannya
  - `gagal`   : pernah dicoba, error -> jalankan crawler lagi (resume otomatis)
  - `hilang`  : manifest bilang 'ok' tapi berkasnya tidak ada/size 0 -> perlu diulang

Tidak menyentuh jaringan dan tidak mengubah apa pun.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from typing import Iterator

import config
from common import done, iter_months, manifest_load

STATUSES = ["ok", "failed", "missing", "skipped", "manual_pending"]
BELUM = "belum"


def expected_era5land() -> Iterator[tuple[str, object]]:
    """177 bulan x 2 grup (instant, accum)."""
    for y, m in iter_months():
        for group in ("instant", "accum"):
            yield (f"era5land/{group}/{y}-{m:02d}",
                   config.RAW / "era5land" / group / f"{y}-{m:02d}.nc")


def expected_cems() -> Iterator[tuple[str, object]]:
    """177 bulan, satu berkas per bulan."""
    for y, m in iter_months():
        yield (f"cems_fire/{y}-{m:02d}", config.RAW / "cems_fire" / f"{y}-{m:02d}.nc")


def human_mb(nbytes: int) -> str:
    for unit, div in (("GB", 1 << 30), ("MB", 1 << 20), ("KB", 1 << 10)):
        if nbytes >= div:
            return f"{nbytes / div:.1f} {unit}"
    return f"{nbytes} B"


def summarize(judul: str, pairs: list[tuple[str, object]], manifest: dict,
              missing_n: int) -> list[tuple[str, str]]:
    """Cetak ringkasan satu sumber. Kembalikan daftar (kunci, alasan) yang bermasalah."""
    print(f"=== {judul} ===")
    if not pairs:
        print("  (tidak ada daftar yang diharapkan; hanya statistik manifest)")
        counts = Counter((v or {}).get("status", "?") for v in manifest.values())
        for k, v in counts.most_common():
            print(f"  {k:<16} {v}")
        print()
        return []

    status: Counter[str] = Counter()
    bermasalah: list[tuple[str, str]] = []
    nbytes = 0
    n_disk = 0

    for key, path in pairs:
        entry = manifest.get(key)
        st = (entry or {}).get("status", BELUM)
        status[st] += 1
        ada = done(path)
        if ada:
            n_disk += 1
            try:
                nbytes += path.stat().st_size
            except OSError:
                pass
        if st == BELUM:
            bermasalah.append((key, BELUM))
        elif st in ("failed", "missing"):
            bermasalah.append((key, st))
        elif st == "ok" and not ada:
            bermasalah.append((key, "hilang"))

    print(f"  diharapkan          : {len(pairs)}")
    print(f"  tercatat di manifest: {len(pairs) - status[BELUM]}")
    print("  status              : " + " | ".join(
        f"{s} {status[s]}" for s in [*STATUSES, BELUM] if status[s]))
    print(f"  berkas ada di disk  : {n_disk} ({human_mb(nbytes)})")
    n_gagal = sum(1 for _, r in bermasalah if r in ("failed", "missing", "hilang"))
    print(f"  PERLU DIULANG       : {len(bermasalah)}  (gagal/hilang: {n_gagal})")
    print()

    if bermasalah_show := bermasalah[:missing_n]:
        for key, reason in bermasalah_show:
            print(f"    [{reason:<7}] {key}")
        sisa = len(bermasalah) - len(bermasalah_show)
        if sisa > 0:
            print(f"    ... dan {sisa} lainnya (pakai --missing N untuk melihat lebih banyak)")
        print()
    return bermasalah


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--missing", type=int, default=20,
                    help="jumlah baris bermasalah yang ditampilkan per sumber (default 20)")
    ap.add_argument("--quiet", action="store_true", help="hanya ringkasan singkat")
    args = ap.parse_args(argv)

    print(f"Sumber kebenaran: config.py  (ACTIVE_AREA={config.ACTIVE_AREA}, "
          f"{config.START} s/d {config.END})")
    print(f"Folder berkas  : {config.RAW.resolve()}")
    print()

    n_show = 0 if args.quiet else args.missing

    m_era5 = manifest_load("era5land")
    m_fire = manifest_load("cems_fire")
    m_stat = manifest_load("static")

    bad_era5 = summarize("ERA5-Land (CDS)", list(expected_era5land()), m_era5, n_show)
    bad_fire = summarize("CEMS Fire (EWDS)", list(expected_cems()), m_fire, n_show)
    summarize("Statis", [], m_stat, n_show)

    total_bad = len(bad_era5) + len(bad_fire)
    print("=" * 60)
    if total_bad == 0:
        print("LENGKAP: tidak ada bulan ERA5-Land/CEMS Fire yang bermasalah.")
    else:
        print(f"BELUM LENGKAP: {total_bad} kunci perlu diulang "
              f"(ERA5-Land {len(bad_era5)}, CEMS Fire {len(bad_fire)}).")
        print("Jalankan ulang crawler yang sama; skrip melewati berkas yang sudah ada:")
        print("    python crawl_copernicus.py all")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

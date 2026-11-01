"""Verifikasi isi data/features_raw terhadap data/MANIFEST_raw.csv."""
from __future__ import annotations

import csv
import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from apikah_crawler.verify_data import verify


def sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


class VerifyDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.data = self.repo / "data"
        self.manifest = self.data / "MANIFEST_raw.csv"

    def tearDown(self):
        self.temp.cleanup()

    def write_manifest(self, rows):
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["path", "bytes", "sha256"])
            writer.writerows(rows)

    def put(self, relative: str, payload: bytes) -> Path:
        path = self.data / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def test_semua_cocok(self):
        a = self.put("features_raw/copernicus/a.nc", b"alpha")
        b = self.put("features_raw/nasa/b.hdf", b"beta")
        self.write_manifest([
            ("features_raw/copernicus/a.nc", a.stat().st_size, sha(b"alpha")),
            ("features_raw/nasa/b.hdf", b.stat().st_size, sha(b"beta")),
        ])

        result = verify(self.manifest, self.data / "features_raw")

        self.assertEqual((result["ok"], result["mismatch"], result["missing"]), (2, 0, 0))
        self.assertEqual(result["exit_code"], 0)

    def test_isi_berubah_terdeteksi(self):
        a = self.put("features_raw/copernicus/a.nc", b"alpha")
        self.write_manifest([
            ("features_raw/copernicus/a.nc", a.stat().st_size, sha(b"alpha"))])
        a.write_bytes(b"alpha-tampered")

        result = verify(self.manifest, self.data / "features_raw")

        self.assertEqual((result["ok"], result["mismatch"]), (0, 1))
        self.assertEqual(result["exit_code"], 1)

    def test_berkas_hilang_terdeteksi(self):
        b = self.put("features_raw/nasa/b.hdf", b"beta")
        self.write_manifest([
            ("features_raw/nasa/b.hdf", b.stat().st_size, sha(b"beta")),
            ("features_raw/nasa/hilang.hdf", 4, sha(b"gone")),
        ])

        result = verify(self.manifest, self.data / "features_raw")

        self.assertEqual((result["ok"], result["missing"]), (1, 1))
        self.assertEqual(result["exit_code"], 1)

    def test_baris_rusak_dilaporkan_bukan_dilewati(self):
        self.write_manifest([("features_raw/x.nc", "bukan-angka", "")])

        result = verify(self.manifest, self.data / "features_raw")

        self.assertEqual(result["invalid"], 1)
        self.assertEqual(result["exit_code"], 1)


if __name__ == "__main__":
    unittest.main()

"""Safety tests for migrating crawler outputs into APIKAH/data."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from migrate_data_layout import apply_plan, build_plan


class DataMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "APIKAH"
        self.legacy = self.repo / "hotspot_crawler" / "hotspot_crawler" / "data"
        self.repo.mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def put(self, relative: str, payload: bytes = b"sample") -> Path:
        path = self.legacy / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        return path

    def plan(self):
        return build_plan(self.repo, legacy_root=self.legacy)

    def test_maps_raw_static_processed_and_metadata(self):
        self.put("raw/era5land/instant/2022-12.nc")
        self.put("raw/cems_fire/2022-12.nc")
        self.put("static/mcd64a1/month.hdf")
        self.put("static/worldcover/tile.tif")
        self.put("processed/era5_daily/2022-12.parquet")
        self.put("logs/manifest_era5land.json")
        self.put("logs/crawl.log")

        got = {src.relative_to(self.legacy).as_posix(): dst.relative_to(self.repo / "data").as_posix()
               for src, dst in self.plan()}
        self.assertEqual(got["raw/era5land/instant/2022-12.nc"],
                         "features_raw/copernicus/era5land/instant/2022-12.nc")
        self.assertEqual(got["raw/cems_fire/2022-12.nc"],
                         "features_raw/copernicus/cems_fire/2022-12.nc")
        self.assertEqual(got["static/mcd64a1/month.hdf"], "features_raw/nasa/mcd64a1/month.hdf")
        self.assertEqual(got["static/worldcover/tile.tif"], "features_raw/static/worldcover/tile.tif")
        self.assertEqual(got["processed/era5_daily/2022-12.parquet"],
                         "features_processed/era5_daily/2022-12.parquet")
        self.assertEqual(got["logs/manifest_era5land.json"], "metadata/manifests/manifest_era5land.json")
        self.assertEqual(got["logs/crawl.log"], "metadata/logs/crawl.log")

    def test_dry_run_does_not_create_target_or_remove_source(self):
        source = self.put("raw/cems_fire/2022-12.nc", b"preserve me")
        plan = self.plan()

        result = apply_plan(plan, dry_run=True)

        self.assertEqual(result["planned"], 1)
        self.assertFalse((self.repo / "data" / "features_raw").exists())
        self.assertEqual(source.read_bytes(), b"preserve me")

    def test_apply_copies_verifies_and_preserves_source(self):
        source = self.put("raw/cems_fire/2022-12.nc", b"source payload")
        destination = self.repo / "data" / "features_raw" / "copernicus" / "cems_fire" / source.name

        result = apply_plan(self.plan(), dry_run=False)

        self.assertEqual(result["copied"], 1)
        self.assertEqual(destination.read_bytes(), source.read_bytes())
        self.assertTrue(source.exists())

    def test_identical_existing_target_is_safe_to_skip(self):
        source = self.put("raw/cems_fire/2022-12.nc", b"same payload")
        destination = self.repo / "data" / "features_raw" / "copernicus" / "cems_fire" / source.name
        destination.parent.mkdir(parents=True)
        destination.write_bytes(source.read_bytes())

        result = apply_plan(self.plan(), dry_run=False)

        self.assertEqual(result["skipped"], 1)

    def test_conflicting_target_is_never_overwritten(self):
        source = self.put("raw/cems_fire/2022-12.nc", b"source")
        destination = self.repo / "data" / "features_raw" / "copernicus" / "cems_fire" / source.name
        destination.parent.mkdir(parents=True)
        destination.write_bytes(b"other data")

        with self.assertRaises(FileExistsError):
            apply_plan(self.plan(), dry_run=False)
        self.assertEqual(destination.read_bytes(), b"other data")

    def test_partial_source_blocks_migration(self):
        self.put("raw/era5land/instant/2022-12.nc.part")

        with self.assertRaisesRegex(RuntimeError, "partial"):
            self.plan()


if __name__ == "__main__":
    unittest.main()

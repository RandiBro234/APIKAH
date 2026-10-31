"""Tests for tabular climate-index storage; never access production data/network."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from apikah_crawler import config
from apikah_crawler.crawl_static import do_enso
from apikah_crawler.climate_tables import write_climate_parquet


class ClimateParquetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old_static = config.STATIC
        self.old_processed = config.PROCESSED
        self.old_metadata = config.METADATA
        self.old_logs = config.LOGS
        config.STATIC = self.root / "features_raw" / "static"
        config.PROCESSED = self.root / "features_processed"
        config.METADATA = self.root / "metadata"
        config.LOGS = self.root / "metadata" / "logs"

    def tearDown(self):
        config.STATIC = self.old_static
        config.PROCESSED = self.old_processed
        config.METADATA = self.old_metadata
        config.LOGS = self.old_logs
        self.temp.cleanup()

    def test_write_climate_table_as_parquet(self):
        rows = [(2012, 1, 0.1), (2012, 2, 0.2)]
        dest = config.PROCESSED / "climate_index" / "nino34.parquet"

        write_climate_parquet("nino34", rows, dest)

        got = pd.read_parquet(dest)
        self.assertEqual(list(got.columns), ["year", "month", "nino34"])
        self.assertEqual(got.to_dict("records"), [
            {"year": 2012, "month": 1, "nino34": 0.1},
            {"year": 2012, "month": 2, "nino34": 0.2},
        ])

    def test_crawler_converts_existing_raw_text_without_network(self):
        source_dir = config.STATIC / "climate_index"
        source_dir.mkdir(parents=True)
        text = "year values follow\n2012 " + " ".join(
            str(month / 10) for month in range(1, 13)) + "\n"
        for name in config.ENSO_URLS:
            (source_dir / f"{name}.raw.txt").write_text(text, encoding="utf-8")

        with patch("requests.get", side_effect=AssertionError("unexpected network request")) as get:
            do_enso(dry=False)

        get.assert_not_called()
        for name in config.ENSO_URLS:
            dest = config.PROCESSED / "climate_index" / f"{name}.parquet"
            self.assertTrue(dest.is_file())
            self.assertEqual(len(pd.read_parquet(dest)), 12)
            self.assertEqual((source_dir / f"{name}.raw.txt").read_text(encoding="utf-8"), text)


if __name__ == "__main__":
    unittest.main()

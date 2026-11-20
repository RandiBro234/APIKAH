"""Tes kontrak fitur dan grid. Hanya memakai stdlib."""
from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "contracts" / "feature_contract.json"

EXPECTED_FEATURES = [
    "t2m_mean",
    "t2m_max",
    "t2m_min",
    "rh_mean",
    "rh_min",
    "wind_mean",
    "wind_max",
    "u10_mean",
    "v10_mean",
    "vpd_mean",
    "vpd_max",
    "swvl1_mean",
    "swvl4_mean",
    "precip_mm",
    "ssrd_mjm2",
    "pev_mm",
    "fwi",
    "dc",
    "dmc",
    "kbdi",
    "bulan",
    "hari_dalam_tahun",
    "musim_kemarau",
    "hujan_3h",
    "hujan_7h",
    "hujan_14h",
    "hujan_30h",
    "kering_beruntun",
    "t2m_mean_anom",
    "rh_mean_anom",
    "vpd_max_anom",
    "precip_mm_anom",
    "spi_30",
    "spi_90",
    "nino34_lag1",
    "nino34_lag2",
    "nino34_lag3",
    "dmi_lag1",
    "dmi_lag2",
    "dmi_lag3",
]


def cell_id(lat: float, lon: float, step: float = 0.25) -> int:
    lat_c = math.floor(lat / step) * step + step / 2
    lon_c = math.floor(lon / step) * step + step / 2
    lat_i = math.floor((lat_c + 12) / step)
    lon_i = math.floor((lon_c - 94) / step)
    return lat_i * 1000 + lon_i


class FeatureContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with CONTRACT_PATH.open(encoding="utf-8") as handle:
            cls.contract = json.load(handle)

    def test_contract_version_and_pipeline(self) -> None:
        self.assertEqual(self.contract["contract_version"], "1.0.0")
        self.assertEqual(self.contract["canonical_pipeline"], "hotspot_crawler")

    def test_feature_list_matches_expected(self) -> None:
        names = [column["name"] for column in self.contract["feature_columns"]]
        self.assertEqual(names, EXPECTED_FEATURES)
        self.assertEqual(len(names), len(set(names)))

    def test_feature_columns_do_not_include_keys_or_targets(self) -> None:
        names = {column["name"] for column in self.contract["feature_columns"]}
        excluded = self.contract["excluded_columns"]
        forbidden = set(excluded["keys"]) | set(excluded["targets"])
        self.assertFalse(names & forbidden)

    def test_every_feature_has_source_and_live_status(self) -> None:
        for column in self.contract["feature_columns"]:
            self.assertTrue(column.get("source"), column["name"])
            self.assertTrue(column.get("live"), column["name"])

    def test_grid_formula_is_stable(self) -> None:
        samples = [(-11.4, 94.1), (-6.1, 106.8), (0.0, 101.3), (3.3, 117.6), (6.4, 141.4)]
        ids = {cell_id(lat, lon) for lat, lon in samples}
        self.assertEqual(len(ids), len(samples))
        for value in ids:
            self.assertGreaterEqual(value, 0)
            self.assertLess(value, 100_000)

    def test_target_definitions_present(self) -> None:
        targets = self.contract["targets"]
        self.assertEqual(targets["current"]["name"], "ada_api")
        self.assertIn(1, targets["exact_day"]["horizons"])
        self.assertIn(21, targets["window"]["horizons_proposed"])

    def test_anti_leakage_documents_lag(self) -> None:
        anti = self.contract["anti_leakage"]
        self.assertEqual(anti["lag_days"], 1)
        self.assertTrue(anti["shifted_in_training_table"])


if __name__ == "__main__":
    unittest.main()

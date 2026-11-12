"""CLI compatibility smoke tests from the top-level crawler directory."""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


CRAWLER_ROOT = Path(__file__).resolve().parents[2] / "hotspot_crawler"


class CliWrapperTests(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, *args], cwd=CRAWLER_ROOT,
            capture_output=True, text=True, timeout=60,
        )

    def test_copernicus_command_name_and_options_stay_usable(self):
        result = self.run_cli(
            "crawl_copernicus.py", "era5", "--from", "2012-01", "--to", "2012-01", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2012-01", result.stdout + result.stderr)

    def test_static_command_name_and_options_stay_usable(self):
        result = self.run_cli("crawl_static.py", "peat", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_processing_entrypoint_help_remains_available(self):
        result = self.run_cli("postprocess_era5.py", "--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("usage", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()

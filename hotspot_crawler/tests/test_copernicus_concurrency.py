"""Two workers targeting one ERA5 month must share one download per file."""
from __future__ import annotations

import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from apikah_crawler import config, crawl_copernicus
from apikah_crawler.common import manifest_load


class SlowFakeClient:
    def __init__(self):
        self.calls = []
        self.guard = threading.Lock()

    def retrieve(self, _dataset, _request, target):
        with self.guard:
            self.calls.append(target)
        time.sleep(0.5)
        Path(target).write_bytes(b"valid test data")


class CopernicusConcurrencyTests(unittest.TestCase):
    def test_two_workers_do_not_download_same_era5_targets_twice(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = (config.RAW, config.METADATA, config.LOGS, config.SLEEP_BETWEEN_REQUESTS)
            config.RAW = root / "raw" / "copernicus"
            config.METADATA = root / "metadata"
            config.LOGS = root / "logs"
            config.SLEEP_BETWEEN_REQUESTS = 0
            client = SlowFakeClient()
            ready = threading.Barrier(2)

            def make_client(_source):
                ready.wait(timeout=10)
                return client

            try:
                with patch.object(crawl_copernicus, "make_client", side_effect=make_client):
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        futures = [pool.submit(crawl_copernicus.run_era5, [(2012, 1)], False)
                                   for _ in range(2)]
                        for future in futures:
                            future.result(timeout=30)
                instant = config.RAW / "era5land" / "instant" / "2012-01.nc"
                accum = config.RAW / "era5land" / "accum" / "2012-01.nc"
                self.assertEqual(len(client.calls), 2)
                self.assertEqual(instant.read_bytes(), b"valid test data")
                self.assertEqual(accum.read_bytes(), b"valid test data")
                self.assertEqual(len(manifest_load("era5land")), 2)
            finally:
                (config.RAW, config.METADATA, config.LOGS,
                 config.SLEEP_BETWEEN_REQUESTS) = original


if __name__ == "__main__":
    unittest.main()

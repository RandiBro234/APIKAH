"""MCD64A1 stays raw; duplicate crawler runs must not race the same granules."""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from apikah_crawler import config
from apikah_crawler.common import manifest_load
from apikah_crawler.crawl_static import do_burned


class BurnedDownloadLockTests(unittest.TestCase):
    def test_concurrent_runs_download_once_and_completed_run_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_out, old_metadata = config.MCD64A1_DIR, config.METADATA
            config.MCD64A1_DIR = Path(tmp) / "mcd64a1"
            config.METADATA = Path(tmp) / "metadata"
            granule_path = config.MCD64A1_DIR / "sample.hdf"
            counts = {"search": 0, "download": 0}
            guard = threading.Lock()

            def search_data(**_kwargs):
                with guard:
                    counts["search"] += 1
                return ["one-granule"]

            def download(_results, out):
                with guard:
                    counts["download"] += 1
                time.sleep(0.15)
                (Path(out) / "sample.hdf").write_bytes(b"raw granule")

            fake_earthaccess = types.SimpleNamespace(
                login=lambda **_kwargs: None,
                search_data=search_data,
                download=download,
            )
            try:
                with patch.dict(os.environ, {
                    "EARTHDATA_USERNAME": "test-user",
                    "EARTHDATA_PASSWORD": "test-password",
                }), patch.dict(sys.modules, {"earthaccess": fake_earthaccess}):
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        futures = [pool.submit(do_burned, False) for _ in range(2)]
                        for future in futures:
                            future.result(timeout=30)
                record = manifest_load("static")["mcd64a1"]
            finally:
                granule_exists = granule_path.is_file()
                config.MCD64A1_DIR, config.METADATA = old_out, old_metadata

        self.assertEqual(counts, {"search": 1, "download": 1})
        self.assertEqual(record["status"], "ok")
        self.assertTrue(granule_exists)


if __name__ == "__main__":
    unittest.main()

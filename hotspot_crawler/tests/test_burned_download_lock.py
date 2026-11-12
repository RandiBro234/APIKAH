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


class FakeGranule:
    def __init__(self, filename):
        self.filename = filename

    def data_links(self, access=None):
        return [f"https://earthdata.test/{self.filename}"]


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
                return [FakeGranule("sample.hdf")]

            def download(results, out):
                with guard:
                    counts["download"] += 1
                time.sleep(0.15)
                for result in results:
                    (Path(out) / result.filename).write_bytes(b"raw granule")

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

    def test_changed_query_does_not_skip_same_file_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            old_out, old_metadata, old_end = config.MCD64A1_DIR, config.METADATA, config.END
            config.MCD64A1_DIR = Path(tmp) / "mcd64a1"
            config.METADATA = Path(tmp) / "metadata"
            counts = {"search": 0, "download": 0}

            def search_data(**kwargs):
                counts["search"] += 1
                name = "old-query.hdf" if kwargs["temporal"][1] == old_end.isoformat() else "new-query.hdf"
                return [FakeGranule(name)]

            def download(results, out):
                counts["download"] += 1
                for result in results:
                    (Path(out) / result.filename).write_bytes(b"granule for " + result.filename.encode())

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
                    do_burned(False)
                    config.END = old_end.replace(day=old_end.day - 1)
                    do_burned(False)
                filenames = {p.name for p in config.MCD64A1_DIR.glob("*.hdf")}
            finally:
                config.MCD64A1_DIR, config.METADATA, config.END = old_out, old_metadata, old_end

        self.assertEqual(counts, {"search": 2, "download": 2})
        self.assertEqual(filenames, {"old-query.hdf", "new-query.hdf"})


if __name__ == "__main__":
    unittest.main()

"""Cross-process manifest updates must not drop successful download records."""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from apikah_crawler import config
from apikah_crawler.common import manifest_load


class ManifestConcurrencyTests(unittest.TestCase):
    def test_updates_from_several_workers_are_all_preserved(self):
        package_parent = Path(config.__file__).resolve().parents[1]
        workers, updates = 5, 40
        script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from apikah_crawler import config
from apikah_crawler.common import manifest_update
config.METADATA = Path(sys.argv[2])
worker, updates = sys.argv[3], int(sys.argv[4])
for number in range(updates):
    manifest_update('parallel', f'{worker}-{number}', 'ok')
"""
        with tempfile.TemporaryDirectory() as tmp:
            processes = [
                subprocess.Popen(
                    [sys.executable, "-c", script, str(package_parent), tmp, str(worker), str(updates)],
                    cwd=tmp, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                )
                for worker in range(workers)
            ]
            for process in processes:
                stdout, stderr = process.communicate(timeout=120)
                self.assertEqual(process.returncode, 0, f"{stdout}\n{stderr}")

            previous = config.METADATA
            config.METADATA = Path(tmp)
            try:
                records = manifest_load("parallel")
            finally:
                config.METADATA = previous

        self.assertEqual(len(records), workers * updates)


if __name__ == "__main__":
    unittest.main()

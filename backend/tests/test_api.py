"""Smoke test API tanpa database. Dilewati bila httpx tidak terpasang."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from fastapi.testclient import TestClient

    from app.main import app
except ImportError:  # pragma: no cover - hanya saat dependensi dev tidak ada
    TestClient = None
    app = None


@unittest.skipIf(TestClient is None, "httpx belum terpasang")
class ApiSmokeTest(unittest.TestCase):
    def test_health(self) -> None:
        client = TestClient(app)
        response = client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")


if __name__ == "__main__":
    unittest.main()

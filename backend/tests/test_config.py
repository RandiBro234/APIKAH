"""Tes normalisasi URL database."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import _normalize_database_url


class DatabaseUrlTest(unittest.TestCase):
    def test_postgres_scheme_is_upgraded(self) -> None:
        self.assertEqual(
            _normalize_database_url("postgres://u:p@host/db"),
            "postgresql+psycopg://u:p@host/db",
        )

    def test_postgresql_scheme_is_upgraded(self) -> None:
        self.assertEqual(
            _normalize_database_url("postgresql://u:p@host/db"),
            "postgresql+psycopg://u:p@host/db",
        )

    def test_explicit_driver_is_kept(self) -> None:
        url = "postgresql+psycopg://u:p@host/db"
        self.assertEqual(_normalize_database_url(url), url)

    def test_empty_value_is_kept(self) -> None:
        self.assertEqual(_normalize_database_url(""), "")


if __name__ == "__main__":
    unittest.main()

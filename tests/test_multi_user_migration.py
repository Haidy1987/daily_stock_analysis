# -*- coding: utf-8 -*-
"""Multi-user migration idempotency and legacy backfill tests."""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import src.auth as auth
from src.config import Config
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class MultiUserMigrationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.db_path = self.data_dir / "legacy.db"
        self.env_path = self.data_dir / ".env"
        self.env_path.write_text(
            "STOCK_LIST=600519,000001\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=true\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.db_path)
        Config.reset_instance()
        DatabaseManager.reset_instance()
        self.auth_patcher = patch.object(auth, "_is_auth_enabled_from_env", return_value=True)
        self.data_dir_patcher = patch.object(auth, "_get_data_dir", return_value=self.data_dir)
        self.auth_patcher.start()
        self.data_dir_patcher.start()
        auth._auth_enabled = True

    def tearDown(self) -> None:
        self.auth_patcher.stop()
        self.data_dir_patcher.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _create_legacy_sqlite(self) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE analysis_history (
                    id INTEGER PRIMARY KEY,
                    query_id TEXT,
                    code TEXT,
                    name TEXT,
                    report_type TEXT,
                    sentiment_score INTEGER,
                    operation_advice TEXT,
                    analysis_summary TEXT,
                    created_at TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO analysis_history
                (query_id, code, name, report_type, sentiment_score, operation_advice, analysis_summary, created_at)
                VALUES ('q1', '600519', '贵州茅台', 'detailed', 60, 'hold', 'legacy', '2020-01-01T00:00:00')
                """
            )
            conn.commit()
        finally:
            conn.close()

    def test_empty_db_migration_creates_users_and_user_id_columns(self) -> None:
        db = DatabaseManager.get_instance()
        auth.set_initial_password("adminpass")
        admin_id = auth.get_default_admin_user_id(create_if_missing=False)
        self.assertIsNotNone(admin_id)

        # Re-run ensure path (idempotent).
        db._ensure_user_owned_user_id_columns()
        db._ensure_user_owned_user_id_columns()

        with db._engine.connect() as conn:
            from sqlalchemy import text

            nulls = conn.execute(
                text("SELECT COUNT(*) FROM analysis_history WHERE user_id IS NULL")
            ).scalar_one()
            self.assertEqual(int(nulls), 0)

        from src.repositories.watchlist_repo import WatchlistRepository

        codes = WatchlistRepository(db).list_codes(admin_id)
        self.assertEqual(codes, ["600519", "000001"])

    def test_legacy_history_backfill_and_idempotent_rerun(self) -> None:
        self._create_legacy_sqlite()
        db = DatabaseManager.get_instance()
        auth.set_initial_password("adminpass")
        admin_id = auth.get_default_admin_user_id(create_if_missing=False)

        db._ensure_user_owned_user_id_columns()
        with db._engine.connect() as conn:
            from sqlalchemy import text

            row = conn.execute(
                text("SELECT user_id FROM analysis_history WHERE query_id='q1'")
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(int(row[0]), int(admin_id))

            nulls = conn.execute(
                text("SELECT COUNT(*) FROM analysis_history WHERE user_id IS NULL")
            ).scalar_one()
            self.assertEqual(int(nulls), 0)

        # Second run must remain stable.
        db._ensure_user_owned_user_id_columns()
        with db._engine.connect() as conn:
            from sqlalchemy import text

            count = conn.execute(text("SELECT COUNT(*) FROM analysis_history")).scalar_one()
            self.assertEqual(int(count), 1)


class AuthModeGateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.pop("AUTH_MODE", None)

    def tearDown(self) -> None:
        os.environ.pop("AUTH_MODE", None)

    def test_default_auth_mode_is_multi_user(self) -> None:
        self.assertEqual(auth.get_auth_mode(), auth.AUTH_MODE_MULTI_USER)
        self.assertTrue(auth.is_multi_user_mode())

    def test_single_admin_mode(self) -> None:
        os.environ["AUTH_MODE"] = "single_admin"
        self.assertEqual(auth.get_auth_mode(), auth.AUTH_MODE_SINGLE_ADMIN)
        self.assertFalse(auth.is_multi_user_mode())


if __name__ == "__main__":
    unittest.main()

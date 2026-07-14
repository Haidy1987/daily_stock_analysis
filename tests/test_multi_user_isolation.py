# -*- coding: utf-8 -*-
"""Cross-user data isolation tests for multi-user stage 2."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import src.auth as auth
from src.config import Config
from src.repositories.alert_repo import AlertRepository
from src.repositories.portfolio_repo import PortfolioRepository
from src.repositories.watchlist_repo import WatchlistRepository
from src.storage import AnalysisHistory, DatabaseManager, DecisionSignalRecord, utc_naive_now


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class MultiUserIsolationTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=true\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.data_dir / "test.db")
        Config.reset_instance()
        DatabaseManager.reset_instance()

        self.auth_patcher = patch.object(auth, "_is_auth_enabled_from_env", return_value=True)
        self.data_dir_patcher = patch.object(auth, "_get_data_dir", return_value=self.data_dir)
        self.auth_patcher.start()
        self.data_dir_patcher.start()
        auth._auth_enabled = True

        auth.set_initial_password("adminpass")
        self.admin = auth._get_user_repo().get_user_by_username("admin")
        self.alice = auth._get_user_repo().create_user(
            username="alice",
            password_hash=auth.hash_password("alicepass"),
            role="user",
            status="active",
        )
        self.bob = auth._get_user_repo().create_user(
            username="bob",
            password_hash=auth.hash_password("bobpass"),
            role="user",
            status="active",
        )
        self.db = DatabaseManager.get_instance()

    def tearDown(self) -> None:
        self.auth_patcher.stop()
        self.data_dir_patcher.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    def _insert_history(self, user_id: int, code: str = "600519") -> int:
        with self.db.get_session() as session:
            row = AnalysisHistory(
                query_id=f"q-{user_id}-{code}",
                code=code,
                name="test",
                report_type="detailed",
                sentiment_score=50,
                operation_advice="hold",
                analysis_summary="summary",
                user_id=user_id,
                created_at=utc_naive_now(),
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return int(row.id)

    def test_analysis_history_isolated_by_user(self) -> None:
        alice_id = self._insert_history(self.alice.id)
        bob_id = self._insert_history(self.bob.id)

        alice_rows = self.db.get_analysis_history(user_id=self.alice.id, limit=50)
        bob_rows = self.db.get_analysis_history(user_id=self.bob.id, limit=50)
        self.assertEqual({r.id for r in alice_rows}, {alice_id})
        self.assertEqual({r.id for r in bob_rows}, {bob_id})

        self.assertIsNone(self.db.get_analysis_history_by_id(alice_id, user_id=self.bob.id))
        self.assertIsNotNone(self.db.get_analysis_history_by_id(alice_id, user_id=self.alice.id))
        # Explicit: bob cannot see alice via filtered list
        self.assertFalse(any(r.id == alice_id for r in bob_rows))

    def test_watchlist_isolated(self) -> None:
        repo = WatchlistRepository(self.db)
        repo.add_code(self.alice.id, "600519")
        repo.add_code(self.bob.id, "000001")
        self.assertEqual(repo.list_codes(self.alice.id), ["600519"])
        self.assertEqual(repo.list_codes(self.bob.id), ["000001"])
        self.assertFalse(repo.remove_code(self.bob.id, "600519"))
        self.assertTrue(repo.remove_code(self.alice.id, "600519"))

    def test_portfolio_accounts_isolated(self) -> None:
        repo = PortfolioRepository(self.db)
        a = repo.create_account(user_id=self.alice.id, name="Alice CN", broker=None, market="cn", base_currency="CNY")
        b = repo.create_account(user_id=self.bob.id, name="Bob CN", broker=None, market="cn", base_currency="CNY")
        alice_accounts = repo.list_accounts(user_id=self.alice.id)
        bob_accounts = repo.list_accounts(user_id=self.bob.id)
        self.assertEqual([x.id for x in alice_accounts], [a.id])
        self.assertEqual([x.id for x in bob_accounts], [b.id])
        self.assertIsNone(repo.get_account(a.id, user_id=self.bob.id))
        self.assertIsNotNone(repo.get_account(a.id, user_id=self.alice.id))

    def test_alert_rules_isolated(self) -> None:
        repo = AlertRepository(self.db)
        alice_rule = repo.create_rule(
            {
                "name": "alice-rule",
                "target_scope": "single_symbol",
                "target": "600519",
                "alert_type": "price_cross",
                "parameters": "{}",
                "severity": "warning",
                "enabled": True,
                "source": "api",
                "user_id": self.alice.id,
            }
        )
        bob_rule = repo.create_rule(
            {
                "name": "bob-rule",
                "target_scope": "single_symbol",
                "target": "000001",
                "alert_type": "price_cross",
                "parameters": "{}",
                "severity": "warning",
                "enabled": True,
                "source": "api",
                "user_id": self.bob.id,
            }
        )
        alice_list, _ = repo.list_rules(user_id=self.alice.id)
        bob_list, _ = repo.list_rules(user_id=self.bob.id)
        self.assertEqual([r.id for r in alice_list], [alice_rule.id])
        self.assertEqual([r.id for r in bob_list], [bob_rule.id])
        self.assertIsNone(repo.get_rule(alice_rule.id, user_id=self.bob.id))

    def test_decision_signals_isolated(self) -> None:
        with self.db.get_session() as session:
            a = DecisionSignalRecord(
                stock_code="600519",
                market="cn",
                source_type="analysis",
                trigger_source="api",
                action="buy",
                status="active",
                user_id=self.alice.id,
            )
            b = DecisionSignalRecord(
                stock_code="000001",
                market="cn",
                source_type="analysis",
                trigger_source="api",
                action="hold",
                status="active",
                user_id=self.bob.id,
            )
            session.add(a)
            session.add(b)
            session.commit()
            session.refresh(a)
            session.refresh(b)
            alice_signal_id = a.id
            bob_signal_id = b.id

        from src.repositories.decision_signal_repo import DecisionSignalRepository

        repo = DecisionSignalRepository(self.db)
        alice_rows, _ = repo.list(user_id=self.alice.id, page=1, page_size=20)
        bob_rows, _ = repo.list(user_id=self.bob.id, page=1, page_size=20)
        self.assertEqual([r.id for r in alice_rows], [alice_signal_id])
        self.assertEqual([r.id for r in bob_rows], [bob_signal_id])
        self.assertIsNone(repo.get(alice_signal_id, user_id=self.bob.id))


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Tests for manual A-share universe sync API helpers."""

from __future__ import annotations

import os
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.repositories.a_share_universe_repo import AShareUniverseRepository
from src.services.a_share_universe.manual_sync import (
    MANUAL_SYNC_COOLDOWN_SECONDS,
    ManualSyncState,
    ManualSyncStateStore,
    ManualSyncRejected,
    build_manual_sync_stats,
    reserve_manual_sync,
    run_manual_a_share_universe_sync,
)
from src.storage import DatabaseManager, utc_naive_now


@pytest.fixture()
def isolated_db(tmp_path):
    old_database_path = os.environ.get("DATABASE_PATH")
    db_path = tmp_path / "a_share_universe_manual.db"
    os.environ["DATABASE_PATH"] = str(db_path)
    Config.reset_instance()
    DatabaseManager.reset_instance()
    db = DatabaseManager.get_instance()
    try:
        yield db
    finally:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        if old_database_path is None:
            os.environ.pop("DATABASE_PATH", None)
        else:
            os.environ["DATABASE_PATH"] = old_database_path


@pytest.fixture
def manual_store(tmp_path):
    return ManualSyncStateStore(tmp_path / "a_share_sync")


def test_build_manual_sync_stats_idle(manual_store) -> None:
    repo = MagicMock()
    repo.count_universe.side_effect = lambda active_only=False: 5000 if active_only else 5100
    stats = build_manual_sync_stats(
        config=SimpleNamespace(a_share_universe_sync_enabled=False),
        repository=repo,
        store=manual_store,
    )
    assert stats["total_count"] == 5000
    assert stats["sync_status"] == "idle"
    assert stats["cooldown_remaining_seconds"] == 0
    assert stats["manual_only"] is True


def test_reserve_manual_sync_rejects_during_cooldown(manual_store) -> None:
    now = utc_naive_now()
    manual_store.save(
        ManualSyncState(
            status="succeeded",
            last_success_at=(now - timedelta(minutes=10)).isoformat(timespec="seconds"),
        )
    )
    with pytest.raises(ManualSyncRejected) as exc:
        reserve_manual_sync(store=manual_store)
    assert exc.value.code == "cooldown_active"
    assert exc.value.retry_after_seconds > 0


def test_reserve_manual_sync_rejects_when_running(manual_store) -> None:
    manual_store.save(ManualSyncState(status="running"))
    with pytest.raises(ManualSyncRejected) as exc:
        reserve_manual_sync(store=manual_store)
    assert exc.value.code == "sync_in_progress"


def test_run_manual_a_share_universe_sync_persists_success(manual_store) -> None:
    config = SimpleNamespace(
        a_share_universe_sync_mode="universe-only",
        a_share_universe_source="eastmoney",
        a_share_universe_sync_resume=True,
        a_share_universe_trading_day_check_enabled=False,
        a_share_universe_index_refresh_enabled=False,
    )
    report = SimpleNamespace(
        source="eastmoney",
        mode="universe-only",
        fetched=100,
        inserted=10,
        updated=90,
        snapshot_fetched=0,
        report_path=None,
    )
    job_result = SimpleNamespace(
        skipped=False,
        skip_reason=None,
        index_refreshed=False,
        index_stats={},
        errors=[],
        report=report,
    )
    with patch(
        "src.services.a_share_universe.manual_sync.run_a_share_universe_sync_job",
        return_value=job_result,
    ):
        run_manual_a_share_universe_sync(config=config, store=manual_store)

    state = manual_store.load()
    assert state.status == "succeeded"
    assert state.last_success_at
    assert state.last_report["fetched"] == 100


def test_search_normalizes_exchange_suffix(isolated_db) -> None:
    repo = AShareUniverseRepository(isolated_db)
    repo.upsert_universe(
        [
            {
                "code": "600519",
                "name": "贵州茅台",
                "exchange": "SH",
                "board": "主板",
                "industry": "白酒",
                "active": True,
                "source": "test",
            }
        ]
    )
    rows = repo.search("600519.SH", limit=10)
    assert len(rows) == 1
    assert rows[0].code == "600519"


def test_search_supports_empty_keyword_pagination(isolated_db) -> None:
    repo = AShareUniverseRepository(isolated_db)
    repo.upsert_universe(
        [
            {"code": "000001", "name": "平安银行", "exchange": "SZ", "active": True, "source": "test"},
            {"code": "600519", "name": "贵州茅台", "exchange": "SH", "active": True, "source": "test"},
        ]
    )
    page = repo.search("", limit=1, offset=0)
    assert len(page) == 1
    assert page[0].code == "000001"
    assert repo.count_search("", active_only=True) == 2


def test_manual_sync_cooldown_constant_is_one_hour() -> None:
    assert MANUAL_SYNC_COOLDOWN_SECONDS == 3600

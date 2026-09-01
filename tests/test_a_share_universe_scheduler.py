# -*- coding: utf-8 -*-
"""Tests for A-share universe scheduler (Phase 4)."""

from __future__ import annotations

import os
from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.services.a_share_universe.scheduler import (
    build_a_share_universe_background_tasks,
    normalize_sync_mode,
    refresh_a_share_stock_index,
    run_a_share_universe_sync_job,
    should_skip_a_share_sync,
)
from src.services.a_share_universe_sync_service import AShareUniverseSyncReport


def test_normalize_sync_mode_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        normalize_sync_mode("invalid")


def test_should_skip_a_share_sync_on_non_trading_day_for_snapshot_mode() -> None:
    config = SimpleNamespace(
        a_share_universe_trading_day_check_enabled=True,
        a_share_universe_sync_mode="snapshot",
    )
    with patch("src.core.trading_calendar.is_market_open", return_value=False):
        reason = should_skip_a_share_sync(config, today=date(2026, 1, 1))
    assert reason is not None


def test_should_not_skip_universe_only_on_non_trading_day() -> None:
    config = SimpleNamespace(
        a_share_universe_trading_day_check_enabled=True,
        a_share_universe_sync_mode="universe-only",
    )
    with patch("src.core.trading_calendar.is_market_open", return_value=False):
        assert should_skip_a_share_sync(config, today=date(2026, 1, 1)) is None


def test_run_a_share_universe_sync_job_calls_full_sync_and_refresh() -> None:
    config = SimpleNamespace(
        a_share_universe_sync_mode="full",
        a_share_universe_source="eastmoney",
        a_share_universe_sync_resume=True,
        a_share_universe_trading_day_check_enabled=False,
        a_share_universe_index_refresh_enabled=True,
    )
    report = AShareUniverseSyncReport(source="eastmoney", mode="full", fetched=5000)
    service = MagicMock()
    service.sync_full.return_value = report
    service.repository = MagicMock()

    with patch(
        "src.services.a_share_universe.scheduler.refresh_a_share_stock_index",
        return_value={"total": 5200, "a_share_count": 5000, "non_a_share_count": 200},
    ) as refresh:
        result = run_a_share_universe_sync_job(config, service=service)

    service.sync_full.assert_called_once_with(source="eastmoney", resume=True)
    refresh.assert_called_once_with(repository=service.repository)
    assert result.index_refreshed is True
    assert result.index_stats["total"] == 5200


def test_build_a_share_universe_background_tasks_disabled_returns_empty() -> None:
    config = SimpleNamespace(a_share_universe_sync_enabled=False)
    assert build_a_share_universe_background_tasks(config, config_provider=lambda: config) == []


def test_build_a_share_universe_background_tasks_enabled_returns_interval_task() -> None:
    config = SimpleNamespace(
        a_share_universe_sync_enabled=True,
        a_share_universe_sync_interval_hours=12,
        a_share_universe_sync_run_immediately=False,
    )
    tasks = build_a_share_universe_background_tasks(config, config_provider=lambda: config)
    assert len(tasks) == 1
    assert tasks[0]["name"] == "a_share_universe_sync"
    assert tasks[0]["interval_seconds"] == 12 * 3600
    assert tasks[0]["run_immediately"] is False


def test_refresh_a_share_stock_index_writes_web_and_static(tmp_path, monkeypatch) -> None:
    repo = MagicMock()
    repo.count_universe.return_value = 2

    web_path = tmp_path / "web" / "stocks.index.json"
    static_path = tmp_path / "static" / "stocks.index.json"

    monkeypatch.setattr("src.services.a_share_universe.scheduler._web_index_path", lambda: web_path)
    monkeypatch.setattr("src.services.a_share_universe.scheduler._static_index_path", lambda: static_path)
    monkeypatch.setattr(
        "src.services.a_share_universe.scheduler.write_merged_index_from_db",
        lambda output_path, repository, merge_from=None: (
            output_path.parent.mkdir(parents=True, exist_ok=True),
            output_path.write_text("[]", encoding="utf-8"),
            {"total": 2, "a_share_count": 2, "non_a_share_count": 0},
        )[2],
    )
    with patch("src.data.stock_index_loader.clear_stock_index_cache") as clear_cache:
        stats = refresh_a_share_stock_index(repository=repo)

    assert stats["total"] == 2
    assert web_path.is_file()
    assert static_path.is_file()
    clear_cache.assert_called_once()

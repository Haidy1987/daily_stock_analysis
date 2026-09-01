# -*- coding: utf-8 -*-
"""Scheduled jobs for A-share universe sync and index refresh."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Callable, Dict, List, Optional

from src.config import Config, get_config
from src.repositories.a_share_universe_repo import AShareUniverseRepository
from src.services.a_share_universe.index_builder import write_merged_index_from_db
from src.services.a_share_universe_sync_service import AShareUniverseSyncReport, AShareUniverseSyncService

logger = logging.getLogger(__name__)

_VALID_SYNC_MODES = {"universe-only", "snapshot", "full"}
_BACKGROUND_TASK_NAME = "a_share_universe_sync"


@dataclass
class AShareUniverseSyncJobResult:
    skipped: bool = False
    skip_reason: Optional[str] = None
    report: Optional[AShareUniverseSyncReport] = None
    index_refreshed: bool = False
    index_stats: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


def normalize_sync_mode(mode: str | None, *, default: str = "full") -> str:
    normalized = str(mode or default).strip().lower()
    if normalized not in _VALID_SYNC_MODES:
        raise ValueError(f"unsupported A-share sync mode: {normalized}")
    return normalized


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _web_index_path() -> Path:
    return _repo_root() / "apps" / "dsa-web" / "public" / "stocks.index.json"


def _static_index_path() -> Path:
    return _repo_root() / "static" / "stocks.index.json"


def should_skip_a_share_sync(config: Config, *, today: Optional[date] = None) -> Optional[str]:
    """Return skip reason when snapshot/full sync should not run today."""
    if not getattr(config, "a_share_universe_trading_day_check_enabled", True):
        return None

    mode = normalize_sync_mode(getattr(config, "a_share_universe_sync_mode", "full"))
    if mode == "universe-only":
        return None

    try:
        from src.core.trading_calendar import get_market_now, is_market_open
    except ImportError:  # pragma: no cover - defensive branch
        return None

    check_date = today or get_market_now("cn").date()
    if is_market_open("cn", check_date):
        return None
    return f"cn market closed on {check_date.isoformat()}"


def refresh_a_share_stock_index(*, repository: Optional[AShareUniverseRepository] = None) -> Dict[str, int]:
    repo = repository or AShareUniverseRepository()
    if repo.count_universe(active_only=True) == 0:
        raise RuntimeError("a_share_universe is empty; run universe sync before index refresh")

    web_path = _web_index_path()
    merge_from = web_path if web_path.is_file() else None
    stats = write_merged_index_from_db(web_path, repo, merge_from=merge_from)

    static_path = _static_index_path()
    static_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(web_path, static_path)

    from src.data.stock_index_loader import clear_stock_index_cache

    clear_stock_index_cache()
    return stats


def run_a_share_universe_sync_job(
    config: Optional[Config] = None,
    *,
    service: Optional[AShareUniverseSyncService] = None,
    repository: Optional[AShareUniverseRepository] = None,
    today: Optional[date] = None,
) -> AShareUniverseSyncJobResult:
    active_config = config or get_config()
    result = AShareUniverseSyncJobResult()

    skip_reason = should_skip_a_share_sync(active_config, today=today)
    if skip_reason:
        result.skipped = True
        result.skip_reason = skip_reason
        logger.info("[A-share sync] skipped: %s", skip_reason)
        return result

    sync_service = service or AShareUniverseSyncService(config=active_config, repository=repository)
    mode = normalize_sync_mode(getattr(active_config, "a_share_universe_sync_mode", "full"))
    resume = bool(getattr(active_config, "a_share_universe_sync_resume", True))
    source = getattr(active_config, "a_share_universe_source", "eastmoney")

    try:
        if mode == "universe-only":
            report = sync_service.sync_universe(source=source)
        elif mode == "snapshot":
            report = sync_service.sync_snapshot(source=source, resume=resume)
        else:
            report = sync_service.sync_full(source=source, resume=resume)
    except Exception as exc:  # noqa: BLE001 - scheduler must not crash the host loop
        logger.exception("[A-share sync] job failed before report: %s", exc)
        result.errors.append(str(exc))
        return result

    result.report = report
    if report.errors:
        result.errors.extend(report.errors)
        logger.warning(
            "[A-share sync] completed with errors mode=%s fetched=%s snapshot_fetched=%s errors=%s",
            report.mode,
            report.fetched,
            report.snapshot_fetched,
            len(report.errors),
        )
        return result

    logger.info(
        "[A-share sync] completed mode=%s universe=%s snapshot=%s report=%s",
        report.mode,
        report.fetched,
        report.snapshot_fetched,
        report.report_path,
    )

    if getattr(active_config, "a_share_universe_index_refresh_enabled", True):
        try:
            result.index_stats = refresh_a_share_stock_index(repository=sync_service.repository)
            result.index_refreshed = True
            logger.info(
                "[A-share sync] refreshed stock index total=%s a_share=%s",
                result.index_stats.get("total"),
                result.index_stats.get("a_share_count"),
            )
        except Exception as exc:  # noqa: BLE001 - index refresh failure should not undo DB sync
            message = f"index refresh failed: {exc}"
            logger.warning("[A-share sync] %s", message)
            result.errors.append(message)

    return result


def build_a_share_universe_background_tasks(
    config: Config,
    *,
    config_provider: Callable[[], Config],
) -> List[Dict[str, object]]:
    if not getattr(config, "a_share_universe_sync_enabled", False):
        return []

    interval_hours = max(1, int(getattr(config, "a_share_universe_sync_interval_hours", 24)))
    run_immediately = bool(getattr(config, "a_share_universe_sync_run_immediately", True))

    def sync_task() -> None:
        active_config = config_provider()
        run_a_share_universe_sync_job(active_config)

    return [{
        "task": sync_task,
        "interval_seconds": interval_hours * 3600,
        "run_immediately": run_immediately,
        "name": _BACKGROUND_TASK_NAME,
    }]

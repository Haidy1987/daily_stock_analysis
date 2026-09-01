# -*- coding: utf-8 -*-
"""Manual A-share universe sync with cooldown and mutual exclusion."""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import Config, get_config
from src.repositories.a_share_universe_repo import AShareUniverseRepository
from src.services.a_share_universe.scheduler import run_a_share_universe_sync_job
from src.storage import utc_naive_now

logger = logging.getLogger(__name__)

MANUAL_SYNC_COOLDOWN_SECONDS = 60 * 60
_STATE_FILENAME = "manual_sync_state.json"
_LOCK_FILENAME = "manual_sync.lock"

_thread_lock = threading.Lock()
_running = False


class ManualSyncRejected(Exception):
    """Raised when a manual sync request cannot be accepted."""

    def __init__(self, *, code: str, message: str, retry_after_seconds: int = 0):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retry_after_seconds = max(0, int(retry_after_seconds or 0))


@dataclass
class ManualSyncState:
    status: str = "idle"  # idle | running | succeeded | failed
    last_triggered_at: Optional[str] = None
    last_completed_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_error: Optional[str] = None
    last_report: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict) -> "ManualSyncState":
        return cls(
            status=str(payload.get("status") or "idle"),
            last_triggered_at=payload.get("last_triggered_at"),
            last_completed_at=payload.get("last_completed_at"),
            last_success_at=payload.get("last_success_at"),
            last_error=payload.get("last_error"),
            last_report=dict(payload.get("last_report") or {}),
        )


class ManualSyncStateStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = self.base_dir / _STATE_FILENAME
        self.lock_path = self.base_dir / _LOCK_FILENAME

    def load(self) -> ManualSyncState:
        if not self.state_path.is_file():
            return ManualSyncState()
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
            return ManualSyncState.from_dict(payload if isinstance(payload, dict) else {})
        except Exception as exc:
            logger.warning("[a-share-manual-sync] failed to load state: %s", exc)
            return ManualSyncState()

    def save(self, state: ManualSyncState) -> None:
        self.state_path.write_text(
            json.dumps(asdict(state), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _default_store(config: Optional[Config] = None) -> ManualSyncStateStore:
    active = config or get_config()
    database_path = getattr(active, "database_path", "./data/stock_analysis.db")
    return ManualSyncStateStore(Path(database_path).parent / "a_share_sync")


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _cooldown_remaining_seconds(state: ManualSyncState, *, now: Optional[datetime] = None) -> int:
    anchor = _parse_iso(state.last_success_at) or _parse_iso(state.last_completed_at)
    if anchor is None:
        return 0
    current = now or utc_naive_now()
    elapsed = (current - anchor).total_seconds()
    remaining = MANUAL_SYNC_COOLDOWN_SECONDS - elapsed
    return max(0, int(remaining))


def _load_last_report(store: ManualSyncStateStore) -> Dict[str, Any]:
    report_path = store.base_dir / "last_report.json"
    if not report_path.is_file():
        return {}
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        return dict(payload) if isinstance(payload, dict) else {}
    except Exception:
        return {}


def build_manual_sync_stats(
    *,
    config: Optional[Config] = None,
    repository: Optional[AShareUniverseRepository] = None,
    store: Optional[ManualSyncStateStore] = None,
) -> Dict[str, Any]:
    active_config = config or get_config()
    repo = repository or AShareUniverseRepository()
    state_store = store or _default_store(active_config)
    state = state_store.load()
    last_report = state.last_report or _load_last_report(state_store)
    cooldown_remaining = _cooldown_remaining_seconds(state)
    running = state.status == "running" or _running

    if running:
        sync_status = "running"
    elif cooldown_remaining > 0:
        sync_status = "cooldown"
    else:
        sync_status = "idle"

    next_available_at = None
    if cooldown_remaining > 0:
        anchor = _parse_iso(state.last_success_at) or _parse_iso(state.last_completed_at)
        if anchor is not None:
            next_available_at = (anchor + timedelta(seconds=MANUAL_SYNC_COOLDOWN_SECONDS)).isoformat(
                timespec="seconds"
            )

    return {
        "total_count": repo.count_universe(active_only=True),
        "total_including_inactive": repo.count_universe(active_only=False),
        "sync_status": sync_status,
        "cooldown_seconds": MANUAL_SYNC_COOLDOWN_SECONDS,
        "cooldown_remaining_seconds": cooldown_remaining,
        "next_available_at": next_available_at,
        "last_triggered_at": state.last_triggered_at,
        "last_completed_at": state.last_completed_at,
        "last_success_at": state.last_success_at,
        "last_error": state.last_error,
        "last_report": last_report,
        "manual_only": True,
        "auto_sync_enabled": bool(getattr(active_config, "a_share_universe_sync_enabled", False)),
    }


def reserve_manual_sync(
    *,
    config: Optional[Config] = None,
    store: Optional[ManualSyncStateStore] = None,
) -> ManualSyncStateStore:
    """Validate cooldown/running guards and persist a running state."""
    global _running

    state_store = store or _default_store(config)
    with _thread_lock:
        state = state_store.load()
        if state.status == "running" or _running:
            raise ManualSyncRejected(
                code="sync_in_progress",
                message="A-share sync is already running",
            )
        remaining = _cooldown_remaining_seconds(state)
        if remaining > 0:
            raise ManualSyncRejected(
                code="cooldown_active",
                message=f"Manual sync is on cooldown; retry after {remaining}s",
                retry_after_seconds=remaining,
            )
        now_iso = utc_naive_now().isoformat(timespec="seconds")
        state.status = "running"
        state.last_triggered_at = now_iso
        state.last_error = None
        state_store.save(state)
        _running = True
    return state_store


def run_manual_a_share_universe_sync(
    *,
    config: Optional[Config] = None,
    store: Optional[ManualSyncStateStore] = None,
) -> None:
    """Execute one manual sync job and update persisted state."""
    global _running

    active_config = config or get_config()
    state_store = store or _default_store(active_config)
    try:
        result = run_a_share_universe_sync_job(active_config)
        report = result.report
        payload = {
            "skipped": result.skipped,
            "skip_reason": result.skip_reason,
            "index_refreshed": result.index_refreshed,
            "index_stats": result.index_stats,
            "errors": list(result.errors or []),
        }
        if report is not None:
            payload.update(
                {
                    "source": report.source,
                    "mode": report.mode,
                    "fetched": report.fetched,
                    "inserted": report.inserted,
                    "updated": report.updated,
                    "snapshot_fetched": report.snapshot_fetched,
                    "report_path": report.report_path,
                }
            )

        now_iso = utc_naive_now().isoformat(timespec="seconds")
        state = state_store.load()
        state.last_completed_at = now_iso
        state.last_report = payload
        if result.skipped:
            state.status = "failed"
            state.last_error = result.skip_reason or "sync skipped"
        elif payload.get("errors"):
            state.status = "failed"
            state.last_error = "; ".join(str(item) for item in payload["errors"][:3])
        else:
            state.status = "succeeded"
            state.last_success_at = now_iso
            state.last_error = None
        state_store.save(state)
    except Exception as exc:
        logger.exception("[a-share-manual-sync] manual sync failed: %s", exc)
        now_iso = utc_naive_now().isoformat(timespec="seconds")
        state = state_store.load()
        state.status = "failed"
        state.last_completed_at = now_iso
        state.last_error = str(exc)
        state_store.save(state)
    finally:
        with _thread_lock:
            _running = False


def finalize_manual_sync_state_on_failure(store: ManualSyncStateStore, message: str) -> None:
    global _running

    with _thread_lock:
        state = store.load()
        state.status = "failed"
        state.last_completed_at = utc_naive_now().isoformat(timespec="seconds")
        state.last_error = message
        store.save(state)
        _running = False

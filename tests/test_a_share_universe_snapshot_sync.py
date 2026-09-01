# -*- coding: utf-8
"""Tests for A-share snapshot sync (Phase 2)."""

from __future__ import annotations

import json
import os
from datetime import date
from typing import List

import pytest

from src.config import Config
from src.repositories.a_share_universe_repo import AShareUniverseRepository
from src.schemas.a_share_universe import AShareSnapshotRow
from src.services.a_share_universe.checkpoint import SnapshotCheckpointStore
from src.services.a_share_universe.snapshot_providers import SnapshotFetchResult
from src.services.a_share_universe_sync_service import AShareUniverseSyncService
from src.storage import DatabaseManager


class _FakeSnapshotProvider:
    source_name = "eastmoney"

    def __init__(self, rows: List[AShareSnapshotRow]):
        self._rows = rows
        self.enrich_calls = 0

    def fetch_snapshots(self) -> SnapshotFetchResult:
        return SnapshotFetchResult(
            rows=list(self._rows),
            data_date=self._rows[0].data_date if self._rows else date.today(),
            financial_report_date="20250630",
        )

    def enrich_snapshots(self, rows, **kwargs):
        self.enrich_calls += 1
        from src.services.a_share_universe.snapshot_providers import SnapshotEnrichResult

        return SnapshotEnrichResult(rows=list(rows), enriched=0, failed=0)


@pytest.fixture()
def isolated_db(tmp_path):
    old_database_path = os.environ.get("DATABASE_PATH")
    db_path = tmp_path / "a_share_snapshot_sync.db"
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


def test_sync_snapshot_persists_rows_and_writes_report(isolated_db, tmp_path) -> None:
    rows = [
        AShareSnapshotRow(code="600519", data_date=date(2026, 8, 29), price=1700, source="eastmoney"),
        AShareSnapshotRow(code="300750", data_date=date(2026, 8, 29), price=200, source="eastmoney"),
    ]
    provider = _FakeSnapshotProvider(rows)
    store = SnapshotCheckpointStore(tmp_path / "a_share_sync")
    service = AShareUniverseSyncService(
        repository=AShareUniverseRepository(isolated_db),
        snapshot_provider=provider,
        checkpoint_store=store,
    )

    report = service.sync_snapshot(enrich=False)

    assert report.persisted is True
    assert report.snapshot_fetched == 2
    assert report.snapshot_inserted == 2
    assert report.report_path is not None
    assert json.loads((tmp_path / "a_share_sync" / "last_report.json").read_text(encoding="utf-8"))["snapshot_fetched"] == 2

    repo = AShareUniverseRepository(isolated_db)
    snapshot = repo.get_latest_snapshot("600519")
    assert snapshot is not None
    assert snapshot.price == 1700


def test_purge_snapshots_before(isolated_db) -> None:
    repo = AShareUniverseRepository(isolated_db)
    repo.upsert_snapshot([
        AShareSnapshotRow(code="600519", data_date=date(2026, 8, 28), price=100, source="test"),
        AShareSnapshotRow(code="600519", data_date=date(2026, 8, 29), price=101, source="test"),
    ])
    deleted = repo.purge_snapshots_before(date(2026, 8, 29))
    assert deleted == 1
    latest = repo.get_latest_snapshot("600519")
    assert latest is not None
    assert latest.data_date == date(2026, 8, 29)

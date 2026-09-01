# -*- coding: utf-8 -*-
"""Repository tests for A-share universe Phase 0 schema."""

from __future__ import annotations

import os
from datetime import date

import pytest
from sqlalchemy import func, inspect, select

from src.config import Config
from src.repositories.a_share_universe_repo import AShareUniverseRepository
from src.schemas.a_share_universe import AShareSnapshotRow, AShareUniverseRow
from src.storage import AShareSnapshot, AShareUniverse, DatabaseManager


@pytest.fixture()
def isolated_db(tmp_path):
    old_database_path = os.environ.get("DATABASE_PATH")
    db_path = tmp_path / "a_share_universe_repo.db"
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


def test_tables_are_created_on_init(isolated_db) -> None:
    inspector = inspect(isolated_db._engine)
    assert "a_share_universe" in inspector.get_table_names()
    assert "a_share_snapshot" in inspector.get_table_names()


def test_upsert_universe_inserts_and_updates(isolated_db) -> None:
    repo = AShareUniverseRepository(isolated_db)

    first = repo.upsert_universe([
        AShareUniverseRow(
            code="600519",
            name="贵州茅台",
            exchange="SH",
            board="主板",
            industry="白酒",
            list_date=date(2001, 8, 27),
            source="test",
        )
    ])
    assert first.total == 1
    assert first.inserted == 1
    assert first.updated == 0

    second = repo.upsert_universe([
        {
            "code": "sh600519",
            "name": "贵州茅台（更新）",
            "exchange": "SH",
            "industry": "酿酒",
            "source": "test",
        }
    ])
    assert second.total == 1
    assert second.inserted == 0
    assert second.updated == 1

    row = repo.get_by_code("600519")
    assert row is not None
    assert row.name == "贵州茅台（更新）"
    assert row.industry == "酿酒"


def test_upsert_snapshot_is_idempotent_for_same_code_and_date(isolated_db) -> None:
    repo = AShareUniverseRepository(isolated_db)
    repo.upsert_universe([
        AShareUniverseRow(code="300750", name="宁德时代", exchange="SZ", source="test")
    ])

    trade_date = date(2026, 8, 29)
    first = repo.upsert_snapshot([
        AShareSnapshotRow(
            code="300750",
            data_date=trade_date,
            price=200.5,
            pct_chg=1.2,
            source="test",
        )
    ])
    assert first.inserted == 1
    assert first.updated == 0

    second = repo.upsert_snapshot([
        AShareSnapshotRow(
            code="sz300750",
            data_date=trade_date,
            price=201.0,
            pct_chg=1.5,
            source="test",
        )
    ])
    assert second.inserted == 0
    assert second.updated == 1

    snapshot = repo.get_latest_snapshot("300750")
    assert snapshot is not None
    assert snapshot.price == 201.0
    assert snapshot.pct_chg == 1.5


def test_list_active_codes_and_search(isolated_db) -> None:
    repo = AShareUniverseRepository(isolated_db)
    repo.upsert_universe([
        AShareUniverseRow(code="600519", name="贵州茅台", exchange="SH", active=True, source="test"),
        AShareUniverseRow(code="000001", name="平安银行", exchange="SZ", active=True, source="test"),
        AShareUniverseRow(code="430047", name="已退市样例", exchange="BJ", active=False, source="test"),
    ])

    assert repo.count_universe() == 3
    assert repo.count_universe(active_only=True) == 2
    assert repo.list_active_codes() == ["000001", "600519"]
    assert [row.code for row in repo.list_universe(active_only=True)] == ["000001", "600519"]

    by_code = repo.search("6005", limit=5)
    assert [row.code for row in by_code] == ["600519"]

    by_name = repo.search("茅台", limit=5)
    assert [row.code for row in by_name] == ["600519"]


def test_invalid_rows_are_skipped_without_error(isolated_db) -> None:
    repo = AShareUniverseRepository(isolated_db)

    universe_result = repo.upsert_universe([
        {"code": "", "name": "无效", "exchange": "SH"},
        {"code": "600519", "name": "", "exchange": "SH"},
    ])
    assert universe_result.total == 0
    assert repo.count_universe() == 0

    snapshot_result = repo.upsert_snapshot([
        {"code": "600519", "data_date": None, "price": 1.0},
    ])
    assert snapshot_result.total == 0
    with isolated_db.get_session() as session:
        count = session.execute(select(func.count(AShareSnapshot.id))).scalar()
        assert count == 0

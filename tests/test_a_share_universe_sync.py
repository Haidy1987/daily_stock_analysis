# -*- coding: utf-8 -*-
"""Tests for A-share universe sync (Phase 1)."""

from __future__ import annotations

import os
from datetime import date
from typing import List

import pandas as pd
import pytest

from src.config import Config
from src.repositories.a_share_universe_repo import AShareUniverseRepository
from src.schemas.a_share_universe import AShareUniverseRow
from src.services.a_share_universe.providers import (
    EastMoneyUniverseProvider,
    TushareUniverseProvider,
    UniverseProviderError,
)
from src.services.a_share_universe_sync_service import AShareUniverseSyncService
from src.storage import DatabaseManager


class _StaticUniverseProvider:
    source_name = "test"

    def __init__(self, rows: List[AShareUniverseRow]):
        self._rows = rows

    def fetch_universe(self) -> List[AShareUniverseRow]:
        return list(self._rows)


@pytest.fixture()
def isolated_db(tmp_path):
    old_database_path = os.environ.get("DATABASE_PATH")
    db_path = tmp_path / "a_share_universe_sync.db"
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


def test_eastmoney_provider_parses_spot_dataframe() -> None:
    df = pd.DataFrame(
        [
            {"代码": "600519", "名称": "贵州茅台", "所属行业": "酿酒行业"},
            {"代码": "300750", "名称": "宁德时代", "所属行业": "电池"},
            {"代码": "900901", "名称": "B股样例", "所属行业": "忽略"},
        ]
    )
    rows = EastMoneyUniverseProvider._rows_from_dataframe(df, source="eastmoney")
    assert len(rows) == 2
    assert rows[0].code == "600519"
    assert rows[0].exchange == "SH"
    assert rows[0].board == "沪市主板"
    assert rows[0].industry == "酿酒行业"
    assert rows[1].code == "300750"


def test_tushare_provider_parses_stock_basic(monkeypatch) -> None:
    class _FakeAPI:
        def stock_basic(self, **kwargs):
            return pd.DataFrame(
                [
                    {
                        "ts_code": "600519.SH",
                        "symbol": "600519",
                        "name": "贵州茅台",
                        "industry": "白酒",
                        "market": "主板",
                        "exchange": "SSE",
                        "list_date": "20010827",
                        "list_status": "L",
                    }
                ]
            )

    fake_module = type("tushare", (), {"pro_api": staticmethod(lambda token: _FakeAPI())})()
    monkeypatch.setitem(__import__("sys").modules, "tushare", fake_module)

    provider = TushareUniverseProvider(token="demo-token")
    rows = provider.fetch_universe()
    assert len(rows) == 1
    assert rows[0].code == "600519"
    assert rows[0].exchange == "SH"
    assert rows[0].list_date == date(2001, 8, 27)
    assert rows[0].industry == "白酒"


def test_tushare_provider_requires_token() -> None:
    with pytest.raises(UniverseProviderError):
        TushareUniverseProvider(token="")


def test_sync_service_persists_provider_rows(isolated_db) -> None:
    provider = _StaticUniverseProvider(
        [
            AShareUniverseRow(code="600519", name="贵州茅台", exchange="SH", board="沪市主板", source="test"),
            AShareUniverseRow(code="000001", name="平安银行", exchange="SZ", board="深市主板", source="test"),
        ]
    )
    service = AShareUniverseSyncService(repository=AShareUniverseRepository(isolated_db), provider=provider)
    report = service.sync_universe(source="eastmoney")

    assert report.persisted is True
    assert report.fetched == 2
    assert report.inserted == 2
    assert report.updated == 0

    repo = AShareUniverseRepository(isolated_db)
    assert repo.count_universe(active_only=True) == 2


def test_sync_service_dry_run_skips_persist(isolated_db) -> None:
    provider = _StaticUniverseProvider(
        [AShareUniverseRow(code="600519", name="贵州茅台", exchange="SH", source="test")]
    )
    service = AShareUniverseSyncService(repository=AShareUniverseRepository(isolated_db), provider=provider)
    report = service.sync_universe(dry_run=True)

    assert report.fetched == 1
    assert report.persisted is False
    assert AShareUniverseRepository(isolated_db).count_universe() == 0


def test_sync_service_records_provider_error(isolated_db) -> None:
    class _BrokenProvider:
        source_name = "broken"

        def fetch_universe(self):
            raise UniverseProviderError("boom")

    service = AShareUniverseSyncService(
        repository=AShareUniverseRepository(isolated_db),
        provider=_BrokenProvider(),
    )
    report = service.sync_universe()

    assert report.fetched == 0
    assert report.errors == ["boom"]
    assert report.persisted is False

# -*- coding: utf-8 -*-
"""Tests for A-share universe index builder (Phase 3)."""

from __future__ import annotations

import json
import os
from datetime import date

import pytest

pypinyin = pytest.importorskip("pypinyin")

from src.config import Config
from src.repositories.a_share_universe_repo import AShareUniverseRepository
from src.schemas.a_share_universe import AShareUniverseRow
from src.services.a_share_universe.index_builder import (
    build_compressed_a_share_index,
    build_merged_index_from_db,
    merge_a_share_index_with_existing,
    universe_row_to_stock_dict,
    write_merged_index_from_db,
)
from src.storage import AShareUniverse, DatabaseManager


@pytest.fixture()
def isolated_db(tmp_path):
    old_database_path = os.environ.get("DATABASE_PATH")
    db_path = tmp_path / "a_share_universe_index_builder.db"
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


def test_universe_row_to_stock_dict_maps_bse() -> None:
    row = AShareUniverse(
        code="920001",
        name="测试北交所",
        exchange="BJ",
        active=True,
    )
    payload = universe_row_to_stock_dict(row)
    assert payload["ts_code"] == "920001.BJ"
    assert payload["market"] == "BSE"
    assert payload["symbol"] == "920001"


def test_build_compressed_a_share_index_includes_pinyin(isolated_db) -> None:
    repo = AShareUniverseRepository(isolated_db)
    repo.upsert_universe([
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
    rows = repo.list_universe(active_only=True)
    compressed = build_compressed_a_share_index(rows)
    assert len(compressed) == 1
    assert compressed[0][0] == "600519.SH"
    assert compressed[0][2] == "贵州茅台"
    assert compressed[0][6] == "CN"
    assert compressed[0][3]
    assert compressed[0][4]


def test_merge_a_share_index_with_existing_keeps_non_cn(tmp_path) -> None:
    existing_path = tmp_path / "stocks.index.json"
    existing_path.write_text(
        json.dumps(
            [
                ["600000.SH", "600000", "旧A股", "jiu", "j", [], "CN", "stock", True, 100],
                ["00700.HK", "00700", "腾讯控股", "tx", "tx", [], "HK", "stock", True, 100],
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    a_share_entries = [["600519.SH", "600519", "贵州茅台", "gzmt", "gzmt", [], "CN", "stock", True, 100]]
    merged = merge_a_share_index_with_existing(a_share_entries, existing_path)
    assert len(merged) == 2
    assert merged[0][6] == "HK"
    assert merged[1][0] == "600519.SH"


def test_write_merged_index_from_db(isolated_db, tmp_path) -> None:
    repo = AShareUniverseRepository(isolated_db)
    repo.upsert_universe([
        AShareUniverseRow(code="000001", name="平安银行", exchange="SZ", source="test"),
        AShareUniverseRow(code="600519", name="贵州茅台", exchange="SH", source="test"),
    ])
    output_path = tmp_path / "stocks.index.json"
    stats = write_merged_index_from_db(output_path, repo, merge_from=None)
    assert stats["total"] == 2
    assert stats["a_share_count"] == 2
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert len(payload) == 2


def test_build_merged_index_from_db_uses_repo(isolated_db) -> None:
    repo = AShareUniverseRepository(isolated_db)
    repo.upsert_universe([
        AShareUniverseRow(code="000001", name="平安银行", exchange="SZ", source="test"),
    ])
    merged = build_merged_index_from_db(repo)
    assert len(merged) == 1
    assert merged[0][0] == "000001.SZ"

# -*- coding: utf-8 -*-
"""Build stock autocomplete index entries from A-share universe DB rows."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence

from src.repositories.a_share_universe_repo import AShareUniverseRepository
from src.services.stock_index_builder import (
    build_stock_index,
    compress_index,
    filter_non_a_share_entries,
    load_compressed_index,
    normalize_stock_name_for_index,
    write_compressed_index,
)
from src.storage import AShareUniverse

_A_SHARE_MARKETS = {"CN", "BSE"}


def exchange_to_market(exchange: str) -> str:
    normalized = str(exchange or "").strip().upper()
    if normalized == "BJ":
        return "BSE"
    return "CN"


def exchange_to_suffix(exchange: str) -> str:
    normalized = str(exchange or "").strip().upper()
    return normalized or "SH"


def universe_row_to_stock_dict(row: AShareUniverse) -> dict:
    exchange = exchange_to_suffix(row.exchange)
    market = exchange_to_market(row.exchange)
    name = normalize_stock_name_for_index(row.name, market)
    return {
        "ts_code": f"{row.code}.{exchange}",
        "symbol": row.code,
        "name": name,
        "market": market,
        "active": bool(row.active),
    }


def build_compressed_a_share_index(rows: Iterable[AShareUniverse]) -> List[list]:
    stocks = [
        universe_row_to_stock_dict(row)
        for row in rows
        if row.code and row.name and row.active
    ]
    return compress_index(build_stock_index(stocks))


def merge_a_share_index_with_existing(
    a_share_entries: Sequence[Sequence],
    existing_index_path: Path | None,
) -> List[list]:
    if existing_index_path is None or not existing_index_path.is_file():
        return list(a_share_entries)

    existing_items = load_compressed_index(existing_index_path)
    preserved = filter_non_a_share_entries(existing_items)
    return preserved + list(a_share_entries)


def build_merged_index_from_db(
    repo: AShareUniverseRepository,
    *,
    existing_index_path: Path | None = None,
) -> List[list]:
    rows = repo.list_universe(active_only=True)
    a_share_entries = build_compressed_a_share_index(rows)
    return merge_a_share_index_with_existing(a_share_entries, existing_index_path)


def write_merged_index_from_db(
    output_path: Path,
    repo: AShareUniverseRepository,
    *,
    merge_from: Path | None = None,
) -> dict:
    merged = build_merged_index_from_db(repo, existing_index_path=merge_from)
    write_compressed_index(output_path, merged)
    a_share_count = sum(
        1 for item in merged if isinstance(item, list) and len(item) >= 7 and item[6] in _A_SHARE_MARKETS
    )
    return {
        "total": len(merged),
        "a_share_count": a_share_count,
        "non_a_share_count": len(merged) - a_share_count,
    }

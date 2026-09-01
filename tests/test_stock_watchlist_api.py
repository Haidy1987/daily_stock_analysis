# -*- coding: utf-8 -*-
"""Watchlist API regressions for stock-code variant matching."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from api.v1.endpoints.stocks import add_to_watchlist, get_watchlist, remove_from_watchlist
from api.v1.schemas.history import WatchlistRequest
from src.config import Config
from src.repositories.watchlist_repo import WatchlistRepository
from src.storage import DatabaseManager
from tests.auth_test_support import ensure_default_user_id, make_http_request


@pytest.fixture()
def watchlist_db(tmp_path):
    old_database_path = os.environ.get("DATABASE_PATH")
    db_path = tmp_path / "watchlist_api_test.db"
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


def _seed_codes(*codes: str) -> int:
    user_id = ensure_default_user_id()
    repo = WatchlistRepository()
    for code in codes:
        repo.add_code(user_id, code)
    return user_id


def test_watchlist_add_deduplicates_raw_hk_code_against_prefixed_variant(watchlist_db) -> None:
    request = make_http_request()
    _seed_codes("00700")

    response = add_to_watchlist(WatchlistRequest(stock_code="HK00700"), request)

    assert response.stock_codes == ["00700"]


def test_watchlist_remove_deletes_raw_hk_code_from_prefixed_variant_request(watchlist_db) -> None:
    request = make_http_request()
    _seed_codes("00700")

    response = remove_from_watchlist(WatchlistRequest(stock_code="HK00700"), request)

    assert response.stock_codes == []


def test_watchlist_matching_is_case_insensitive_for_us_tickers(watchlist_db) -> None:
    request = make_http_request()
    _seed_codes("aapl")

    add_response = add_to_watchlist(WatchlistRequest(stock_code="AAPL"), request)
    remove_response = remove_from_watchlist(WatchlistRequest(stock_code="AAPL"), request)

    assert add_response.stock_codes == ["aapl"]
    assert remove_response.stock_codes == []


def test_watchlist_reads_seeded_codes(watchlist_db) -> None:
    request = make_http_request()
    _seed_codes("600519", "300750", "AAPL")

    response = get_watchlist(request)

    assert response.stock_codes == ["600519", "300750", "AAPL"]


def test_watchlist_add_appends_new_code(watchlist_db) -> None:
    request = make_http_request()
    _seed_codes("600519", "300750")

    response = add_to_watchlist(WatchlistRequest(stock_code="AAPL"), request)

    assert response.stock_codes == ["600519", "300750", "AAPL"]

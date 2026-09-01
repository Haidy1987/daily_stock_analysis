# -*- coding: utf-8 -*-
"""Tests for A-share universe mapping helpers."""

from __future__ import annotations

from src.services.a_share_universe.mapping import infer_board, infer_exchange, is_a_share_universe_code


def test_infer_exchange_and_board() -> None:
    assert infer_exchange("600519") == "SH"
    assert infer_board("600519") == "沪市主板"
    assert infer_exchange("300750") == "SZ"
    assert infer_board("300750") == "创业板"
    assert infer_exchange("688981") == "SH"
    assert infer_board("688981") == "科创板"
    assert infer_exchange("920001") == "BJ"
    assert infer_board("920001") == "北交所"


def test_is_a_share_universe_code_filters_b_shares() -> None:
    assert is_a_share_universe_code("600519") is True
    assert is_a_share_universe_code("900901") is False
    assert is_a_share_universe_code("200002") is False
    assert is_a_share_universe_code("AAPL") is False

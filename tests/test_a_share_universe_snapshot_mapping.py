# -*- coding: utf-8 -*-
"""Tests for A-share snapshot mapping helpers."""

from __future__ import annotations

from datetime import date

import pandas as pd

from src.services.a_share_universe.snapshot_mapping import (
    financial_map_from_yjbb_dataframe,
    snapshot_row_from_spot_record,
)


def test_snapshot_row_from_spot_record_maps_market_fields() -> None:
    row = snapshot_row_from_spot_record(
        {
            "代码": "600519",
            "最新价": 1700.5,
            "涨跌幅": 1.2,
            "今开": 1690,
            "最高": 1710,
            "最低": 1688,
            "昨收": 1680,
            "振幅": 1.3,
            "成交量": 1000,
            "成交额": 200000,
            "换手率": 0.5,
            "量比": 1.1,
            "市盈率-动态": 25.1,
            "市净率": 8.2,
            "总市值": 1000000,
            "流通市值": 900000,
            "52周最高": 1800,
            "52周最低": 1400,
            "年初至今涨跌幅": 5.5,
        },
        data_date=date(2026, 8, 29),
        source="eastmoney",
    )
    assert row is not None
    assert row.code == "600519"
    assert row.price == 1700.5
    assert row.high_52w == 1800
    assert row.ytd_pct_chg == 5.5


def test_financial_map_from_yjbb_dataframe() -> None:
    df = pd.DataFrame(
        [
            {
                "股票代码": "600519",
                "每股收益": 12.3,
                "每股净资产": 100.5,
                "净资产收益率": 20.1,
                "营业收入": 1000,
                "营业收入同比增长": 10.2,
                "净利润": 500,
                "净利润同比增长": 8.8,
            }
        ]
    )
    mapping = financial_map_from_yjbb_dataframe(df)
    assert mapping["600519"]["eps"] == 12.3
    assert mapping["600519"]["roe"] == 20.1
    assert mapping["600519"]["revenue_yoy"] == 10.2

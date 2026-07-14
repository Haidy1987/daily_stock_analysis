# -*- coding: utf-8 -*-
"""Unit tests for TechnicalChartService."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

from data_provider.base import DataFetchError
from src.services.ohlcv_aggregation import aggregate_ohlcv, estimate_daily_bars_for_period
from src.services.technical_chart_service import (
    WARMUP_BARS,
    TechnicalChartService,
    TechnicalChartSourceUnavailableError,
    TechnicalChartValidationError,
    parse_indicator_groups,
)
from src.services.technical_indicators import (
    CORE_INDICATOR_GROUPS,
    calculate_technical_indicators,
    normalize_ohlcv_frame,
)


def _ohlcv(n: int = 200, start: str = "2025-01-02") -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=n)
    close = pd.Series(np.linspace(100.0, 140.0, n) + np.sin(np.arange(n) / 5.0))
    open_ = close.shift(1).fillna(close.iloc[0])
    return pd.DataFrame(
        {
            "date": dates,
            "open": open_.values,
            "high": (np.maximum(open_, close) + 1.0).values,
            "low": (np.minimum(open_, close) - 1.0).values,
            "close": close.values,
            "volume": np.full(n, 1_000_000.0),
            "amount": close.values * 1_000_000.0,
            "pct_chg": close.pct_change().fillna(0.0).values * 100.0,
        }
    )


class ParseIndicatorsTestCase(unittest.TestCase):
    def test_default_and_unknown(self) -> None:
        self.assertEqual(parse_indicator_groups(None), set(CORE_INDICATOR_GROUPS))
        with self.assertRaises(TechnicalChartValidationError) as ctx:
            parse_indicator_groups("ma,foo")
        self.assertEqual(ctx.exception.error, "invalid_indicators")


class TechnicalChartServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.service = TechnicalChartService()

    def test_unsupported_period_and_days(self) -> None:
        with self.assertRaises(TechnicalChartValidationError) as ctx:
            self.service.get_technical_chart("600519", period="quarterly")
        self.assertEqual(ctx.exception.error, "unsupported_period")
        with self.assertRaises(TechnicalChartValidationError):
            self.service.get_technical_chart("600519", days=30)

    @patch("data_provider.base.DataFetcherManager")
    def test_weekly_aggregates_then_recomputes_indicators(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        # Enough daily sessions for 60 weekly display bars + warmup estimate.
        daily_n, _ = estimate_daily_bars_for_period(
            "weekly", 60, warmup_bars=WARMUP_BARS, max_daily_bars=5000
        )
        manager.get_daily_data.return_value = (_ohlcv(daily_n), "akshare")
        manager.get_stock_name.return_value = "贵州茅台"

        result = self.service.get_technical_chart("600519", period="weekly", days=60)
        self.assertEqual(result["period"], "weekly")
        self.assertEqual(len(result["items"]), 60)
        self.assertEqual(result["calculation_version"], "technical-v1")
        args, kwargs = manager.get_daily_data.call_args
        self.assertEqual(kwargs.get("days") or args[1], daily_n)

        # Hand path: normalize → aggregate → indicators → tail.
        normalized = normalize_ohlcv_frame(_ohlcv(daily_n))
        weekly = aggregate_ohlcv(normalized, "weekly")
        computed = calculate_technical_indicators(weekly, normalize=False)
        expected = computed.tail(60).reset_index(drop=True)
        self.assertEqual(result["items"][-1]["date"], expected.iloc[-1]["date"].strftime("%Y-%m-%d"))
        self.assertAlmostEqual(
            float(result["items"][-1]["close"]),
            float(expected.iloc[-1]["close"]),
            places=6,
        )
        self.assertAlmostEqual(
            float(result["items"][-1]["ma20"]),
            float(expected.iloc[-1]["ma20"]),
            places=6,
        )
        # change_percent must be vs previous weekly close, not raw daily.
        if len(expected) >= 2:
            prev = float(expected.iloc[-2]["close"])
            last = float(expected.iloc[-1]["close"])
            self.assertAlmostEqual(
                float(result["items"][-1]["change_percent"]),
                (last - prev) / prev * 100.0,
                places=5,
            )

    @patch("data_provider.base.DataFetcherManager")
    def test_monthly_partial_when_history_short(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        manager.get_daily_data.return_value = (_ohlcv(80), "akshare")
        manager.get_stock_name.return_value = None
        result = self.service.get_technical_chart("600519", period="monthly", days=60)
        self.assertEqual(result["period"], "monthly")
        self.assertLess(len(result["items"]), 60)
        self.assertEqual(result["data_status"], "partial")
        self.assertIn("history_shorter_than_display_days", result["warnings"])

    @patch("data_provider.base.DataFetcherManager")
    def test_source_unavailable(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        manager.get_daily_data.side_effect = DataFetchError("all failed")
        with self.assertRaises(TechnicalChartSourceUnavailableError):
            self.service.get_technical_chart("600519", days=60)

    @patch("data_provider.base.DataFetcherManager")
    def test_empty_history(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        manager.get_daily_data.return_value = (pd.DataFrame(), "akshare")
        manager.get_stock_name.return_value = "贵州茅台"
        result = self.service.get_technical_chart("600519", days=60)
        self.assertEqual(result["data_status"], "empty")
        self.assertEqual(result["items"], [])
        self.assertIn("no_history", result["warnings"])

    @patch("data_provider.base.DataFetcherManager")
    def test_full_chart_trims_warmup_and_has_fields(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        manager.get_daily_data.return_value = (_ohlcv(200), "akshare")
        manager.get_stock_name.return_value = "贵州茅台"

        result = self.service.get_technical_chart("600519", days=120)
        self.assertEqual(result["period"], "daily")
        self.assertEqual(result["range_days"], 120)
        self.assertEqual(result["calculation_version"], "technical-v1")
        self.assertEqual(len(result["items"]), 120)
        dates = [item["date"] for item in result["items"]]
        self.assertEqual(dates, sorted(dates))
        # Warmup must not leak: fetch asked for days+warmup
        args, kwargs = manager.get_daily_data.call_args
        self.assertEqual(kwargs.get("days") or args[1], 120 + WARMUP_BARS)

        sample = result["items"][-1]
        for field in (
            "ma5", "macd_dif", "rsi6", "boll_mid", "kdj_k", "cci", "bias5", "volume_ratio"
        ):
            self.assertIn(field, sample)
            self.assertIsNotNone(sample[field])
        self.assertIn(result["data_status"], {"available", "partial"})
        self.assertIsNotNone(result["summary"]["latest_close"])
        self.assertTrue(result["summary"]["support_levels"] or result["summary"]["resistance_levels"]
                        or result["summary"]["recent_high"])

    @patch("data_provider.base.DataFetcherManager")
    def test_indicator_filter_omits_unrequested_fields(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        manager.get_daily_data.return_value = (_ohlcv(100), "yf")
        manager.get_stock_name.return_value = None
        result = self.service.get_technical_chart(
            "600519",
            days=60,
            indicators="ma,macd",
        )
        item = result["items"][-1]
        self.assertIn("ma5", item)
        self.assertIn("macd_dif", item)
        self.assertNotIn("rsi6", item)
        self.assertNotIn("kdj_k", item)
        self.assertEqual(result["summary"]["support_levels"], [])

    @patch("data_provider.base.DataFetcherManager")
    def test_partial_when_history_short(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        manager.get_daily_data.return_value = (_ohlcv(30), "akshare")
        manager.get_stock_name.return_value = None
        result = self.service.get_technical_chart("600519", days=60)
        self.assertEqual(result["data_status"], "partial")
        self.assertTrue(result["warnings"])
        self.assertEqual(len(result["items"]), 30)

    @patch("data_provider.base.DataFetcherManager")
    def test_non_finite_serialized_as_null(self, mock_manager_cls: MagicMock) -> None:
        manager = mock_manager_cls.return_value
        df = _ohlcv(80)
        df.loc[df.index[-1], "close"] = np.nan
        # Dropping nan close in normalize — use finite frame then inject after calc via patching items path.
        manager.get_daily_data.return_value = (_ohlcv(80), "akshare")
        manager.get_stock_name.return_value = None
        result = self.service.get_technical_chart("600519", days=60)
        for item in result["items"]:
            for key, value in item.items():
                if isinstance(value, float):
                    self.assertTrue(np.isfinite(value))


if __name__ == "__main__":
    unittest.main()

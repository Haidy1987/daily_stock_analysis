# -*- coding: utf-8 -*-
"""Fixed-sample tests for weekly / monthly OHLCV aggregation."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.services.ohlcv_aggregation import (
    aggregate_ohlcv,
    estimate_daily_bars_for_period,
)
from src.services.technical_indicators import (
    calculate_technical_indicators,
    normalize_ohlcv_frame,
)


def _daily_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class AggregateOhlcvTestCase(unittest.TestCase):
    def test_weekly_ohlcv_cross_week_and_holiday_gap(self) -> None:
        # Mon–Fri week1; gap across weekend; Mon–Wed week2 (short week).
        daily = _daily_frame(
            [
                {"date": "2026-01-05", "open": 10, "high": 11, "low": 9, "close": 10.5, "volume": 100, "amount": 1000},
                {"date": "2026-01-06", "open": 10.5, "high": 12, "low": 10, "close": 11, "volume": 200, "amount": 2200},
                {"date": "2026-01-07", "open": 11, "high": 11.5, "low": 10.5, "close": 11.2, "volume": 150, "amount": 1680},
                {"date": "2026-01-08", "open": 11.2, "high": 13, "low": 11, "close": 12, "volume": 300, "amount": 3600},
                {"date": "2026-01-09", "open": 12, "high": 12.5, "low": 11.8, "close": 12.2, "volume": 250, "amount": 3050},
                # No Sat/Sun bars (holiday/weekend gap).
                {"date": "2026-01-12", "open": 12.3, "high": 12.8, "low": 12.0, "close": 12.5, "volume": 180, "amount": 2250},
                {"date": "2026-01-13", "open": 12.5, "high": 13.0, "low": 12.4, "close": 12.8, "volume": 220, "amount": 2816},
                {"date": "2026-01-14", "open": 12.8, "high": 13.2, "low": 12.6, "close": 13.0, "volume": 210, "amount": 2730},
            ]
        )
        weekly = aggregate_ohlcv(daily, "weekly")
        self.assertEqual(len(weekly), 2)
        self.assertEqual(str(weekly.iloc[0]["date"].date()), "2026-01-09")
        self.assertEqual(weekly.iloc[0]["open"], 10.0)
        self.assertEqual(weekly.iloc[0]["high"], 13.0)
        self.assertEqual(weekly.iloc[0]["low"], 9.0)
        self.assertEqual(weekly.iloc[0]["close"], 12.2)
        self.assertEqual(weekly.iloc[0]["volume"], 1000.0)
        self.assertEqual(weekly.iloc[0]["amount"], 11530.0)
        self.assertTrue(pd.isna(weekly.iloc[0]["change_percent"]))

        self.assertEqual(str(weekly.iloc[1]["date"].date()), "2026-01-14")
        self.assertEqual(weekly.iloc[1]["open"], 12.3)
        self.assertEqual(weekly.iloc[1]["high"], 13.2)
        self.assertEqual(weekly.iloc[1]["low"], 12.0)
        self.assertEqual(weekly.iloc[1]["close"], 13.0)
        self.assertEqual(weekly.iloc[1]["volume"], 610.0)
        expected_pct = (13.0 - 12.2) / 12.2 * 100.0
        self.assertAlmostEqual(float(weekly.iloc[1]["change_percent"]), expected_pct, places=6)

    def test_monthly_uses_last_trading_day_and_month_end(self) -> None:
        daily = _daily_frame(
            [
                {"date": "2026-01-05", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 100, "amount": 1000},
                {"date": "2026-01-30", "open": 11, "high": 12, "low": 10.5, "close": 11.5, "volume": 200, "amount": 2300},
                # Feb ends early (no 28/29 bars) — date must be last actual session.
                {"date": "2026-02-02", "open": 11.5, "high": 12, "low": 11, "close": 11.8, "volume": 150, "amount": 1770},
                {"date": "2026-02-27", "open": 12, "high": 13, "low": 11.9, "close": 12.5, "volume": 300, "amount": 3750},
            ]
        )
        monthly = aggregate_ohlcv(daily, "monthly")
        self.assertEqual(len(monthly), 2)
        self.assertEqual(str(monthly.iloc[0]["date"].date()), "2026-01-30")
        self.assertEqual(monthly.iloc[0]["open"], 10.0)
        self.assertEqual(monthly.iloc[0]["close"], 11.5)
        self.assertEqual(str(monthly.iloc[1]["date"].date()), "2026-02-27")
        self.assertEqual(monthly.iloc[1]["high"], 13.0)
        self.assertEqual(monthly.iloc[1]["low"], 11.0)
        expected_pct = (12.5 - 11.5) / 11.5 * 100.0
        self.assertAlmostEqual(float(monthly.iloc[1]["change_percent"]), expected_pct, places=6)

    def test_all_volume_amount_missing_stay_null(self) -> None:
        daily = _daily_frame(
            [
                {"date": "2026-03-02", "open": 1, "high": 2, "low": 1, "close": 1.5, "volume": np.nan, "amount": np.nan},
                {"date": "2026-03-03", "open": 1.5, "high": 2.5, "low": 1.4, "close": 2.0, "volume": np.nan, "amount": np.nan},
            ]
        )
        weekly = aggregate_ohlcv(daily, "weekly")
        self.assertEqual(len(weekly), 1)
        self.assertTrue(pd.isna(weekly.iloc[0]["volume"]))
        self.assertTrue(pd.isna(weekly.iloc[0]["amount"]))

    def test_single_session_week_and_month(self) -> None:
        daily = _daily_frame(
            [
                {"date": "2026-04-01", "open": 5, "high": 6, "low": 4, "close": 5.5, "volume": 50, "amount": 275},
            ]
        )
        weekly = aggregate_ohlcv(daily, "weekly")
        monthly = aggregate_ohlcv(daily, "monthly")
        self.assertEqual(len(weekly), 1)
        self.assertEqual(len(monthly), 1)
        self.assertEqual(weekly.iloc[0]["open"], 5.0)
        self.assertEqual(weekly.iloc[0]["close"], 5.5)
        self.assertEqual(str(monthly.iloc[0]["date"].date()), "2026-04-01")

    def test_no_fabricated_empty_weeks(self) -> None:
        daily = _daily_frame(
            [
                {"date": "2026-01-05", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "amount": 1},
                # Skip an entire calendar week (no sessions Jan 12–16).
                {"date": "2026-01-19", "open": 2, "high": 2, "low": 2, "close": 2, "volume": 2, "amount": 2},
            ]
        )
        weekly = aggregate_ohlcv(daily, "weekly")
        self.assertEqual(len(weekly), 2)
        dates = [str(ts.date()) for ts in weekly["date"]]
        self.assertEqual(dates, ["2026-01-05", "2026-01-19"])

    def test_indicators_match_hand_aggregation_then_engine(self) -> None:
        dates = pd.bdate_range("2025-01-02", periods=120)
        close = pd.Series(np.linspace(100.0, 130.0, 120) + np.sin(np.arange(120) / 7.0))
        daily = pd.DataFrame(
            {
                "date": dates,
                "open": close.shift(1).fillna(close.iloc[0]).values,
                "high": (close + 1).values,
                "low": (close - 1).values,
                "close": close.values,
                "volume": np.full(120, 1_000.0),
                "amount": close.values * 1_000.0,
            }
        )
        normalized = normalize_ohlcv_frame(daily)
        weekly = aggregate_ohlcv(normalized, "weekly")
        computed = calculate_technical_indicators(weekly, normalize=False)
        # Spot-check MA20 on aggregated frame equals engine on same OHLC.
        hand = weekly["close"].rolling(20, min_periods=20).mean()
        pd.testing.assert_series_equal(
            computed["ma20"].reset_index(drop=True),
            hand.reset_index(drop=True),
            check_names=False,
        )
        # Must not equal a naive average of daily MA20 over the week.
        daily_with_ma = calculate_technical_indicators(normalized, indicators={"ma"}, normalize=False)
        daily_with_ma = daily_with_ma.copy()
        daily_with_ma["_wk"] = daily_with_ma["date"].dt.to_period("W-SUN")
        naive = daily_with_ma.groupby("_wk", sort=True)["ma20"].mean()
        last_week = weekly["date"].iloc[-1].to_period("W-SUN")
        if pd.notna(naive.loc[last_week]) and pd.notna(computed["ma20"].iloc[-1]):
            self.assertNotAlmostEqual(
                float(computed["ma20"].iloc[-1]),
                float(naive.loc[last_week]),
                places=6,
            )


class EstimateDailyBarsTestCase(unittest.TestCase):
    def test_estimate_and_cap(self) -> None:
        weekly, capped = estimate_daily_bars_for_period(
            "weekly", 120, warmup_bars=60, max_daily_bars=5000
        )
        self.assertFalse(capped)
        self.assertEqual(weekly, 180 * 5 + 10)

        monthly, capped = estimate_daily_bars_for_period(
            "monthly", 250, warmup_bars=60, max_daily_bars=5000
        )
        self.assertTrue(capped)
        self.assertEqual(monthly, 5000)

        daily, capped = estimate_daily_bars_for_period(
            "daily", 120, warmup_bars=60, max_daily_bars=5000
        )
        self.assertEqual(daily, 180)
        self.assertFalse(capped)


if __name__ == "__main__":
    unittest.main()

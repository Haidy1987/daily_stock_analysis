# -*- coding: utf-8 -*-
"""Fixed-sample tests for shared technical indicator engine (stage 01)."""

from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from src.services.technical_indicators import (
    MACD_FIRST_VALID_INDEX,
    VOLUME_HEAVY_RATIO,
    VOLUME_SHRINK_RATIO,
    VOLUME_STATUS_HEAVY_UP,
    VOLUME_STATUS_NORMAL,
    VOLUME_STATUS_SHRINK_DOWN,
    build_support_resistance_summary,
    calculate_cci_series,
    calculate_kdj_series,
    calculate_technical_indicators,
    normalize_ohlcv_frame,
    wilder_rsi,
)
from src.services.alert_indicators import _calculate_rsi as calculate_alert_rsi
from src.services.alert_indicators import evaluate_indicator_alert, normalize_indicator_parameters
from src.stock_analyzer import StockTrendAnalyzer
from tests.test_stock_analyzer_rsi import REPORT_RSI_CLOSE


def _sample_ohlcv(n: int = 40, start: str = "2026-01-01") -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=n)
    close = pd.Series(np.linspace(100.0, 120.0, n) + np.sin(np.arange(n) / 3.0))
    open_ = close.shift(1).fillna(close.iloc[0])
    high = np.maximum(open_, close) + 1.0
    low = np.minimum(open_, close) - 1.0
    volume = pd.Series(np.full(n, 1_000_000.0))
    volume.iloc[-1] = 2_000_000.0
    return pd.DataFrame(
        {
            "date": dates,
            "open": open_.values,
            "high": high.values,
            "low": low.values,
            "close": close.values,
            "volume": volume.values,
            "amount": volume.values * close.values,
            "change_percent": close.pct_change().fillna(0.0).values * 100.0,
        }
    )


class NormalizeOhlcvTestCase(unittest.TestCase):
    def test_sorts_dedupes_and_keeps_last_duplicate_date(self) -> None:
        df = pd.DataFrame(
            {
                "date": ["2026-01-02", "2026-01-01", "2026-01-02"],
                "open": [2.0, 1.0, 3.0],
                "high": [2.5, 1.5, 3.5],
                "low": [1.5, 0.5, 2.5],
                "close": [2.2, 1.2, 3.2],
                "volume": [100.0, 200.0, 300.0],
            }
        )
        out = normalize_ohlcv_frame(df)
        self.assertEqual(len(out), 2)
        self.assertEqual(out.iloc[0]["close"], 1.2)
        self.assertEqual(out.iloc[1]["close"], 3.2)
        self.assertEqual(out.iloc[1]["volume"], 300.0)

    def test_non_finite_prices_become_nan_and_missing_close_dropped(self) -> None:
        df = pd.DataFrame(
            {
                "date": ["2026-01-01", "2026-01-02", "2026-01-03"],
                "open": [1.0, 2.0, 3.0],
                "high": [1.0, 2.0, 3.0],
                "low": [1.0, 2.0, 3.0],
                "close": [1.0, np.inf, np.nan],
                "volume": [10.0, 20.0, 30.0],
            }
        )
        out = normalize_ohlcv_frame(df)
        self.assertEqual(len(out), 1)
        self.assertEqual(float(out.iloc[0]["close"]), 1.0)

    def test_empty_and_missing_columns(self) -> None:
        empty = normalize_ohlcv_frame(pd.DataFrame())
        self.assertTrue(empty.empty)
        with self.assertRaises(ValueError):
            normalize_ohlcv_frame(pd.DataFrame({"date": ["2026-01-01"], "close": [1.0]}))

    def test_pct_chg_alias(self) -> None:
        df = _sample_ohlcv(5).drop(columns=["change_percent"])
        df["pct_chg"] = 1.5
        out = normalize_ohlcv_frame(df)
        self.assertIn("change_percent", out.columns)
        self.assertTrue((out["change_percent"] == 1.5).all())


class CoreIndicatorsTestCase(unittest.TestCase):
    def test_ma_full_window_null_before_period(self) -> None:
        df = _sample_ohlcv(260)
        out = calculate_technical_indicators(df, indicators={"ma"})
        self.assertTrue(pd.isna(out["ma5"].iloc[3]))
        self.assertFalse(pd.isna(out["ma5"].iloc[4]))
        self.assertTrue(pd.isna(out["ma20"].iloc[18]))
        self.assertFalse(pd.isna(out["ma20"].iloc[19]))
        expected = float(df["close"].iloc[0:5].mean())
        self.assertAlmostEqual(float(out["ma5"].iloc[4]), expected)
        self.assertTrue(pd.isna(out["ma250"].iloc[248]))
        self.assertFalse(pd.isna(out["ma250"].iloc[249]))
        self.assertAlmostEqual(
            float(out["ma250"].iloc[249]),
            float(df["close"].iloc[0:250].mean()),
        )

    def test_macd_bar_formula_and_warmup_null(self) -> None:
        df = _sample_ohlcv(40)
        out = calculate_technical_indicators(df, indicators={"macd"})
        self.assertTrue(pd.isna(out["macd_dif"].iloc[MACD_FIRST_VALID_INDEX - 1]))
        self.assertFalse(pd.isna(out["macd_dif"].iloc[MACD_FIRST_VALID_INDEX]))
        row = out.iloc[-1]
        self.assertAlmostEqual(
            float(row["macd_bar"]),
            (float(row["macd_dif"]) - float(row["macd_dea"])) * 2.0,
            places=10,
        )

    def test_rsi_chart_no_fillna_50_and_matches_report_latest(self) -> None:
        dates = pd.bdate_range("2026-01-01", periods=len(REPORT_RSI_CLOSE))
        df = pd.DataFrame(
            {
                "date": dates,
                "open": REPORT_RSI_CLOSE,
                "high": [c + 1 for c in REPORT_RSI_CLOSE],
                "low": [c - 1 for c in REPORT_RSI_CLOSE],
                "close": REPORT_RSI_CLOSE,
                "volume": [1_000.0] * len(REPORT_RSI_CLOSE),
            }
        )
        chart = calculate_technical_indicators(df, indicators={"rsi"})
        self.assertTrue(pd.isna(chart["rsi6"].iloc[5]))
        self.assertFalse(pd.isna(chart["rsi6"].iloc[6]))
        self.assertFalse((chart["rsi6"].iloc[:6] == 50).any())

        report = StockTrendAnalyzer()._calculate_rsi(pd.DataFrame({"close": REPORT_RSI_CLOSE}))
        self.assertAlmostEqual(float(chart["rsi6"].iloc[-1]), float(report["RSI_6"].iloc[-1]))
        self.assertAlmostEqual(float(chart["rsi12"].iloc[-1]), float(report["RSI_12"].iloc[-1]))
        self.assertAlmostEqual(float(chart["rsi24"].iloc[-1]), float(report["RSI_24"].iloc[-1]))

    def test_rsi_all_up_and_flat(self) -> None:
        up = pd.Series(range(1, 20), dtype="float64")
        rsi_up = wilder_rsi(up, 6, fill_neutral=False)
        self.assertTrue(np.isfinite(rsi_up.iloc[-1]))
        self.assertGreaterEqual(float(rsi_up.iloc[-1]), 99.0)

        flat = pd.Series([10.0] * 20)
        rsi_flat = wilder_rsi(flat, 6, fill_neutral=False)
        # Chart mode: both-zero avg gain/loss → NaN (never fill 50).
        self.assertTrue(pd.isna(rsi_flat.iloc[-1]))

    def test_bias_uses_ma_and_null_when_ma_missing(self) -> None:
        df = _sample_ohlcv(12)
        out = calculate_technical_indicators(df, indicators={"bias"})
        self.assertTrue(pd.isna(out["bias20"].iloc[-1]))
        self.assertFalse(pd.isna(out["bias5"].iloc[-1]))
        ma5 = float(out["ma5"].iloc[-1])
        close = float(out["close"].iloc[-1])
        self.assertAlmostEqual(float(out["bias5"].iloc[-1]), (close - ma5) / ma5 * 100.0)

    def test_volume_ratio_excludes_current_bar(self) -> None:
        df = _sample_ohlcv(10)
        df.loc[df.index[-1], "volume"] = 5_000_000.0
        out = calculate_technical_indicators(df, indicators={"volume"})
        prev_avg = float(df["volume"].iloc[-6:-1].mean())
        expected = 5_000_000.0 / prev_avg
        self.assertAlmostEqual(float(out["volume_ratio"].iloc[-1]), expected)
        self.assertTrue(pd.isna(out["volume_ratio"].iloc[4]))
        self.assertFalse(pd.isna(out["volume_ratio"].iloc[5]))

    def test_volume_status_thresholds(self) -> None:
        df = _sample_ohlcv(10)
        # Make prior 5 volumes = 1000, last = 2000 → ratio 2.0 heavy; close up
        df["volume"] = 1000.0
        df.loc[df.index[-1], "volume"] = 2000.0
        df.loc[df.index[-1], "close"] = float(df.iloc[-2]["close"]) + 1.0
        out = calculate_technical_indicators(df, indicators={"volume"})
        self.assertGreaterEqual(float(out["volume_ratio"].iloc[-1]), VOLUME_HEAVY_RATIO)
        self.assertEqual(out["volume_status"].iloc[-1], VOLUME_STATUS_HEAVY_UP)

        df2 = df.copy()
        df2.loc[df2.index[-1], "volume"] = 500.0
        df2.loc[df2.index[-1], "close"] = float(df2.iloc[-2]["close"]) - 1.0
        out2 = calculate_technical_indicators(df2, indicators={"volume"})
        self.assertLessEqual(float(out2["volume_ratio"].iloc[-1]), VOLUME_SHRINK_RATIO)
        self.assertEqual(out2["volume_status"].iloc[-1], VOLUME_STATUS_SHRINK_DOWN)

        df3 = df.copy()
        df3.loc[df3.index[-1], "volume"] = 1000.0
        out3 = calculate_technical_indicators(df3, indicators={"volume"})
        self.assertEqual(out3["volume_status"].iloc[-1], VOLUME_STATUS_NORMAL)

    def test_volume_zero_denominator_is_null(self) -> None:
        df = _sample_ohlcv(8)
        df["volume"] = 0.0
        df.loc[df.index[-1], "volume"] = 100.0
        out = calculate_technical_indicators(df, indicators={"volume"})
        self.assertTrue(pd.isna(out["volume_ratio"].iloc[-1]))
        self.assertIsNone(out["volume_status"].iloc[-1])

    def test_does_not_mutate_input(self) -> None:
        df = _sample_ohlcv(30)
        original_cols = list(df.columns)
        _ = calculate_technical_indicators(df)
        self.assertEqual(list(df.columns), original_cols)


class BollKdjCciTestCase(unittest.TestCase):
    def test_boll_reuses_ma20_and_fixed_sample(self) -> None:
        close = [10.0, 11.0, 12.0, 11.0, 13.0] + [12.0 + (i % 5) * 0.2 for i in range(20)]
        df = pd.DataFrame(
            {
                "date": pd.bdate_range("2026-01-01", periods=len(close)),
                "open": close,
                "high": [c + 0.5 for c in close],
                "low": [c - 0.5 for c in close],
                "close": close,
                "volume": [1000.0] * len(close),
            }
        )
        out = calculate_technical_indicators(df, indicators={"ma", "boll"})
        self.assertTrue(pd.isna(out["boll_mid"].iloc[18]))
        self.assertFalse(pd.isna(out["boll_mid"].iloc[19]))
        # Mid equals MA20 from same frame.
        self.assertAlmostEqual(float(out["boll_mid"].iloc[-1]), float(out["ma20"].iloc[-1]))
        window = out["close"].iloc[-20:]
        mid = float(window.mean())
        std = float(window.std(ddof=0))
        self.assertAlmostEqual(float(out["boll_upper"].iloc[-1]), mid + 2 * std)
        self.assertAlmostEqual(float(out["boll_lower"].iloc[-1]), mid - 2 * std)
        upper = float(out["boll_upper"].iloc[-1])
        lower = float(out["boll_lower"].iloc[-1])
        self.assertAlmostEqual(
            float(out["boll_bandwidth"].iloc[-1]),
            (upper - lower) / mid * 100.0,
        )
        last_close = float(out["close"].iloc[-1])
        self.assertAlmostEqual(
            float(out["boll_position"].iloc[-1]),
            (last_close - lower) / (upper - lower) * 100.0,
        )

    def test_boll_constant_price_null_position(self) -> None:
        df = _sample_ohlcv(25)
        df["close"] = 100.0
        df["open"] = 100.0
        df["high"] = 100.0
        df["low"] = 100.0
        out = calculate_technical_indicators(df, indicators={"boll"})
        self.assertTrue(pd.isna(out["boll_position"].iloc[-1]))
        self.assertEqual(float(out["boll_bandwidth"].iloc[-1]), 0.0)

    def test_kdj_seed_and_high_equals_low(self) -> None:
        # Flat highs/lows → RSV=50; first valid K blends seed 50 with RSV 50 → 50.
        n = 12
        df = pd.DataFrame(
            {
                "date": pd.bdate_range("2026-01-01", periods=n),
                "open": [10.0] * n,
                "high": [10.0] * n,
                "low": [10.0] * n,
                "close": [10.0] * n,
                "volume": [100.0] * n,
            }
        )
        out = calculate_technical_indicators(df, indicators={"kdj"})
        self.assertTrue(pd.isna(out["kdj_k"].iloc[7]))
        self.assertAlmostEqual(float(out["kdj_k"].iloc[8]), 50.0)
        self.assertAlmostEqual(float(out["kdj_d"].iloc[8]), 50.0)
        self.assertAlmostEqual(float(out["kdj_j"].iloc[8]), 50.0)
        self.assertFalse(np.isinf(out[["kdj_k", "kdj_d", "kdj_j"]].to_numpy()).any())

    def test_kdj_manual_step(self) -> None:
        # RSV window 3; after 3 bars RSV=(6-4)/(8-4)*100=50, then bump close.
        rows = [
            (5, 8, 4),
            (5, 8, 4),
            (6, 8, 4),
            (7, 9, 5),
        ]
        df = pd.DataFrame(
            {
                "date": pd.bdate_range("2026-01-01", periods=len(rows)),
                "open": [r[0] for r in rows],
                "high": [r[1] for r in rows],
                "low": [r[2] for r in rows],
                "close": [r[0] for r in rows],
                "volume": [1.0] * len(rows),
            }
        )
        k_value, d_value, j_value = calculate_kdj_series(
            df["high"], df["low"], df["close"], period=3, k_period=3, d_period=3
        )
        # First RSV at i=2: ((6-4)/(8-4))*100 = 50 → K=50, D=50, J=50
        self.assertAlmostEqual(float(k_value.iloc[2]), 50.0)
        self.assertAlmostEqual(float(d_value.iloc[2]), 50.0)
        # Next RSV=((7-4)/(9-4))*100=60 → K=(2/3)*50+(1/3)*60=53.333...
        self.assertAlmostEqual(float(k_value.iloc[3]), 160.0 / 3.0)
        self.assertAlmostEqual(float(j_value.iloc[3]), 3 * float(k_value.iloc[3]) - 2 * float(d_value.iloc[3]))

    def test_cci_mean_dev_zero_is_null(self) -> None:
        n = 20
        df = pd.DataFrame(
            {
                "date": pd.bdate_range("2026-01-01", periods=n),
                "open": [10.0] * n,
                "high": [10.0] * n,
                "low": [10.0] * n,
                "close": [10.0] * n,
                "volume": [1.0] * n,
            }
        )
        out = calculate_technical_indicators(df, indicators={"cci"})
        self.assertTrue(pd.isna(out["cci"].iloc[-1]))

    def test_cci_fixed_sample(self) -> None:
        cci_close = [5, 5, 6, 5, 7]
        df = pd.DataFrame(
            {
                "date": pd.date_range("2026-01-01", periods=len(cci_close)),
                "open": cci_close,
                "high": [v + 1 for v in cci_close],
                "low": [v - 1 for v in cci_close],
                "close": cci_close,
                "volume": [1.0] * len(cci_close),
            }
        )
        series = calculate_cci_series(df["high"], df["low"], df["close"], period=3)
        self.assertAlmostEqual(float(series.iloc[-1]), 100.0)


class SupportResistanceTestCase(unittest.TestCase):
    def test_levels_no_look_ahead_and_recent_dates(self) -> None:
        df = _sample_ohlcv(40)
        # Force a distinct recent high early in the window and a later higher close base.
        df.loc[df.index[25], "high"] = float(df.loc[df.index[25], "high"]) + 50.0
        summary_cut = build_support_resistance_summary(df.iloc[:30], as_of_index=29)
        # Append future bars that raise a new high after the as-of point.
        future = df.iloc[:35].copy()
        future.loc[future.index[34], "high"] = float(summary_cut["recent_high"]["price"]) + 100.0
        summary_with_future = build_support_resistance_summary(future, as_of_index=29)
        self.assertEqual(summary_cut["recent_high"], summary_with_future["recent_high"])
        self.assertEqual(summary_cut["recent_low"], summary_with_future["recent_low"])
        self.assertEqual(summary_cut["support_levels"], summary_with_future["support_levels"])
        self.assertEqual(summary_cut["resistance_levels"], summary_with_future["resistance_levels"])
        self.assertRegex(summary_cut["recent_high"]["date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_near_levels_merged_within_half_percent(self) -> None:
        n = 25
        # Flat around 100 with MA eventually near close.
        close = [100.0] * n
        df = pd.DataFrame(
            {
                "date": pd.bdate_range("2026-01-01", periods=n),
                "open": close,
                "high": [101.0] * n,
                "low": [99.0] * n,
                "close": close,
                "volume": [1000.0] * n,
            }
        )
        # Slight bump on last close so MA20 < close < high.
        df.loc[df.index[-1], "close"] = 100.2
        df.loc[df.index[-1], "high"] = 100.4
        summary = build_support_resistance_summary(df)
        # With constant prices, MA5/10/20 and recent_low may merge.
        sources = [level["source"] for level in summary["support_levels"]]
        self.assertTrue(any("ma" in source or "recent_low" in source for source in sources))
        for level in summary["support_levels"] + summary["resistance_levels"]:
            self.assertIn("price", level)
            self.assertIn("label", level)
            self.assertIn("source", level)


class FullIndicatorSetTestCase(unittest.TestCase):
    def test_default_call_emits_all_required_series_columns(self) -> None:
        df = _sample_ohlcv(60)
        out = calculate_technical_indicators(df)
        required = [
            "date", "open", "high", "low", "close", "volume",
            "ma5", "ma10", "ma20", "ma30", "ma60", "ma90", "ma120", "ma250",
            "macd_dif", "macd_dea", "macd_bar",
            "rsi6", "rsi12", "rsi24",
            "boll_upper", "boll_mid", "boll_lower", "boll_bandwidth", "boll_position",
            "kdj_k", "kdj_d", "kdj_j",
            "cci",
            "bias5", "bias10", "bias20",
            "volume_ratio", "volume_status",
        ]
        for col in required:
            self.assertIn(col, out.columns)
        # OHLCV alignment preserved
        self.assertEqual(list(out["date"]), list(normalize_ohlcv_frame(df)["date"]))
        self.assertTrue(np.allclose(out["close"].values, normalize_ohlcv_frame(df)["close"].values))


class AlertSharedSeriesCompatibilityTestCase(unittest.TestCase):
    """Prove alert edge-cross semantics still hold after shared KDJ/CCI extraction."""

    def test_kdj_cross_fixed_sample_still_triggers(self) -> None:
        params = normalize_indicator_parameters(
            "kdj_cross",
            {"period": 3, "k_period": 2, "d_period": 2, "direction": "bullish_cross"},
        )
        close = [5, 5, 5, 5, 5, 5, 5, 6]
        result = evaluate_indicator_alert(
            "kdj_cross",
            "TEST",
            params,
            pd.DataFrame(
                {
                    "date": pd.date_range("2026-01-01", periods=len(close)),
                    "high": [value + 1 for value in close],
                    "low": [value - 1 for value in close],
                    "close": close,
                }
            ),
        )
        self.assertEqual(result.status, "triggered")
        self.assertAlmostEqual(result.observed_value, 4.166666666666664)

    def test_cci_threshold_fixed_sample_still_triggers(self) -> None:
        params = normalize_indicator_parameters(
            "cci_threshold",
            {"period": 3, "threshold": 50, "direction": "above"},
        )
        close = [5, 5, 6, 5, 7]
        result = evaluate_indicator_alert(
            "cci_threshold",
            "TEST",
            params,
            pd.DataFrame(
                {
                    "date": pd.date_range("2026-01-01", periods=len(close)),
                    "high": [value + 1 for value in close],
                    "low": [value - 1 for value in close],
                    "close": close,
                }
            ),
        )
        self.assertEqual(result.status, "triggered")
        self.assertAlmostEqual(result.observed_value, 100.00000000000001)


class AnalyzerCompatibilityTestCase(unittest.TestCase):
    def test_report_rsi_matches_alert_formula(self) -> None:
        analyzer = StockTrendAnalyzer()
        close = pd.Series(REPORT_RSI_CLOSE, dtype="float64")
        report_rsi = analyzer._calculate_rsi(pd.DataFrame({"close": close}))
        for period in (analyzer.RSI_SHORT, analyzer.RSI_MID, analyzer.RSI_LONG):
            alert_rsi = calculate_alert_rsi(close, period)
            self.assertAlmostEqual(
                float(report_rsi[f"RSI_{period}"].iloc[-1]),
                float(alert_rsi.iloc[-1]),
            )

    def test_report_macd_matches_legacy_ewm_path(self) -> None:
        df = _sample_ohlcv(40)
        analyzer = StockTrendAnalyzer()
        got = analyzer._calculate_macd(df)
        close = df["close"]
        ema_fast = close.ewm(span=12, adjust=False).mean()
        ema_slow = close.ewm(span=26, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=9, adjust=False).mean()
        bar = (dif - dea) * 2
        self.assertAlmostEqual(float(got["MACD_DIF"].iloc[-1]), float(dif.iloc[-1]))
        self.assertAlmostEqual(float(got["MACD_DEA"].iloc[-1]), float(dea.iloc[-1]))
        self.assertAlmostEqual(float(got["MACD_BAR"].iloc[-1]), float(bar.iloc[-1]))


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
"""Shared technical-indicator time-series engine (technical-v1).

Stage 01: normalize OHLCV, MA, MACD, RSI, BIAS, volume ratio/status.
Stage 02: BOLL, KDJ, CCI, support/resistance summary.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import numpy as np
import pandas as pd

CALCULATION_VERSION = "technical-v1"

# Volume thresholds (single source of truth for chart + report adapters).
VOLUME_SHRINK_RATIO = 0.7
VOLUME_HEAVY_RATIO = 1.5

# MACD: first displayable bar is the 26th row (1-based) → index 25.
MACD_SLOW_PERIOD = 26
MACD_FAST_PERIOD = 12
MACD_SIGNAL_PERIOD = 9
MACD_FIRST_VALID_INDEX = MACD_SLOW_PERIOD - 1

MA_PERIODS = (5, 10, 20)
RSI_PERIODS = (6, 12, 24)
BIAS_PERIODS = (5, 10, 20)

BOLL_PERIOD = 20
BOLL_STD_MULT = 2.0
BOLL_DDOF = 0

KDJ_RSV_PERIOD = 9
KDJ_K_PERIOD = 3
KDJ_D_PERIOD = 3
KDJ_SEED = 50.0

CCI_PERIOD = 14
CCI_CONSTANT = 0.015

SUPPORT_RESISTANCE_WINDOW = 20
LEVEL_MERGE_RELATIVE = 0.005  # 0.5%

# Machine-readable volume_status codes (display copy belongs to UI / report).
VOLUME_STATUS_HEAVY_UP = "heavy_volume_up"
VOLUME_STATUS_HEAVY_DOWN = "heavy_volume_down"
VOLUME_STATUS_SHRINK_UP = "shrink_volume_up"
VOLUME_STATUS_SHRINK_DOWN = "shrink_volume_down"
VOLUME_STATUS_NORMAL = "normal"

CORE_INDICATOR_GROUPS: Dict[str, tuple[str, ...]] = {
    "ma": ("ma5", "ma10", "ma20"),
    "macd": ("macd_dif", "macd_dea", "macd_bar"),
    "rsi": ("rsi6", "rsi12", "rsi24"),
    "bias": ("bias5", "bias10", "bias20"),
    "volume": ("volume_ratio", "volume_status"),
    "boll": ("boll_upper", "boll_mid", "boll_lower", "boll_bandwidth", "boll_position"),
    "kdj": ("kdj_k", "kdj_d", "kdj_j"),
    "cci": ("cci",),
    # Summary-only group; no per-bar columns.
    "support_resistance": (),
}

DEFAULT_CORE_INDICATORS: Set[str] = set(CORE_INDICATOR_GROUPS.keys())

# Report / analyzer legacy column aliases (adapter only; not chart API fields).
REPORT_COLUMN_MAP = {
    "ma5": "MA5",
    "ma10": "MA10",
    "ma20": "MA20",
    "macd_dif": "MACD_DIF",
    "macd_dea": "MACD_DEA",
    "macd_bar": "MACD_BAR",
    "rsi6": "RSI_6",
    "rsi12": "RSI_12",
    "rsi24": "RSI_24",
}

REQUIRED_OHLC = ("open", "high", "low", "close")
OPTIONAL_NUMERIC = ("volume", "amount", "change_percent")


def normalize_ohlcv_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize OHLCV for indicator calculation (no network/DB I/O).

    - Requires open/high/low/close.
    - volume / amount / change_percent may be missing (filled as NaN).
    - Accepts ``pct_chg`` as an alias for ``change_percent``.
    - Sorts by date ascending; keeps the last row on duplicate dates.
    - Non-finite numerics become NaN; rows without date/close are dropped.
    """
    if df is None or df.empty:
        return _empty_ohlcv_frame()

    out = df.copy()
    if "change_percent" not in out.columns and "pct_chg" in out.columns:
        out["change_percent"] = out["pct_chg"]

    missing = [col for col in REQUIRED_OHLC if col not in out.columns]
    if "date" not in out.columns:
        missing.append("date")
    if missing:
        raise ValueError(f"normalize_ohlcv_frame missing required columns: {missing}")

    out["date"] = pd.to_datetime(out["date"], errors="coerce")

    for col in REQUIRED_OHLC:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    for col in OPTIONAL_NUMERIC:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
        else:
            out[col] = np.nan

    for col in list(REQUIRED_OHLC) + list(OPTIONAL_NUMERIC):
        out[col] = out[col].replace([np.inf, -np.inf], np.nan)

    out = out.dropna(subset=["date", "close"])
    out = out.sort_values("date", ascending=True)
    out = out.drop_duplicates(subset=["date"], keep="last")
    out = out.reset_index(drop=True)

    cols = ["date", *REQUIRED_OHLC, *OPTIONAL_NUMERIC]
    extra = [c for c in out.columns if c not in cols]
    return out[cols + extra]


def calculate_technical_indicators(
    df: pd.DataFrame,
    indicators: Optional[Set[str]] = None,
    *,
    normalize: bool = True,
) -> pd.DataFrame:
    """Return OHLCV plus requested indicator columns.

    Does not access network or database. Does not mutate the caller's frame.
    Default indicators are the full technical-v1 set (including empty
    ``support_resistance`` group which adds no series columns).
    """
    frame = normalize_ohlcv_frame(df) if normalize else df.copy()
    if indicators is None:
        groups = set(DEFAULT_CORE_INDICATORS)
    else:
        groups = {name.strip().lower() for name in indicators if name}
        unknown = groups - set(CORE_INDICATOR_GROUPS)
        if unknown:
            raise ValueError(f"unsupported indicator groups: {sorted(unknown)}")

    if frame.empty:
        return _with_empty_indicator_columns(frame, groups)

    need_ma = bool(groups & {"ma", "bias", "boll", "support_resistance"})
    if need_ma:
        _append_ma(frame)
    if "macd" in groups:
        _append_macd(frame, apply_display_mask=True)
    if "rsi" in groups:
        _append_rsi(frame, fill_neutral=False)
    if "bias" in groups:
        _append_bias(frame)
    if "volume" in groups:
        _append_volume(frame)
    if "boll" in groups:
        _append_boll(frame)
    if "kdj" in groups:
        _append_kdj(frame)
    if "cci" in groups:
        _append_cci(frame)

    return frame


def build_support_resistance_summary(
    df: pd.DataFrame,
    *,
    as_of_index: Optional[int] = None,
    window: int = SUPPORT_RESISTANCE_WINDOW,
    normalize: bool = True,
) -> Dict[str, Any]:
    """Build support/resistance summary at end of (or ``as_of_index``) series.

    Uses only bars at or before the as-of bar (no look-ahead).
    """
    frame = normalize_ohlcv_frame(df) if normalize else df.copy()
    if frame.empty:
        return {
            "support_levels": [],
            "resistance_levels": [],
            "recent_high": None,
            "recent_low": None,
        }

    if as_of_index is None:
        as_of_index = len(frame) - 1
    if as_of_index < 0 or as_of_index >= len(frame):
        raise IndexError(f"as_of_index out of range: {as_of_index}")

    truncated = frame.iloc[: as_of_index + 1].copy()
    if "ma5" not in truncated.columns or "ma20" not in truncated.columns:
        _append_ma(truncated)

    close = float(truncated.iloc[-1]["close"])
    win = truncated.tail(window)

    recent_high_price = float(win["high"].max())
    recent_low_price = float(win["low"].min())
    high_hits = win.index[win["high"] == recent_high_price]
    low_hits = win.index[win["low"] == recent_low_price]
    recent_high_date = _format_date(truncated.loc[high_hits[0], "date"])
    recent_low_date = _format_date(truncated.loc[low_hits[0], "date"])

    candidates: List[Dict[str, Any]] = []
    latest = truncated.iloc[-1]
    for period, source, label in (
        (5, "ma5", "MA5"),
        (10, "ma10", "MA10"),
        (20, "ma20", "MA20"),
    ):
        col = f"ma{period}"
        value = latest.get(col)
        if value is None or not np.isfinite(float(value)):
            continue
        price = float(value)
        level = {
            "price": price,
            "label": label,
            "source": source,
            "date": _format_date(latest["date"]),
        }
        if price < close:
            level["_side"] = "support"
            candidates.append(level)
        elif price > close:
            level["_side"] = "resistance"
            candidates.append(level)

    candidates.append(
        {
            "price": recent_low_price,
            "label": "recent_low",
            "source": "recent_low",
            "date": recent_low_date,
            "_side": "support",
        }
    )
    candidates.append(
        {
            "price": recent_high_price,
            "label": "recent_high",
            "source": "recent_high",
            "date": recent_high_date,
            "_side": "resistance",
        }
    )

    support = _merge_levels([c for c in candidates if c["_side"] == "support"])
    resistance = _merge_levels([c for c in candidates if c["_side"] == "resistance"])
    support.sort(key=lambda item: item["price"], reverse=True)
    resistance.sort(key=lambda item: item["price"])

    return {
        "support_levels": support,
        "resistance_levels": resistance,
        "recent_high": {"price": recent_high_price, "date": recent_high_date},
        "recent_low": {"price": recent_low_price, "date": recent_low_date},
    }


def calculate_kdj_series(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    period: int = KDJ_RSV_PERIOD,
    k_period: int = KDJ_K_PERIOD,
    d_period: int = KDJ_D_PERIOD,
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """KDJ with RSV period and K/D smooth periods; K/D seed 50; no 0–100 clip."""
    high = pd.to_numeric(high, errors="coerce")
    low = pd.to_numeric(low, errors="coerce")
    close = pd.to_numeric(close, errors="coerce")

    lowest_low = low.rolling(window=period, min_periods=period).min()
    highest_high = high.rolling(window=period, min_periods=period).max()
    denom = highest_high - lowest_low

    rsv = pd.Series(np.nan, index=close.index, dtype="float64")
    equal = denom.notna() & (denom == 0)
    nonzero = denom.notna() & (denom != 0)
    rsv.loc[nonzero] = (close.loc[nonzero] - lowest_low.loc[nonzero]) / denom.loc[nonzero] * 100.0
    rsv.loc[equal] = KDJ_SEED

    alpha_k = 1.0 / float(k_period)
    alpha_d = 1.0 / float(d_period)
    k_values = np.full(len(close), np.nan, dtype="float64")
    d_values = np.full(len(close), np.nan, dtype="float64")
    j_values = np.full(len(close), np.nan, dtype="float64")

    prev_k = KDJ_SEED
    prev_d = KDJ_SEED
    for i in range(len(close)):
        rsv_i = rsv.iloc[i]
        if not np.isfinite(rsv_i):
            continue
        k_i = (1.0 - alpha_k) * prev_k + alpha_k * float(rsv_i)
        d_i = (1.0 - alpha_d) * prev_d + alpha_d * k_i
        k_values[i] = k_i
        d_values[i] = d_i
        j_values[i] = 3.0 * k_i - 2.0 * d_i
        prev_k = k_i
        prev_d = d_i

    return (
        pd.Series(k_values, index=close.index, dtype="float64"),
        pd.Series(d_values, index=close.index, dtype="float64"),
        pd.Series(j_values, index=close.index, dtype="float64"),
    )


def calculate_cci_series(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    period: int = CCI_PERIOD,
) -> pd.Series:
    """CCI series; MD==0 or incomplete window → NaN (never inf)."""
    high = pd.to_numeric(high, errors="coerce")
    low = pd.to_numeric(low, errors="coerce")
    close = pd.to_numeric(close, errors="coerce")
    typical_price = (high + low + close) / 3.0
    tp_ma = typical_price.rolling(window=period, min_periods=period).mean()
    mean_deviation = typical_price.rolling(window=period, min_periods=period).apply(
        lambda values: float(np.mean(np.abs(values - values.mean()))),
        raw=True,
    )
    cci = (typical_price - tp_ma) / (CCI_CONSTANT * mean_deviation)
    cci = cci.where(mean_deviation.notna() & (mean_deviation != 0), np.nan)
    return cci.replace([np.inf, -np.inf], np.nan)


def wilder_rsi(
    close: pd.Series,
    period: int,
    *,
    fill_neutral: bool = False,
) -> pd.Series:
    """Wilder / SMMA RSI for a close series.

    Chart mode (``fill_neutral=False``): insufficient / undefined → NaN (no 50 fill).
    Report/alert compatibility (``fill_neutral=True``): match historical
    ``fillna(50)`` behavior used by StockTrendAnalyzer / alert_indicators.
    """
    close = pd.to_numeric(close, errors="coerce")
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0).astype("float64")
    loss = (-delta.where(delta < 0, 0.0)).astype("float64")

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    if fill_neutral:
        rs = avg_gain / avg_loss
        rsi = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)
        return rsi

    rsi = pd.Series(np.nan, index=close.index, dtype="float64")
    both_zero = (avg_gain == 0) & (avg_loss == 0)
    gain_only = (avg_loss == 0) & (avg_gain > 0)
    valid = avg_loss > 0
    rs = avg_gain[valid] / avg_loss[valid]
    rsi.loc[valid] = 100.0 - (100.0 / (1.0 + rs))
    rsi.loc[gain_only] = 100.0
    rsi.loc[both_zero] = np.nan
    if len(rsi) > 0:
        rsi.iloc[: min(period, len(rsi))] = np.nan
    return rsi


def map_indicators_to_report_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Copy snake_case indicator columns onto report/analyzer legacy names."""
    out = frame.copy()
    for src, dest in REPORT_COLUMN_MAP.items():
        if src in out.columns:
            out[dest] = out[src]
    return out


def compute_report_indicator_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Compute MA/MACD/RSI columns for StockTrendAnalyzer (report adapters)."""
    out = df.copy()
    close = pd.to_numeric(out["close"], errors="coerce")

    for period in MA_PERIODS:
        out[f"MA{period}"] = close.rolling(window=period, min_periods=period).mean()

    dif, dea, bar = _compute_macd_raw(close)
    out["MACD_DIF"] = dif
    out["MACD_DEA"] = dea
    out["MACD_BAR"] = bar

    for period in RSI_PERIODS:
        out[f"RSI_{period}"] = wilder_rsi(close, period, fill_neutral=True)

    return out


def _append_ma(frame: pd.DataFrame) -> None:
    close = frame["close"]
    for period in MA_PERIODS:
        frame[f"ma{period}"] = close.rolling(window=period, min_periods=period).mean()


def _compute_macd_raw(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = close.ewm(span=MACD_FAST_PERIOD, adjust=False).mean()
    ema_slow = close.ewm(span=MACD_SLOW_PERIOD, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=MACD_SIGNAL_PERIOD, adjust=False).mean()
    bar = (dif - dea) * 2.0
    return dif, dea, bar


def _append_macd(frame: pd.DataFrame, *, apply_display_mask: bool = True) -> None:
    dif, dea, bar = _compute_macd_raw(frame["close"])

    if apply_display_mask:
        dif = dif.copy()
        dea = dea.copy()
        bar = bar.copy()
        if len(frame) > MACD_FIRST_VALID_INDEX:
            dif.iloc[:MACD_FIRST_VALID_INDEX] = np.nan
            dea.iloc[:MACD_FIRST_VALID_INDEX] = np.nan
            bar.iloc[:MACD_FIRST_VALID_INDEX] = np.nan
        elif len(frame) > 0:
            dif[:] = np.nan
            dea[:] = np.nan
            bar[:] = np.nan

    frame["macd_dif"] = dif
    frame["macd_dea"] = dea
    frame["macd_bar"] = bar


def _append_rsi(frame: pd.DataFrame, *, fill_neutral: bool) -> None:
    close = frame["close"]
    for period in RSI_PERIODS:
        frame[f"rsi{period}"] = wilder_rsi(close, period, fill_neutral=fill_neutral)


def _append_bias(frame: pd.DataFrame) -> None:
    close = frame["close"]
    for period in BIAS_PERIODS:
        ma_col = f"ma{period}"
        if ma_col not in frame.columns:
            frame[ma_col] = close.rolling(window=period, min_periods=period).mean()
        ma = frame[ma_col]
        bias = (close - ma) / ma * 100.0
        bias = bias.where(ma.notna() & (ma != 0), np.nan)
        frame[f"bias{period}"] = bias


def _append_volume(frame: pd.DataFrame) -> None:
    volume = frame["volume"]
    prev_avg = volume.shift(1).rolling(window=5, min_periods=5).mean()
    ratio = volume / prev_avg
    ratio = ratio.where(prev_avg.notna() & (prev_avg != 0), np.nan)
    frame["volume_ratio"] = ratio

    prev_close = frame["close"].shift(1)
    up = frame["close"] > prev_close
    statuses: list[Optional[str]] = []
    for idx in range(len(frame)):
        r = ratio.iloc[idx]
        pc = prev_close.iloc[idx]
        if not np.isfinite(r) or not np.isfinite(pc):
            statuses.append(None)
            continue
        is_up = bool(up.iloc[idx])
        if r >= VOLUME_HEAVY_RATIO:
            statuses.append(VOLUME_STATUS_HEAVY_UP if is_up else VOLUME_STATUS_HEAVY_DOWN)
        elif r <= VOLUME_SHRINK_RATIO:
            statuses.append(VOLUME_STATUS_SHRINK_UP if is_up else VOLUME_STATUS_SHRINK_DOWN)
        else:
            statuses.append(VOLUME_STATUS_NORMAL)
    frame["volume_status"] = statuses


def _append_boll(frame: pd.DataFrame) -> None:
    if "ma20" not in frame.columns:
        frame["ma20"] = frame["close"].rolling(window=BOLL_PERIOD, min_periods=BOLL_PERIOD).mean()
    mid = frame["ma20"]
    std = frame["close"].rolling(window=BOLL_PERIOD, min_periods=BOLL_PERIOD).std(ddof=BOLL_DDOF)
    upper = mid + BOLL_STD_MULT * std
    lower = mid - BOLL_STD_MULT * std
    bandwidth = ((upper - lower) / mid * 100.0).where(mid.notna() & (mid != 0), np.nan)
    width = upper - lower
    position = ((frame["close"] - lower) / width * 100.0).where(width.notna() & (width != 0), np.nan)

    frame["boll_mid"] = mid
    frame["boll_upper"] = upper
    frame["boll_lower"] = lower
    frame["boll_bandwidth"] = bandwidth
    frame["boll_position"] = position


def _append_kdj(frame: pd.DataFrame) -> None:
    k_value, d_value, j_value = calculate_kdj_series(
        frame["high"],
        frame["low"],
        frame["close"],
        period=KDJ_RSV_PERIOD,
        k_period=KDJ_K_PERIOD,
        d_period=KDJ_D_PERIOD,
    )
    frame["kdj_k"] = k_value
    frame["kdj_d"] = d_value
    frame["kdj_j"] = j_value


def _append_cci(frame: pd.DataFrame) -> None:
    frame["cci"] = calculate_cci_series(
        frame["high"],
        frame["low"],
        frame["close"],
        period=CCI_PERIOD,
    )


def _merge_levels(levels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not levels:
        return []
    ordered = sorted(levels, key=lambda item: item["price"])
    merged: List[Dict[str, Any]] = []
    for level in ordered:
        if not merged:
            merged.append(_public_level(level))
            continue
        prev = merged[-1]
        mid = (prev["price"] + level["price"]) / 2.0
        if mid == 0:
            relative = abs(prev["price"] - level["price"])
        else:
            relative = abs(prev["price"] - level["price"]) / abs(mid)
        if relative <= LEVEL_MERGE_RELATIVE:
            sources = sorted({prev["source"], level["source"]})
            labels = sorted({prev["label"], level["label"]})
            prev["price"] = (prev["price"] + level["price"]) / 2.0
            prev["source"] = "+".join(sources)
            prev["label"] = "+".join(labels)
            if level.get("date") and (not prev.get("date") or level["date"] < prev["date"]):
                prev["date"] = level["date"]
        else:
            merged.append(_public_level(level))
    return merged


def _public_level(level: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "price": float(level["price"]),
        "label": str(level["label"]),
        "source": str(level["source"]),
        "date": level.get("date"),
    }


def _format_date(value: Any) -> str:
    ts = pd.Timestamp(value)
    return ts.strftime("%Y-%m-%d")


def _empty_ohlcv_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["date", *REQUIRED_OHLC, *OPTIONAL_NUMERIC])


def _with_empty_indicator_columns(frame: pd.DataFrame, groups: Iterable[str]) -> pd.DataFrame:
    out = frame.copy()
    for group in groups:
        for col in CORE_INDICATOR_GROUPS.get(group, ()):
            out[col] = pd.Series(dtype="float64")
    return out


def indicator_columns_for(groups: Iterable[str]) -> tuple[str, ...]:
    """Return snake_case column names for the given indicator groups."""
    cols: list[str] = []
    for group in groups:
        cols.extend(CORE_INDICATOR_GROUPS.get(group, ()))
    return tuple(cols)

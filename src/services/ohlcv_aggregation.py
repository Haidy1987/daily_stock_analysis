# -*- coding: utf-8 -*-
"""Pure DataFrame OHLCV aggregation for weekly / monthly bars (technical-v1).

Used by technical-chart before indicator recalculation. Does not touch network,
DB, or the legacy ``/history`` endpoint.
"""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

AggregatePeriod = Literal["weekly", "monthly"]

_OHLCV_COLS = ("date", "open", "high", "low", "close", "volume", "amount", "change_percent")


def _empty_aggregated_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(_OHLCV_COLS))


def aggregate_ohlcv(df: pd.DataFrame, period: AggregatePeriod) -> pd.DataFrame:
    """Aggregate daily OHLCV into weekly or monthly bars.

    Rules (technical-v1 contract §3):

    - Group weekly by natural Mon–Sun weeks; monthly by calendar year-month.
    - Skip empty groups (no fabricated holiday bars).
    - ``date`` = last trading day in the group.
    - ``open`` / ``close`` = first / last bar; ``high`` / ``low`` = max / min.
    - ``volume`` / ``amount`` = sum with ``min_count=1`` (all-missing → null).
    - ``change_percent`` = % change vs previous aggregated close (first = null).
    - Output sorted ascending by ``date``.
    """
    if period not in ("weekly", "monthly"):
        raise ValueError(f"unsupported aggregation period: {period}")
    if df is None or getattr(df, "empty", True):
        return _empty_aggregated_frame()

    frame = df.copy()
    if "date" not in frame.columns:
        raise ValueError("aggregate_ohlcv requires a date column")

    for col in ("open", "high", "low", "close"):
        if col not in frame.columns:
            raise ValueError(f"aggregate_ohlcv requires column: {col}")

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    for col in ("open", "high", "low", "close", "volume", "amount"):
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
        elif col in ("volume", "amount"):
            frame[col] = np.nan

    frame = frame.dropna(subset=["date", "open", "high", "low", "close"])
    if frame.empty:
        return _empty_aggregated_frame()

    frame = frame.sort_values("date", ascending=True).reset_index(drop=True)

    if period == "weekly":
        # Weeks ending Sunday == natural Mon–Sun buckets.
        group_key = frame["date"].dt.to_period("W-SUN")
    else:
        group_key = frame["date"].dt.to_period("M")

    rows = []
    for _, group in frame.groupby(group_key, sort=True):
        if group.empty:
            continue
        volume_sum = group["volume"].sum(min_count=1)
        amount_sum = group["amount"].sum(min_count=1)
        rows.append(
            {
                "date": group["date"].iloc[-1],
                "open": float(group["open"].iloc[0]),
                "high": float(group["high"].max()),
                "low": float(group["low"].min()),
                "close": float(group["close"].iloc[-1]),
                "volume": float(volume_sum) if pd.notna(volume_sum) else np.nan,
                "amount": float(amount_sum) if pd.notna(amount_sum) else np.nan,
            }
        )

    if not rows:
        return _empty_aggregated_frame()

    out = pd.DataFrame(rows)
    out = out.sort_values("date", ascending=True).reset_index(drop=True)
    prev_close = out["close"].shift(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        change = (out["close"] - prev_close) / prev_close * 100.0
    out["change_percent"] = change.replace([np.inf, -np.inf], np.nan)
    return out[list(_OHLCV_COLS)]


def estimate_daily_bars_for_period(
    period: str,
    display_bars: int,
    *,
    warmup_bars: int,
    max_daily_bars: int,
) -> tuple[int, bool]:
    """Estimate how many daily bars to fetch for ``display_bars`` + warmup.

    Returns ``(daily_days, capped)`` where ``capped`` is True when the estimate
    hit ``max_daily_bars`` (caller should emit a warning / partial if short).
    """
    needed = int(display_bars) + int(warmup_bars)
    if period == "daily":
        return needed, False
    if period == "weekly":
        # ~5 sessions/week + small calendar buffer for holidays.
        estimate = needed * 5 + 10
    elif period == "monthly":
        # ~22 sessions/month + buffer.
        estimate = needed * 22 + 20
    else:
        raise ValueError(f"unsupported period for fetch estimate: {period}")

    if estimate > max_daily_bars:
        return max_daily_bars, True
    return estimate, False

# -*- coding: utf-8 -*-
"""Technical chart service: fetch, warmup, indicators, display trim, summary."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import numpy as np
import pandas as pd

from src.services.ohlcv_aggregation import (
    aggregate_ohlcv,
    estimate_daily_bars_for_period,
)
from src.services.technical_indicators import (
    CALCULATION_VERSION,
    CORE_INDICATOR_GROUPS,
    DEFAULT_CORE_INDICATORS,
    MA_PERIODS,
    build_support_resistance_summary,
    calculate_technical_indicators,
    normalize_ohlcv_frame,
)

logger = logging.getLogger(__name__)

# Baseline extra bars beyond display_days for EMA/RSI/BOLL warmup (contract ≥ 60).
# Warmup counts in the *target* period (daily / weekly / monthly bars).
WARMUP_BARS = 60
MA_WARMUP_BARS = max(MA_PERIODS)
MIN_DAYS = 60
MAX_DAYS = 250
DEFAULT_DAYS = 120
SUPPORTED_PERIODS = frozenset({"daily", "weekly", "monthly"})
# Soft cap on daily prefetch for weekly/monthly (partial + warning when hit).
MAX_DAILY_FETCH_BARS = 7000

OHLCV_ITEM_FIELDS = (
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "change_percent",
)


class TechnicalChartValidationError(ValueError):
    """Invalid period / indicators / days for technical chart."""

    def __init__(self, error: str, message: str) -> None:
        super().__init__(message)
        self.error = error
        self.message = message


class TechnicalChartSourceUnavailableError(RuntimeError):
    """All upstream market data sources failed."""

    def __init__(self, message: str = "market data sources unavailable") -> None:
        super().__init__(message)
        self.error = "source_unavailable"
        self.message = message


def parse_indicator_groups(indicators: Optional[str]) -> Set[str]:
    """Parse comma-separated indicator groups; default = full technical-v1 set."""
    if indicators is None or not str(indicators).strip():
        return set(DEFAULT_CORE_INDICATORS)

    groups = {part.strip().lower() for part in str(indicators).split(",") if part.strip()}
    if not groups:
        return set(DEFAULT_CORE_INDICATORS)

    unknown = groups - set(CORE_INDICATOR_GROUPS)
    if unknown:
        raise TechnicalChartValidationError(
            "invalid_indicators",
            f"unknown indicators: {', '.join(sorted(unknown))}",
        )
    return groups


def _json_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(number):
        return None
    return number


def _format_date(value: Any) -> str:
    ts = pd.Timestamp(value)
    return ts.strftime("%Y-%m-%d")


class TechnicalChartService:
    """Assemble technical-chart payloads without mutating history API behavior."""

    def get_technical_chart(
        self,
        stock_code: str,
        *,
        period: str = "daily",
        days: int = DEFAULT_DAYS,
        indicators: Optional[str] = None,
    ) -> Dict[str, Any]:
        if period not in SUPPORTED_PERIODS:
            raise TechnicalChartValidationError(
                "unsupported_period",
                f"暂不支持 '{period}' 周期，目前仅支持 daily/weekly/monthly。",
            )
        if days < MIN_DAYS or days > MAX_DAYS:
            raise TechnicalChartValidationError(
                "invalid_days",
                f"days must be between {MIN_DAYS} and {MAX_DAYS}",
            )

        groups = parse_indicator_groups(indicators)
        warmup_bars = max(WARMUP_BARS, MA_WARMUP_BARS if "ma" in groups else 0)
        calculation_bars = days + warmup_bars
        daily_fetch_days, fetch_capped = estimate_daily_bars_for_period(
            period,
            days,
            warmup_bars=warmup_bars,
            max_daily_bars=MAX_DAILY_FETCH_BARS,
        )

        try:
            from data_provider.base import DataFetchError, DataFetcherManager
        except ImportError as exc:
            logger.error("DataFetcherManager unavailable for technical-chart")
            raise TechnicalChartSourceUnavailableError(
                "market data provider is not available"
            ) from exc

        manager = DataFetcherManager()
        try:
            # Always fetch daily bars; weekly/monthly aggregate in-process.
            df, source = manager.get_daily_data(stock_code, days=daily_fetch_days)
        except DataFetchError as exc:
            logger.warning(
                "technical-chart upstream unavailable for %s: %s",
                stock_code,
                type(exc).__name__,
            )
            raise TechnicalChartSourceUnavailableError(
                "unable to fetch market history from available data sources"
            ) from exc
        except Exception as exc:
            logger.error(
                "technical-chart fetch failed for %s: %s",
                stock_code,
                type(exc).__name__,
                exc_info=True,
            )
            raise TechnicalChartSourceUnavailableError(
                "unable to fetch market history from available data sources"
            ) from exc

        stock_name: Optional[str] = None
        try:
            stock_name = manager.get_stock_name(stock_code)
        except Exception:
            stock_name = None

        updated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

        if df is None or getattr(df, "empty", True):
            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "period": period,
                "range_days": days,
                "calculation_version": CALCULATION_VERSION,
                "data_status": "empty",
                "data_source": source if isinstance(source, str) else None,
                "updated_at": updated_at,
                "items": [],
                "summary": self._empty_summary(),
                "warnings": ["no_history"],
            }

        # Ensure pct_chg / amount available for normalize.
        frame = df.copy()
        if "change_percent" not in frame.columns and "pct_chg" in frame.columns:
            frame["change_percent"] = frame["pct_chg"]

        try:
            normalized = normalize_ohlcv_frame(frame)
        except ValueError:
            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "period": period,
                "range_days": days,
                "calculation_version": CALCULATION_VERSION,
                "data_status": "empty",
                "data_source": source if isinstance(source, str) else None,
                "updated_at": updated_at,
                "items": [],
                "summary": self._empty_summary(),
                "warnings": ["invalid_ohlcv"],
            }

        if normalized.empty:
            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "period": period,
                "range_days": days,
                "calculation_version": CALCULATION_VERSION,
                "data_status": "empty",
                "data_source": source if isinstance(source, str) else None,
                "updated_at": updated_at,
                "items": [],
                "summary": self._empty_summary(),
                "warnings": ["no_history"],
            }

        warnings: List[str] = []
        if fetch_capped:
            warnings.append("daily_history_fetch_capped")

        # Aggregate first when needed; indicators always run on target-period bars.
        working = normalized
        if period in ("weekly", "monthly"):
            working = aggregate_ohlcv(normalized, period)  # type: ignore[arg-type]
            if working.empty:
                return {
                    "stock_code": stock_code,
                    "stock_name": stock_name,
                    "period": period,
                    "range_days": days,
                    "calculation_version": CALCULATION_VERSION,
                    "data_status": "empty",
                    "data_source": source if isinstance(source, str) else None,
                    "updated_at": updated_at,
                    "items": [],
                    "summary": self._empty_summary(),
                    "warnings": warnings + ["no_aggregated_bars"],
                }

        series_groups = {g for g in groups if g != "support_resistance"}
        if not series_groups:
            # Only summary requested — still need MA for levels.
            computed = calculate_technical_indicators(
                working,
                indicators={"ma"},
                normalize=False,
            )
        else:
            # Ensure MA when bias/boll/support need it.
            need = set(series_groups)
            if need & {"bias", "boll"} or "support_resistance" in groups:
                need.add("ma")
            computed = calculate_technical_indicators(
                working,
                indicators=need,
                normalize=False,
            )

        display = computed.tail(days).reset_index(drop=True)
        if len(computed) < calculation_bars:
            warnings.append("history_shorter_than_requested_warmup")
        if len(display) < days:
            warnings.append("history_shorter_than_display_days")

        items = [
            self._row_to_item(row, groups)
            for _, row in display.iterrows()
        ]

        summary = self._build_summary(display, groups)
        data_status = self._resolve_status(display, groups, warnings)

        return {
            "stock_code": stock_code,
            "stock_name": stock_name,
            "period": period,
            "range_days": days,
            "calculation_version": CALCULATION_VERSION,
            "data_status": data_status,
            "data_source": source if isinstance(source, str) else None,
            "updated_at": updated_at,
            "items": items,
            "summary": summary,
            "warnings": warnings,
        }

    def _empty_summary(self) -> Dict[str, Any]:
        return {
            "latest_close": None,
            "latest_change_percent": None,
            "latest_volume_status": None,
            "volume_ratio": None,
            "support_levels": [],
            "resistance_levels": [],
            "recent_high": None,
            "recent_low": None,
        }

    def _row_to_item(self, row: pd.Series, groups: Set[str]) -> Dict[str, Any]:
        item: Dict[str, Any] = {
            "date": _format_date(row["date"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": _json_number(row.get("volume")),
            "amount": _json_number(row.get("amount")),
            "change_percent": _json_number(row.get("change_percent")),
        }
        for group in groups:
            for col in CORE_INDICATOR_GROUPS.get(group, ()):
                value = row.get(col)
                if col == "volume_status":
                    item[col] = None if value is None or (isinstance(value, float) and not np.isfinite(value)) else value
                else:
                    item[col] = _json_number(value)
        return item

    def _build_summary(self, display: pd.DataFrame, groups: Set[str]) -> Dict[str, Any]:
        summary = self._empty_summary()
        if display.empty:
            return summary

        latest = display.iloc[-1]
        summary["latest_close"] = _json_number(latest.get("close"))
        summary["latest_change_percent"] = _json_number(latest.get("change_percent"))
        if "volume" in groups:
            status = latest.get("volume_status")
            summary["latest_volume_status"] = None if status is None else str(status)
            summary["volume_ratio"] = _json_number(latest.get("volume_ratio"))

        if "support_resistance" in groups:
            levels = build_support_resistance_summary(display, normalize=False)
            summary["support_levels"] = levels.get("support_levels") or []
            summary["resistance_levels"] = levels.get("resistance_levels") or []
            summary["recent_high"] = levels.get("recent_high")
            summary["recent_low"] = levels.get("recent_low")

        return summary

    def _resolve_status(
        self,
        display: pd.DataFrame,
        groups: Set[str],
        warnings: List[str],
    ) -> str:
        if display.empty:
            return "empty"

        indicator_cols: List[str] = []
        for group in groups:
            indicator_cols.extend(CORE_INDICATOR_GROUPS.get(group, ()))
        if not indicator_cols:
            return "available"

        latest = display.iloc[-1]
        missing = 0
        checked = 0
        for col in indicator_cols:
            if col not in display.columns:
                continue
            checked += 1
            value = latest.get(col)
            if col == "volume_status":
                if value is None:
                    missing += 1
            elif _json_number(value) is None:
                missing += 1

        if checked == 0:
            return "available"
        if missing == 0 and not warnings:
            return "available"
        if missing == checked:
            warnings.append("indicators_unavailable_on_latest_bar")
            return "partial"
        if missing > 0 or warnings:
            if missing > 0 and "partial_indicators" not in warnings:
                warnings.append("partial_indicators")
            return "partial"
        return "available"

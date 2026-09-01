# -*- coding: utf-8 -*-
"""Typed row contracts for A-share universe sync (Phase 0)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Dict, Optional


def normalize_a_share_code(raw_code: str) -> str:
    """Normalize an A-share code to a 6-digit string."""
    candidate = str(raw_code or "").strip().upper()
    if not candidate:
        return ""
    if candidate.startswith(("SH", "SZ", "BJ")) and len(candidate) > 2:
        candidate = candidate[2:]
    if candidate.isdigit():
        return candidate.zfill(6)
    return candidate


@dataclass
class AShareUniverseRow:
    code: str
    name: str
    exchange: str
    board: Optional[str] = None
    industry: Optional[str] = None
    list_date: Optional[date] = None
    active: bool = True
    source: Optional[str] = None

    def normalized_code(self) -> str:
        return normalize_a_share_code(self.code)

    def to_record_dict(self) -> Dict[str, Any]:
        return {
            "code": self.normalized_code(),
            "name": (self.name or "").strip(),
            "exchange": (self.exchange or "").strip().upper(),
            "board": (self.board or None),
            "industry": (self.industry or None),
            "list_date": self.list_date,
            "active": bool(self.active),
            "source": (self.source or None),
        }


@dataclass
class AShareSnapshotRow:
    code: str
    data_date: date
    price: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    pre_close: Optional[float] = None
    pct_chg: Optional[float] = None
    amplitude: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    turnover_rate: Optional[float] = None
    volume_ratio: Optional[float] = None
    pe_ttm: Optional[float] = None
    pe_dynamic: Optional[float] = None
    pb: Optional[float] = None
    ps: Optional[float] = None
    total_mv: Optional[float] = None
    circ_mv: Optional[float] = None
    total_share: Optional[float] = None
    float_share: Optional[float] = None
    eps: Optional[float] = None
    bps: Optional[float] = None
    roe: Optional[float] = None
    revenue: Optional[float] = None
    revenue_yoy: Optional[float] = None
    net_profit: Optional[float] = None
    net_profit_yoy: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    ytd_pct_chg: Optional[float] = None
    source: Optional[str] = None
    fetched_at: Optional[datetime] = None

    def normalized_code(self) -> str:
        return normalize_a_share_code(self.code)

    def to_record_dict(self) -> Dict[str, Any]:
        return {
            "code": self.normalized_code(),
            "data_date": self.data_date,
            "price": self.price,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "pre_close": self.pre_close,
            "pct_chg": self.pct_chg,
            "amplitude": self.amplitude,
            "volume": self.volume,
            "amount": self.amount,
            "turnover_rate": self.turnover_rate,
            "volume_ratio": self.volume_ratio,
            "pe_ttm": self.pe_ttm,
            "pe_dynamic": self.pe_dynamic,
            "pb": self.pb,
            "ps": self.ps,
            "total_mv": self.total_mv,
            "circ_mv": self.circ_mv,
            "total_share": self.total_share,
            "float_share": self.float_share,
            "eps": self.eps,
            "bps": self.bps,
            "roe": self.roe,
            "revenue": self.revenue,
            "revenue_yoy": self.revenue_yoy,
            "net_profit": self.net_profit,
            "net_profit_yoy": self.net_profit_yoy,
            "high_52w": self.high_52w,
            "low_52w": self.low_52w,
            "ytd_pct_chg": self.ytd_pct_chg,
            "source": self.source,
            "fetched_at": self.fetched_at,
        }


@dataclass
class AShareUpsertResult:
    total: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0

    def merge(self, other: "AShareUpsertResult") -> "AShareUpsertResult":
        return AShareUpsertResult(
            total=self.total + other.total,
            inserted=self.inserted + other.inserted,
            updated=self.updated + other.updated,
            skipped=self.skipped + other.skipped,
        )

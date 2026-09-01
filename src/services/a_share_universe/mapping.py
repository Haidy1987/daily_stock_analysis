# -*- coding: utf-8 -*-
"""Deterministic A-share exchange/board mapping from stock codes."""

from __future__ import annotations

from src.schemas.a_share_universe import normalize_a_share_code


def is_a_share_universe_code(code: str) -> bool:
    """Return True for 6-digit CN A-share codes included in universe sync."""
    normalized = normalize_a_share_code(code)
    if len(normalized) != 6 or not normalized.isdigit():
        return False
    # Exclude legacy B-shares from the A-share universe scope.
    if normalized.startswith(("900", "200")):
        return False
    return normalized.startswith(
        (
            "0",
            "2",
            "3",
            "6",
            "8",
            "43",
            "81",
            "82",
            "83",
            "87",
            "88",
            "920",
        )
    )


def infer_exchange(code: str) -> str:
    normalized = normalize_a_share_code(code)
    if normalized.startswith(("920", "43", "83", "87", "88", "81", "82")) or normalized.startswith("8"):
        return "BJ"
    if normalized.startswith(("6", "688", "900")):
        return "SH"
    if normalized.startswith(("0", "2", "3")):
        return "SZ"
    return "SH"


def infer_board(code: str) -> str:
    normalized = normalize_a_share_code(code)
    if normalized.startswith("688"):
        return "科创板"
    if normalized.startswith("300"):
        return "创业板"
    if normalized.startswith(("920", "43", "83", "87", "88", "81", "82")) or normalized.startswith("8"):
        return "北交所"
    if normalized.startswith("60"):
        return "沪市主板"
    if normalized.startswith("002"):
        return "中小板"
    if normalized.startswith("00"):
        return "深市主板"
    return "A股"


def map_tushare_exchange(raw_exchange: str) -> str:
    mapping = {
        "SSE": "SH",
        "SZSE": "SZ",
        "BSE": "BJ",
    }
    return mapping.get(str(raw_exchange or "").strip().upper(), infer_exchange(""))

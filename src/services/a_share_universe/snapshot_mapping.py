# -*- coding: utf-8
"""Helpers for mapping EastMoney/AkShare payloads to snapshot rows."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from data_provider.realtime_types import safe_float
from src.schemas.a_share_universe import AShareSnapshotRow, normalize_a_share_code
from src.services.a_share_universe.mapping import is_a_share_universe_code
from src.services.a_share_universe.providers import EastMoneyUniverseProvider


def get_cn_market_date() -> date:
    return datetime.now(ZoneInfo("Asia/Shanghai")).date()


def snapshot_row_from_spot_record(record: Dict[str, Any], *, data_date: date, source: str) -> Optional[AShareSnapshotRow]:
    code = normalize_a_share_code(str(record.get("代码") or record.get("code") or ""))
    if not code or not is_a_share_universe_code(code):
        return None
    return AShareSnapshotRow(
        code=code,
        data_date=data_date,
        price=safe_float(record.get("最新价")),
        open=safe_float(record.get("今开")),
        high=safe_float(record.get("最高")),
        low=safe_float(record.get("最低")),
        pre_close=safe_float(record.get("昨收")),
        pct_chg=safe_float(record.get("涨跌幅")),
        amplitude=safe_float(record.get("振幅")),
        volume=safe_float(record.get("成交量")),
        amount=safe_float(record.get("成交额")),
        turnover_rate=safe_float(record.get("换手率")),
        volume_ratio=safe_float(record.get("量比")),
        pe_dynamic=safe_float(record.get("市盈率-动态")),
        pb=safe_float(record.get("市净率")),
        ps=safe_float(record.get("市销率")),
        pe_ttm=safe_float(record.get("市盈率")) or safe_float(record.get("市盈率(TTM)")),
        total_mv=safe_float(record.get("总市值")),
        circ_mv=safe_float(record.get("流通市值")),
        high_52w=safe_float(record.get("52周最高")),
        low_52w=safe_float(record.get("52周最低")),
        ytd_pct_chg=safe_float(record.get("年初至今涨跌幅")),
        source=source,
    )


def merge_financial_fields(row: AShareSnapshotRow, financial: Dict[str, Any]) -> AShareSnapshotRow:
    if not financial:
        return row
    return AShareSnapshotRow(
        code=row.code,
        data_date=row.data_date,
        price=row.price,
        open=row.open,
        high=row.high,
        low=row.low,
        pre_close=row.pre_close,
        pct_chg=row.pct_chg,
        amplitude=row.amplitude,
        volume=row.volume,
        amount=row.amount,
        turnover_rate=row.turnover_rate,
        volume_ratio=row.volume_ratio,
        pe_ttm=row.pe_ttm or safe_float(financial.get("pe_ttm")),
        pe_dynamic=row.pe_dynamic,
        pb=row.pb,
        ps=row.ps,
        total_mv=row.total_mv,
        circ_mv=row.circ_mv,
        total_share=row.total_share or safe_float(financial.get("total_share")),
        float_share=row.float_share or safe_float(financial.get("float_share")),
        eps=row.eps or safe_float(financial.get("eps")),
        bps=row.bps or safe_float(financial.get("bps")),
        roe=row.roe or safe_float(financial.get("roe")),
        revenue=row.revenue or safe_float(financial.get("revenue")),
        revenue_yoy=row.revenue_yoy or safe_float(financial.get("revenue_yoy")),
        net_profit=row.net_profit or safe_float(financial.get("net_profit")),
        net_profit_yoy=row.net_profit_yoy or safe_float(financial.get("net_profit_yoy")),
        high_52w=row.high_52w,
        low_52w=row.low_52w,
        ytd_pct_chg=row.ytd_pct_chg,
        source=row.source,
        fetched_at=row.fetched_at,
    )


def financial_map_from_yjbb_dataframe(df: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    if df is None or df.empty:
        return {}

    code_col = EastMoneyUniverseProvider._pick_column(df.columns, ("股票代码", "代码", "symbol"))
    if not code_col:
        return {}

    mapping: Dict[str, Dict[str, Any]] = {}
    for record in df.to_dict(orient="records"):
        code = normalize_a_share_code(str(record.get(code_col) or ""))
        if not code:
            continue
        mapping[code] = {
            "eps": safe_float(_pick(record, ("每股收益", "基本每股收益"))),
            "bps": safe_float(_pick(record, ("每股净资产",))),
            "roe": safe_float(_pick(record, ("净资产收益率",))),
            "revenue": safe_float(_pick(record, ("营业总收入", "营业收入"))),
            "revenue_yoy": safe_float(_pick(record, ("营业总收入同比增长", "营业收入同比增长", "营收同比"))),
            "net_profit": safe_float(_pick(record, ("净利润", "归母净利润"))),
            "net_profit_yoy": safe_float(_pick(record, ("净利润同比增长", "归母净利润同比增长"))),
            "total_share": safe_float(_pick(record, ("总股本",))),
            "float_share": safe_float(_pick(record, ("流通股本",))),
            "pe_ttm": safe_float(_pick(record, ("市盈率", "市盈率(TTM)"))),
        }
    return mapping


def _pick(record: Dict[str, Any], candidates: tuple[str, ...]) -> Any:
    for key in candidates:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def candidate_yjbb_report_dates(reference: Optional[date] = None) -> list[str]:
    ref = reference or get_cn_market_date()
    candidates: list[str] = []
    for year in range(ref.year, ref.year - 2, -1):
        for suffix in ("1231", "0930", "0630", "0331"):
            candidates.append(f"{year}{suffix}")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return deduped[:8]

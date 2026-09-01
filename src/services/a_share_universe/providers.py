# -*- coding: utf-8 -*-
"""Universe data providers for A-share master sync."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Iterable, List, Optional, Sequence

import pandas as pd

from src.schemas.a_share_universe import AShareUniverseRow, normalize_a_share_code
from src.services.a_share_universe.mapping import (
    infer_board,
    infer_exchange,
    is_a_share_universe_code,
    map_tushare_exchange,
)

logger = logging.getLogger(__name__)


class UniverseProviderError(RuntimeError):
    """Raised when a universe provider cannot fetch the full A-share list."""


class BaseUniverseProvider(ABC):
    source_name: str = "unknown"

    @abstractmethod
    def fetch_universe(self) -> List[AShareUniverseRow]:
        """Fetch the full A-share universe list."""


class EastMoneyUniverseProvider(BaseUniverseProvider):
    source_name = "eastmoney"

    def fetch_universe(self) -> List[AShareUniverseRow]:
        import akshare as ak

        errors: List[str] = []
        for fetcher in (self._fetch_from_spot_em, self._fetch_from_code_name):
            try:
                rows = fetcher(ak)
            except Exception as exc:
                message = f"{fetcher.__name__} failed: {exc}"
                logger.warning(message)
                errors.append(message)
                continue
            if rows:
                logger.info("[a-share-universe] EastMoney fetched %s rows via %s", len(rows), fetcher.__name__)
                return rows

        detail = "; ".join(errors) if errors else "no rows returned"
        raise UniverseProviderError(f"EastMoney universe fetch failed: {detail}")

    @classmethod
    def _fetch_from_spot_em(cls, ak_module) -> List[AShareUniverseRow]:
        df = ak_module.stock_zh_a_spot_em()
        if df is None or df.empty:
            return []
        return cls._rows_from_dataframe(df, source=cls.source_name)

    @classmethod
    def _fetch_from_code_name(cls, ak_module) -> List[AShareUniverseRow]:
        df = ak_module.stock_info_a_code_name()
        if df is None or df.empty:
            return []
        return cls._rows_from_dataframe(df, source=cls.source_name)

    @classmethod
    def _rows_from_dataframe(cls, df: pd.DataFrame, *, source: str) -> List[AShareUniverseRow]:
        code_candidates = ("代码", "code", "symbol", "证券代码")
        name_candidates = ("名称", "name", "证券简称")
        industry_candidates = ("所属行业", "行业", "industry")

        code_col = cls._pick_column(df.columns, code_candidates)
        name_col = cls._pick_column(df.columns, name_candidates)
        industry_col = cls._pick_column(df.columns, industry_candidates)
        if not code_col or not name_col:
            return []

        rows: List[AShareUniverseRow] = []
        seen: set[str] = set()
        for record in df.to_dict(orient="records"):
            code = normalize_a_share_code(str(record.get(code_col) or ""))
            name = str(record.get(name_col) or "").strip()
            if not code or not name or not is_a_share_universe_code(code):
                continue
            if code in seen:
                continue
            seen.add(code)
            industry = str(record.get(industry_col) or "").strip() if industry_col else ""
            rows.append(
                AShareUniverseRow(
                    code=code,
                    name=name,
                    exchange=infer_exchange(code),
                    board=infer_board(code),
                    industry=industry or None,
                    list_date=None,
                    active=True,
                    source=source,
                )
            )
        return rows

    @staticmethod
    def _pick_column(columns: Sequence[str], candidates: Iterable[str]) -> Optional[str]:
        normalized = {str(column).strip(): str(column) for column in columns}
        lookup = {key.lower(): value for key, value in normalized.items()}
        for candidate in candidates:
            match = lookup.get(candidate.lower())
            if match:
                return match
        return None


class TushareUniverseProvider(BaseUniverseProvider):
    source_name = "tushare"

    def __init__(self, token: str):
        self.token = str(token or "").strip()
        if not self.token:
            raise UniverseProviderError("TUSHARE_TOKEN is required for Tushare universe sync")

    def fetch_universe(self) -> List[AShareUniverseRow]:
        try:
            import tushare as ts
        except ImportError as exc:
            raise UniverseProviderError("tushare is not installed") from exc

        api = ts.pro_api(self.token)
        try:
            df = api.stock_basic(
                exchange="",
                list_status="L",
                fields="ts_code,symbol,name,industry,market,exchange,list_date,list_status",
            )
        except Exception as exc:
            raise UniverseProviderError(f"Tushare stock_basic failed: {exc}") from exc

        if df is None or df.empty:
            raise UniverseProviderError("Tushare stock_basic returned empty data")

        rows: List[AShareUniverseRow] = []
        seen: set[str] = set()
        for record in df.to_dict(orient="records"):
            code = normalize_a_share_code(str(record.get("symbol") or record.get("ts_code") or ""))
            name = str(record.get("name") or "").strip()
            if not code or not name or not is_a_share_universe_code(code):
                continue
            if code in seen:
                continue
            seen.add(code)
            exchange = map_tushare_exchange(str(record.get("exchange") or "")) or infer_exchange(code)
            board = str(record.get("market") or "").strip() or infer_board(code)
            rows.append(
                AShareUniverseRow(
                    code=code,
                    name=name,
                    exchange=exchange,
                    board=board,
                    industry=(str(record.get("industry") or "").strip() or None),
                    list_date=self._parse_list_date(record.get("list_date")),
                    active=str(record.get("list_status") or "L").upper() == "L",
                    source=self.source_name,
                )
            )

        if not rows:
            raise UniverseProviderError("Tushare stock_basic returned no usable A-share rows")
        logger.info("[a-share-universe] Tushare fetched %s rows", len(rows))
        return rows

    @staticmethod
    def _parse_list_date(raw_value) -> Optional[date]:
        if raw_value is None or (isinstance(raw_value, float) and pd.isna(raw_value)):
            return None
        text = str(raw_value).strip()
        if not text or text.lower() in {"nan", "none", "nat"}:
            return None
        for fmt in ("%Y%m%d", "%Y-%m-%d"):
            try:
                return datetime.strptime(text[:10], fmt).date()
            except ValueError:
                continue
        return None


def build_universe_provider(source: str, *, tushare_token: Optional[str] = None) -> BaseUniverseProvider:
    normalized = str(source or "eastmoney").strip().lower()
    if normalized == "tushare":
        return TushareUniverseProvider(token=tushare_token or "")
    if normalized == "eastmoney":
        return EastMoneyUniverseProvider()
    raise UniverseProviderError(f"Unsupported A-share universe source: {source}")

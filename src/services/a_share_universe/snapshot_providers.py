# -*- coding: utf-8
"""Snapshot providers for A-share market data sync."""

from __future__ import annotations

import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Dict, List, Optional

import pandas as pd

from src.schemas.a_share_universe import AShareSnapshotRow, normalize_a_share_code
from src.services.a_share_universe.checkpoint import SnapshotCheckpoint
from src.services.a_share_universe.mapping import is_a_share_universe_code
from src.services.a_share_universe.providers import UniverseProviderError
from src.services.a_share_universe.snapshot_mapping import (
    candidate_yjbb_report_dates,
    financial_map_from_yjbb_dataframe,
    get_cn_market_date,
    merge_financial_fields,
    snapshot_row_from_spot_record,
)
from data_provider.realtime_types import safe_float

logger = logging.getLogger(__name__)


@dataclass
class SnapshotFetchResult:
    rows: List[AShareSnapshotRow] = field(default_factory=list)
    data_date: Optional[date] = None
    financial_report_date: Optional[str] = None
    errors: List[str] = field(default_factory=list)


@dataclass
class SnapshotEnrichResult:
    rows: List[AShareSnapshotRow] = field(default_factory=list)
    enriched: int = 0
    failed: int = 0
    failed_codes: Dict[str, str] = field(default_factory=dict)


class EastMoneySnapshotProvider:
    source_name = "eastmoney"

    def __init__(self, *, workers: int = 6, min_interval_sec: float = 1.0):
        self.workers = max(1, int(workers))
        self.min_interval_sec = max(0.0, float(min_interval_sec))

    def fetch_snapshots(self) -> SnapshotFetchResult:
        import akshare as ak

        result = SnapshotFetchResult(data_date=get_cn_market_date())
        try:
            df = ak.stock_zh_a_spot_em()
        except Exception as exc:
            result.errors.append(f"stock_zh_a_spot_em failed: {exc}")
            return result

        if df is None or df.empty:
            result.errors.append("stock_zh_a_spot_em returned empty data")
            return result

        rows: List[AShareSnapshotRow] = []
        for record in df.to_dict(orient="records"):
            row = snapshot_row_from_spot_record(
                record,
                data_date=result.data_date,
                source=self.source_name,
            )
            if row is not None:
                rows.append(row)

        financial_map, report_date = self._fetch_financial_map(ak)
        result.financial_report_date = report_date
        if financial_map:
            rows = [merge_financial_fields(row, financial_map.get(row.code, {})) for row in rows]

        result.rows = rows
        logger.info(
            "[a-share-snapshot] bulk fetched rows=%s financial_report_date=%s",
            len(rows),
            report_date,
        )
        return result

    def enrich_snapshots(
        self,
        rows: List[AShareSnapshotRow],
        *,
        checkpoint: Optional[SnapshotCheckpoint] = None,
        resume: bool = False,
        progress_callback: Optional[Callable[[SnapshotCheckpoint], None]] = None,
    ) -> SnapshotEnrichResult:
        import akshare as ak

        if checkpoint is None:
            checkpoint = SnapshotCheckpoint(
                data_date=(rows[0].data_date.isoformat() if rows else ""),
                pending_codes=[row.code for row in rows],
            )
        elif resume:
            pending = set(checkpoint.pending_codes)
            completed = set(checkpoint.completed_codes)
            rows = [row for row in rows if row.code in pending and row.code not in completed]
        else:
            checkpoint.pending_codes = [row.code for row in rows]
            checkpoint.completed_codes = []
            checkpoint.failed_codes = {}

        row_by_code = {row.code: row for row in rows}
        enrich_result = SnapshotEnrichResult(rows=list(rows))

        if not rows:
            enrich_result.rows = []
            return enrich_result

        def _worker(code: str) -> tuple[str, Optional[AShareSnapshotRow], Optional[str]]:
            if self.min_interval_sec > 0:
                time.sleep(random.uniform(0.0, self.min_interval_sec))
            try:
                enriched = self._enrich_single_code(ak, row_by_code[code])
                return code, enriched, None
            except Exception as exc:
                return code, None, str(exc)

        updated_rows: Dict[str, AShareSnapshotRow] = dict(row_by_code)
        with ThreadPoolExecutor(max_workers=self.workers) as executor:
            futures = {executor.submit(_worker, row.code): row.code for row in rows}
            for future in as_completed(futures):
                code, enriched_row, error = future.result()
                if error:
                    enrich_result.failed += 1
                    enrich_result.failed_codes[code] = error
                    checkpoint.failed_codes[code] = error
                elif enriched_row is not None:
                    updated_rows[code] = enriched_row
                    enrich_result.enriched += 1
                    checkpoint.completed_codes.append(code)
                if code in checkpoint.pending_codes:
                    checkpoint.pending_codes = [item for item in checkpoint.pending_codes if item != code]
                if progress_callback is not None:
                    progress_callback(checkpoint)

        enrich_result.rows = list(updated_rows.values())
        return enrich_result

    def _fetch_financial_map(self, ak_module) -> tuple[Dict[str, Dict], Optional[str]]:
        for report_date in candidate_yjbb_report_dates():
            try:
                df = ak_module.stock_yjbb_em(date=report_date)
            except Exception as exc:
                logger.debug("[a-share-snapshot] stock_yjbb_em(%s) failed: %s", report_date, exc)
                continue
            financial_map = financial_map_from_yjbb_dataframe(df)
            if financial_map:
                return financial_map, report_date
        return {}, None

    @classmethod
    def _enrich_single_code(cls, ak_module, row: AShareSnapshotRow) -> AShareSnapshotRow:
        if not cls._needs_enrichment(row):
            return row

        info_df = ak_module.stock_individual_info_em(symbol=row.code)
        if info_df is None or info_df.empty:
            return row

        info_map = cls._info_dataframe_to_map(info_df)
        patch = {
            "total_share": safe_float(info_map.get("总股本")),
            "float_share": safe_float(info_map.get("流通股")),
            "bps": safe_float(info_map.get("每股净资产")),
            "pe_ttm": safe_float(info_map.get("市盈率")),
            "ps": safe_float(info_map.get("市销率")),
        }
        return merge_financial_fields(row, patch)

    @staticmethod
    def _needs_enrichment(row: AShareSnapshotRow) -> bool:
        return any(
            value is None
            for value in (
                row.total_share,
                row.float_share,
                row.bps,
                row.pe_ttm,
                row.ps,
            )
        )

    @staticmethod
    def _info_dataframe_to_map(df: pd.DataFrame) -> Dict[str, str]:
        item_col = None
        value_col = None
        for column in df.columns:
            lowered = str(column).strip().lower()
            if lowered in {"item", "项目"}:
                item_col = column
            if lowered in {"value", "值"}:
                value_col = column
        if item_col is None or value_col is None:
            return {}
        mapping: Dict[str, str] = {}
        for record in df.to_dict(orient="records"):
            key = str(record.get(item_col) or "").strip()
            value = str(record.get(value_col) or "").strip()
            if key:
                mapping[key] = value
        return mapping


def build_snapshot_provider(source: str, *, workers: int = 6, min_interval_sec: float = 1.0):
    normalized = str(source or "eastmoney").strip().lower()
    if normalized == "eastmoney":
        return EastMoneySnapshotProvider(workers=workers, min_interval_sec=min_interval_sec)
    raise UniverseProviderError(f"Unsupported A-share snapshot source: {source}")

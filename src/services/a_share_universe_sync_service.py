# -*- coding: utf-8 -*-
"""Orchestrator for syncing A-share universe master data into SQLite."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from src.config import Config, get_config
from src.repositories.a_share_universe_repo import AShareUniverseRepository
from src.schemas.a_share_universe import AShareSnapshotRow
from src.services.a_share_universe.checkpoint import SnapshotCheckpoint, SnapshotCheckpointStore
from src.services.a_share_universe.providers import (
    BaseUniverseProvider,
    UniverseProviderError,
    build_universe_provider,
)
from src.services.a_share_universe.snapshot_providers import (
    EastMoneySnapshotProvider,
    build_snapshot_provider,
)

logger = logging.getLogger(__name__)


@dataclass
class AShareUniverseSyncReport:
    source: str
    mode: str = "universe-only"
    fetched: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    dry_run: bool = False
    persisted: bool = False
    errors: list[str] = field(default_factory=list)
    snapshot_fetched: int = 0
    snapshot_inserted: int = 0
    snapshot_updated: int = 0
    snapshot_enriched: int = 0
    snapshot_enrich_failed: int = 0
    data_date: Optional[str] = None
    financial_report_date: Optional[str] = None
    field_coverage: Dict[str, float] = field(default_factory=dict)
    failed_codes: Dict[str, str] = field(default_factory=dict)
    report_path: Optional[str] = None

    @property
    def total_in_db(self) -> int:
        return self.inserted + self.updated


class AShareUniverseSyncService:
    """Fetch A-share universe rows from a provider and upsert into the DB."""

    def __init__(
        self,
        *,
        config: Optional[Config] = None,
        repository: Optional[AShareUniverseRepository] = None,
        provider: Optional[BaseUniverseProvider] = None,
        snapshot_provider: Optional[EastMoneySnapshotProvider] = None,
        checkpoint_store: Optional[SnapshotCheckpointStore] = None,
    ):
        self.config = config or get_config()
        self.repository = repository or AShareUniverseRepository()
        self._provider = provider
        self._snapshot_provider = snapshot_provider
        repo_root = Path(__file__).resolve().parents[2]
        self.checkpoint_store = checkpoint_store or SnapshotCheckpointStore(repo_root / "data" / "a_share_sync")

    def sync_universe(
        self,
        *,
        dry_run: bool = False,
        source: Optional[str] = None,
    ) -> AShareUniverseSyncReport:
        selected_source = self._resolve_source(source)
        report = AShareUniverseSyncReport(source=selected_source, mode="universe-only", dry_run=dry_run)

        try:
            provider = self._provider or build_universe_provider(
                selected_source,
                tushare_token=self.config.tushare_token,
            )
            rows = provider.fetch_universe()
        except UniverseProviderError as exc:
            report.errors.append(str(exc))
            logger.error("[a-share-universe] fetch failed: %s", exc)
            return report

        report.fetched = len(rows)
        if report.fetched == 0:
            report.errors.append("provider returned zero rows")
            return report

        if dry_run:
            logger.info(
                "[a-share-universe] dry-run fetched=%s source=%s",
                report.fetched,
                selected_source,
            )
            return report

        upsert_result = self.repository.upsert_universe(rows)
        report.inserted = upsert_result.inserted
        report.updated = upsert_result.updated
        report.skipped = upsert_result.skipped
        report.persisted = True
        logger.info(
            "[a-share-universe] sync complete source=%s fetched=%s inserted=%s updated=%s",
            selected_source,
            report.fetched,
            report.inserted,
            report.updated,
        )
        return report

    def sync_snapshot(
        self,
        *,
        dry_run: bool = False,
        resume: bool = False,
        source: Optional[str] = None,
        enrich: bool = True,
    ) -> AShareUniverseSyncReport:
        selected_source = self._resolve_source(source)
        report = AShareUniverseSyncReport(source=selected_source, mode="snapshot", dry_run=dry_run)

        snapshot_provider = self._snapshot_provider or build_snapshot_provider(
            selected_source,
            workers=self.config.a_share_universe_workers,
            min_interval_sec=self.config.a_share_universe_min_interval_sec,
        )

        checkpoint = self.checkpoint_store.load() if resume else None
        fetch_result = snapshot_provider.fetch_snapshots()
        report.errors.extend(fetch_result.errors)
        report.snapshot_fetched = len(fetch_result.rows)
        report.data_date = fetch_result.data_date.isoformat() if fetch_result.data_date else None
        report.financial_report_date = fetch_result.financial_report_date
        report.field_coverage = self._compute_field_coverage(fetch_result.rows)

        if not fetch_result.rows:
            if not report.errors:
                report.errors.append("snapshot provider returned zero rows")
            return report

        rows = fetch_result.rows
        if enrich:
            rows, enrich_stats = self._run_enrichment(
                snapshot_provider,
                rows,
                checkpoint=checkpoint,
                resume=resume,
            )
            report.snapshot_enriched = enrich_stats["enriched"]
            report.snapshot_enrich_failed = enrich_stats["failed"]
            report.failed_codes = enrich_stats["failed_codes"]
            report.field_coverage = self._compute_field_coverage(rows)

        if dry_run:
            return report

        upsert_result = self.repository.upsert_snapshot(rows)
        report.snapshot_inserted = upsert_result.inserted
        report.snapshot_updated = upsert_result.updated
        report.skipped = upsert_result.skipped
        report.persisted = True

        if fetch_result.data_date is not None:
            self._apply_snapshot_retention(fetch_result.data_date)

        if not resume:
            self.checkpoint_store.clear()

        report.report_path = str(
            self.checkpoint_store.write_report(self._build_report_payload(report, rows))
        )
        return report

    def sync_full(
        self,
        *,
        dry_run: bool = False,
        resume: bool = False,
        source: Optional[str] = None,
        enrich: bool = True,
    ) -> AShareUniverseSyncReport:
        selected_source = self._resolve_source(source)
        universe_report = self.sync_universe(dry_run=dry_run, source=selected_source)
        snapshot_source = "eastmoney" if selected_source == "tushare" else selected_source
        snapshot_report = self.sync_snapshot(
            dry_run=dry_run,
            resume=resume,
            source=snapshot_source,
            enrich=enrich,
        )
        return self._merge_reports(universe_report, snapshot_report, mode="full")

    def _run_enrichment(
        self,
        snapshot_provider: EastMoneySnapshotProvider,
        rows: list[AShareSnapshotRow],
        *,
        checkpoint: Optional[SnapshotCheckpoint],
        resume: bool,
    ) -> tuple[list[AShareSnapshotRow], Dict[str, Any]]:
        if resume and checkpoint is not None:
            pending = set(checkpoint.pending_codes)
            needs_enrichment = [row for row in rows if row.code in pending]
        else:
            needs_enrichment = [row for row in rows if snapshot_provider._needs_enrichment(row)]

        if not needs_enrichment:
            return rows, {"enriched": 0, "failed": 0, "failed_codes": {}}

        if checkpoint is None:
            checkpoint = SnapshotCheckpoint(
                data_date=(rows[0].data_date.isoformat() if rows else ""),
                pending_codes=[row.code for row in needs_enrichment],
            )
        elif not resume:
            checkpoint.pending_codes = [row.code for row in needs_enrichment]
            checkpoint.completed_codes = []
            checkpoint.failed_codes = {}

        def _persist_checkpoint(state: SnapshotCheckpoint) -> None:
            self.checkpoint_store.save(state)

        enrich_result = snapshot_provider.enrich_snapshots(
            needs_enrichment,
            checkpoint=checkpoint,
            resume=resume,
            progress_callback=_persist_checkpoint,
        )
        _persist_checkpoint(checkpoint)

        merged = {row.code: row for row in rows}
        for row in enrich_result.rows:
            merged[row.code] = row
        return list(merged.values()), {
            "enriched": enrich_result.enriched,
            "failed": enrich_result.failed,
            "failed_codes": enrich_result.failed_codes,
        }

    def _apply_snapshot_retention(self, active_date: date) -> None:
        retention_days = int(self.config.a_share_universe_history_retention_days or 0)
        if retention_days <= 0:
            cutoff = active_date
        else:
            cutoff = active_date - timedelta(days=retention_days)
        deleted = self.repository.purge_snapshots_before(cutoff)
        if deleted:
            logger.info("[a-share-snapshot] purged %s stale snapshot rows before %s", deleted, cutoff)

    @staticmethod
    def _compute_field_coverage(rows: list[AShareSnapshotRow]) -> Dict[str, float]:
        if not rows:
            return {}
        tracked_fields = (
            "price",
            "pe_ttm",
            "pb",
            "ps",
            "total_mv",
            "eps",
            "roe",
            "revenue",
            "net_profit",
            "high_52w",
            "low_52w",
        )
        coverage: Dict[str, float] = {}
        total = len(rows)
        for field_name in tracked_fields:
            non_null = sum(1 for row in rows if getattr(row, field_name) is not None)
            coverage[field_name] = round(non_null / total, 4)
        return coverage

    def _build_report_payload(
        self,
        report: AShareUniverseSyncReport,
        rows: list[AShareSnapshotRow],
    ) -> Dict[str, Any]:
        return {
            "source": report.source,
            "mode": report.mode,
            "data_date": report.data_date,
            "financial_report_date": report.financial_report_date,
            "snapshot_fetched": report.snapshot_fetched,
            "snapshot_inserted": report.snapshot_inserted,
            "snapshot_updated": report.snapshot_updated,
            "snapshot_enrich_failed": report.snapshot_enrich_failed,
            "field_coverage": report.field_coverage,
            "failed_codes": report.failed_codes,
            "sample_codes": [row.code for row in rows[:5]],
        }

    @staticmethod
    def _merge_reports(
        universe_report: AShareUniverseSyncReport,
        snapshot_report: AShareUniverseSyncReport,
        *,
        mode: str,
    ) -> AShareUniverseSyncReport:
        merged = AShareUniverseSyncReport(
            source=snapshot_report.source,
            mode=mode,
            dry_run=universe_report.dry_run,
            fetched=universe_report.fetched,
            inserted=universe_report.inserted,
            updated=universe_report.updated,
            skipped=universe_report.skipped + snapshot_report.skipped,
            persisted=universe_report.persisted and snapshot_report.persisted,
            errors=[*universe_report.errors, *snapshot_report.errors],
            snapshot_fetched=snapshot_report.snapshot_fetched,
            snapshot_inserted=snapshot_report.snapshot_inserted,
            snapshot_updated=snapshot_report.snapshot_updated,
            snapshot_enriched=snapshot_report.snapshot_enriched,
            snapshot_enrich_failed=snapshot_report.snapshot_enrich_failed,
            data_date=snapshot_report.data_date,
            financial_report_date=snapshot_report.financial_report_date,
            field_coverage=snapshot_report.field_coverage,
            failed_codes=snapshot_report.failed_codes,
            report_path=snapshot_report.report_path,
        )
        return merged

    def _resolve_source(self, source: Optional[str]) -> str:
        return (source or self.config.a_share_universe_source or "eastmoney").strip().lower()

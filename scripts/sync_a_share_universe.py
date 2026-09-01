#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sync A-share universe master data into the local database.

Usage:
    python scripts/sync_a_share_universe.py --mode universe-only
    python scripts/sync_a_share_universe.py --mode snapshot
    python scripts/sync_a_share_universe.py --mode full
    python scripts/sync_a_share_universe.py --dry-run
    python scripts/sync_a_share_universe.py --mode snapshot --resume
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.services.a_share_universe_sync_service import AShareUniverseSyncService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="同步 A 股全量主数据/快照到本地数据库")
    parser.add_argument(
        "--mode",
        choices=("universe-only", "full", "snapshot"),
        default="universe-only",
        help="universe-only=主数据；snapshot=快照；full=主数据+快照",
    )
    parser.add_argument(
        "--source",
        choices=("eastmoney", "tushare"),
        default=None,
        help="覆盖 A_SHARE_UNIVERSE_SOURCE 配置（snapshot 当前仅支持 eastmoney）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只拉取并统计，不写入数据库",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="从 checkpoint 继续快照补充（仅 snapshot/full 生效）",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="跳过快照个股补充（仅 snapshot/full 生效）",
    )
    return parser


def _print_report(report) -> None:
    print(
        "[sync_a_share_universe] "
        f"mode={report.mode} source={report.source} dry_run={report.dry_run} "
        f"universe_fetched={report.fetched} universe_inserted={report.inserted} universe_updated={report.updated} "
        f"snapshot_fetched={report.snapshot_fetched} snapshot_inserted={report.snapshot_inserted} "
        f"snapshot_updated={report.snapshot_updated} enriched={report.snapshot_enriched} "
        f"enrich_failed={report.snapshot_enrich_failed} data_date={report.data_date}"
    )
    if report.field_coverage:
        coverage_text = ", ".join(f"{key}={value:.1%}" for key, value in sorted(report.field_coverage.items()))
        print(f"[sync_a_share_universe] field_coverage: {coverage_text}")
    if report.report_path:
        print(f"[sync_a_share_universe] report={report.report_path}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = AShareUniverseSyncService()
    enrich = not args.no_enrich

    if args.mode == "universe-only":
        report = service.sync_universe(dry_run=args.dry_run, source=args.source)
    elif args.mode == "snapshot":
        if args.source == "tushare":
            print("[sync_a_share_universe] ERROR: snapshot 模式当前仅支持 eastmoney 数据源", file=sys.stderr)
            return 2
        report = service.sync_snapshot(
            dry_run=args.dry_run,
            resume=args.resume,
            source=args.source,
            enrich=enrich,
        )
    else:
        report = service.sync_full(
            dry_run=args.dry_run,
            resume=args.resume,
            source=args.source,
            enrich=enrich,
        )

    _print_report(report)

    if report.errors:
        for message in report.errors:
            print(f"[sync_a_share_universe] ERROR: {message}", file=sys.stderr)
        return 1

    if report.mode in {"universe-only", "full"} and report.fetched < 5000 and not report.dry_run:
        print(
            "[sync_a_share_universe] WARNING: universe fetched rows below expected 5000+ threshold",
            file=sys.stderr,
        )
    if report.mode in {"snapshot", "full"} and report.snapshot_fetched < 5000 and not report.dry_run:
        print(
            "[sync_a_share_universe] WARNING: snapshot fetched rows below expected 5000+ threshold",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

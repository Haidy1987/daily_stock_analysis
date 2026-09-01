#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate stock autocomplete index from A-share universe DB rows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.repositories.a_share_universe_repo import AShareUniverseRepository
from src.services.a_share_universe.index_builder import write_merged_index_from_db
from src.services.stock_index_builder import pypinyin_available

WEB_INDEX_PATH = REPO_ROOT / "apps" / "dsa-web" / "public" / "stocks.index.json"


def require_pypinyin() -> bool:
    if pypinyin_available():
        return True
    print("[Error] pypinyin not available; cannot generate stock autocomplete index.")
    print("[Info] Install dependencies with: pip install -r requirements.txt")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="从 A 股 universe 数据库生成股票自动补全索引")
    parser.add_argument(
        "--output",
        type=Path,
        default=WEB_INDEX_PATH,
        help=f"输出路径（默认: {WEB_INDEX_PATH.relative_to(REPO_ROOT)}）",
    )
    parser.add_argument(
        "--merge-from",
        type=Path,
        default=WEB_INDEX_PATH,
        help="保留非 A 股条目时读取的现有索引文件（默认与输出路径相同）",
    )
    parser.add_argument(
        "--no-merge",
        action="store_true",
        help="仅写入 A 股条目，不合并现有 HK/US/JP/KR 索引",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="测试模式：只统计不写文件",
    )
    args = parser.parse_args(argv)

    if not require_pypinyin():
        return 1

    repo = AShareUniverseRepository()
    active_count = repo.count_universe(active_only=True)
    if active_count == 0:
        print("[Error] a_share_universe 为空，请先运行 scripts/sync_a_share_universe.py")
        return 1

    merge_from = None if args.no_merge else args.merge_from
    if args.test:
        from src.services.a_share_universe.index_builder import build_merged_index_from_db

        merged = build_merged_index_from_db(repo, existing_index_path=merge_from)
        print(f"[generate_index_from_db] active universe rows: {active_count}")
        print(f"[generate_index_from_db] merged index size: {len(merged)}")
        return 0

    stats = write_merged_index_from_db(
        args.output,
        repo,
        merge_from=merge_from,
    )
    print(
        "[generate_index_from_db] wrote "
        f"{stats['total']} entries "
        f"(A-share={stats['a_share_count']}, other={stats['non_a_share_count']}) "
        f"-> {args.output}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate Stock Index from CSV File

Input:
  - Tushare format: data/stock_list_{a,hk,us}.csv
  - Seed format: scripts/stock_index_seeds/stock_list_{jp,kr}.csv
  - AkShare format: logs/stock_basic_*.csv

Output: apps/dsa-web/public/stocks.index.json

Usage:
    python3 scripts/generate_index_from_csv.py              # 默认使用 Tushare
    python3 scripts/generate_index_from_csv.py --source akshare
    python3 scripts/generate_index_from_csv.py --test       # 测试模式
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add the project root to sys.path.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.services.stock_index_builder import (
    build_stock_index,
    compress_index,
    normalize_stock_name_for_index,
    pypinyin_available,
    write_compressed_index,
)


def require_pypinyin() -> bool:
    """Ensure pypinyin is available before generating autocomplete assets."""
    if pypinyin_available():
        return True

    print("[Error] pypinyin not available; cannot generate stock autocomplete index.")
    print("[Info] Install dependencies with: pip install -r requirements.txt")
    return False


def load_csv_data(csv_path: Path) -> List[Dict[str, Any]]:
    """
    Load stock data from AkShare format CSV file

    Args:
        csv_path: CSV file path

    Returns:
        List of stock data
    """
    stocks = []

    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            ts_code = row['ts_code'].strip()
            symbol = row['symbol'].strip()
            name = row['name'].strip()

            # Skip invalid rows.
            if not ts_code or not symbol or not name:
                continue

            stocks.append({
                'ts_code': ts_code,
                'symbol': symbol,
                'name': name,
                'area': row.get('area', ''),
                'industry': row.get('industry', ''),
                'list_date': row.get('list_date', ''),
            })

    return stocks


def load_tushare_data(data_dir: Path) -> List[Dict[str, Any]]:
    """
    从 Tushare CSV 文件加载多市场股票数据

    Args:
        data_dir: 数据目录路径

    Returns:
        合并后的股票列表
    """
    all_stocks = []
    seed_dir = Path(__file__).parent / 'stock_index_seeds'
    default_data_dir = Path(__file__).parent.parent / 'data'
    use_seed_fallback = data_dir.resolve() == default_data_dir.resolve()

    def _csv_path(file_name: str) -> Path:
        data_path = data_dir / file_name
        if data_path.exists() or not use_seed_fallback:
            return data_path
        return seed_dir / file_name

    market_files = {
        'CN': data_dir / 'stock_list_a.csv',
        'HK': data_dir / 'stock_list_hk.csv',
        'US': data_dir / 'stock_list_us.csv',
        'JP': _csv_path('stock_list_jp.csv'),
        'KR': _csv_path('stock_list_kr.csv'),
    }

    for market_name, csv_file in market_files.items():
        if not csv_file.exists():
            print(f"[Warning] 未找到文件：{csv_file}")
            continue

        print(f"  正在读取 {market_name} 市场数据：{csv_file.name}")

        try:
            file_stocks = []
            selected_us_stocks: Dict[str, tuple[Dict[str, Any], int]] = {}
            with open(csv_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    # 传入市场参数以优化判断（对于特殊格式如 DUMMY）
                    parsed = parse_stock_row(row, market_name)
                    if not parsed:
                        continue

                    if market_name == 'US':
                        # Tushare us_basic may include historical rows for a reused ticker.
                        # Keep one deterministic row per ts_code before generating the index.
                        delist_priority = get_us_delist_priority(row)
                        existing = selected_us_stocks.get(parsed['ts_code'])
                        if existing is None or delist_priority > existing[1]:
                            selected_us_stocks[parsed['ts_code']] = (parsed, delist_priority)
                        continue

                    if parsed:
                        all_stocks.append(parsed)
                        file_stocks.append(parsed)

            if market_name == 'US':
                file_stocks = [item for item, _priority in selected_us_stocks.values()]
                all_stocks.extend(file_stocks)

            print(f"    ✓ {market_name} 市场读取完成：{len(file_stocks)} 只股票")

        except Exception as e:
            print(f"    [Error] 读取 {csv_file.name} 失败：{e}")

    return all_stocks


def get_us_delist_priority(row: Dict[str, str]) -> int:
    """
    为复用 ticker 的美股记录生成去重优先级。

    Tushare us_basic 导出的 delist_date 对当前记录并不总是稳定：
    - 空字符串通常表示当前仍在使用的 ticker
    - ``NaT`` 多见于历史记录或日期占位值
    - 实际日期表示明确退市

    因此前置去重时优先选择：
    1. delist_date 为空
    2. delist_date 为 NaT
    3. delist_date 为实际日期

    同优先级时保留 CSV 中最先出现的记录，避免在信息不足时随意切换名称。
    """
    delist_date = (row.get('delist_date') or '').strip()
    if not delist_date:
        return 2
    if delist_date.upper() == 'NAT':
        return 1
    return 0


def load_akshare_data(logs_dir: Path) -> List[Dict[str, Any]]:
    """
    从 AkShare CSV 文件加载股票数据

    Args:
        logs_dir: 日志目录路径

    Returns:
        股票列表

    说明：
        AkShare 这条输入路径保留其原始 name 字段，不额外套用
        Tushare A 股那套 XD / XR / DR 状态前缀修正逻辑。这里的目标是
        复用 AkShare 已输出的展示名，而不是对其做二次归一化。
    """
    csv_files = list(logs_dir.glob("stock_basic_*.csv"))

    if not csv_files:
        print("[Error] 未找到 CSV 文件：logs/stock_basic_*.csv")
        return []

    # 使用最新的 CSV 文件
    csv_file = sorted(csv_files)[-1]
    print(f"  正在读取 AkShare 数据：{csv_file.name}")

    stocks = []
    with open(csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        for row in reader:
            ts_code = row['ts_code'].strip()
            symbol = row['symbol'].strip()
            name = row['name'].strip()

            # Skip invalid rows.
            if not ts_code or not symbol or not name:
                continue

            stocks.append({
                'ts_code': ts_code,
                'symbol': symbol,
                'name': name,
                'area': row.get('area', ''),
                'industry': row.get('industry', ''),
                'list_date': row.get('list_date', ''),
            })

    print(f"    ✓ 共读取 {len(stocks)} 只股票")
    return stocks


def extract_symbol_from_ts_code(ts_code: str, market: str) -> Optional[str]:
    """
    从 ts_code 提取 displayCode

    - A股：000001.SZ → 000001
    - 港股：00700.HK → 00700
    - 美股：AAPL → AAPL
    - 日股/韩股：7203.T / 005930.KS → 保留后缀，避免与其他市场裸代码冲突

    Args:
        ts_code: TS代码
        market: 市场代码

    Returns:
        displayCode 或 None
    """
    if not ts_code:
        return None

    if market in {'US', 'JP', 'KR'}:
        # 美股常见 class/share 后缀、日韩 Yahoo 后缀都是代码身份的一部分。
        return ts_code

    if '.' in ts_code:
        # A股和港股：去除后缀
        return ts_code.split('.')[0]

    return ts_code


def get_stock_name(row: Dict[str, str], market: str) -> Optional[str]:
    """
    获取股票名称

    - A股/港股/日股/韩股：使用 name 字段
    - 美股：使用 enname 字段（英文名称）

    Args:
        row: CSV 行数据
        market: 市场代码

    Returns:
        股票名称或 None
    """
    if market == 'US':
        # 美股使用英文名称
        name = row.get('enname', '').strip()
        return name if name else None
    else:
        # A股和港股使用中文名称
        name = row.get('name', '').strip()
        name = normalize_stock_name_for_index(name, market)
        return name if name else None


def parse_aliases(row: Dict[str, str]) -> List[str]:
    """Parse optional seed aliases from a CSV row."""
    raw_aliases = (row.get('aliases') or row.get('alias') or '').strip()
    if not raw_aliases:
        return []

    aliases: List[str] = []
    for alias in re.split(r'[|;,，、]+', raw_aliases):
        normalized = unicodedata.normalize('NFKC', alias).strip()
        if normalized and normalized not in aliases:
            aliases.append(normalized)
    return aliases


def parse_stock_row(row: Dict[str, str], preferred_market: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    解析单行股票数据

    - 美股 DUMMY 过滤（严格过滤）
    - 空值校验
    - 自动判断市场类型（当无法判断时使用 preferred_market）
    - 返回统一格式的字典

    Args:
        row: CSV 行数据
        preferred_market: 当 ts_code 无法判断市场时使用（如美股 DUMMY 记录）

    Returns:
        解析后的股票字典，无效数据返回 None
    """
    ts_code = row.get('ts_code', '').strip()

    if not ts_code:
        return None

    # 自动判断市场类型
    market = determine_market(ts_code)

    # 如果 ts_code 没有后缀（无法准确判断），且提供了 preferred_market，则使用它
    # 这主要用于处理美股的特殊格式（如 DUMMY 记录）
    if '.' not in ts_code and preferred_market:
        market = preferred_market

    # 美股特殊处理：严格过滤 DUMMY 记录
    if market == 'US':
        enname = row.get('enname', '').strip()
        if not enname or 'DUMMY' in enname.upper():
            return None

    # 获取股票名称
    name = get_stock_name(row, market)
    if not name:
        return None

    # 提取 displayCode
    display_code = extract_symbol_from_ts_code(ts_code, market)
    if not display_code:
        return None

    return {
        'ts_code': ts_code,
        'symbol': display_code,
        'name': name,
        'market': market,
        'aliases': parse_aliases(row),
    }


def determine_market(ts_code: str) -> str:
    """
    Determine market based on code

    Args:
        ts_code: Trading code (e.g., 000001.SZ, AAPL, BRK.B, 7203.T, 005930.KS)

    Returns:
        Market code (CN, HK, US, BSE, JP, KR)
    """
    if '.' in ts_code:
        # 有后缀的情况
        suffix = ts_code.split('.')[1]
        # 检查是否为中国市场后缀
        if suffix in ['SH', 'SZ']:
            return 'CN'
        elif suffix == 'HK':
            return 'HK'
        elif suffix == 'BJ':
            return 'BSE'
        elif suffix == 'T':
            return 'JP'
        elif suffix in ['KS', 'KQ']:
            return 'KR'
        # 有后缀但不是中国市场后缀，检查是否为美股
        # 美股可能有点号后缀（如 BRK.B, GOOG.A, AAPL.U）
        prefix = ts_code.split('.')[0]
        if prefix.isalpha():
            return 'US'
    else:
        # 无后缀的情况
        # 纯字母代码为美股
        if ts_code.isalpha():
            return 'US'

    # 默认为 A股
    return 'CN'


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='从 CSV 生成股票自动补全索引')
    parser.add_argument(
        '--source',
        choices=['tushare', 'akshare'],
        default='tushare',
        help='数据源选择（默认: tushare）'
    )
    parser.add_argument(
        '--test', '-t',
        action='store_true',
        help='测试模式：只验证不写入文件'
    )
    args = parser.parse_args()

    print("=" * 60)
    print("股票索引生成工具（从 CSV）")
    print("=" * 60)
    print(f"数据源：{args.source}")

    if not require_pypinyin():
        return 1

    # 加载数据
    print("\n[1/5] 读取 CSV 数据...")
    if args.source == 'tushare':
        data_dir = Path(__file__).parent.parent / 'data'
        stocks = load_tushare_data(data_dir)
    elif args.source == 'akshare':
        logs_dir = Path(__file__).parent.parent / 'logs'
        stocks = load_akshare_data(logs_dir)
    else:
        print(f"[Error] 不支持的数据源：{args.source}")
        return 1

    if not stocks:
        print("[Error] 未加载到任何股票数据")
        return 1

    print(f"      共读取 {len(stocks)} 只股票")

    print("\n[2/5] 生成索引数据...")
    index = build_stock_index(stocks)

    # 输出路径
    output_path = (
        Path(__file__).parent.parent / "apps" / "dsa-web" / "public" / "stocks.index.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print("\n[3/5] 压缩索引数据...")
    compressed = compress_index(index)

    if args.test:
        print("\n[4/5] 测试模式：跳过写入文件")
        print(f"      输出路径：{output_path}")

        # 验证数据
        print("\n[5/5] 验证数据...")
        print(f"      压缩前：{len(index)} 条记录")
        print(f"      压缩后：{len(compressed)} 条记录")

        # 显示前5条示例
        if compressed:
            print("\n      前5条示例：")
            for i, item in enumerate(compressed[:5]):
                print(f"        {i + 1}. {item}")
    else:
        print(f"\n[4/5] 写入文件：{output_path}")
        write_compressed_index(output_path, compressed)

        file_size = output_path.stat().st_size
        print(f"      文件大小：{file_size / 1024:.2f} KB")

        # 验证文件
        print("\n[5/5] 验证文件...")
        with open(output_path, 'r', encoding='utf-8') as f:
            test_data = json.load(f)
            print(f"      验证通过：{len(test_data)} 条记录")

    # 统计信息
    market_stats = {}
    for item in index:
        market = item['market']
        market_stats[market] = market_stats.get(market, 0) + 1

    print(f"\n{'=' * 60}")
    print("生成完成！市场分布：")
    for market, count in sorted(market_stats.items()):
        print(f"  - {market}: {count} 只")
    print(f"{'=' * 60}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

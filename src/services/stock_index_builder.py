# -*- coding: utf-8 -*-
"""Shared helpers for building compressed stock autocomplete index payloads."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Sequence

try:
    from pypinyin import Style, lazy_pinyin

    PYPINYIN_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via explicit guard helpers
    Style = None
    lazy_pinyin = None
    PYPINYIN_AVAILABLE = False


def pypinyin_available() -> bool:
    return PYPINYIN_AVAILABLE


def normalize_name_for_pinyin(name: str) -> str:
    normalized = unicodedata.normalize("NFKC", name).strip()
    normalized = re.sub(r"^(?:\*?ST|N)+", "", normalized, flags=re.IGNORECASE)
    return normalized.strip() or unicodedata.normalize("NFKC", name).strip()


def normalize_stock_name_for_index(name: str, market: str) -> str:
    normalized = unicodedata.normalize("NFKC", str(name or "")).strip()
    if market in {"CN", "BSE"}:
        normalized = re.sub(r"^(?:XD|XR|DR)\s*", "", normalized, flags=re.IGNORECASE)
    return normalized.strip()


def generate_pinyin(name: str) -> tuple[str | None, str | None]:
    if not PYPINYIN_AVAILABLE:
        raise RuntimeError("pypinyin is required to generate stock autocomplete index")

    try:
        normalized_name = normalize_name_for_pinyin(name)
        py_full = lazy_pinyin(normalized_name, style=Style.NORMAL)
        py_abbr = lazy_pinyin(normalized_name, style=Style.FIRST_LETTER)
        return ("".join(py_full), "".join(py_abbr))
    except Exception:  # noqa: BLE001 - keep index generation resilient for single rows
        return (None, None)


def generate_aliases(name: str, market: str) -> List[str]:
    cn_alias_map = {
        "贵州茅台": ["茅台"],
        "中国平安": ["平安"],
        "平安银行": ["平银"],
        "招商银行": ["招行"],
        "五粮液": ["五粮"],
        "宁德时代": ["宁德"],
        "比亚迪": ["比亚"],
        "工商银行": ["工行"],
        "建设银行": ["建行"],
        "农业银行": ["农行"],
        "中国银行": ["中行"],
        "交通银行": ["交行"],
        "兴业银行": ["兴业"],
        "浦发银行": ["浦发"],
        "民生银行": ["民生"],
        "中信证券": ["中信"],
        "东方财富": ["东财"],
        "海康威视": ["海康"],
        "隆基绿能": ["隆基"],
        "中国神华": ["神华"],
        "长江电力": ["长电"],
        "中国石化": ["石化"],
        "中国石油": ["石油"],
    }
    hk_alias_map = {
        "腾讯控股": ["腾讯", "Tencent"],
        "阿里巴巴-SW": ["阿里", "阿里巴巴", "Alibaba"],
        "美团-W": ["美团", "Meituan"],
        "小米集团-W": ["小米", "Xiaomi"],
        "京东集团-SW": ["京东", "JD"],
        "网易-S": ["网易", "NetEase"],
        "百度集团-SW": ["百度", "Baidu"],
        "中芯国际": ["中芯", "SMIC"],
        "中国移动": ["中移动", "China Mobile"],
        "中国海洋石油": ["中海油", "CNOOC"],
    }
    us_alias_map = {
        "Apple Inc.": ["Apple", "AAPL"],
        "Microsoft Corporation": ["Microsoft", "MSFT"],
        "Amazon.com, Inc.": ["Amazon", "AMZN"],
        "Tesla Inc.": ["Tesla", "TSLA"],
        "Meta Platforms, Inc.": ["Meta", "Facebook", "META"],
        "Alphabet Inc.": ["Google", "Alphabet", "GOOGL"],
        "NVIDIA Corporation": ["NVIDIA", "NVDA"],
        "Netflix Inc.": ["Netflix", "NFLX"],
        "Intel Corporation": ["Intel", "INTC"],
        "Advanced Micro Devices": ["AMD", "AMD"],
    }

    if market == "CN":
        alias_map = cn_alias_map
    elif market == "HK":
        alias_map = hk_alias_map
    elif market == "US":
        alias_map = us_alias_map
    else:
        alias_map = {}

    return list(alias_map.get(name, []))


def build_stock_index(stocks: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    index: List[Dict[str, Any]] = []
    for stock in stocks:
        ts_code = stock["ts_code"]
        symbol = stock["symbol"]
        name = stock["name"]
        market = stock.get("market", "CN")

        pinyin_full, pinyin_abbr = generate_pinyin(name)
        aliases = generate_aliases(name, market)
        for alias in stock.get("aliases", []):
            if alias != name and alias not in aliases:
                aliases.append(alias)

        index.append(
            {
                "canonicalCode": ts_code,
                "displayCode": symbol,
                "nameZh": name,
                "pinyinFull": pinyin_full,
                "pinyinAbbr": pinyin_abbr,
                "aliases": aliases,
                "market": market,
                "assetType": "stock",
                "active": bool(stock.get("active", True)),
                "popularity": int(stock.get("popularity", 100)),
            }
        )
    return index


def compress_index(index: Sequence[Dict[str, Any]]) -> List[list]:
    compressed: List[list] = []
    for item in index:
        compressed.append(
            [
                item["canonicalCode"],
                item["displayCode"],
                item["nameZh"],
                item.get("pinyinFull"),
                item.get("pinyinAbbr"),
                item.get("aliases", []),
                item["market"],
                item["assetType"],
                item["active"],
                item.get("popularity", 0),
            ]
        )
    return compressed


def write_compressed_index(output_path: Path, compressed: Sequence[Sequence[Any]]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("[\n")
        for index, item in enumerate(compressed):
            json.dump(item, handle, ensure_ascii=False, separators=(",", ":"))
            if index < len(compressed) - 1:
                handle.write(",\n")
            else:
                handle.write("\n")
        handle.write("]\n")


def load_compressed_index(index_path: Path) -> List[list]:
    with index_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise ValueError(f"Unexpected index payload type: {type(payload).__name__}")
    return payload


def filter_non_a_share_entries(items: Sequence[Sequence[Any]]) -> List[list]:
    kept: List[list] = []
    for item in items:
        if not isinstance(item, list) or len(item) < 7:
            continue
        market = str(item[6] or "").upper()
        if market in {"CN", "BSE"}:
            continue
        kept.append(list(item))
    return kept

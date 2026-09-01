# -*- coding: utf-8 -*-
"""Universe search API schemas."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class AShareUniverseItem(BaseModel):
    code: str = Field(..., description="6 位 A 股代码")
    name: str = Field(..., description="股票简称")
    exchange: str = Field(..., description="交易所 SH/SZ/BJ")
    canonical_code: str = Field(..., description="带后缀的标准代码，如 600519.SH")
    board: Optional[str] = Field(None, description="板块")
    industry: Optional[str] = Field(None, description="行业")
    active: bool = Field(True, description="是否仍在 universe 中")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "code": "600519",
            "name": "贵州茅台",
            "exchange": "SH",
            "canonical_code": "600519.SH",
            "board": "主板",
            "industry": "白酒",
            "active": True,
        }
    })


class AShareUniverseSearchResponse(BaseModel):
    query: str = Field(..., description="原始查询关键字")
    items: List[AShareUniverseItem] = Field(default_factory=list, description="匹配结果")
    total: int = Field(..., description="返回条数")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query": "茅台",
            "items": [
                {
                    "code": "600519",
                    "name": "贵州茅台",
                    "exchange": "SH",
                    "canonical_code": "600519.SH",
                    "board": "主板",
                    "industry": "白酒",
                    "active": True,
                }
            ],
            "total": 1,
        }
    })

# -*- coding: utf-8 -*-
"""Technical chart API schemas (technical-v1)."""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChartLevel(BaseModel):
    price: float
    label: str
    source: str
    date: Optional[str] = None


class ChartExtreme(BaseModel):
    price: float
    date: str


class TechnicalChartItem(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None
    amount: Optional[float] = None
    change_percent: Optional[float] = None

    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    volume_ratio: Optional[float] = None
    volume_status: Optional[str] = None
    macd_dif: Optional[float] = None
    macd_dea: Optional[float] = None
    macd_bar: Optional[float] = None
    rsi6: Optional[float] = None
    rsi12: Optional[float] = None
    rsi24: Optional[float] = None
    boll_upper: Optional[float] = None
    boll_mid: Optional[float] = None
    boll_lower: Optional[float] = None
    boll_bandwidth: Optional[float] = None
    boll_position: Optional[float] = None
    kdj_k: Optional[float] = None
    kdj_d: Optional[float] = None
    kdj_j: Optional[float] = None
    cci: Optional[float] = None
    bias5: Optional[float] = None
    bias10: Optional[float] = None
    bias20: Optional[float] = None


class TechnicalChartSummary(BaseModel):
    latest_close: Optional[float] = None
    latest_change_percent: Optional[float] = None
    latest_volume_status: Optional[str] = None
    volume_ratio: Optional[float] = None
    support_levels: List[ChartLevel] = Field(default_factory=list)
    resistance_levels: List[ChartLevel] = Field(default_factory=list)
    recent_high: Optional[ChartExtreme] = None
    recent_low: Optional[ChartExtreme] = None


class TechnicalChartResponse(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    period: str
    range_days: int
    calculation_version: str
    data_status: str
    data_source: Optional[str] = None
    updated_at: Optional[str] = None
    items: List[TechnicalChartItem] = Field(default_factory=list)
    summary: TechnicalChartSummary = Field(default_factory=TechnicalChartSummary)
    warnings: List[str] = Field(default_factory=list)

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "stock_code": "600519",
            "stock_name": "贵州茅台",
            "period": "daily",
            "range_days": 120,
            "calculation_version": "technical-v1",
            "data_status": "available",
            "data_source": "akshare",
            "updated_at": "2026-07-14T15:00:00+08:00",
            "items": [],
            "summary": {},
            "warnings": [],
        }
    })

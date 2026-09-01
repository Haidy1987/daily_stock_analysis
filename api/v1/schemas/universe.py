# -*- coding: utf-8 -*-
"""Universe search API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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
    total: int = Field(..., description="匹配总数（用于分页）")
    offset: int = Field(0, description="分页偏移")
    limit: int = Field(20, description="分页大小")

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
            "offset": 0,
            "limit": 20,
        }
    })


class AShareUniverseStatsResponse(BaseModel):
    total_count: int = Field(..., description="活跃 A 股数量")
    total_including_inactive: int = Field(..., description="含 inactive 的总数")
    sync_status: str = Field(..., description="idle | running | cooldown")
    cooldown_seconds: int = Field(..., description="手动采集冷却秒数")
    cooldown_remaining_seconds: int = Field(0, description="剩余冷却秒数")
    next_available_at: Optional[str] = Field(None, description="下次可采集时间 ISO")
    last_triggered_at: Optional[str] = None
    last_completed_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_error: Optional[str] = None
    last_report: Dict[str, Any] = Field(default_factory=dict)
    manual_only: bool = Field(True, description="当前产品语义：仅手动采集")
    auto_sync_enabled: bool = Field(False, description="后台自动同步是否开启")


class AShareUniverseManualSyncResponse(BaseModel):
    accepted: bool = Field(True, description="是否已接受手动采集任务")
    message: str = Field(..., description="提示信息")
    sync_status: str = Field("running", description="接受后的同步状态")

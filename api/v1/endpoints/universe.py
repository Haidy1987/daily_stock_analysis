# -*- coding: utf-8 -*-
"""
===================================
A 股 Universe 查询接口
===================================

职责：
1. GET /api/v1/universe/a-share/search 基于本地 universe 表搜索 A 股
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.universe import AShareUniverseItem, AShareUniverseSearchResponse
from src.repositories.a_share_universe_repo import AShareUniverseRepository
from src.services.a_share_universe.index_builder import exchange_to_suffix

router = APIRouter()


def _to_item(row) -> AShareUniverseItem:
    exchange = exchange_to_suffix(row.exchange)
    return AShareUniverseItem(
        code=row.code,
        name=row.name,
        exchange=exchange,
        canonical_code=f"{row.code}.{exchange}",
        board=row.board,
        industry=row.industry,
        active=bool(row.active),
    )


@router.get("/a-share/search", response_model=AShareUniverseSearchResponse)
async def search_a_share_universe(
    q: str = Query(..., min_length=1, description="代码前缀或名称关键字"),
    limit: int = Query(20, ge=1, le=100, description="返回条数上限"),
) -> AShareUniverseSearchResponse:
    keyword = q.strip()
    if not keyword:
        raise HTTPException(status_code=422, detail="query must not be empty")
    repo = AShareUniverseRepository()
    rows = repo.search(keyword, limit=limit)
    items = [_to_item(row) for row in rows]
    return AShareUniverseSearchResponse(query=keyword, items=items, total=len(items))

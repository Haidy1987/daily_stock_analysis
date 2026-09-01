# -*- coding: utf-8 -*-
"""
===================================
A 股 Universe 查询接口
===================================

职责：
1. GET /api/v1/universe/a-share/search 基于本地 universe 表搜索 A 股
2. GET /api/v1/universe/a-share/stats 查询采集状态与统计
3. POST /api/v1/universe/a-share/sync 手动触发采集（60 分钟冷却）
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from api.deps import get_config_dep, require_admin
from api.v1.schemas.universe import (
    AShareUniverseItem,
    AShareUniverseManualSyncResponse,
    AShareUniverseSearchResponse,
    AShareUniverseStatsResponse,
)
from src.config import Config
from src.repositories.a_share_universe_repo import AShareUniverseRepository
from src.services.a_share_universe.index_builder import exchange_to_suffix
from src.services.a_share_universe.manual_sync import (
    ManualSyncRejected,
    build_manual_sync_stats,
    reserve_manual_sync,
    run_manual_a_share_universe_sync,
    finalize_manual_sync_state_on_failure,
)

logger = logging.getLogger(__name__)

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
    q: str = Query("", description="代码前缀或名称关键字；留空则分页浏览"),
    limit: int = Query(20, ge=1, le=100, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="分页偏移"),
) -> AShareUniverseSearchResponse:
    keyword = q.strip()
    repo = AShareUniverseRepository()
    rows = repo.search(keyword, limit=limit, offset=offset, active_only=True)
    total = repo.count_search(keyword, active_only=True)
    items = [_to_item(row) for row in rows]
    return AShareUniverseSearchResponse(
        query=keyword,
        items=items,
        total=total,
        offset=offset,
        limit=limit,
    )


@router.get("/a-share/stats", response_model=AShareUniverseStatsResponse)
async def get_a_share_universe_stats(
    config: Config = Depends(get_config_dep),
) -> AShareUniverseStatsResponse:
    payload = build_manual_sync_stats(config=config)
    return AShareUniverseStatsResponse.model_validate(payload)


@router.post("/a-share/sync", response_model=AShareUniverseManualSyncResponse, status_code=202)
async def trigger_a_share_universe_manual_sync(
    background_tasks: BackgroundTasks,
    config: Config = Depends(get_config_dep),
    _admin=Depends(require_admin),
) -> AShareUniverseManualSyncResponse:
    try:
        store = reserve_manual_sync(config=config)
    except ManualSyncRejected as exc:
        status_code = 409 if exc.code == "sync_in_progress" else 429
        raise HTTPException(
            status_code=status_code,
            detail={
                "error": exc.code,
                "message": exc.message,
                "retry_after_seconds": exc.retry_after_seconds,
            },
        ) from exc

    async def _run_job() -> None:
        try:
            await run_in_threadpool(run_manual_a_share_universe_sync, config=config, store=store)
        except Exception as exc:
            logger.exception("[a-share-manual-sync] background job failed: %s", exc)
            finalize_manual_sync_state_on_failure(store, str(exc))

    background_tasks.add_task(_run_job)
    return AShareUniverseManualSyncResponse(
        accepted=True,
        message="Manual A-share sync started",
        sync_status="running",
    )

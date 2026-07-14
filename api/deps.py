# -*- coding: utf-8 -*-
"""
===================================
API 依赖注入模块
===================================

职责：
1. 提供数据库 Session 依赖
2. 提供配置依赖
3. 提供服务层依赖
4. 提供当前用户 / 管理员依赖
"""

from typing import Generator, Optional

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from src.auth import (
    COOKIE_NAME,
    AuthUser,
    get_default_admin_user_id,
    is_auth_enabled,
    resolve_session,
)
from src.storage import DatabaseManager
from src.config import get_config, Config
from src.services.system_config_service import SystemConfigService
from src.services.runtime_scheduler import RuntimeSchedulerService


def get_db() -> Generator[Session, None, None]:
    """
    获取数据库 Session 依赖
    
    使用 FastAPI 依赖注入机制，确保请求结束后自动关闭 Session
    
    Yields:
        Session: SQLAlchemy Session 对象
        
    Example:
        @router.get("/items")
        async def get_items(db: Session = Depends(get_db)):
            ...
    """
    db_manager = DatabaseManager.get_instance()
    session = db_manager.get_session()
    try:
        yield session
    finally:
        session.close()


def get_config_dep() -> Config:
    """
    获取配置依赖
    
    Returns:
        Config: 配置单例对象
    """
    return get_config()


def get_database_manager() -> DatabaseManager:
    """
    获取数据库管理器依赖
    
    Returns:
        DatabaseManager: 数据库管理器单例对象
    """
    return DatabaseManager.get_instance()


def get_system_config_service(request: Request) -> SystemConfigService:
    """Get app-lifecycle shared SystemConfigService instance."""
    service = getattr(request.app.state, "system_config_service", None)
    if service is None:
        service = SystemConfigService()
        request.app.state.system_config_service = service
    return service


def get_runtime_scheduler_service(request: Request) -> RuntimeSchedulerService:
    """Get app-lifecycle shared RuntimeSchedulerService instance."""
    service = getattr(request.app.state, "runtime_scheduler_service", None)
    if service is None:
        service = RuntimeSchedulerService()
        request.app.state.runtime_scheduler_service = service
    return service


def get_optional_user(request: Request) -> Optional[AuthUser]:
    """Resolve current user from session cookie when auth is enabled."""
    if not is_auth_enabled():
        return None
    cookie_val = request.cookies.get(COOKIE_NAME)
    if not cookie_val:
        return None
    return resolve_session(cookie_val)


def get_current_user(request: Request) -> AuthUser:
    """Require an authenticated active user when auth is enabled."""
    if not is_auth_enabled():
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Login required"},
        )
    user = get_optional_user(request)
    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "message": "Login required"},
        )
    return user


def require_admin(request: Request) -> Optional[AuthUser]:
    """
    Require admin role when auth is enabled.

    When auth is disabled (local/desktop open mode), returns None and allows access.
    """
    if not is_auth_enabled():
        return None
    user = get_current_user(request)
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "Admin required"},
        )
    return user


def get_scoped_user(request: Request) -> AuthUser:
    """
    Resolve the user that owns API data for this request.

    - Auth enabled: require a valid session (401 if missing).
    - Auth disabled: fall back to local admin (single-tenant compatibility).
    """
    if is_auth_enabled():
        return get_current_user(request)
    admin_id = get_default_admin_user_id(create_if_missing=True)
    return AuthUser(
        id=admin_id,
        username="admin",
        role="admin",
        status="active",
        session_id=0,
    )


def resolve_effective_user_id(request: Request) -> int:
    """Return the local user_id that should own/filter user-private data."""
    return int(get_scoped_user(request).id)

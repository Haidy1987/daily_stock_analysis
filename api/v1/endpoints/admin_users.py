# -*- coding: utf-8 -*-
"""Admin user management endpoints."""

from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, Response

from api.deps import require_admin
from api.v1.schemas.admin_users import (
    AdminUserListResponse,
    AdminUserSummary,
    CreateAdminUserRequest,
    ResetAdminUserPasswordRequest,
    UpdateAdminUserRequest,
)
from src.auth import (
    AuthUser,
    DEFAULT_ADMIN_USERNAME,
    _validate_password,
    get_client_ip,
    hash_password,
    is_multi_user_mode,
    record_audit,
    revoke_all_sessions,
    _write_credential_file,
)
from src.repositories.user_repo import UserRepository
from src.storage import UserRecord

logger = logging.getLogger(__name__)

router = APIRouter()


def _user_agent(request: Request) -> Optional[str]:
    ua = request.headers.get("User-Agent")
    return ua[:512] if ua else None


def _iso(value) -> Optional[str]:
    if value is None:
        return None
    try:
        return value.isoformat()
    except Exception:
        return str(value)


def _to_summary(row: UserRecord) -> AdminUserSummary:
    return AdminUserSummary(
        id=int(row.id),
        username=row.username,
        email=row.email,
        role=row.role,
        status=row.status,
        createdAt=_iso(row.created_at),
        updatedAt=_iso(row.updated_at),
        lastLoginAt=_iso(row.last_login_at),
    )


def _error(status_code: int, error: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": error, "message": message})


def _would_remove_last_admin(
    repo: UserRepository,
    target: UserRecord,
    *,
    new_role=None,
    new_status=None,
) -> bool:
    role = new_role if new_role is not None else target.role
    status = new_status if new_status is not None else target.status
    if target.role != "admin" or target.status != "active":
        return False
    if role == "admin" and status == "active":
        return False
    return repo.count_admins(status="active") <= 1


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="List users",
)
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100, alias="pageSize"),
    search: Optional[str] = Query(None),
    role: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    admin: AuthUser = Depends(require_admin),
):
    _ = admin
    repo = UserRepository()
    rows, total = repo.list_users(
        page=page,
        page_size=page_size,
        search=search,
        role=role,
        status=status,
    )
    return AdminUserListResponse(
        items=[_to_summary(row) for row in rows],
        total=total,
        page=page,
        pageSize=page_size,
    )


@router.post(
    "/users",
    response_model=AdminUserSummary,
    summary="Create user",
)
def create_user(
    request: Request,
    body: CreateAdminUserRequest,
    admin: AuthUser = Depends(require_admin),
):
    if not is_multi_user_mode():
        return _error(
            409,
            "auth_mode_single_admin",
            "当前 AUTH_MODE=single_admin，请先切换为 multi_user 后再创建用户",
        )
    username = (body.username or "").strip()
    if not username:
        return _error(400, "invalid_username", "用户名不能为空")
    err = _validate_password(body.password)
    if err:
        return _error(400, "invalid_password", err)
    if body.role not in ("admin", "user"):
        return _error(400, "invalid_role", "角色无效")

    repo = UserRepository()
    if repo.get_user_by_username(username) is not None:
        return _error(409, "username_taken", "用户名已存在")

    row = repo.create_user(
        username=username,
        password_hash=hash_password(body.password),
        role=body.role,
        status="active",
        email=(body.email or None),
    )
    repo.ensure_preferences(row.id)
    actor_id = admin.id if admin is not None else None
    record_audit(
        "create_user",
        actor_user_id=actor_id,
        target_type="user",
        target_id=str(row.id),
        ip_address=get_client_ip(request),
        user_agent=_user_agent(request),
        detail_json=json.dumps({"username": username, "role": body.role}, ensure_ascii=False),
    )
    return _to_summary(row)


@router.patch(
    "/users/{user_id}",
    response_model=AdminUserSummary,
    summary="Update user",
)
def update_user(
    request: Request,
    user_id: int,
    body: UpdateAdminUserRequest,
    admin: AuthUser = Depends(require_admin),
):
    repo = UserRepository()
    target = repo.get_user_by_id(user_id)
    if target is None:
        return _error(404, "user_not_found", "用户不存在")

    fields = {}
    if body.role is not None:
        fields["role"] = body.role
    if body.status is not None:
        fields["status"] = body.status
    if body.email is not None:
        fields["email"] = body.email.strip() or None

    if not fields:
        return _to_summary(target)

    if fields.get("role") == "admin" and target.role != "admin" and not is_multi_user_mode():
        return _error(
            409,
            "auth_mode_single_admin",
            "当前 AUTH_MODE=single_admin，请先切换为 multi_user 后再提升管理员",
        )

    if _would_remove_last_admin(
        repo,
        target,
        new_role=fields.get("role"),
        new_status=fields.get("status"),
    ):
        return _error(409, "last_admin", "不能降级或禁用最后一个可用管理员")

    updated = repo.update_user(user_id, fields)
    if updated is None:
        return _error(404, "user_not_found", "用户不存在")

    if fields.get("status") == "disabled" or (
        target.role == "admin" and fields.get("role") == "user"
    ):
        revoke_all_sessions(user_id)

    actor_id = admin.id if admin is not None else None
    record_audit(
        "update_user",
        actor_user_id=actor_id,
        target_type="user",
        target_id=str(user_id),
        ip_address=get_client_ip(request),
        user_agent=_user_agent(request),
        detail_json=json.dumps(fields, ensure_ascii=False),
    )
    return _to_summary(updated)


@router.delete(
    "/users/{user_id}",
    summary="Disable user (soft delete)",
)
def delete_user(
    request: Request,
    user_id: int,
    admin: AuthUser = Depends(require_admin),
):
    repo = UserRepository()
    target = repo.get_user_by_id(user_id)
    if target is None:
        return _error(404, "user_not_found", "用户不存在")

    if _would_remove_last_admin(repo, target, new_status="disabled"):
        return _error(409, "last_admin", "不能删除最后一个可用管理员")

    if admin is not None and int(admin.id) == int(user_id):
        return _error(409, "cannot_delete_self", "不能删除当前登录的管理员账号")

    updated = repo.update_user(user_id, {"status": "disabled"})
    if updated is None:
        return _error(404, "user_not_found", "用户不存在")
    revoke_all_sessions(user_id)

    actor_id = admin.id if admin is not None else None
    record_audit(
        "disable_user",
        actor_user_id=actor_id,
        target_type="user",
        target_id=str(user_id),
        ip_address=get_client_ip(request),
        user_agent=_user_agent(request),
        detail_json=json.dumps({"username": target.username}, ensure_ascii=False),
    )
    return Response(status_code=204)


@router.post(
    "/users/{user_id}/reset-password",
    summary="Reset user password",
)
def reset_user_password(
    request: Request,
    user_id: int,
    body: ResetAdminUserPasswordRequest,
    admin: AuthUser = Depends(require_admin),
):
    err = _validate_password(body.new_password)
    if err:
        return _error(400, "invalid_password", err)

    repo = UserRepository()
    target = repo.get_user_by_id(user_id)
    if target is None:
        return _error(404, "user_not_found", "用户不存在")

    content = hash_password(body.new_password)
    updated = repo.update_user(user_id, {"password_hash": content})
    if updated is None:
        return _error(404, "user_not_found", "用户不存在")
    revoke_all_sessions(user_id)

    if target.username == DEFAULT_ADMIN_USERNAME or target.role == "admin":
        try:
            file_err = _write_credential_file(content)
            if file_err:
                logger.warning("Failed to sync legacy admin password file: %s", file_err)
        except Exception as exc:
            logger.warning("Failed to sync legacy admin password file: %s", exc)

    actor_id = admin.id if admin is not None else None
    record_audit(
        "reset_password",
        actor_user_id=actor_id,
        target_type="user",
        target_id=str(user_id),
        ip_address=get_client_ip(request),
        user_agent=_user_agent(request),
    )
    return Response(status_code=204)


@router.post(
    "/users/{user_id}/revoke-sessions",
    summary="Revoke all sessions for a user",
)
def revoke_user_sessions(
    request: Request,
    user_id: int,
    admin: AuthUser = Depends(require_admin),
):
    repo = UserRepository()
    target = repo.get_user_by_id(user_id)
    if target is None:
        return _error(404, "user_not_found", "用户不存在")

    count = revoke_all_sessions(user_id)
    actor_id = admin.id if admin is not None else None
    record_audit(
        "revoke_sessions",
        actor_user_id=actor_id,
        target_type="user",
        target_id=str(user_id),
        ip_address=get_client_ip(request),
        user_agent=_user_agent(request),
        detail_json=json.dumps({"revoked": count}, ensure_ascii=False),
    )
    return Response(status_code=204)

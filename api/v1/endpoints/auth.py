# -*- coding: utf-8 -*-
"""Authentication endpoints for Web multi-user login."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from api.deps import get_current_user, get_system_config_service
from src.auth import (
    COOKIE_NAME,
    DEFAULT_ADMIN_USERNAME,
    SESSION_MAX_AGE_HOURS_DEFAULT,
    AuthUser,
    authenticate_user,
    change_password,
    check_rate_limit,
    clear_rate_limit,
    create_session,
    get_client_ip,
    has_stored_password,
    is_auth_enabled,
    is_password_changeable,
    is_password_set,
    mark_login_success,
    record_audit,
    record_login_failure,
    refresh_auth_state,
    resolve_session,
    revoke_all_sessions,
    revoke_session_token,
    rotate_session_secret,
    set_initial_password,
    verify_stored_password,
)
from src.config import Config, setup_env
from src.core.config_manager import ConfigManager

logger = logging.getLogger(__name__)

router = APIRouter()


class LoginRequest(BaseModel):
    """Login request body. For first-time setup use password + password_confirm."""

    model_config = {"populate_by_name": True}

    username: str = Field(default="", description="Username (defaults to admin)")
    password: str = Field(default="", description="Password")
    password_confirm: str | None = Field(default=None, alias="passwordConfirm", description="Confirm (first-time)")


class ChangePasswordRequest(BaseModel):
    """Change password request body."""

    model_config = {"populate_by_name": True}

    current_password: str = Field(default="", alias="currentPassword")
    new_password: str = Field(default="", alias="newPassword")
    new_password_confirm: str = Field(default="", alias="newPasswordConfirm")


class AuthSettingsRequest(BaseModel):
    """Update auth enablement and initial password settings."""

    model_config = {"populate_by_name": True}

    auth_enabled: bool = Field(alias="authEnabled")
    password: str = Field(default="")
    password_confirm: str | None = Field(default=None, alias="passwordConfirm")
    current_password: str = Field(default="", alias="currentPassword")


def _cookie_params(request: Request) -> dict:
    """Build cookie params including Secure based on request."""
    secure = False
    if os.getenv("TRUST_X_FORWARDED_FOR", "false").lower() == "true":
        proto = request.headers.get("X-Forwarded-Proto", "").lower()
        secure = proto == "https"
    else:
        secure = request.url.scheme == "https"

    try:
        max_age_hours = int(os.getenv("ADMIN_SESSION_MAX_AGE_HOURS", str(SESSION_MAX_AGE_HOURS_DEFAULT)))
    except ValueError:
        max_age_hours = SESSION_MAX_AGE_HOURS_DEFAULT
    max_age = max_age_hours * 3600

    return {
        "httponly": True,
        "samesite": "lax",
        "secure": secure,
        "path": "/",
        "max_age": max_age,
    }


def _apply_auth_enabled(enabled: bool, request: Request | None = None) -> bool:
    """Persist auth toggle to .env and reload runtime config."""
    manager_applied = False
    if request is not None:
        try:
            service = get_system_config_service(request)
            service.apply_simple_updates(
                updates=[("ADMIN_AUTH_ENABLED", "true" if enabled else "false")],
                mask_token="******",
            )
            manager_applied = True
        except Exception as exc:
            logger.warning(
                "Failed to apply auth toggle via shared SystemConfigService, falling back: %s",
                exc,
                exc_info=True,
            )
            manager_applied = False

    if not manager_applied:
        try:
            manager = ConfigManager()
            manager.apply_updates(
                updates=[("ADMIN_AUTH_ENABLED", "true" if enabled else "false")],
                sensitive_keys=set(),
                mask_token="******",
            )
            manager_applied = True
        except Exception as exc:
            logger.error("Failed to apply auth toggle via ConfigManager: %s", exc, exc_info=True)
            manager_applied = False

    if not manager_applied:
        return False

    Config.reset_instance()
    setup_env(override=True)
    refresh_auth_state()
    return True


def _password_set_for_response(auth_enabled: bool) -> bool:
    """Avoid exposing stored-password state when auth is disabled."""
    return is_password_set() if auth_enabled else False


def _set_session_cookie(response: Response, session_value: str, request: Request) -> None:
    """Attach the session cookie to a response."""
    params = _cookie_params(request)
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_value,
        httponly=params["httponly"],
        samesite=params["samesite"],
        secure=params["secure"],
        path=params["path"],
        max_age=params["max_age"],
    )


def _user_agent(request: Request) -> str | None:
    ua = request.headers.get("User-Agent")
    if not ua:
        return None
    return ua[:512]


def _current_user_dict(user: AuthUser | None) -> dict | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "status": user.status,
    }


def _get_auth_status_dict(request: Request | None = None) -> dict:
    """Helper to build consistent auth status response body."""
    auth_enabled = is_auth_enabled()
    logged_in = False
    current_user = None
    if auth_enabled and request:
        cookie_val = request.cookies.get(COOKIE_NAME)
        user = resolve_session(cookie_val) if cookie_val else None
        logged_in = user is not None
        current_user = _current_user_dict(user)

    if auth_enabled:
        setup_state = "enabled"
    elif has_stored_password():
        setup_state = "password_retained"
    else:
        setup_state = "no_password"

    return {
        "authEnabled": auth_enabled,
        "loggedIn": logged_in,
        "passwordSet": _password_set_for_response(auth_enabled),
        "passwordChangeable": is_password_changeable() if auth_enabled else False,
        "setupState": setup_state,
        "currentUser": current_user,
    }


@router.get(
    "/status",
    summary="Get auth status",
    description="Returns whether auth is enabled and if the current request is logged in.",
)
async def auth_status(request: Request):
    """Return authEnabled, loggedIn, passwordSet, passwordChangeable, setupState without requiring auth."""
    return _get_auth_status_dict(request)


@router.get(
    "/me",
    summary="Get current user",
    description="Return the authenticated user from the server-side session.",
)
async def auth_me(user: AuthUser = Depends(get_current_user)):
    """Return current user identity."""
    return _current_user_dict(user)


@router.post(
    "/settings",
    summary="Update auth settings",
    description=(
        "Enable or disable password login. When enabling without an existing password, "
        "password + passwordConfirm are required. When re-enabling with a stored password, "
        "currentPassword is required. Only admins may change settings when already logged in."
    ),
)
async def auth_update_settings(request: Request, body: AuthSettingsRequest):
    """Manage auth enablement from the settings page."""
    # When auth is already enabled and a session exists, only admin may change settings.
    # Requests without a session still fall through to currentPassword / first-time paths
    # (HTTP middleware normally requires a session when auth is on).
    if is_auth_enabled():
        cookie_val = request.cookies.get(COOKIE_NAME)
        actor = resolve_session(cookie_val) if cookie_val else None
        if actor is not None and actor.role != "admin":
            return JSONResponse(
                status_code=403,
                content={"error": "forbidden", "message": "Admin required"},
            )

    target_enabled = body.auth_enabled
    current_enabled = is_auth_enabled()
    stored_password_exists = has_stored_password()

    password = (body.password or "").strip()
    confirm = (body.password_confirm or "").strip()
    current_password = (body.current_password or "").strip()

    if target_enabled:
        if password or confirm:
            if stored_password_exists:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "password_already_set",
                        "message": "已存在管理员密码，请启用认证后通过修改密码功能更新",
                    },
                )
            if not password:
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_required", "message": "请输入要设置的管理员密码"},
                )
            if password != confirm:
                return JSONResponse(
                    status_code=400,
                    content={"error": "password_mismatch", "message": "两次输入的密码不一致"},
                )
            if has_stored_password():
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "password_already_set",
                        "message": "已存在管理员密码，请启用认证后通过修改密码功能更新",
                    },
                )
            err = set_initial_password(password)
            if err:
                return JSONResponse(
                    status_code=400,
                    content={"error": "invalid_password", "message": err},
                )
        elif not stored_password_exists:
            return JSONResponse(
                status_code=400,
                content={"error": "password_required", "message": "开启密码登录前请先设置密码"},
            )
        else:
            cookie_val = request.cookies.get(COOKIE_NAME)
            is_valid_session = bool(cookie_val and resolve_session(cookie_val))

            if not is_valid_session:
                if not current_password:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "current_required", "message": "重新开启认证前请输入当前密码"},
                    )
                ip = get_client_ip(request)
                if not check_rate_limit(ip):
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "rate_limited",
                            "message": "Too many failed attempts. Please try again later.",
                        },
                    )
                if not verify_stored_password(current_password):
                    record_login_failure(ip)
                    return JSONResponse(
                        status_code=401,
                        content={"error": "invalid_password", "message": "当前密码错误"},
                    )
                clear_rate_limit(ip)
    else:
        if current_enabled:
            cookie_val = request.cookies.get(COOKIE_NAME)
            is_valid_session = bool(cookie_val and resolve_session(cookie_val))

            if not is_valid_session:
                if not current_password:
                    return JSONResponse(
                        status_code=400,
                        content={"error": "current_required", "message": "关闭认证前请输入当前密码"},
                    )
                ip = get_client_ip(request)
                if not check_rate_limit(ip):
                    return JSONResponse(
                        status_code=429,
                        content={
                            "error": "rate_limited",
                            "message": "Too many failed attempts. Please try again later.",
                        },
                    )
                if not verify_stored_password(current_password):
                    record_login_failure(ip)
                    return JSONResponse(
                        status_code=401,
                        content={"error": "invalid_password", "message": "当前密码错误"},
                    )
                clear_rate_limit(ip)

    if target_enabled != current_enabled:
        if not _apply_auth_enabled(target_enabled, request=request):
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to update auth settings"},
            )
        if not rotate_session_secret():
            rollback_ok = _apply_auth_enabled(current_enabled, request=request)
            if not rollback_ok:
                logger.error("Failed to roll back auth state after session secret rotation failure")
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to rotate session secret"},
            )
    else:
        if not _apply_auth_enabled(target_enabled, request=request):
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to update auth settings"},
            )

    if target_enabled:
        ip = get_client_ip(request)
        session_val = create_session(ip_address=ip, user_agent=_user_agent(request))
        if not session_val:
            rollback_ok = _apply_auth_enabled(current_enabled, request=request)
            if not rollback_ok:
                logger.error("Failed to roll back auth state after session creation failure")
            return JSONResponse(
                status_code=500,
                content={"error": "internal_error", "message": "Failed to create session"},
            )
        content = _get_auth_status_dict(request)
        content["loggedIn"] = True
        user = resolve_session(session_val)
        content["currentUser"] = _current_user_dict(user)
        resp = JSONResponse(content=content)
        _set_session_cookie(resp, session_val, request)
        return resp

    resp = JSONResponse(content=_get_auth_status_dict(request))
    resp.delete_cookie(key=COOKIE_NAME, path="/")
    return resp


@router.post(
    "/login",
    summary="Login or set initial password",
    description="Verify password and set session cookie. If password not set yet, accepts password+passwordConfirm.",
)
async def auth_login(request: Request, body: LoginRequest):
    """Verify password or set initial password, set cookie on success. Returns 401 or 429 on failure."""
    if not is_auth_enabled():
        return JSONResponse(
            status_code=400,
            content={"error": "auth_disabled", "message": "Authentication is not configured"},
        )

    password = (body.password or "").strip()
    username = (body.username or "").strip() or DEFAULT_ADMIN_USERNAME
    if not password:
        return JSONResponse(
            status_code=400,
            content={"error": "password_required", "message": "请输入密码"},
        )

    ip = get_client_ip(request)
    ua = _user_agent(request)
    if not check_rate_limit(ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "message": "Too many failed attempts. Please try again later.",
            },
        )

    password_set = is_password_set()

    if not password_set:
        if username != DEFAULT_ADMIN_USERNAME:
            record_login_failure(ip)
            record_audit(
                "login_failed",
                ip_address=ip,
                user_agent=ua,
                detail_json='{"reason":"setup_requires_admin"}',
            )
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_username", "message": "首次设置仅支持管理员账号"},
            )
        confirm = (body.password_confirm or "").strip()
        if password != confirm:
            record_login_failure(ip)
            record_audit("login_failed", ip_address=ip, user_agent=ua, detail_json='{"reason":"mismatch"}')
            return JSONResponse(
                status_code=400,
                content={"error": "password_mismatch", "message": "Passwords do not match"},
            )
        err = set_initial_password(password)
        if err:
            record_login_failure(ip)
            return JSONResponse(
                status_code=400,
                content={"error": "invalid_password", "message": err},
            )
        user = authenticate_user(DEFAULT_ADMIN_USERNAME, password)
    else:
        user = authenticate_user(username, password)
        if user is None:
            record_login_failure(ip)
            record_audit(
                "login_failed",
                ip_address=ip,
                user_agent=ua,
                target_type="user",
                target_id=username,
            )
            return JSONResponse(
                status_code=401,
                content={"error": "invalid_password", "message": "密码错误"},
            )

    if user is None:
        record_login_failure(ip)
        return JSONResponse(
            status_code=401,
            content={"error": "invalid_password", "message": "密码错误"},
        )

    clear_rate_limit(ip)
    session_val = create_session(user.id, ip_address=ip, user_agent=ua)
    if not session_val:
        return JSONResponse(
            status_code=500,
            content={"error": "internal_error", "message": "Failed to create session"},
        )

    mark_login_success(user.id)
    record_audit(
        "login_success",
        actor_user_id=user.id,
        ip_address=ip,
        user_agent=ua,
        target_type="user",
        target_id=str(user.id),
    )

    resp = JSONResponse(content={"ok": True})
    _set_session_cookie(resp, session_val, request)
    return resp


@router.post(
    "/change-password",
    summary="Change password",
    description="Change password. Requires valid session. Revokes all sessions for the user.",
)
async def auth_change_password(
    request: Request,
    body: ChangePasswordRequest,
    user: AuthUser = Depends(get_current_user),
):
    """Change password. Requires login."""
    if not is_password_changeable():
        return JSONResponse(
            status_code=400,
            content={"error": "not_changeable", "message": "Password cannot be changed via web"},
        )

    current = (body.current_password or "").strip()
    new_pwd = (body.new_password or "").strip()
    new_confirm = (body.new_password_confirm or "").strip()

    if not current:
        return JSONResponse(
            status_code=400,
            content={"error": "current_required", "message": "请输入当前密码"},
        )
    if new_pwd != new_confirm:
        return JSONResponse(
            status_code=400,
            content={"error": "password_mismatch", "message": "两次输入的新密码不一致"},
        )

    err = change_password(current, new_pwd, user_id=user.id)
    if err:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_password", "message": err},
        )

    record_audit(
        "change_password",
        actor_user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=_user_agent(request),
        target_type="user",
        target_id=str(user.id),
    )

    # Issue a fresh session so the caller stays logged in after revoke-all
    session_val = create_session(
        user.id,
        ip_address=get_client_ip(request),
        user_agent=_user_agent(request),
    )
    resp = Response(status_code=204)
    if session_val:
        _set_session_cookie(resp, session_val, request)
    else:
        resp.delete_cookie(key=COOKIE_NAME, path="/")
    return resp


@router.post(
    "/logout",
    summary="Logout",
    description="Revoke current session and clear cookie.",
)
async def auth_logout(request: Request):
    """Revoke current session cookie."""
    cookie_val = request.cookies.get(COOKIE_NAME)
    user = resolve_session(cookie_val) if cookie_val else None
    if cookie_val:
        revoke_session_token(cookie_val)
    if user is not None:
        record_audit(
            "logout",
            actor_user_id=user.id,
            ip_address=get_client_ip(request),
            user_agent=_user_agent(request),
            target_type="user",
            target_id=str(user.id),
        )
    resp = Response(status_code=204)
    resp.delete_cookie(key=COOKIE_NAME, path="/")
    return resp


@router.post(
    "/logout-all",
    summary="Logout all devices",
    description="Revoke all sessions for the current user.",
)
async def auth_logout_all(request: Request, user: AuthUser = Depends(get_current_user)):
    """Revoke all sessions for the authenticated user."""
    revoke_all_sessions(user.id)
    record_audit(
        "logout_all",
        actor_user_id=user.id,
        ip_address=get_client_ip(request),
        user_agent=_user_agent(request),
        target_type="user",
        target_id=str(user.id),
    )
    resp = Response(status_code=204)
    resp.delete_cookie(key=COOKIE_NAME, path="/")
    return resp

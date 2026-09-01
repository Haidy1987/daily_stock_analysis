# -*- coding: utf-8 -*-
"""Shared helpers for auth-aware integration tests."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

import src.auth as auth

_AUTH_ENV_KEYS = ("ADMIN_AUTH_ENABLED", "AUTH_MODE")


def reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def clear_auth_env_keys() -> None:
    for key in _AUTH_ENV_KEYS:
        os.environ.pop(key, None)
    reset_auth_globals()


def ensure_default_user_id() -> int:
    return auth.get_default_admin_user_id(create_if_missing=True)


def make_http_request(cookies: dict[str, str] | None = None) -> SimpleNamespace:
    """Minimal Request stand-in for endpoint unit tests."""
    return SimpleNamespace(
        cookies=cookies or {},
        state=SimpleNamespace(),
        app=SimpleNamespace(state=SimpleNamespace()),
    )


def make_admin_user(**overrides: Any) -> SimpleNamespace:
    payload = {
        "id": ensure_default_user_id(),
        "username": "admin",
        "role": "admin",
        "status": "active",
        "session_id": 0,
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)

# -*- coding: utf-8 -*-
"""Admin user management API tests."""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import src.auth as auth
from api.v1.endpoints import admin_users, auth as auth_endpoint
from api.v1.schemas.admin_users import (
    CreateAdminUserRequest,
    ResetAdminUserPasswordRequest,
    UpdateAdminUserRequest,
)
from src.config import Config
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class AdminUsersApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.env_path = self.data_dir / ".env"
        self.env_path.write_text(
            "STOCK_LIST=600519\nGEMINI_API_KEY=test\nADMIN_AUTH_ENABLED=true\n",
            encoding="utf-8",
        )
        os.environ["ENV_FILE"] = str(self.env_path)
        os.environ["DATABASE_PATH"] = str(self.data_dir / "test.db")
        Config.reset_instance()
        DatabaseManager.reset_instance()

        self.auth_patcher = patch.object(auth, "_is_auth_enabled_from_env", return_value=True)
        self.data_dir_patcher = patch.object(auth, "_get_data_dir", return_value=self.data_dir)
        self.auth_patcher.start()
        self.data_dir_patcher.start()
        auth._auth_enabled = True

    def tearDown(self) -> None:
        self.auth_patcher.stop()
        self.data_dir_patcher.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("ENV_FILE", None)
        os.environ.pop("DATABASE_PATH", None)
        self.temp_dir.cleanup()

    @staticmethod
    def _request(cookies=None):
        return SimpleNamespace(
            headers={"User-Agent": "pytest"},
            url=SimpleNamespace(scheme="http"),
            cookies=cookies or {},
            client=SimpleNamespace(host="127.0.0.1"),
        )

    def _login(self, *, username: str = "admin", password: str = "adminpass") -> str:
        kwargs = {"password": password}
        if username == "admin" and not auth.is_password_set():
            kwargs["passwordConfirm"] = password
        if username != "admin":
            kwargs["username"] = username
        response = asyncio.run(
            auth_endpoint.auth_login(
                self._request(),
                auth_endpoint.LoginRequest(**kwargs),
            )
        )
        self.assertEqual(response.status_code, 200)
        return response.headers["set-cookie"].split("dsa_session=", 1)[1].split(";", 1)[0]

    def _admin_user(self) -> auth.AuthUser:
        cookie = self._login()
        user = auth.resolve_session(cookie)
        self.assertIsNotNone(user)
        return user

    def _create_plain_user(self, username: str = "alice", password: str = "alicepass") -> auth.AuthUser:
        from fastapi.responses import JSONResponse

        admin = self._admin_user()
        created = admin_users.create_user(
            self._request(),
            CreateAdminUserRequest(username=username, password=password, role="user"),
            admin=admin,
        )
        if isinstance(created, JSONResponse):
            self.fail(f"create_user failed: {created.body}")
        return auth.AuthUser(
            id=created.id,
            username=created.username,
            role=created.role,
            status=created.status,
            session_id=0,
        )

    def test_admin_can_list_and_create_users(self) -> None:
        admin = self._admin_user()
        listed = admin_users.list_users(
            page=1,
            page_size=20,
            search=None,
            role=None,
            status=None,
            admin=admin,
        )
        self.assertGreaterEqual(listed.total, 1)
        payload = listed.model_dump(by_alias=True)
        self.assertNotIn("password_hash", json.dumps(payload))

        created = admin_users.create_user(
            self._request(),
            CreateAdminUserRequest(username="bob", password="bobpass1", role="user"),
            admin=admin,
        )
        self.assertEqual(created.username, "bob")
        self.assertEqual(created.role, "user")
        self.assertNotIn("password", created.model_dump())

    def test_user_cannot_access_admin_api(self) -> None:
        self._create_plain_user()
        user_cookie = self._login(username="alice", password="alicepass")
        alice = auth.resolve_session(user_cookie)
        self.assertEqual(alice.role, "user")

        from fastapi import HTTPException

        from api.deps import require_admin

        with self.assertRaises(HTTPException) as ctx:
            require_admin(
                SimpleNamespace(
                    headers={},
                    cookies={auth.COOKIE_NAME: user_cookie},
                    client=SimpleNamespace(host="127.0.0.1"),
                    url=SimpleNamespace(scheme="http"),
                )
            )
        self.assertEqual(ctx.exception.status_code, 403)

    def test_last_admin_protection_and_disable(self) -> None:
        admin = self._admin_user()
        alice = self._create_plain_user()

        conflict = admin_users.update_user(
            self._request(),
            admin.id,
            UpdateAdminUserRequest(role="user"),
            admin=admin,
        )
        self.assertEqual(conflict.status_code, 409)

        disabled = admin_users.delete_user(self._request(), alice.id, admin=admin)
        self.assertEqual(disabled.status_code, 204)
        repo = auth._get_user_repo()
        self.assertEqual(repo.get_user_by_id(alice.id).status, "disabled")

    def test_reset_password_revokes_sessions_without_returning_secret(self) -> None:
        admin = self._admin_user()
        alice = self._create_plain_user()
        alice_cookie = self._login(username="alice", password="alicepass")
        self.assertIsNotNone(auth.resolve_session(alice_cookie))

        result = admin_users.reset_user_password(
            self._request(),
            alice.id,
            ResetAdminUserPasswordRequest(newPassword="newpass1"),
            admin=admin,
        )
        self.assertEqual(result.status_code, 204)
        self.assertIsNone(auth.resolve_session(alice_cookie))

        new_cookie = self._login(username="alice", password="newpass1")
        self.assertIsNotNone(auth.resolve_session(new_cookie))

    def test_single_admin_mode_blocks_create_user(self) -> None:
        admin = self._admin_user()
        with patch.dict(os.environ, {"AUTH_MODE": "single_admin"}, clear=False):
            result = admin_users.create_user(
                self._request(),
                CreateAdminUserRequest(username="blocked", password="blocked1", role="user"),
                admin=admin,
            )
        self.assertEqual(result.status_code, 409)
        self.assertIn(b"single_admin", result.body)


if __name__ == "__main__":
    unittest.main()

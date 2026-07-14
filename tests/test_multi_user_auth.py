# -*- coding: utf-8 -*-
"""Multi-user auth core tests: roles, disable, logout-all, /me, admin gate."""

from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import src.auth as auth
from api.deps import require_admin
from api.v1.endpoints import auth as auth_endpoint
from src.config import Config
from src.storage import DatabaseManager


def _reset_auth_globals() -> None:
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


class MultiUserAuthCoreTestCase(unittest.TestCase):
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

    def _login_admin(self, password: str = "adminpass") -> str:
        response = asyncio.run(
            auth_endpoint.auth_login(
                self._request(),
                auth_endpoint.LoginRequest(password=password, passwordConfirm=password),
            )
        )
        self.assertEqual(response.status_code, 200)
        return response.headers["set-cookie"].split("dsa_session=", 1)[1].split(";", 1)[0]

    def _create_user(self, username: str, password: str, role: str = "user") -> auth.AuthUser:
        repo = auth._get_user_repo()
        row = repo.create_user(
            username=username,
            password_hash=auth.hash_password(password),
            role=role,
            status="active",
        )
        return auth.AuthUser(
            id=row.id,
            username=row.username,
            role=row.role,
            status=row.status,
            session_id=0,
        )

    def test_auth_me_returns_current_user(self) -> None:
        cookie = self._login_admin()
        user = auth.resolve_session(cookie)
        self.assertIsNotNone(user)
        payload = asyncio.run(auth_endpoint.auth_me(user=user))
        self.assertEqual(payload["username"], "admin")
        self.assertEqual(payload["role"], "admin")
        self.assertNotIn("password", payload)
        self.assertNotIn("password_hash", payload)

    def test_user_and_admin_independent_sessions(self) -> None:
        admin_cookie = self._login_admin()
        self._create_user("alice", "alicepass")
        user_login = asyncio.run(
            auth_endpoint.auth_login(
                self._request(),
                auth_endpoint.LoginRequest(username="alice", password="alicepass"),
            )
        )
        self.assertEqual(user_login.status_code, 200)
        user_cookie = user_login.headers["set-cookie"].split("dsa_session=", 1)[1].split(";", 1)[0]

        admin = auth.resolve_session(admin_cookie)
        alice = auth.resolve_session(user_cookie)
        self.assertEqual(admin.username, "admin")
        self.assertEqual(alice.username, "alice")
        self.assertEqual(alice.role, "user")

    def test_disabled_user_cannot_login_or_use_session(self) -> None:
        self._login_admin()
        alice = self._create_user("alice", "alicepass")
        login = asyncio.run(
            auth_endpoint.auth_login(
                self._request(),
                auth_endpoint.LoginRequest(username="alice", password="alicepass"),
            )
        )
        cookie = login.headers["set-cookie"].split("dsa_session=", 1)[1].split(";", 1)[0]
        self.assertTrue(auth.verify_session(cookie))

        auth._get_user_repo().update_user(alice.id, {"status": "disabled"})
        self.assertFalse(auth.verify_session(cookie))

        again = asyncio.run(
            auth_endpoint.auth_login(
                self._request(),
                auth_endpoint.LoginRequest(username="alice", password="alicepass"),
            )
        )
        self.assertEqual(again.status_code, 401)

    def test_logout_all_revokes_other_sessions(self) -> None:
        cookie1 = self._login_admin("adminpass")
        user = auth.resolve_session(cookie1)
        cookie2 = auth.create_session(user.id)
        self.assertTrue(auth.verify_session(cookie1))
        self.assertTrue(auth.verify_session(cookie2))

        response = asyncio.run(
            auth_endpoint.auth_logout_all(self._request(cookies={"dsa_session": cookie1}), user=user)
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(auth.verify_session(cookie1))
        self.assertFalse(auth.verify_session(cookie2))

    def test_change_password_revokes_old_sessions(self) -> None:
        cookie1 = self._login_admin("oldpass1")
        user = auth.resolve_session(cookie1)
        cookie2 = auth.create_session(user.id)

        response = asyncio.run(
            auth_endpoint.auth_change_password(
                self._request(cookies={"dsa_session": cookie1}),
                auth_endpoint.ChangePasswordRequest(
                    currentPassword="oldpass1",
                    newPassword="newpass1",
                    newPasswordConfirm="newpass1",
                ),
                user=user,
            )
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(auth.verify_session(cookie1))
        self.assertFalse(auth.verify_session(cookie2))
        # Fresh cookie issued on response
        new_cookie = response.headers["set-cookie"].split("dsa_session=", 1)[1].split(";", 1)[0]
        self.assertTrue(auth.verify_session(new_cookie))

    def test_require_admin_rejects_user_role(self) -> None:
        self._login_admin()
        alice = self._create_user("alice", "alicepass")
        cookie = auth.create_session(alice.id)
        request = self._request(cookies={"dsa_session": cookie})
        with self.assertRaises(Exception) as ctx:
            require_admin(request)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_require_admin_allows_admin(self) -> None:
        cookie = self._login_admin()
        request = self._request(cookies={"dsa_session": cookie})
        admin = require_admin(request)
        self.assertEqual(admin.role, "admin")

    def test_status_includes_current_user(self) -> None:
        cookie = self._login_admin()
        data = asyncio.run(auth_endpoint.auth_status(self._request(cookies={"dsa_session": cookie})))
        self.assertTrue(data["loggedIn"])
        self.assertEqual(data["currentUser"]["username"], "admin")


if __name__ == "__main__":
    unittest.main()

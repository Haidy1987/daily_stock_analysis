# -*- coding: utf-8 -*-
"""Unit tests for src.auth module."""

import hashlib
import os
import secrets
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import src.auth as auth
from src.config import Config
from src.storage import DatabaseManager, utc_naive_now


def _reset_auth_globals() -> None:
    """Reset auth module globals for test isolation."""
    auth._auth_enabled = None
    auth._session_secret = None
    auth._password_hash_salt = None
    auth._password_hash_stored = None
    auth._rate_limit = {}


def _reset_db(data_dir: Path) -> None:
    os.environ["DATABASE_PATH"] = str(data_dir / "test.db")
    Config.reset_instance()
    DatabaseManager.reset_instance()


class AuthValidationTestCase(unittest.TestCase):
    """Test password validation."""

    def setUp(self) -> None:
        _reset_auth_globals()

    def test_validate_password_empty(self) -> None:
        self.assertIsNotNone(auth._validate_password(""))
        self.assertIsNotNone(auth._validate_password("   "))

    def test_validate_password_too_short(self) -> None:
        self.assertIsNotNone(auth._validate_password("12345"))

    def test_validate_password_valid(self) -> None:
        self.assertIsNone(auth._validate_password("123456"))
        self.assertIsNone(auth._validate_password("password123"))


class AuthPasswordHashTestCase(unittest.TestCase):
    """Test password hashing and verification."""

    def setUp(self) -> None:
        _reset_auth_globals()

    def test_verify_password_hash_correct(self) -> None:
        salt = secrets.token_bytes(32)
        pwd = "testpass123"
        derived = hashlib.pbkdf2_hmac(
            "sha256", pwd.encode("utf-8"), salt=salt, iterations=auth.PBKDF2_ITERATIONS
        )
        self.assertTrue(auth._verify_password_hash(pwd, salt, derived))

    def test_verify_password_hash_wrong_password(self) -> None:
        salt = secrets.token_bytes(32)
        pwd = "testpass123"
        derived = hashlib.pbkdf2_hmac(
            "sha256", pwd.encode("utf-8"), salt=salt, iterations=auth.PBKDF2_ITERATIONS
        )
        self.assertFalse(auth._verify_password_hash("wrong", salt, derived))

    def test_verify_password_hash_constant_time(self) -> None:
        """Verify compare_digest is used (constant-time)."""
        salt = secrets.token_bytes(32)
        derived = hashlib.pbkdf2_hmac(
            "sha256", b"x", salt=salt, iterations=auth.PBKDF2_ITERATIONS
        )
        self.assertFalse(auth._verify_password_hash("y", salt, derived))

    def test_hash_password_roundtrip(self) -> None:
        stored = auth.hash_password("secret123")
        self.assertTrue(auth.verify_password_hash_string("secret123", stored))
        self.assertFalse(auth.verify_password_hash_string("wrong", stored))


class AuthSessionTestCase(unittest.TestCase):
    """Test session creation and verification against user_sessions."""

    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.addCleanup(self.temp_dir.cleanup)
        _reset_db(self.data_dir)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)

    def _patch_env_and_run(self, auth_enabled: bool = True, test_fn=None):
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=auth_enabled):
            with patch.object(auth, "_get_data_dir", return_value=self.data_dir):
                auth._auth_enabled = auth_enabled
                if auth_enabled:
                    auth.set_initial_password("password123")
                if test_fn:
                    return test_fn()

    def test_create_session_returns_opaque_token(self) -> None:
        def run():
            tok = auth.create_session()
            self.assertTrue(tok, "session token should be non-empty")
            self.assertNotEqual(tok.count("."), 2, "should not use legacy HMAC format")
            self.assertTrue(auth.verify_session(tok))
            return tok

        self._patch_env_and_run(test_fn=run)

    def test_verify_session_valid_token(self) -> None:
        def run():
            tok = auth.create_session()
            self.assertTrue(auth.verify_session(tok))
            user = auth.resolve_session(tok)
            self.assertIsNotNone(user)
            self.assertEqual(user.username, "admin")
            self.assertEqual(user.role, "admin")

        self._patch_env_and_run(test_fn=run)

    def test_verify_session_expired(self) -> None:
        def run():
            tok = auth.create_session()
            self.assertTrue(auth.verify_session(tok))
            repo = auth._get_user_repo()
            sess = repo.get_session_by_token_hash(auth._hash_session_token(tok))
            repo = auth._get_user_repo()
            with repo.db.get_session() as session:
                from src.storage import UserSessionRecord

                row = session.get(UserSessionRecord, sess.id)
                row.expires_at = utc_naive_now() - timedelta(hours=1)
                session.commit()
            self.assertFalse(auth.verify_session(tok), "expired token should be invalid")

        self._patch_env_and_run(test_fn=run)

    def test_verify_session_invalid_format(self) -> None:
        def run():
            self.assertFalse(auth.verify_session(""))
            self.assertFalse(auth.verify_session("a.b"))
            self.assertFalse(auth.verify_session("invalid"))
            # Legacy HMAC cookies must not validate after upgrade
            self.assertFalse(auth.verify_session("nonce.1234567890." + ("a" * 64)))

        self._patch_env_and_run(test_fn=run)

    def test_revoke_session_token(self) -> None:
        def run():
            tok = auth.create_session()
            self.assertTrue(auth.verify_session(tok))
            self.assertTrue(auth.revoke_session_token(tok))
            self.assertFalse(auth.verify_session(tok))

        self._patch_env_and_run(test_fn=run)

    def test_rotate_session_secret_overwrites_existing(self) -> None:
        def run():
            secret_path = self.data_dir / ".session_secret"
            secret_path.write_bytes(b"a" * 32)
            secret_path.chmod(0o600)
            old_secret = secret_path.read_bytes()

            auth.rotate_session_secret()

            new_secret = secret_path.read_bytes()
            self.assertNotEqual(old_secret, new_secret)
            self.assertEqual(auth._session_secret, new_secret)

        self._patch_env_and_run(test_fn=run)

    def test_disabled_user_session_rejected(self) -> None:
        def run():
            tok = auth.create_session()
            user = auth.resolve_session(tok)
            self.assertIsNotNone(user)
            auth._get_user_repo().update_user(user.id, {"status": "disabled"})
            self.assertFalse(auth.verify_session(tok))

        self._patch_env_and_run(test_fn=run)


class AuthRateLimitTestCase(unittest.TestCase):
    """Test rate limiting."""

    def setUp(self) -> None:
        _reset_auth_globals()

    def test_rate_limit_allows_under_limit(self) -> None:
        self.assertTrue(auth.check_rate_limit("192.168.1.1"))

    def test_rate_limit_blocks_after_max_failures(self) -> None:
        ip = "10.0.0.99"
        for _ in range(auth.RATE_LIMIT_MAX_FAILURES):
            auth.record_login_failure(ip)
        self.assertFalse(auth.check_rate_limit(ip))

    def test_clear_rate_limit_resets_ip(self) -> None:
        ip = "10.0.0.100"
        for _ in range(auth.RATE_LIMIT_MAX_FAILURES):
            auth.record_login_failure(ip)
        self.assertFalse(auth.check_rate_limit(ip))
        auth.clear_rate_limit(ip)
        self.assertTrue(auth.check_rate_limit(ip))


class AuthSetPasswordTestCase(unittest.TestCase):
    """Test set_initial_password, change_password, overwrite_password."""

    def setUp(self) -> None:
        _reset_auth_globals()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        self.addCleanup(self.temp_dir.cleanup)
        _reset_db(self.data_dir)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        os.environ.pop("DATABASE_PATH", None)

    def _run_with_patch(self, fn):
        with patch.object(auth, "_is_auth_enabled_from_env", return_value=True):
            with patch.object(auth, "_get_data_dir", return_value=self.data_dir):
                auth._auth_enabled = True
                return fn()

    def test_set_initial_password_success(self) -> None:
        def run():
            err = auth.set_initial_password("password123")
            self.assertIsNone(err)
            self.assertIsNotNone(auth._password_hash_stored)
            self.assertTrue(auth.is_password_set())
            self.assertTrue(auth.verify_password("password123"))
            user = auth._get_user_repo().get_user_by_username("admin")
            self.assertIsNotNone(user)
            self.assertEqual(user.role, "admin")

        self._run_with_patch(run)

    def test_has_stored_password_remains_true_after_auth_disabled(self) -> None:
        def run():
            err = auth.set_initial_password("password123")
            self.assertIsNone(err)
            self.assertTrue(auth.has_stored_password())

            auth._auth_enabled = False
            self.assertTrue(auth.has_stored_password())
            self.assertFalse(auth.is_password_set())

        self._run_with_patch(run)

    def test_verify_stored_password_when_auth_disabled(self) -> None:
        def run():
            err = auth.set_initial_password("password123")
            self.assertIsNone(err)

            auth._auth_enabled = False
            self.assertTrue(auth.verify_stored_password("password123"))
            self.assertFalse(auth.verify_stored_password("wrongpass"))

        self._run_with_patch(run)

    def test_is_auth_enabled_from_env_respects_env_file(self) -> None:
        custom_env = self.data_dir / "custom.env"
        custom_env.write_text("ADMIN_AUTH_ENABLED=true\n", encoding="utf-8")

        with patch.dict(os.environ, {"ENV_FILE": str(custom_env)}):
            auth._auth_enabled = None
            self.assertTrue(auth._is_auth_enabled_from_env())

    def test_refresh_auth_state_clears_session_secret_cache(self) -> None:
        def run():
            auth.set_initial_password("password123")
            first_secret = auth.create_session()
            self.assertTrue(first_secret)
            self.assertIsNotNone(auth._session_secret)

            auth._session_secret = b"x" * 32
            auth.refresh_auth_state()
            self.assertIsNone(auth._session_secret)

        self._run_with_patch(run)

    def test_set_initial_password_invalid(self) -> None:
        def run():
            self.assertIsNotNone(auth.set_initial_password(""))
            self.assertIsNotNone(auth.set_initial_password("12345"))

        self._run_with_patch(run)

    def test_change_password_success(self) -> None:
        def run():
            auth.set_initial_password("oldpass123")
            err = auth.change_password("oldpass123", "newpass456")
            self.assertIsNone(err)
            self.assertFalse(auth.verify_password("oldpass123"))
            self.assertTrue(auth.verify_password("newpass456"))

        self._run_with_patch(run)

    def test_change_password_wrong_current(self) -> None:
        def run():
            auth.set_initial_password("correctpass")
            err = auth.change_password("wrongpass", "newpass456")
            self.assertIsNotNone(err)
            self.assertTrue(auth.verify_password("correctpass"))

        self._run_with_patch(run)

    def test_overwrite_password_cli_style(self) -> None:
        def run():
            auth.set_initial_password("original")
            err = auth.overwrite_password("resetpass")
            self.assertIsNone(err)
            self.assertFalse(auth.verify_password("original"))
            self.assertTrue(auth.verify_password("resetpass"))

        self._run_with_patch(run)

    def test_migrate_admin_password_file_to_users(self) -> None:
        def run():
            content = auth.hash_password("legacy123")
            (self.data_dir / ".admin_password_hash").write_text(content)
            # Fresh DB so create_all + _ensure_admin_user_migrated picks up the file.
            Config.reset_instance()
            DatabaseManager.reset_instance()
            DatabaseManager.get_instance()
            user = auth._get_user_repo().get_user_by_username("admin")
            self.assertIsNotNone(user)
            self.assertTrue(auth.verify_password_hash_string("legacy123", user.password_hash))
            # Second call is a no-op
            self.assertFalse(auth.migrate_admin_password_file_to_users())

        self._run_with_patch(run)


if __name__ == "__main__":
    unittest.main()

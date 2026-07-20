# -*- coding: utf-8 -*-
"""
Web authentication module.

Supports multi-user DB credentials and server-side sessions while retaining
legacy single-admin file credentials for migration compatibility.
"""

from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import logging
import os
import secrets
import sys
import time
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Optional, Tuple

from dotenv import dotenv_values

logger = logging.getLogger(__name__)

COOKIE_NAME = "dsa_session"
PBKDF2_ITERATIONS = 100_000
RATE_LIMIT_WINDOW_SEC = 300
RATE_LIMIT_MAX_FAILURES = 5
SESSION_MAX_AGE_HOURS_DEFAULT = 24
AUTH_MODE_SINGLE_ADMIN = "single_admin"
AUTH_MODE_MULTI_USER = "multi_user"
AUTH_MODE_DEFAULT = AUTH_MODE_MULTI_USER
MIN_PASSWORD_LEN = 6
DEFAULT_ADMIN_USERNAME = "admin"

# Lazy-loaded state
_auth_enabled: Optional[bool] = None
_session_secret: Optional[bytes] = None
_password_hash_salt: Optional[bytes] = None
_password_hash_stored: Optional[bytes] = None
_rate_limit: dict[str, Tuple[int, float]] = {}
_rate_limit_lock = None


@dataclass(frozen=True)
class AuthUser:
    """Authenticated user resolved from a server-side session."""

    id: int
    username: str
    role: str
    status: str
    session_id: int


def _get_lock():
    """Lazy init threading lock for rate limit dict."""
    global _rate_limit_lock
    if _rate_limit_lock is None:
        import threading
        _rate_limit_lock = threading.Lock()
    return _rate_limit_lock


def _ensure_env_loaded() -> None:
    """Ensure .env is loaded before reading config."""
    from src.config import setup_env
    setup_env()


def _get_data_dir() -> Path:
    """Return DATA_DIR as parent of DATABASE_PATH."""
    db_path = os.getenv("DATABASE_PATH", "./data/stock_analysis.db")
    return Path(db_path).resolve().parent


def _get_credential_path() -> Path:
    """Path to stored password hash file."""
    return _get_data_dir() / ".admin_password_hash"


def _is_auth_enabled_from_env() -> bool:
    """Read ADMIN_AUTH_ENABLED from .env file."""
    _ensure_env_loaded()
    # Docker and other process managers commonly inject configuration through
    # the process environment without mounting the source .env file.
    env_value = os.getenv("ADMIN_AUTH_ENABLED")
    if env_value is not None:
        return env_value.strip().lower() in ("true", "1", "yes")

    env_file = os.getenv("ENV_FILE")
    env_path = Path(env_file) if env_file else Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return False
    values = dotenv_values(env_path)
    val = (values.get("ADMIN_AUTH_ENABLED") or "").strip().lower()
    return val in ("true", "1", "yes")


def rotate_session_secret() -> bool:
    """Rotate the session signing secret (legacy HMAC; also used as pepper for hashing)."""
    global _session_secret
    data_dir = _get_data_dir()
    secret_path = data_dir / ".session_secret"
    data_dir.mkdir(parents=True, exist_ok=True)
    new_secret = secrets.token_bytes(32)
    try:
        tmp_path = secret_path.with_suffix(".tmp")
        tmp_path.write_bytes(new_secret)
        tmp_path.chmod(0o600)
        tmp_path.replace(secret_path)
        _session_secret = new_secret
        logger.info("Session secret rotated successfully")
        return True
    except OSError as e:
        logger.error("Failed to rotate .session_secret: %s", e)
        return False


def _load_session_secret() -> Optional[bytes]:
    """Load or create session secret."""
    global _session_secret
    if _session_secret is not None:
        return _session_secret

    data_dir = _get_data_dir()
    secret_path = data_dir / ".session_secret"

    try:
        if secret_path.exists():
            _session_secret = secret_path.read_bytes()
            if len(_session_secret) != 32:
                logger.warning("Invalid .session_secret length, regenerating")
                _session_secret = None
                if rotate_session_secret():
                    return _session_secret
                return None
            return _session_secret

        data_dir.mkdir(parents=True, exist_ok=True)
        new_secret = secrets.token_bytes(32)
        try:
            with open(secret_path, "xb") as f:
                f.write(new_secret)
            secret_path.chmod(0o600)
        except FileExistsError:
            _session_secret = secret_path.read_bytes()
        else:
            _session_secret = new_secret
        return _session_secret
    except OSError as e:
        logger.error("Failed to create or read .session_secret: %s", e)
        return None


def _parse_password_hash(value: str) -> Optional[Tuple[bytes, bytes]]:
    """Parse salt_b64:hash_b64. Returns (salt, hash) or None."""
    if not value or ":" not in value:
        return None
    parts = value.strip().split(":", 1)
    if len(parts) != 2:
        return None
    try:
        salt_b64, hash_b64 = parts[0].strip(), parts[1].strip()
        salt = base64.standard_b64decode(salt_b64)
        stored_hash = base64.standard_b64decode(hash_b64)
        if salt and stored_hash:
            return (salt, stored_hash)
    except (ValueError, TypeError):
        pass
    return None


def _verify_password_hash(submitted: str, salt: bytes, stored_hash: bytes) -> bool:
    """Verify submitted password against stored pbkdf2 hash."""
    computed = hashlib.pbkdf2_hmac(
        "sha256",
        submitted.encode("utf-8"),
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    return hmac.compare_digest(computed, stored_hash)


def hash_password(password: str) -> str:
    """Create salt_b64:hash_b64 credential string."""
    salt = secrets.token_bytes(32)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    salt_b64 = base64.standard_b64encode(salt).decode("ascii")
    hash_b64 = base64.standard_b64encode(derived).decode("ascii")
    return f"{salt_b64}:{hash_b64}"


def verify_password_hash_string(password: str, stored: str) -> bool:
    """Verify password against stored salt_b64:hash_b64 string."""
    parsed = _parse_password_hash(stored)
    if parsed is None:
        return False
    salt, stored_hash = parsed
    return _verify_password_hash(password, salt, stored_hash)


def _hash_session_token(raw_token: str) -> str:
    """Hash opaque session token for DB storage."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _session_max_age_hours() -> int:
    try:
        return int(os.getenv("ADMIN_SESSION_MAX_AGE_HOURS", str(SESSION_MAX_AGE_HOURS_DEFAULT)))
    except ValueError:
        return SESSION_MAX_AGE_HOURS_DEFAULT


def _load_credential_from_file() -> bool:
    """Load credential from file into module globals. Returns True if loaded."""
    global _password_hash_salt, _password_hash_stored

    path = _get_credential_path()
    if not path.exists():
        _password_hash_salt = None
        _password_hash_stored = None
        return False

    try:
        raw = path.read_text().strip()
        parsed = _parse_password_hash(raw)
        if parsed is None:
            logger.warning("Invalid .admin_password_hash format, ignoring")
            return False
        _password_hash_salt, _password_hash_stored = parsed
        return True
    except OSError as e:
        logger.error("Failed to read credential file: %s", e)
        return False


def _write_credential_file(content: str) -> Optional[str]:
    """Atomically write credential file. Returns error message or None."""
    data_dir = _get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    cred_path = _get_credential_path()
    try:
        tmp_path = cred_path.with_suffix(".tmp")
        tmp_path.write_text(content)
        tmp_path.chmod(0o600)
        tmp_path.replace(cred_path)
        _load_credential_from_file()
        return None
    except OSError as e:
        logger.error("Failed to write credential file: %s", e)
        return "密码保存失败"


def _get_user_repo(db_manager=None):
    from src.repositories.user_repo import UserRepository

    return UserRepository(db_manager=db_manager)


def migrate_admin_password_file_to_users(db_manager=None) -> bool:
    """
    If users table is empty and .admin_password_hash exists, create admin user.
    Returns True if a user was created.
    """
    repo = _get_user_repo(db_manager)
    if repo.count_users() > 0:
        return False
    path = _get_credential_path()
    if not path.exists():
        return False
    try:
        raw = path.read_text().strip()
    except OSError as e:
        logger.error("Failed to read .admin_password_hash for migration: %s", e)
        return False
    if _parse_password_hash(raw) is None:
        logger.warning("Skip admin migration: invalid .admin_password_hash")
        return False
    repo.create_user(
        username=DEFAULT_ADMIN_USERNAME,
        password_hash=raw,
        role="admin",
        status="active",
    )
    repo.ensure_preferences(repo.get_user_by_username(DEFAULT_ADMIN_USERNAME).id)
    logger.info("Migrated .admin_password_hash into users.username=%s", DEFAULT_ADMIN_USERNAME)
    return True


def refresh_auth_state() -> None:
    """Reload auth-related state from disk and env."""
    global _auth_enabled, _session_secret
    _auth_enabled = None
    _session_secret = None
    _load_credential_from_file()


def is_auth_enabled() -> bool:
    """Return whether admin authentication is enabled (ADMIN_AUTH_ENABLED=true)."""
    global _auth_enabled
    if _auth_enabled is not None:
        return _auth_enabled
    _auth_enabled = _is_auth_enabled_from_env()
    return _auth_enabled


def get_auth_mode() -> str:
    """
    Return operational auth mode.

    - single_admin: authentication may be on, but creating additional users is blocked.
    - multi_user: admin user management (create/promote) is allowed.

    Schema/user_id isolation is always applied when the DB migrates; AUTH_MODE only
    gates multi-user operations. Default is multi_user for backward compatibility.
    """
    raw = (os.getenv("AUTH_MODE") or AUTH_MODE_DEFAULT).strip().lower()
    if raw in (AUTH_MODE_SINGLE_ADMIN, AUTH_MODE_MULTI_USER):
        return raw
    logger.warning("Unknown AUTH_MODE=%r, falling back to %s", raw, AUTH_MODE_DEFAULT)
    return AUTH_MODE_DEFAULT


def is_multi_user_mode() -> bool:
    """Return True when AUTH_MODE allows creating additional users."""
    return get_auth_mode() == AUTH_MODE_MULTI_USER


def has_stored_password() -> bool:
    """Return whether a password credential exists (users table or legacy file)."""
    try:
        repo = _get_user_repo()
        if repo.get_user_by_username(DEFAULT_ADMIN_USERNAME) is not None:
            return True
        if repo.count_users() > 0:
            return True
    except Exception:
        pass
    return _load_credential_from_file()


def verify_stored_password(password: str) -> bool:
    """Verify password against admin/user credentials even when auth is disabled."""
    try:
        user = _get_user_repo().get_user_by_username(DEFAULT_ADMIN_USERNAME)
        if user is not None:
            return verify_password_hash_string(password, user.password_hash)
    except Exception:
        pass
    if not _load_credential_from_file():
        return False
    return _verify_password_hash(password, _password_hash_salt, _password_hash_stored)


def is_password_set() -> bool:
    """Return whether initial password has been set."""
    if not is_auth_enabled():
        return False
    return has_stored_password()


def is_password_changeable() -> bool:
    """Return whether password can be changed via web/CLI (always True when auth enabled)."""
    return is_auth_enabled()


def _get_session_secret() -> Optional[bytes]:
    """Return session signing secret (legacy)."""
    if not is_auth_enabled():
        return None
    return _load_session_secret()


def _validate_password(pwd: str) -> Optional[str]:
    """Return error message if invalid, None if valid."""
    if not pwd or not pwd.strip():
        return "密码不能为空"
    if len(pwd) < MIN_PASSWORD_LEN:
        return f"密码至少 {MIN_PASSWORD_LEN} 位"
    return None


def set_initial_password(password: str) -> Optional[str]:
    """
    Set initial admin password (first-time setup).
    Writes users table + legacy credential file.
    """
    err = _validate_password(password)
    if err:
        return err

    content = hash_password(password)
    file_err = _write_credential_file(content)
    if file_err:
        return file_err

    try:
        repo = _get_user_repo()
        existing = repo.get_user_by_username(DEFAULT_ADMIN_USERNAME)
        if existing is None:
            user = repo.create_user(
                username=DEFAULT_ADMIN_USERNAME,
                password_hash=content,
                role="admin",
                status="active",
            )
            repo.ensure_preferences(user.id)
        else:
            repo.update_user(existing.id, {"password_hash": content})
        try:
            from src.storage import DatabaseManager

            DatabaseManager.get_instance()._ensure_user_owned_user_id_columns()
        except Exception as exc:
            logger.warning("Post-password user_id backfill skipped: %s", exc)
    except Exception as e:
        logger.error("Failed to persist initial admin user: %s", e)
        return "密码保存失败"
    return None


def verify_password(password: str) -> bool:
    """Verify password against admin credential. Constant-time where applicable."""
    if not is_auth_enabled():
        return True
    return verify_stored_password(password)


def authenticate_user(username: str, password: str) -> Optional[AuthUser]:
    """
    Authenticate username/password.
    Returns AuthUser-like stub without session_id on success (session_id=0).
    """
    username = (username or DEFAULT_ADMIN_USERNAME).strip() or DEFAULT_ADMIN_USERNAME
    try:
        migrate_admin_password_file_to_users()
        repo = _get_user_repo()
        user = repo.get_user_by_username(username)
        if user is None and username == DEFAULT_ADMIN_USERNAME:
            # Fall back to file-only credential and create user
            if verify_stored_password(password) and _load_credential_from_file():
                path = _get_credential_path()
                raw = path.read_text().strip()
                user = repo.create_user(
                    username=DEFAULT_ADMIN_USERNAME,
                    password_hash=raw,
                    role="admin",
                    status="active",
                )
                repo.ensure_preferences(user.id)
            else:
                return None
        if user is None:
            return None
        if user.status != "active":
            return None
        if not verify_password_hash_string(password, user.password_hash):
            return None
        return AuthUser(
            id=user.id,
            username=user.username,
            role=user.role,
            status=user.status,
            session_id=0,
        )
    except Exception as e:
        logger.error("authenticate_user failed: %s", e)
        return None


def change_password(current: str, new: str, *, user_id: Optional[int] = None) -> Optional[str]:
    """
    Change password. Verifies current, writes new hash, revokes sessions.
    Returns error message or None on success.
    """
    if not is_auth_enabled():
        return "认证功能未启用"
    if not is_password_set():
        return "尚未设置密码"

    if not current or not current.strip():
        return "请输入当前密码"

    err = _validate_password(new)
    if err:
        return err

    try:
        repo = _get_user_repo()
        user = None
        if user_id is not None:
            user = repo.get_user_by_id(user_id)
        if user is None:
            user = repo.get_user_by_username(DEFAULT_ADMIN_USERNAME)
        if user is None:
            if not _load_credential_from_file():
                return "尚未设置密码"
            if not _verify_password_hash(current, _password_hash_salt, _password_hash_stored):
                return "当前密码错误"
            content = hash_password(new)
            file_err = _write_credential_file(content)
            if file_err:
                return file_err
            migrate_admin_password_file_to_users()
            user = repo.get_user_by_username(DEFAULT_ADMIN_USERNAME)
            if user is None:
                return "密码保存失败"
            repo.update_user(user.id, {"password_hash": content})
            repo.revoke_all_sessions_for_user(user.id)
            return None

        if not verify_password_hash_string(current, user.password_hash):
            return "当前密码错误"

        content = hash_password(new)
        repo.update_user(user.id, {"password_hash": content})
        if user.username == DEFAULT_ADMIN_USERNAME or user.role == "admin":
            _write_credential_file(content)
        repo.revoke_all_sessions_for_user(user.id)
        return None
    except Exception as e:
        logger.error("change_password failed: %s", e)
        return "密码保存失败"


def create_session(
    user_id: Optional[int] = None,
    *,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    """
    Create opaque session token stored as hash in user_sessions.
    If user_id is omitted, uses the default admin user (compat with settings enable flow).
    """
    if not is_auth_enabled():
        return ""
    try:
        migrate_admin_password_file_to_users()
        repo = _get_user_repo()
        uid = user_id
        if uid is None:
            admin = repo.get_user_by_username(DEFAULT_ADMIN_USERNAME)
            if admin is None:
                return ""
            uid = admin.id
        raw_token = secrets.token_urlsafe(32)
        token_hash = _hash_session_token(raw_token)
        from src.storage import utc_naive_now

        expires_at = utc_naive_now() + timedelta(hours=_session_max_age_hours())
        repo.create_session(
            user_id=uid,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        # Ensure legacy secret file exists for deployments that still expect it
        _load_session_secret()
        return raw_token
    except Exception as e:
        logger.error("create_session failed: %s", e)
        return ""


def resolve_session(value: str) -> Optional[AuthUser]:
    """Resolve cookie token to AuthUser; None if invalid/expired/revoked/disabled."""
    if not is_auth_enabled() or not value:
        return None
    # Reject legacy HMAC cookies (nonce.ts.sig) — force re-login after upgrade
    if value.count(".") == 2:
        parts = value.split(".")
        if len(parts) == 3 and parts[1].isdigit() and len(parts[2]) == 64:
            return None
    try:
        repo = _get_user_repo()
        token_hash = _hash_session_token(value)
        sess = repo.get_session_by_token_hash(token_hash)
        if sess is None or sess.revoked_at is not None:
            return None
        from src.storage import utc_naive_now

        if sess.expires_at <= utc_naive_now():
            return None
        user = repo.get_user_by_id(sess.user_id)
        if user is None or user.status != "active":
            return None
        repo.touch_session(sess.id)
        return AuthUser(
            id=user.id,
            username=user.username,
            role=user.role,
            status=user.status,
            session_id=sess.id,
        )
    except Exception as e:
        logger.error("resolve_session failed: %s", e)
        return None


def verify_session(value: str) -> bool:
    """Verify session cookie against server-side session store."""
    return resolve_session(value) is not None


def revoke_session_token(value: str) -> bool:
    """Revoke a single session by raw cookie token."""
    if not value:
        return False
    try:
        return _get_user_repo().revoke_session_by_token_hash(_hash_session_token(value))
    except Exception as e:
        logger.error("revoke_session_token failed: %s", e)
        return False


def revoke_all_sessions(user_id: int) -> int:
    """Revoke all sessions for a user. Returns count revoked."""
    try:
        return _get_user_repo().revoke_all_sessions_for_user(user_id)
    except Exception as e:
        logger.error("revoke_all_sessions failed: %s", e)
        return 0


def record_audit(
    action: str,
    *,
    actor_user_id: Optional[int] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    detail_json: Optional[str] = None,
) -> None:
    """Best-effort audit log write; never raises to callers."""
    try:
        _get_user_repo().add_audit_log(
            action=action,
            actor_user_id=actor_user_id,
            target_type=target_type,
            target_id=target_id,
            ip_address=ip_address,
            user_agent=user_agent,
            detail_json=detail_json,
        )
    except Exception as e:
        logger.warning("Failed to write audit log action=%s: %s", action, e)


def get_default_admin_user_id(*, create_if_missing: bool = False) -> int:
    """
    Return the local admin user's id (migrate from legacy file if needed).

    When create_if_missing is False (default), raises RuntimeError if no admin exists
    yet so first-time password setup is not blocked by a random placeholder hash.
    When True (auth-disabled / CLI ownership), creates an admin row with a random
    unusable password hash solely for data ownership.
    """
    migrate_admin_password_file_to_users()
    repo = _get_user_repo()
    user = repo.get_user_by_username(DEFAULT_ADMIN_USERNAME)
    if user is not None:
        return int(user.id)
    if not create_if_missing:
        raise RuntimeError(
            "Default admin user is not available yet; set an initial password or migrate "
            ".admin_password_hash first"
        )
    content = hash_password(secrets.token_urlsafe(32))
    user = repo.create_user(
        username=DEFAULT_ADMIN_USERNAME,
        password_hash=content,
        role="admin",
        status="active",
    )
    repo.ensure_preferences(user.id)
    logger.info("Created ownership admin user id=%s (create_if_missing)", user.id)
    return int(user.id)


def mark_login_success(user_id: int) -> None:
    """Update last_login_at after successful login."""
    try:
        from src.storage import utc_naive_now

        _get_user_repo().update_user(user_id, {"last_login_at": utc_naive_now()})
    except Exception as e:
        logger.warning("Failed to update last_login_at: %s", e)


def get_client_ip(request) -> str:
    """Get client IP, respecting TRUST_X_FORWARDED_FOR.

    When behind a single trusted reverse proxy, the proxy appends the real
    client IP as the rightmost entry in X-Forwarded-For.  We use [-1] instead
    of [0] so that an attacker cannot spoof an arbitrary leftmost value to
    rotate rate-limit buckets and bypass brute-force protection.
    """
    if os.getenv("TRUST_X_FORWARDED_FOR", "false").lower() == "true":
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[-1].strip()
    if request.client:
        return request.client.host or "127.0.0.1"
    return "127.0.0.1"


def check_rate_limit(ip: str) -> bool:
    """Return True if under limit, False if rate limited."""
    lock = _get_lock()
    now = time.time()
    with lock:
        expired_keys = [k for k, (_, ts) in _rate_limit.items() if now - ts > RATE_LIMIT_WINDOW_SEC]
        for k in expired_keys:
            del _rate_limit[k]
        if ip in _rate_limit:
            count, first_ts = _rate_limit[ip]
            if count >= RATE_LIMIT_MAX_FAILURES:
                return False
        return True


def record_login_failure(ip: str) -> None:
    """Record a failed login attempt for rate limiting."""
    lock = _get_lock()
    now = time.time()
    with lock:
        if ip in _rate_limit:
            count, first_ts = _rate_limit[ip]
            if now - first_ts > RATE_LIMIT_WINDOW_SEC:
                _rate_limit[ip] = (1, now)
            else:
                _rate_limit[ip] = (count + 1, first_ts)
        else:
            _rate_limit[ip] = (1, now)


def clear_rate_limit(ip: str) -> None:
    """Clear rate limit for IP after successful login."""
    lock = _get_lock()
    with lock:
        _rate_limit.pop(ip, None)


def overwrite_password(new_password: str) -> Optional[str]:
    """
    Overwrite stored admin password without verifying current. For CLI reset only.
    Returns error message or None on success.
    """
    if not is_auth_enabled():
        return "认证功能未启用"
    err = _validate_password(new_password)
    if err:
        return err

    content = hash_password(new_password)
    file_err = _write_credential_file(content)
    if file_err:
        return file_err

    try:
        repo = _get_user_repo()
        migrate_admin_password_file_to_users()
        user = repo.get_user_by_username(DEFAULT_ADMIN_USERNAME)
        if user is None:
            user = repo.create_user(
                username=DEFAULT_ADMIN_USERNAME,
                password_hash=content,
                role="admin",
                status="active",
            )
            repo.ensure_preferences(user.id)
        else:
            repo.update_user(user.id, {"password_hash": content})
            repo.revoke_all_sessions_for_user(user.id)
    except Exception as e:
        logger.error("overwrite_password failed: %s", e)
        return "密码保存失败"
    return None


def reset_password_cli() -> int:
    """Interactive CLI to reset password. Returns exit code."""
    _ensure_env_loaded()
    if not _is_auth_enabled_from_env():
        print("Error: Auth is not enabled. Set ADMIN_AUTH_ENABLED=true in .env", file=sys.stderr)
        return 1

    print("Enter new admin password (will not echo):", end=" ")
    pwd = getpass.getpass("")
    err = _validate_password(pwd)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print("Confirm new password:", end=" ")
    pwd2 = getpass.getpass("")
    if pwd != pwd2:
        print("Error: Passwords do not match", file=sys.stderr)
        return 1

    err = overwrite_password(pwd)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    print("Password has been reset successfully.")
    return 0


def _main() -> int:
    """CLI entry: reset_password subcommand."""
    if len(sys.argv) > 1 and sys.argv[1] == "reset_password":
        return reset_password_cli()
    print("Usage: python -m src.auth reset_password", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(_main())

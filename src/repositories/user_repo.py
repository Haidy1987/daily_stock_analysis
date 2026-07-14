# -*- coding: utf-8 -*-
"""User / session / audit repository for multi-user auth core."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select, update

from src.storage import (
    AuditLogRecord,
    DatabaseManager,
    UserPreferenceRecord,
    UserRecord,
    UserSessionRecord,
    utc_naive_now,
)


class UserRepository:
    """DB access for users, sessions, preferences, and audit logs."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def count_users(self) -> int:
        with self.db.get_session() as session:
            return int(session.execute(select(func.count()).select_from(UserRecord)).scalar_one())

    def count_admins(self, *, status: Optional[str] = "active") -> int:
        with self.db.get_session() as session:
            conditions = [UserRecord.role == "admin"]
            if status is not None:
                conditions.append(UserRecord.status == status)
            return int(
                session.execute(
                    select(func.count()).select_from(UserRecord).where(and_(*conditions))
                ).scalar_one()
            )

    def list_users(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Tuple[List[UserRecord], int]:
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 20), 100))
        conditions = []
        if search:
            q = f"%{search.strip()}%"
            conditions.append(
                or_(
                    UserRecord.username.ilike(q),
                    UserRecord.email.ilike(q),
                )
            )
        if role:
            conditions.append(UserRecord.role == role)
        if status:
            conditions.append(UserRecord.status == status)
        offset = (page - 1) * page_size
        with self.db.get_session() as session:
            count_stmt = select(func.count()).select_from(UserRecord)
            list_stmt = select(UserRecord).order_by(UserRecord.id.asc()).offset(offset).limit(page_size)
            if conditions:
                where_clause = and_(*conditions)
                count_stmt = count_stmt.where(where_clause)
                list_stmt = list_stmt.where(where_clause)
            total = int(session.execute(count_stmt).scalar_one())
            rows = session.execute(list_stmt).scalars().all()
            for row in rows:
                session.expunge(row)
            return list(rows), total

    def get_user_by_id(self, user_id: int) -> Optional[UserRecord]:
        with self.db.get_session() as session:
            row = session.get(UserRecord, user_id)
            if row is None:
                return None
            session.expunge(row)
            return row

    def get_user_by_username(self, username: str) -> Optional[UserRecord]:
        with self.db.get_session() as session:
            row = session.execute(
                select(UserRecord).where(UserRecord.username == username).limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            session.expunge(row)
            return row

    def create_user(
        self,
        *,
        username: str,
        password_hash: str,
        role: str = "user",
        status: str = "active",
        email: Optional[str] = None,
    ) -> UserRecord:
        with self.db.get_session() as session:
            row = UserRecord(
                username=username,
                password_hash=password_hash,
                role=role,
                status=status,
                email=email,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def update_user(self, user_id: int, fields: Dict[str, Any]) -> Optional[UserRecord]:
        with self.db.get_session() as session:
            row = session.get(UserRecord, user_id)
            if row is None:
                return None
            for key, value in fields.items():
                setattr(row, key, value)
            row.updated_at = utc_naive_now()
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def create_session(
        self,
        *,
        user_id: int,
        token_hash: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> UserSessionRecord:
        with self.db.get_session() as session:
            row = UserSessionRecord(
                user_id=user_id,
                token_hash=token_hash,
                expires_at=expires_at,
                last_seen_at=utc_naive_now(),
                ip_address=ip_address,
                user_agent=user_agent,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def get_session_by_token_hash(self, token_hash: str) -> Optional[UserSessionRecord]:
        with self.db.get_session() as session:
            row = session.execute(
                select(UserSessionRecord)
                .where(UserSessionRecord.token_hash == token_hash)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return None
            session.expunge(row)
            return row

    def touch_session(self, session_id: int) -> None:
        with self.db.get_session() as session:
            session.execute(
                update(UserSessionRecord)
                .where(UserSessionRecord.id == session_id)
                .values(last_seen_at=utc_naive_now())
            )
            session.commit()

    def revoke_session_by_token_hash(self, token_hash: str) -> bool:
        with self.db.get_session() as session:
            row = session.execute(
                select(UserSessionRecord)
                .where(UserSessionRecord.token_hash == token_hash)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                return False
            if row.revoked_at is None:
                row.revoked_at = utc_naive_now()
                session.commit()
            return True

    def revoke_all_sessions_for_user(self, user_id: int) -> int:
        with self.db.get_session() as session:
            rows = session.execute(
                select(UserSessionRecord).where(
                    UserSessionRecord.user_id == user_id,
                    UserSessionRecord.revoked_at.is_(None),
                )
            ).scalars().all()
            now = utc_naive_now()
            for row in rows:
                row.revoked_at = now
            session.commit()
            return len(rows)

    def ensure_preferences(self, user_id: int) -> UserPreferenceRecord:
        with self.db.get_session() as session:
            row = session.execute(
                select(UserPreferenceRecord)
                .where(UserPreferenceRecord.user_id == user_id)
                .limit(1)
            ).scalar_one_or_none()
            if row is None:
                row = UserPreferenceRecord(user_id=user_id)
                session.add(row)
                session.commit()
                session.refresh(row)
            session.expunge(row)
            return row

    def add_audit_log(
        self,
        *,
        action: str,
        actor_user_id: Optional[int] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        detail_json: Optional[str] = None,
    ) -> AuditLogRecord:
        with self.db.get_session() as session:
            row = AuditLogRecord(
                actor_user_id=actor_user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                ip_address=ip_address,
                user_agent=user_agent,
                detail_json=detail_json,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            session.expunge(row)
            return row

    def list_audit_logs(self, *, limit: int = 100) -> List[AuditLogRecord]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(AuditLogRecord)
                .order_by(AuditLogRecord.created_at.desc())
                .limit(limit)
            ).scalars().all()
            for row in rows:
                session.expunge(row)
            return list(rows)

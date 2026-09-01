# -*- coding: utf-8 -*-
"""Repository for A-share universe master data and market snapshots."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable, List, Optional, Sequence, Union

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.schemas.a_share_universe import (
    AShareSnapshotRow,
    AShareUniverseRow,
    AShareUpsertResult,
    normalize_a_share_code,
)
from src.storage import AShareSnapshot, AShareUniverse, DatabaseManager, utc_naive_now

UniverseInput = Union[AShareUniverseRow, dict]
SnapshotInput = Union[AShareSnapshotRow, dict]

_SQLITE_CHUNK = 200


class AShareUniverseRepository:
    """DB access layer for A-share universe master data and snapshots."""

    _UNIVERSE_UPDATE_COLUMNS = (
        "name",
        "exchange",
        "board",
        "industry",
        "list_date",
        "active",
        "source",
        "updated_at",
    )
    _SNAPSHOT_UPDATE_COLUMNS = (
        "price",
        "open",
        "high",
        "low",
        "pre_close",
        "pct_chg",
        "amplitude",
        "volume",
        "amount",
        "turnover_rate",
        "volume_ratio",
        "pe_ttm",
        "pe_dynamic",
        "pb",
        "ps",
        "total_mv",
        "circ_mv",
        "total_share",
        "float_share",
        "eps",
        "bps",
        "roe",
        "revenue",
        "revenue_yoy",
        "net_profit",
        "net_profit_yoy",
        "high_52w",
        "low_52w",
        "ytd_pct_chg",
        "source",
        "fetched_at",
        "updated_at",
    )

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def upsert_universe(self, rows: Iterable[UniverseInput]) -> AShareUpsertResult:
        records = [self._normalize_universe_row(row) for row in rows]
        records = [record for record in records if record.get("code") and record.get("name")]
        if not records:
            return AShareUpsertResult()

        now = utc_naive_now()
        for record in records:
            record.setdefault("created_at", now)
            record["updated_at"] = now

        existing_codes = self._fetch_existing_universe_codes([record["code"] for record in records])
        result = AShareUpsertResult(total=len(records))
        result.inserted = sum(1 for record in records if record["code"] not in existing_codes)
        result.updated = result.total - result.inserted

        with self.db.get_session() as session:
            for index in range(0, len(records), _SQLITE_CHUNK):
                chunk = records[index : index + _SQLITE_CHUNK]
                stmt = sqlite_insert(AShareUniverse).values(chunk)
                excluded = stmt.excluded
                session.execute(
                    stmt.on_conflict_do_update(
                        index_elements=["code"],
                        set_={column: getattr(excluded, column) for column in self._UNIVERSE_UPDATE_COLUMNS},
                    )
                )
            session.commit()
        return result

    def upsert_snapshot(self, rows: Iterable[SnapshotInput]) -> AShareUpsertResult:
        records = [self._normalize_snapshot_row(row) for row in rows]
        records = [
            record
            for record in records
            if record.get("code") and record.get("data_date") is not None
        ]
        if not records:
            return AShareUpsertResult()

        now = utc_naive_now()
        for record in records:
            record.setdefault("created_at", now)
            if not record.get("fetched_at"):
                record["fetched_at"] = now
            record["updated_at"] = now

        existing_keys = self._fetch_existing_snapshot_keys(
            [(record["code"], record["data_date"]) for record in records]
        )
        result = AShareUpsertResult(total=len(records))
        result.inserted = sum(
            1 for record in records if (record["code"], record["data_date"]) not in existing_keys
        )
        result.updated = result.total - result.inserted

        with self.db.get_session() as session:
            for index in range(0, len(records), _SQLITE_CHUNK):
                chunk = records[index : index + _SQLITE_CHUNK]
                stmt = sqlite_insert(AShareSnapshot).values(chunk)
                excluded = stmt.excluded
                session.execute(
                    stmt.on_conflict_do_update(
                        index_elements=["code", "data_date"],
                        set_={column: getattr(excluded, column) for column in self._SNAPSHOT_UPDATE_COLUMNS},
                    )
                )
            session.commit()
        return result

    def get_by_code(self, code: str) -> Optional[AShareUniverse]:
        normalized = normalize_a_share_code(code)
        if not normalized:
            return None
        with self.db.get_session() as session:
            return session.execute(
                select(AShareUniverse).where(AShareUniverse.code == normalized).limit(1)
            ).scalar_one_or_none()

    def get_latest_snapshot(self, code: str) -> Optional[AShareSnapshot]:
        normalized = normalize_a_share_code(code)
        if not normalized:
            return None
        with self.db.get_session() as session:
            return session.execute(
                select(AShareSnapshot)
                .where(AShareSnapshot.code == normalized)
                .order_by(desc(AShareSnapshot.data_date), desc(AShareSnapshot.id))
                .limit(1)
            ).scalar_one_or_none()

    def list_active_codes(self) -> List[str]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(AShareUniverse.code)
                .where(AShareUniverse.active.is_(True))
                .order_by(AShareUniverse.code)
            ).scalars().all()
            return list(rows)

    def list_universe(
        self,
        *,
        active_only: bool = True,
        limit: Optional[int] = None,
    ) -> List[AShareUniverse]:
        safe_limit: Optional[int] = None
        if limit is not None:
            safe_limit = max(1, min(int(limit), 100_000))

        with self.db.get_session() as session:
            query = select(AShareUniverse).order_by(AShareUniverse.code)
            if active_only:
                query = query.where(AShareUniverse.active.is_(True))
            if safe_limit is not None:
                query = query.limit(safe_limit)
            return list(session.execute(query).scalars().all())

    def count_universe(self, *, active_only: bool = False) -> int:
        with self.db.get_session() as session:
            query = select(func.count(AShareUniverse.id))
            if active_only:
                query = query.where(AShareUniverse.active.is_(True))
            return int(session.execute(query).scalar() or 0)

    def _search_where_clause(self, query_text: str, *, active_only: bool = True):
        keyword = self._normalize_search_keyword(query_text)
        conditions = []
        if active_only:
            conditions.append(AShareUniverse.active.is_(True))

        if keyword:
            if keyword.isdigit():
                conditions.append(AShareUniverse.code.like(f"{keyword}%"))
            else:
                conditions.append(
                    or_(
                        AShareUniverse.name.like(f"%{keyword}%"),
                        AShareUniverse.industry.like(f"%{keyword}%"),
                    )
                )

        return and_(*conditions) if conditions else True

    def count_search(
        self,
        query_text: str,
        *,
        active_only: bool = True,
    ) -> int:
        where_clause = self._search_where_clause(query_text, active_only=active_only)
        with self.db.get_session() as session:
            return int(
                session.execute(
                    select(func.count(AShareUniverse.id)).where(where_clause)
                ).scalar()
                or 0
            )

    def search(
        self,
        query_text: str,
        *,
        limit: int = 20,
        offset: int = 0,
        active_only: bool = True,
    ) -> List[AShareUniverse]:
        safe_limit = max(1, min(int(limit), 100))
        safe_offset = max(0, int(offset))
        where_clause = self._search_where_clause(query_text, active_only=active_only)
        with self.db.get_session() as session:
            rows = session.execute(
                select(AShareUniverse)
                .where(where_clause)
                .order_by(AShareUniverse.code)
                .offset(safe_offset)
                .limit(safe_limit)
            ).scalars().all()
            return list(rows)

    @staticmethod
    def _normalize_search_keyword(query_text: str) -> str:
        keyword = str(query_text or "").strip()
        if not keyword:
            return ""
        upper = keyword.upper()
        if "." in upper:
            upper = upper.split(".", 1)[0]
        if upper.startswith(("SH", "SZ", "BJ")) and len(upper) > 2:
            upper = upper[2:]
        if upper.isdigit():
            return upper.zfill(6)[:6]
        return keyword

    def purge_snapshots_before(self, cutoff_date: date) -> int:
        with self.db.get_session() as session:
            result = session.execute(
                AShareSnapshot.__table__.delete().where(AShareSnapshot.data_date < cutoff_date)
            )
            session.commit()
            return int(result.rowcount or 0)

    def _fetch_existing_universe_codes(self, codes: Sequence[str]) -> set[str]:
        normalized = sorted({normalize_a_share_code(code) for code in codes if normalize_a_share_code(code)})
        if not normalized:
            return set()
        existing: set[str] = set()
        with self.db.get_session() as session:
            for index in range(0, len(normalized), _SQLITE_CHUNK):
                chunk = normalized[index : index + _SQLITE_CHUNK]
                rows = session.execute(
                    select(AShareUniverse.code).where(AShareUniverse.code.in_(chunk))
                ).scalars().all()
                existing.update(rows)
        return existing

    def _fetch_existing_snapshot_keys(
        self,
        keys: Sequence[tuple[str, date]],
    ) -> set[tuple[str, date]]:
        normalized_keys = [
            (normalize_a_share_code(code), data_date)
            for code, data_date in keys
            if normalize_a_share_code(code) and data_date is not None
        ]
        if not normalized_keys:
            return set()

        codes = sorted({code for code, _ in normalized_keys})
        existing: set[tuple[str, date]] = set()
        with self.db.get_session() as session:
            rows = session.execute(
                select(AShareSnapshot.code, AShareSnapshot.data_date).where(
                    AShareSnapshot.code.in_(codes)
                )
            ).all()
            existing.update(rows)

        requested = set(normalized_keys)
        return existing & requested

    @classmethod
    def _normalize_universe_row(cls, row: UniverseInput) -> dict:
        if isinstance(row, AShareUniverseRow):
            return row.to_record_dict()
        payload = dict(row)
        payload["code"] = normalize_a_share_code(payload.get("code", ""))
        payload["exchange"] = str(payload.get("exchange") or "").strip().upper()
        payload["name"] = str(payload.get("name") or "").strip()
        payload["active"] = bool(payload.get("active", True))
        return payload

    @classmethod
    def _normalize_snapshot_row(cls, row: SnapshotInput) -> dict:
        if isinstance(row, AShareSnapshotRow):
            return row.to_record_dict()
        payload = dict(row)
        payload["code"] = normalize_a_share_code(payload.get("code", ""))
        fetched_at = payload.get("fetched_at")
        if fetched_at is not None and not isinstance(fetched_at, datetime):
            payload["fetched_at"] = None
        return payload

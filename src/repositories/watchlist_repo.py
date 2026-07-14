# -*- coding: utf-8 -*-
"""Per-user watchlist repository."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import delete, select

from src.storage import DatabaseManager, UserWatchlistItem, utc_naive_now


class WatchlistRepository:
    """DB access for user_watchlist_items."""

    def __init__(self, db_manager: Optional[DatabaseManager] = None):
        self.db = db_manager or DatabaseManager.get_instance()

    def list_codes(self, user_id: int) -> List[str]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(UserWatchlistItem)
                .where(UserWatchlistItem.user_id == user_id)
                .order_by(UserWatchlistItem.sort_order.asc(), UserWatchlistItem.id.asc())
            ).scalars().all()
            return [row.stock_code for row in rows]

    def add_code(self, user_id: int, stock_code: str) -> bool:
        """Add code if missing. Returns True if inserted."""
        code = (stock_code or "").strip()
        if not code:
            return False
        with self.db.get_session() as session:
            existing = session.execute(
                select(UserWatchlistItem)
                .where(
                    UserWatchlistItem.user_id == user_id,
                    UserWatchlistItem.stock_code == code,
                )
                .limit(1)
            ).scalar_one_or_none()
            if existing is not None:
                return False
            max_order = session.execute(
                select(UserWatchlistItem.sort_order)
                .where(UserWatchlistItem.user_id == user_id)
                .order_by(UserWatchlistItem.sort_order.desc())
                .limit(1)
            ).scalar_one_or_none()
            session.add(
                UserWatchlistItem(
                    user_id=user_id,
                    stock_code=code,
                    sort_order=int(max_order or 0) + 1,
                    created_at=utc_naive_now(),
                    updated_at=utc_naive_now(),
                )
            )
            session.commit()
            return True

    def remove_code(self, user_id: int, stock_code: str) -> bool:
        code = (stock_code or "").strip()
        if not code:
            return False
        with self.db.get_session() as session:
            result = session.execute(
                delete(UserWatchlistItem).where(
                    UserWatchlistItem.user_id == user_id,
                    UserWatchlistItem.stock_code == code,
                )
            )
            session.commit()
            return bool(result.rowcount)

    def replace_codes(self, user_id: int, codes: List[str]) -> None:
        normalized = [c.strip() for c in codes if c and str(c).strip()]
        with self.db.get_session() as session:
            session.execute(
                delete(UserWatchlistItem).where(UserWatchlistItem.user_id == user_id)
            )
            for idx, code in enumerate(normalized):
                session.add(
                    UserWatchlistItem(
                        user_id=user_id,
                        stock_code=code,
                        sort_order=idx,
                        created_at=utc_naive_now(),
                        updated_at=utc_naive_now(),
                    )
                )
            session.commit()

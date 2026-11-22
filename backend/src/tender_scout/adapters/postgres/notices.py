from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine

from tender_scout.adapters.postgres.notice_body import from_body, to_body
from tender_scout.adapters.postgres.tables import notices
from tender_scout.domain.notice import Kept, Known, Notice


class PostgresNotices:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def save(self, notice: Notice, read_at: datetime) -> None:
        row = {
            "id": notice.id,
            "number": notice.number,
            "version": notice.version,
            "status": notice.status,
            "title": notice.title,
            "buyer_name": notice.buyer.name,
            "published_on": notice.published_on,
            "deadline": notice.deadline,
            "changed_at": notice.changed_at,
            "cpv_codes": sorted(notice.cpv_codes),
            "body": to_body(notice),
            "read_at": read_at,
        }
        # One statement, so a reading replaces the earlier one whole or not at all.
        statement = insert(notices).values(row)
        statement = statement.on_conflict_do_update(
            index_elements=[notices.c.id],
            set_={name: statement.excluded[name] for name in row if name != "id"},
        )
        async with self._engine.begin() as connection:
            await connection.execute(statement)

    async def get(self, notice_id: int) -> Kept | None:
        async with self._engine.connect() as connection:
            row = (
                await connection.execute(
                    select(notices.c.body, notices.c.read_at).where(notices.c.id == notice_id)
                )
            ).one_or_none()
        if row is None:
            return None
        return Kept(notice=from_body(row.body), read_at=row.read_at)

    async def known(self) -> Mapping[int, Known]:
        async with self._engine.connect() as connection:
            rows = await connection.execute(
                select(notices.c.id, notices.c.title, notices.c.deadline, notices.c.read_at)
            )
            return {
                row.id: Known(title=row.title, deadline=row.deadline, read_at=row.read_at)
                for row in rows
            }

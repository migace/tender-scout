"""A notice store that lives in memory, for fast tests.

The contract tests run against this and against PostgreSQL, so it cannot
quietly become more forgiving than the database.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from tender_scout.domain.notice import Kept, Known, Notice


class InMemoryNotices:
    def __init__(self) -> None:
        self._kept: dict[int, Kept] = {}

    async def save(self, notice: Notice, read_at: datetime) -> None:
        self._kept[notice.id] = Kept(notice=notice, read_at=read_at)

    async def get(self, notice_id: int) -> Kept | None:
        return self._kept.get(notice_id)

    async def known(self) -> Mapping[int, Known]:
        return {
            notice_id: Known(
                title=kept.notice.title, deadline=kept.notice.deadline, read_at=kept.read_at
            )
            for notice_id, kept in self._kept.items()
        }

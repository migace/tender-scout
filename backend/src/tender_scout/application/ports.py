"""What the use cases need from the outside world."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from tender_scout.domain.notice import Kept, Known, Notice, NoticeSummary


@dataclass(frozen=True, slots=True)
class SearchPage:
    summaries: tuple[NoticeSummary, ...]
    # Whether the source has a further page for the same search.
    more: bool


class SourceUnavailable(Exception):
    """The source did not answer, or answered with an error."""


class SourceChanged(Exception):
    """The source answered in a shape this project does not know.

    Carries the place in the answer where the surprise was, so that the
    message alone says which field moved.
    """


class NoticeSource(Protocol):
    """Where notices come from. Every call is one request to someone else's server."""

    async def search(self, cpv_code: str, page: int) -> SearchPage:
        """One page of open notices under a CPV code. Pages start at 1."""
        ...

    async def read(self, notice_id: int) -> Notice: ...


class NoticeRepository(Protocol):
    async def save(self, notice: Notice, read_at: datetime) -> None:
        """Keep the notice, replacing an earlier reading of the same one."""
        ...

    async def get(self, notice_id: int) -> Kept | None: ...

    async def known(self) -> Mapping[int, Known]:
        """Every kept notice, by id."""
        ...

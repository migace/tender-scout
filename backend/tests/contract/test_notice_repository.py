"""What every notice store must do, run against the fake and against PostgreSQL."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tender_scout.adapters.baza.parsing import parse_notice
from tender_scout.adapters.in_memory_notices import InMemoryNotices
from tender_scout.adapters.postgres.notices import PostgresNotices
from tender_scout.application.ports import NoticeRepository
from tender_scout.domain.notice import Kept, Known
from tests.factories import NOW, RECORDED_NOTICES, a_notice, recorded

pytestmark = pytest.mark.anyio


@pytest.fixture(
    params=["in_memory", pytest.param("postgres", marks=pytest.mark.integration)],
)
def notices(request: pytest.FixtureRequest) -> NoticeRepository:
    if request.param == "in_memory":
        return InMemoryNotices()
    engine: AsyncEngine = request.getfixturevalue("engine")
    return PostgresNotices(engine)


async def test_a_notice_that_was_never_kept_is_not_there(notices: NoticeRepository) -> None:
    assert await notices.get(404) is None
    assert await notices.known() == {}


async def test_a_kept_notice_comes_back_whole(notices: NoticeRepository) -> None:
    notice = a_notice(7)

    await notices.save(notice, NOW)

    assert await notices.get(7) == Kept(notice=notice, read_at=NOW)


@pytest.mark.parametrize("notice_id", RECORDED_NOTICES)
async def test_a_real_notice_comes_back_whole(notices: NoticeRepository, notice_id: int) -> None:
    # Thousands of characters of Polish text, tabs and line breaks included.
    notice = parse_notice(recorded(f"notice_{notice_id}.json"))

    await notices.save(notice, NOW)

    kept = await notices.get(notice_id)
    assert kept is not None
    assert kept.notice == notice


async def test_a_second_reading_replaces_the_first(notices: NoticeRepository) -> None:
    first = a_notice(7)
    later = NOW + timedelta(days=3)
    edited = replace(first, version=101, title="Zmieniony tytuł", orders=first.orders[:1])
    await notices.save(first, NOW)

    await notices.save(edited, later)

    assert await notices.get(7) == Kept(notice=edited, read_at=later)
    assert len(await notices.known()) == 1


async def test_known_says_what_deciding_on_a_reread_needs(notices: NoticeRepository) -> None:
    one, two = a_notice(1), a_notice(2, title="Kurs spawania", deadline=NOW + timedelta(days=30))
    await notices.save(one, NOW)
    await notices.save(two, NOW + timedelta(hours=1))

    assert await notices.known() == {
        1: Known(title=one.title, deadline=one.deadline, read_at=NOW),
        2: Known(title="Kurs spawania", deadline=two.deadline, read_at=NOW + timedelta(hours=1)),
    }


async def test_times_are_instants_whatever_zone_they_were_given_in(
    notices: NoticeRepository,
) -> None:
    warsaw = timezone(timedelta(hours=1))
    read_at = datetime(2026, 11, 22, 13, 0, tzinfo=warsaw)
    notice = replace(a_notice(1), deadline=datetime(2026, 12, 1, 10, 0, tzinfo=warsaw))

    await notices.save(notice, read_at)

    kept = await notices.get(1)
    assert kept is not None
    assert kept.read_at == datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
    assert kept.notice.deadline == datetime(2026, 12, 1, 9, 0, tzinfo=UTC)
    assert kept.read_at.utcoffset() is not None
    assert kept.notice.deadline.utcoffset() is not None

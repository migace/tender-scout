"""Collecting, against a source that only remembers what it was asked."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta

import pytest

from tender_scout.adapters.in_memory_notices import InMemoryNotices
from tender_scout.application.collect import Collected, collect
from tender_scout.application.ports import SearchPage
from tender_scout.domain.notice import Notice
from tests.factories import EDUCATION, NOW, TRAINING, a_notice, summary_of

pytestmark = pytest.mark.anyio

WEEK = timedelta(days=7)


class ScriptedSource:
    """Lists the notices it was given under each CPV code, two to a page."""

    PAGE = 2

    def __init__(self, listed: dict[str, list[Notice]]) -> None:
        self.listed = listed
        self.asked: list[str] = []

    async def search(self, cpv_code: str, page: int) -> SearchPage:
        self.asked.append(f"search {cpv_code} {page}")
        notices = self.listed.get(cpv_code, [])
        start = (page - 1) * self.PAGE
        return SearchPage(
            summaries=tuple(summary_of(notice) for notice in notices[start : start + self.PAGE]),
            more=start + self.PAGE < len(notices),
        )

    async def read(self, notice_id: int) -> Notice:
        self.asked.append(f"read {notice_id}")
        return next(
            notice
            for notices in self.listed.values()
            for notice in notices
            if notice.id == notice_id
        )

    @property
    def reads(self) -> list[str]:
        return [request for request in self.asked if request.startswith("read")]


class Clock:
    def __init__(self) -> None:
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now


async def run(
    source: ScriptedSource,
    notices: InMemoryNotices,
    clock: Clock,
    *,
    cpv_codes: tuple[str, ...] = (TRAINING,),
    max_requests: int = 100,
) -> Collected:
    return await collect(
        source,
        notices,
        cpv_codes=cpv_codes,
        now=clock,
        max_requests=max_requests,
        refresh_after=WEEK,
    )


async def test_every_listed_notice_is_read_and_kept_with_the_time_of_reading() -> None:
    listed = [a_notice(1), a_notice(2), a_notice(3)]
    source, notices, clock = ScriptedSource({TRAINING: listed}), InMemoryNotices(), Clock()

    collected = await run(source, notices, clock)

    # Two pages of results and three notices.
    assert collected == Collected(listed=3, read=3, kept_as_is=0, requests=5, out_of_requests=False)
    for notice in listed:
        kept = await notices.get(notice.id)
        assert kept is not None
        assert (kept.notice, kept.read_at) == (notice, NOW)


async def test_a_second_run_asks_only_for_the_search_pages() -> None:
    source = ScriptedSource({TRAINING: [a_notice(1), a_notice(2), a_notice(3)]})
    notices, clock = InMemoryNotices(), Clock()
    await run(source, notices, clock)
    source.asked.clear()
    clock.now += timedelta(days=1)

    collected = await run(source, notices, clock)

    assert collected == Collected(listed=3, read=0, kept_as_is=3, requests=2, out_of_requests=False)
    assert source.reads == []


@pytest.mark.parametrize(
    "edited",
    [
        replace(a_notice(2), deadline=a_notice(2).deadline + timedelta(days=5)),
        replace(a_notice(2), title="Szkolenie z obsługi wózków widłowych - zmiana"),
    ],
    ids=["a later deadline", "another title"],
)
async def test_a_notice_whose_listing_changed_is_read_again(edited: Notice) -> None:
    source = ScriptedSource({TRAINING: [a_notice(1), a_notice(2)]})
    notices, clock = InMemoryNotices(), Clock()
    await run(source, notices, clock)
    source.asked.clear()
    source.listed[TRAINING][1] = replace(edited, version=101)
    clock.now += timedelta(hours=1)

    collected = await run(source, notices, clock)

    assert source.reads == ["read 2"]
    assert (collected.read, collected.kept_as_is) == (1, 1)
    kept = await notices.get(2)
    assert kept is not None
    assert (kept.notice.version, kept.read_at) == (101, clock.now)


async def test_an_old_reading_is_refreshed_even_when_the_listing_looks_the_same() -> None:
    # The search result has no modification date, so an edit to the conditions
    # alone shows nowhere. After a week the notice is opened again regardless.
    source = ScriptedSource({TRAINING: [a_notice(1)]})
    notices, clock = InMemoryNotices(), Clock()
    await run(source, notices, clock)

    source.asked.clear()
    clock.now = NOW + WEEK - timedelta(seconds=1)
    await run(source, notices, clock)
    assert source.reads == []

    clock.now = NOW + WEEK
    await run(source, notices, clock)
    assert source.reads == ["read 1"]


async def test_a_run_stops_at_its_ceiling_and_the_next_one_carries_on() -> None:
    listed = [a_notice(number) for number in range(1, 6)]
    source, notices, clock = ScriptedSource({TRAINING: listed}), InMemoryNotices(), Clock()

    first = await run(source, notices, clock, max_requests=4)

    # search, read 1, read 2, search: the ceiling is reached before notice 3.
    assert first == Collected(listed=2, read=2, kept_as_is=0, requests=4, out_of_requests=True)
    assert source.asked == [
        f"search {TRAINING} 1",
        "read 1",
        "read 2",
        f"search {TRAINING} 2",
    ]

    source.asked.clear()
    second = await run(source, notices, clock)

    assert second == Collected(listed=5, read=3, kept_as_is=2, requests=6, out_of_requests=False)
    assert source.reads == ["read 3", "read 4", "read 5"]


async def test_no_request_is_made_past_the_ceiling() -> None:
    source = ScriptedSource({TRAINING: [a_notice(1)], EDUCATION: [a_notice(2)]})

    collected = await run(
        source, InMemoryNotices(), Clock(), cpv_codes=(TRAINING, EDUCATION), max_requests=2
    )

    assert source.asked == [f"search {TRAINING} 1", "read 1"]
    assert collected.out_of_requests is True


async def test_a_notice_listed_under_two_codes_is_read_once() -> None:
    both = a_notice(1, cpv_codes=(TRAINING, EDUCATION))
    source = ScriptedSource({TRAINING: [both], EDUCATION: [both, a_notice(2)]})

    collected = await run(source, InMemoryNotices(), Clock(), cpv_codes=(TRAINING, EDUCATION))

    assert source.reads == ["read 1", "read 2"]
    assert collected == Collected(listed=2, read=2, kept_as_is=0, requests=4, out_of_requests=False)


async def test_a_code_with_no_open_notices_costs_one_request() -> None:
    source = ScriptedSource({})

    collected = await run(source, InMemoryNotices(), Clock())

    assert collected == Collected(listed=0, read=0, kept_as_is=0, requests=1, out_of_requests=False)

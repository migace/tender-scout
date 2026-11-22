"""Bring the open notices under some CPV codes into our store.

The source belongs to someone else, so a run has a ceiling of requests and
spends them only where they tell us something: a search page, or a notice we
do not have, or have in a reading that may be out of date.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from tender_scout.application.ports import NoticeRepository, NoticeSource
from tender_scout.domain.notice import needs_reading


@dataclass(frozen=True, slots=True)
class Collected:
    # Distinct notices the searches listed.
    listed: int
    # Notices opened at the source and kept.
    read: int
    # Notices listed and left alone, because the kept reading is good enough.
    kept_as_is: int
    requests: int
    # True when the ceiling was reached with work still left. The next run continues.
    out_of_requests: bool


async def collect(
    source: NoticeSource,
    notices: NoticeRepository,
    *,
    cpv_codes: Sequence[str],
    now: Callable[[], datetime],
    max_requests: int,
    refresh_after: timedelta,
) -> Collected:
    known = await notices.known()
    listed: set[int] = set()
    read = kept_as_is = requests = 0

    def result(out_of_requests: bool) -> Collected:
        return Collected(len(listed), read, kept_as_is, requests, out_of_requests)

    for cpv_code in cpv_codes:
        page_number = 1
        while True:
            if requests >= max_requests:
                return result(out_of_requests=True)
            page = await source.search(cpv_code, page_number)
            requests += 1

            for summary in page.summaries:
                # A notice with two of our codes is listed under both.
                if summary.id in listed:
                    continue
                if not needs_reading(known.get(summary.id), summary, now(), refresh_after):
                    listed.add(summary.id)
                    kept_as_is += 1
                    continue
                if requests >= max_requests:
                    return result(out_of_requests=True)
                notice = await source.read(summary.id)
                requests += 1
                await notices.save(notice, now())
                listed.add(summary.id)
                read += 1

            if not page.more:
                break
            page_number += 1

    return result(out_of_requests=False)

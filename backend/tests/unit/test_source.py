"""The HTTP adapter, against a transport that answers from the recorded fixtures."""

from __future__ import annotations

import httpx
import pytest
from pydantic import ValidationError

from tender_scout.adapters.baza.source import BazaSource, baza_client
from tender_scout.application.ports import SourceChanged, SourceUnavailable
from tender_scout.config import SHORTEST_PAUSE, Settings
from tests.factories import TRAINING, recorded

pytestmark = pytest.mark.anyio

BASE = "https://base.invalid"


class Replay:
    """Answers like the Base and keeps what it was asked and how long was waited."""

    def __init__(self, *, total: int | None = None, status: int = 200) -> None:
        self.requests: list[httpx.Request] = []
        self.timeline: list[str] = []
        self._total = total
        self._status = status

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.timeline.append(f"GET {request.url.path}")
        if self._status != httpx.codes.OK:
            return httpx.Response(self._status, json={"status": "Error"})
        if request.url.path == "/api/announcements/search":
            answer = recorded("search.json")
            if self._total is not None:
                answer["data"]["meta"]["total"] = self._total
            return httpx.Response(200, json=answer)
        notice_id = request.url.path.rsplit("/", 1)[-1]
        return httpx.Response(200, json=recorded(f"notice_{notice_id}.json"))

    async def sleep(self, seconds: float) -> None:
        self.timeline.append(f"wait {seconds}")

    def source(self, *, pause: float = 2.0, page_size: int = 50) -> BazaSource:
        client = httpx.AsyncClient(
            base_url=BASE,
            headers=baza_client(BASE, "tender-scout/test").headers,
            transport=httpx.MockTransport(self),
        )
        return BazaSource(client, pause=pause, page_size=page_size, sleep=self.sleep)


async def test_a_search_asks_for_open_notices_under_the_code() -> None:
    replay = Replay()

    page = await replay.source().search(TRAINING, 3)

    (request,) = replay.requests
    assert request.url.path == "/api/announcements/search"
    assert request.url.params.multi_items() == [
        ("page", "3"),
        ("limit", "50"),
        ("sort", "default"),
        # Without a status the Base answers 500.
        ("status[]", "PUBLISHED"),
        ("cpvItem[]", TRAINING),
    ]
    assert [summary.id for summary in page.summaries] == [261815, 297545, 297491]


async def test_requests_say_who_is_asking_and_want_json() -> None:
    replay = Replay()

    await replay.source().read(297898)

    assert replay.requests[0].headers["user-agent"] == "tender-scout/test"
    assert replay.requests[0].headers["accept"] == "application/json"


async def test_every_request_after_the_first_waits_first() -> None:
    replay = Replay()
    source = replay.source(pause=2.5)

    await source.search(TRAINING, 1)
    await source.read(297898)
    await source.read(298002)

    assert replay.timeline == [
        "GET /api/announcements/search",
        "wait 2.5",
        "GET /api/announcements/297898",
        "wait 2.5",
        "GET /api/announcements/298002",
    ]


@pytest.mark.parametrize(
    ("total", "page", "page_size", "more"),
    [
        (88, 1, 50, True),
        (88, 2, 50, False),
        (100, 2, 50, False),
        (101, 2, 50, True),
        (3, 1, 50, False),
    ],
)
async def test_there_is_a_further_page_while_the_total_is_not_reached(
    total: int, page: int, page_size: int, more: bool
) -> None:
    replay = Replay(total=total)

    assert (await replay.source(page_size=page_size).search(TRAINING, page)).more is more


async def test_an_empty_page_ends_the_search_whatever_the_total_says() -> None:
    def empty(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"advertisements": [], "meta": {"total": 999}}})

    client = httpx.AsyncClient(base_url=BASE, transport=httpx.MockTransport(empty))

    assert (await BazaSource(client, pause=1.0).search(TRAINING, 7)).more is False


@pytest.mark.parametrize("status", [401, 404, 429, 500, 503])
async def test_an_error_answer_means_the_source_is_unavailable(status: int) -> None:
    replay = Replay(status=status)

    with pytest.raises(SourceUnavailable, match=f"answered {status}"):
        await replay.source().read(297898)


async def test_a_failed_connection_means_the_source_is_unavailable() -> None:
    def refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route", request=request)

    client = httpx.AsyncClient(base_url=BASE, transport=httpx.MockTransport(refuse))

    with pytest.raises(SourceUnavailable, match="ConnectError"):
        await BazaSource(client, pause=1.0).read(1)


async def test_an_answer_that_is_not_json_means_the_source_changed() -> None:
    def page(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>Przerwa techniczna</html>")

    client = httpx.AsyncClient(base_url=BASE, transport=httpx.MockTransport(page))

    with pytest.raises(SourceChanged, match="did not answer with JSON"):
        await BazaSource(client, pause=1.0).read(1)


def test_the_pause_cannot_be_configured_away(monkeypatch: pytest.MonkeyPatch) -> None:
    assert Settings().source_pause >= SHORTEST_PAUSE

    monkeypatch.setenv("TS_SOURCE_PAUSE", str(SHORTEST_PAUSE / 2))
    with pytest.raises(ValidationError):
        Settings()

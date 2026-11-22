"""Reading the Baza Konkurencyjności over HTTP, one unhurried request at a time.

These are the endpoints the Base's own search page reads. ADR 0001 has the
rules; the one enforced here is the pause between requests.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx

from tender_scout.adapters.baza.parsing import parse_notice, parse_search
from tender_scout.application.ports import SearchPage, SourceChanged, SourceUnavailable
from tender_scout.domain.notice import Notice

# Only notices that still take offers. The search answers with an error when
# no status is given at all.
OPEN = "PUBLISHED"


def baza_client(base_url: str, user_agent: str) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=base_url,
        headers={"User-Agent": user_agent, "Accept": "application/json"},
        timeout=30.0,
    )


class BazaSource:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        pause: float,
        page_size: int = 50,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._client = client
        self._pause = pause
        self._page_size = page_size
        self._sleep = sleep
        self._asked_before = False

    async def search(self, cpv_code: str, page: int) -> SearchPage:
        payload = await self._get(
            "/api/announcements/search",
            [
                ("page", str(page)),
                ("limit", str(self._page_size)),
                ("sort", "default"),
                ("status[]", OPEN),
                ("cpvItem[]", cpv_code),
            ],
        )
        summaries, total = parse_search(payload)
        # An empty page ends the search whatever the total claims, so a wrong
        # total cannot keep a run asking for ever.
        more = bool(summaries) and page * self._page_size < total
        return SearchPage(summaries=summaries, more=more)

    async def read(self, notice_id: int) -> Notice:
        return parse_notice(await self._get(f"/api/announcements/{notice_id}", []))

    async def _get(self, path: str, params: list[tuple[str, str]]) -> object:
        if self._asked_before:
            await self._sleep(self._pause)
        self._asked_before = True
        try:
            response = await self._client.get(path, params=tuple(params))
        except httpx.HTTPError as error:
            raise SourceUnavailable(f"{path}: {error!r}") from error
        if response.status_code != httpx.codes.OK:
            raise SourceUnavailable(f"{path} answered {response.status_code}")
        try:
            payload: object = response.json()
        except ValueError:
            raise SourceChanged(f"{path} did not answer with JSON") from None
        return payload

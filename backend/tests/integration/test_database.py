"""The schema as migrations build it, and a whole collection run into it."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncEngine

from tender_scout.adapters.baza.source import BazaSource
from tender_scout.adapters.postgres.notices import PostgresNotices
from tender_scout.adapters.postgres.tables import metadata
from tender_scout.application.collect import collect
from tests.factories import INVENTED_PERSON, RECORDED_NOTICES, TRAINING, recorded

pytestmark = [pytest.mark.integration, pytest.mark.anyio]


async def test_the_migrations_build_the_tables_the_code_expects(engine: AsyncEngine) -> None:
    def differences(connection: Connection) -> list[Any]:
        return list(compare_metadata(MigrationContext.configure(connection), metadata))

    async with engine.connect() as connection:
        assert await connection.run_sync(differences) == []


def the_base(request: httpx.Request) -> httpx.Response:
    """Lists the two recorded notices and serves them, contact people and all."""
    if request.url.path == "/api/announcements/search":
        versions = [
            recorded(f"notice_{notice_id}.json")["data"]["advertisement"]
            for notice_id in RECORDED_NOTICES
        ]
        listing = [
            {
                "id": version["advertisement"]["id"],
                "title": version["title"],
                "submission_deadline": version["submission_deadline"],
            }
            for version in versions
        ]
        return httpx.Response(
            200, json={"data": {"advertisements": listing, "meta": {"total": len(listing)}}}
        )
    return httpx.Response(200, json=recorded(f"notice_{request.url.path.rsplit('/', 1)[-1]}.json"))


async def _no_wait(seconds: float) -> None:
    return None


async def test_collected_notices_are_in_the_database_without_the_people(
    engine: AsyncEngine,
) -> None:
    client = httpx.AsyncClient(
        base_url="https://base.invalid", transport=httpx.MockTransport(the_base)
    )
    read_at = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)

    collected = await collect(
        BazaSource(client, pause=1.0, sleep=_no_wait),
        PostgresNotices(engine),
        cpv_codes=[TRAINING],
        now=lambda: read_at,
        max_requests=10,
        refresh_after=timedelta(days=7),
    )

    assert (collected.read, collected.requests, collected.out_of_requests) == (2, 3, False)
    async with engine.connect() as connection:
        rows = (
            await connection.execute(
                text(
                    "SELECT id, read_at, cpv_codes, deadline, notices::text AS everything"
                    " FROM notices ORDER BY id"
                )
            )
        ).all()
        by_code = await connection.scalar(
            text("SELECT count(*) FROM notices WHERE cpv_codes @> ARRAY[:code]"),
            {"code": TRAINING},
        )

    assert [row.id for row in rows] == sorted(RECORDED_NOTICES)
    assert by_code == 2
    for row in rows:
        assert row.read_at == read_at
        assert TRAINING in row.cpv_codes
        # Every column of the row as text: nothing of the contact person is anywhere.
        for detail in INVENTED_PERSON:
            assert detail not in row.everything
    assert rows[0].deadline == datetime(2026, 11, 23, 8, 0, tzinfo=UTC)

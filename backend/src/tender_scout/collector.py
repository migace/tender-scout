"""One collection run: ``python -m tender_scout.collector``.

Prints a single JSON line saying what the run did, and exits with 1 when the
source could not be read, so that whatever schedules it can tell.
"""

from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import create_async_engine

from tender_scout.adapters.baza.source import BazaSource, baza_client
from tender_scout.adapters.postgres.notices import PostgresNotices
from tender_scout.application.collect import Collected, collect
from tender_scout.application.ports import SourceChanged, SourceUnavailable
from tender_scout.config import Settings


async def run(settings: Settings) -> Collected:
    engine = create_async_engine(settings.database_url)
    try:
        async with baza_client(settings.source_url, settings.user_agent) as client:
            return await collect(
                BazaSource(client, pause=settings.source_pause),
                PostgresNotices(engine),
                cpv_codes=settings.cpv_codes,
                now=lambda: datetime.now(UTC),
                max_requests=settings.source_requests_per_run,
                refresh_after=timedelta(days=settings.refresh_after_days),
            )
    finally:
        await engine.dispose()


def main() -> int:
    try:
        collected = asyncio.run(run(Settings()))
    except (SourceUnavailable, SourceChanged) as error:
        print(
            json.dumps(
                {"event": "collect.failed", "error": type(error).__name__, "detail": str(error)}
            )
        )
        return 1
    print(json.dumps({"event": "collect.finished", **asdict(collected)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

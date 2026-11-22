"""Record answers of the Baza Konkurencyjności for the tests to replay.

    uv run python scripts/record_fixture.py 297898 261815

Fetches one page of the training search and the notices named, slowly, and
writes them under ``tests/fixtures/baza`` in the Base's own shape with the
people taken out:

- every contact person is replaced by one invented person, so the tests can
  check that even an invented one never reaches the store,
- the accounts that created or changed a record are blanked,
- addresses and phone numbers typed into free text are replaced.

Run it by hand, rarely. The tests never call the Base (ADR 0001).
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx

from tender_scout.config import Settings
from tender_scout.domain.privacy import without_contact_details

FIXTURES = Path(__file__).parents[1] / "tests" / "fixtures" / "baza"

# Nobody. The tests look for these three strings in everything that is kept.
INVENTED_PERSON = {
    "id": 1,
    "forename": "Zmyślona",
    "surname": "Nieistniejąca",
    "phone_number": "000111222",
    "email": "nobody@invalid.example",
    "created_by": None,
    "created_at": "2026-01-01 00:00:00",
    "modified_at": "2026-01-01 00:00:00",
    "modified_by": None,
}
ACCOUNTS = {"created_by", "modified_by"}
# The search page is cut to this many results: enough to test paging.
KEPT_RESULTS = 3


def without_people(value: object) -> object:
    if isinstance(value, dict):
        cleaned: dict[str, object] = {}
        for key, inner in value.items():
            if key == "contact_persons":
                cleaned[key] = [INVENTED_PERSON] if inner else []
            elif key in ACCOUNTS:
                cleaned[key] = None
            else:
                cleaned[key] = without_people(inner)
        return cleaned
    if isinstance(value, list):
        return [without_people(inner) for inner in value]
    if isinstance(value, str):
        return without_contact_details(value)
    return value


def write(name: str, payload: object) -> None:
    path = FIXTURES / name
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(FIXTURES.parents[2])}")


def main(notice_ids: list[int]) -> None:
    settings = Settings()
    FIXTURES.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": settings.user_agent, "Accept": "application/json"}
    with httpx.Client(base_url=settings.source_url, headers=headers, timeout=30.0) as client:
        search = client.get(
            "/api/announcements/search",
            params=[
                ("page", "1"),
                ("limit", "20"),
                ("sort", "default"),
                ("status[]", "PUBLISHED"),
                ("cpvItem[]", settings.cpv_codes[0]),
            ],
        )
        search.raise_for_status()
        page = search.json()
        page["data"]["advertisements"] = page["data"]["advertisements"][:KEPT_RESULTS]
        write("search.json", without_people(page))

        for notice_id in notice_ids:
            time.sleep(settings.source_pause)
            response = client.get(f"/api/announcements/{notice_id}")
            response.raise_for_status()
            write(f"notice_{notice_id}.json", without_people(response.json()))


if __name__ == "__main__":
    main([int(argument) for argument in sys.argv[1:]])

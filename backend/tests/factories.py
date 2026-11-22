"""Notices for tests: invented ones built here, and recorded ones read from disk."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from tender_scout.domain.notice import (
    Buyer,
    Condition,
    Cpv,
    Criterion,
    Item,
    Notice,
    NoticeSummary,
    Order,
    Place,
)

FIXTURES = Path(__file__).parent / "fixtures" / "baza"
RECORDED_NOTICES = (297898, 298002)

# The invented contact person the recorder puts in every fixture. None of this
# may ever be found in a notice or in the database.
INVENTED_PERSON = ("Zmyślona", "Nieistniejąca", "000111222", "nobody@invalid.example")

NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)
TRAINING = "80500000-9"
EDUCATION = "80000000-4"


def recorded(name: str) -> Any:
    """An answer of the Base, as ``scripts/record_fixture.py`` wrote it."""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def a_notice(
    notice_id: int = 1,
    *,
    title: str = "Szkolenie z obsługi wózków widłowych",
    deadline: datetime = NOW + timedelta(days=10),
    cpv_codes: tuple[str, ...] = (TRAINING,),
    version: int = 100,
) -> Notice:
    return Notice(
        id=notice_id,
        number=f"2026-1-{notice_id}",
        version=version,
        status="PUBLISHED",
        title=title,
        buyer=Buyer(name="Fundacja Przykład", identifier_kind="nip", identifier="1234567890"),
        published_on=date(2026, 11, 20),
        deadline=deadline,
        changed_at=NOW - timedelta(days=2),
        partial_offers=True,
        orders=(
            Order(
                title="Szkolenie",
                estimated_value=Decimal("12500.50"),
                items=(
                    Item(
                        description="Przeprowadzenie szkolenia dla 12 osób.",
                        category="Usługa",
                        subcategory="Usługi szkoleniowe",
                        cpv=tuple(Cpv(code=code, name=f"nazwa {code}") for code in cpv_codes),
                        places=(
                            Place(
                                country="Polska",
                                voivodeship="śląskie",
                                poviat=None,
                                commune=None,
                                locality="Chorzów",
                            ),
                        ),
                        conditions=(
                            Condition(
                                kind="Wiedza i doświadczenie",
                                text="Co najmniej 3 szkolenia w ostatnich 3 latach.",
                            ),
                            Condition(kind=None, text="Brak powiązań z zamawiającym."),
                        ),
                    ),
                ),
                criteria=(
                    Criterion(text="Cena - 70%", is_price=True),
                    Criterion(text="Doświadczenie - 30%", is_price=False),
                ),
            ),
            # An order with nothing in it and no estimate: the Base allows both.
            Order(title="Catering", estimated_value=None, items=(), criteria=()),
        ),
        attachments=("Załącznik nr 1.docx",),
    )


def summary_of(notice: Notice) -> NoticeSummary:
    return NoticeSummary(id=notice.id, title=notice.title, deadline=notice.deadline)

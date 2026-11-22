"""The Base's answers, as recorded, turned into notices."""

from __future__ import annotations

import copy
from dataclasses import asdict
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest

from tender_scout.adapters.baza.parsing import parse_notice, parse_search
from tender_scout.application.ports import SourceChanged
from tests.factories import EDUCATION, INVENTED_PERSON, RECORDED_NOTICES, TRAINING, recorded


def small() -> Any:
    return recorded("notice_297898.json")


def test_a_recorded_notice_becomes_a_notice() -> None:
    notice = parse_notice(small())

    assert notice.id == 297898
    assert notice.number == "2026-28705-297898"
    assert notice.version == 395157
    assert notice.status == "PUBLISHED"
    assert notice.title.startswith("Zapytanie ofertowe nr 73/ARZ/FESL.05.04")
    assert notice.buyer.name == "Fundacja Instytut Edukacji"
    assert (notice.buyer.identifier_kind, notice.buyer.identifier) == ("nip", "5472203701")
    assert notice.published_on == date(2026, 11, 13)
    assert notice.partial_offers is False
    assert len(notice.attachments) == 6
    assert {TRAINING, EDUCATION} <= notice.cpv_codes

    (order,) = notice.orders
    assert order.title == "Szkolenie zawodowe"
    assert order.estimated_value is None
    assert [criterion.is_price for criterion in order.criteria] == [True, False, False, False]
    assert order.criteria[0].text.startswith("Cena - 30%")

    (item,) = order.items
    assert (item.category, item.subcategory) == ("Usługa", "Usługi szkoleniowe")
    assert item.places[0].locality == "Chorzów"
    assert item.places[0].voivodeship == "śląskie"
    assert "Wiedza i doświadczenie" in [condition.kind for condition in item.conditions]


def test_the_orders_of_a_notice_keep_their_own_conditions_and_criteria() -> None:
    notice = parse_notice(recorded("notice_298002.json"))

    training, catering, exam = notice.orders
    assert [len(order.criteria) for order in (training, catering, exam)] == [3, 1, 2]
    assert catering.items[0].subcategory == "Usługi cateringowe"
    assert len(training.items[0].conditions) == 3
    assert notice.partial_offers is True


def test_times_are_polish_wall_clock_times_and_become_instants() -> None:
    notice = parse_notice(small())

    # "2026-11-23 09:00:00" in the answer. In November Poland is an hour ahead of UTC.
    assert notice.deadline == datetime(2026, 11, 23, 8, 0, tzinfo=UTC)
    assert notice.changed_at == datetime(2026, 11, 13, 8, 55, 58, tzinfo=UTC)


def test_a_summer_time_is_two_hours_ahead() -> None:
    answer = small()
    answer["data"]["advertisement"]["submission_deadline"] = "2026-07-01 09:00:00"

    assert parse_notice(answer).deadline == datetime(2026, 7, 1, 7, 0, tzinfo=UTC)


def test_an_estimate_is_money_not_a_float() -> None:
    answer = small()
    answer["data"]["advertisement"]["orders"][0]["estimated_value"] = "60000000,10"

    assert parse_notice(answer).orders[0].estimated_value == Decimal("60000000.10")


@pytest.mark.parametrize("notice_id", RECORDED_NOTICES)
def test_the_contact_person_never_reaches_the_notice(notice_id: int) -> None:
    answer = recorded(f"notice_{notice_id}.json")
    # The fixture does have one, or this test would prove nothing.
    assert answer["data"]["advertisement"]["contact_persons"]

    kept = repr(asdict(parse_notice(answer)))

    for detail in INVENTED_PERSON:
        assert detail not in kept


def test_contact_details_typed_into_free_text_are_taken_out() -> None:
    answer = small()
    version = answer["data"]["advertisement"]
    version["title"] += " (pytania: anna.nowak@fundacja.example.pl)"
    item = version["orders"][0]["order_items"][0]
    item["description"] += " Kontakt tel. 512 345 678."
    item["participation_conditions"][0]["description"] = "Wyślij CV na kadry@fundacja.example.pl"
    version["orders"][0]["evaluation_criteria"][0]["description"] += " tel: 32 123 45 67"
    version["attachments"][0]["name"] = "do jan@fundacja.example.pl.docx"

    kept = repr(asdict(parse_notice(answer)))

    assert "@" not in kept
    assert "512 345 678" not in kept
    assert "32 123 45 67" not in kept
    assert kept.count("[e-mail]") == 3
    assert kept.count("[telefon]") == 2


def test_a_search_page_lists_summaries_and_the_total() -> None:
    summaries, total = parse_search(recorded("search.json"))

    assert total == 88
    assert [summary.id for summary in summaries] == [261815, 297545, 297491]
    assert summaries[1].deadline == datetime(2026, 12, 14, 7, 0, tzinfo=UTC)


def test_a_summary_and_its_notice_agree_on_title_and_deadline() -> None:
    # Collecting compares the two to decide whether a kept notice was edited.
    # If the search cut or reformatted titles, every notice would look edited.
    answer = small()
    version = answer["data"]["advertisement"]
    listing = {
        "status": "OK",
        "data": {
            "advertisements": [
                {
                    "id": version["advertisement"]["id"],
                    "title": version["title"],
                    "submission_deadline": version["submission_deadline"],
                }
            ],
            "meta": {"total": 1},
        },
    }

    ((summary,), _) = parse_search(listing)
    notice = parse_notice(answer)

    assert (summary.id, summary.title, summary.deadline) == (
        notice.id,
        notice.title,
        notice.deadline,
    )


def _without(answer: Any, *path: str | int) -> Any:
    changed = copy.deepcopy(answer)
    target = changed
    for step in path[:-1]:
        target = target[step]
    del target[path[-1]]
    return changed


@pytest.mark.parametrize(
    ("path", "place"),
    [
        (
            ("data", "advertisement", "submission_deadline"),
            "notice.data.advertisement.submission_deadline",
        ),
        (
            ("data", "advertisement", "advertisement", "number"),
            "advertisement.advertisement.number",
        ),
        (
            ("data", "advertisement", "orders", 0, "order_items", 0, "participation_conditions"),
            "orders[0].order_items[0].participation_conditions",
        ),
        (
            ("data", "advertisement", "orders", 0, "evaluation_criteria", 1, "price_criterion"),
            "evaluation_criteria[1].price_criterion",
        ),
    ],
)
def test_a_missing_field_is_named_with_its_place(path: tuple[str | int, ...], place: str) -> None:
    with pytest.raises(SourceChanged, match=place.replace("[", r"\[").replace("]", r"\]")):
        parse_notice(_without(small(), *path))


@pytest.mark.parametrize(
    ("field", "value", "complaint"),
    [
        ("submission_deadline", "23.11.2026 09:00", "is not a date and time"),
        ("publication_date", "13 listopada", "is not a date"),
        ("partial_offer_allowed", "nie", "is not true or false"),
        ("orders", {"0": {}}, "is not a list"),
        ("title", 73, "is not text"),
    ],
)
def test_a_field_of_the_wrong_kind_is_refused(field: str, value: object, complaint: str) -> None:
    answer = small()
    answer["data"]["advertisement"][field] = value

    with pytest.raises(SourceChanged, match=f"{field} {complaint}"):
        parse_notice(answer)


def test_an_answer_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(SourceChanged, match=r"notice\.data is missing"):
        parse_notice(["unexpected"])
    with pytest.raises(SourceChanged, match=r"search\.data is missing"):
        parse_search(None)

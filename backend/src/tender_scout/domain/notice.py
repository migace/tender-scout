"""A request for quotation, as this project keeps it.

The shape follows what a bidder reads, not what the Base stores: a notice has
orders, an order has items and scoring criteria, an item has conditions of
taking part. There is no field for a contact person, on purpose (ADR 0001).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class Buyer:
    """The organisation that asks for offers."""

    name: str
    # What kind of number identifies it, for example "nip", and the number.
    identifier_kind: str | None
    identifier: str | None


@dataclass(frozen=True, slots=True)
class Cpv:
    code: str
    name: str


@dataclass(frozen=True, slots=True)
class Place:
    country: str | None
    voivodeship: str | None
    poviat: str | None
    commune: str | None
    locality: str | None


@dataclass(frozen=True, slots=True)
class Condition:
    """Something a bidder must show to be allowed to take part."""

    # The Base's own heading for it, for example "Wiedza i doświadczenie".
    kind: str | None
    text: str


@dataclass(frozen=True, slots=True)
class Criterion:
    """One thing offers are scored on. The weight, if any, is inside the text."""

    text: str
    is_price: bool


@dataclass(frozen=True, slots=True)
class Item:
    description: str
    category: str | None
    subcategory: str | None
    cpv: tuple[Cpv, ...]
    places: tuple[Place, ...]
    conditions: tuple[Condition, ...]


@dataclass(frozen=True, slots=True)
class Order:
    title: str
    estimated_value: Decimal | None
    items: tuple[Item, ...]
    criteria: tuple[Criterion, ...]


@dataclass(frozen=True, slots=True)
class Notice:
    id: int
    # The number the Base prints on the notice, for example "2026-1281-297968".
    number: str
    # The Base keeps every edit of a notice as a version. This is the one read.
    version: int
    status: str
    title: str
    buyer: Buyer
    published_on: date
    # Instants, not wall-clock times: the adapter that reads the source decides the zone.
    deadline: datetime
    changed_at: datetime
    partial_offers: bool
    orders: tuple[Order, ...]
    # Names only. The files themselves are not fetched (ADR 0001).
    attachments: tuple[str, ...]

    @property
    def cpv_codes(self) -> frozenset[str]:
        return frozenset(
            cpv.code for order in self.orders for item in order.items for cpv in item.cpv
        )


@dataclass(frozen=True, slots=True)
class NoticeSummary:
    """What a search result says about a notice, without opening it."""

    id: int
    title: str
    deadline: datetime


@dataclass(frozen=True, slots=True)
class Kept:
    """A notice in our store, with the moment it was read from the source."""

    notice: Notice
    read_at: datetime


@dataclass(frozen=True, slots=True)
class Known:
    """Enough about a kept notice to decide whether to read it again."""

    title: str
    deadline: datetime
    read_at: datetime


def needs_reading(
    known: Known | None, summary: NoticeSummary, now: datetime, refresh_after: timedelta
) -> bool:
    """Whether opening the notice at the source is worth a request.

    A search result carries no modification date, so an edit is noticed in one
    of two ways: the title or the deadline in the result differs from what is
    kept, or the kept reading is old enough that an unnoticed edit is likely.
    """
    if known is None:
        return True
    if (summary.title, summary.deadline) != (known.title, known.deadline):
        return True
    return now - known.read_at >= refresh_after

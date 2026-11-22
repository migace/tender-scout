"""A notice as a JSON document, and back.

The document has a ``shape`` number. A change to what a notice is gets a new
number and a branch in ``from_body``, so documents written earlier stay
readable without rewriting the table.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from tender_scout.domain.notice import (
    Buyer,
    Condition,
    Cpv,
    Criterion,
    Item,
    Notice,
    Order,
    Place,
)

SHAPE = 1


def to_body(notice: Notice) -> dict[str, Any]:
    return {
        "shape": SHAPE,
        "id": notice.id,
        "number": notice.number,
        "version": notice.version,
        "status": notice.status,
        "title": notice.title,
        "buyer": {
            "name": notice.buyer.name,
            "identifier_kind": notice.buyer.identifier_kind,
            "identifier": notice.buyer.identifier,
        },
        "published_on": notice.published_on.isoformat(),
        "deadline": notice.deadline.isoformat(),
        "changed_at": notice.changed_at.isoformat(),
        "partial_offers": notice.partial_offers,
        "orders": [
            {
                "title": order.title,
                # As text: JSON numbers are floats, and this is money.
                "estimated_value": (
                    None if order.estimated_value is None else str(order.estimated_value)
                ),
                "items": [
                    {
                        "description": item.description,
                        "category": item.category,
                        "subcategory": item.subcategory,
                        "cpv": [{"code": cpv.code, "name": cpv.name} for cpv in item.cpv],
                        "places": [
                            {
                                "country": place.country,
                                "voivodeship": place.voivodeship,
                                "poviat": place.poviat,
                                "commune": place.commune,
                                "locality": place.locality,
                            }
                            for place in item.places
                        ],
                        "conditions": [
                            {"kind": condition.kind, "text": condition.text}
                            for condition in item.conditions
                        ],
                    }
                    for item in order.items
                ],
                "criteria": [
                    {"text": criterion.text, "is_price": criterion.is_price}
                    for criterion in order.criteria
                ],
            }
            for order in notice.orders
        ],
        "attachments": list(notice.attachments),
    }


def from_body(body: dict[str, Any]) -> Notice:
    if body["shape"] != SHAPE:
        raise ValueError(f"a notice document of shape {body['shape']!r} is not known")
    return Notice(
        id=body["id"],
        number=body["number"],
        version=body["version"],
        status=body["status"],
        title=body["title"],
        buyer=Buyer(**body["buyer"]),
        published_on=date.fromisoformat(body["published_on"]),
        deadline=datetime.fromisoformat(body["deadline"]),
        changed_at=datetime.fromisoformat(body["changed_at"]),
        partial_offers=body["partial_offers"],
        orders=tuple(
            Order(
                title=order["title"],
                estimated_value=(
                    None if order["estimated_value"] is None else Decimal(order["estimated_value"])
                ),
                items=tuple(
                    Item(
                        description=item["description"],
                        category=item["category"],
                        subcategory=item["subcategory"],
                        cpv=tuple(Cpv(**cpv) for cpv in item["cpv"]),
                        places=tuple(Place(**place) for place in item["places"]),
                        conditions=tuple(
                            Condition(**condition) for condition in item["conditions"]
                        ),
                    )
                    for item in order["items"]
                ),
                criteria=tuple(Criterion(**criterion) for criterion in order["criteria"]),
            )
            for order in body["orders"]
        ),
        attachments=tuple(body["attachments"]),
    )

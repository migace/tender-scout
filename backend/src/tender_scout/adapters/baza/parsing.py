"""From the Base's JSON to a notice, taking only the fields this project keeps.

Nothing is copied wholesale. A field reaches the notice because a line here
names it, which is what keeps contact people and account identifiers out: no
line names them. Free text goes through ``without_contact_details`` on the way.

The Base is undocumented, so every access remembers where it is in the answer
and a missing or mistyped field raises ``SourceChanged`` with that place.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from tender_scout.application.ports import SourceChanged
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
from tender_scout.domain.privacy import without_contact_details

# The Base prints times as a Polish clock shows them, with no zone.
SOURCE_ZONE = ZoneInfo("Europe/Warsaw")


@dataclass(frozen=True, slots=True)
class Node:
    """A piece of the answer that knows its own address."""

    value: object
    path: str

    def __getitem__(self, key: str) -> Node:
        if not isinstance(self.value, dict) or key not in self.value:
            raise SourceChanged(f"{self.path}.{key} is missing")
        return Node(self.value[key], f"{self.path}.{key}")

    def optional(self, key: str) -> Node | None:
        """The field, or nothing when it is absent or null."""
        if not isinstance(self.value, dict):
            raise SourceChanged(f"{self.path} is not an object")
        if self.value.get(key) is None:
            return None
        return Node(self.value[key], f"{self.path}.{key}")

    def each(self) -> list[Node]:
        if not isinstance(self.value, list):
            raise SourceChanged(f"{self.path} is not a list")
        return [Node(value, f"{self.path}[{index}]") for index, value in enumerate(self.value)]

    def text(self) -> str:
        if not isinstance(self.value, str):
            raise SourceChanged(f"{self.path} is not text")
        return self.value

    def free_text(self) -> str:
        """Text a person typed, with addresses and phone numbers taken out."""
        return without_contact_details(self.text())

    def integer(self) -> int:
        # ``True`` is an ``int`` in Python and must not pass for an identifier.
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise SourceChanged(f"{self.path} is not a whole number")
        return self.value

    def boolean(self) -> bool:
        if not isinstance(self.value, bool):
            raise SourceChanged(f"{self.path} is not true or false")
        return self.value

    def day(self) -> date:
        try:
            return date.fromisoformat(self.text())
        except ValueError:
            raise SourceChanged(f"{self.path} is not a date") from None

    def instant(self) -> datetime:
        try:
            local = datetime.strptime(self.text(), "%Y-%m-%d %H:%M:%S")  # noqa: DTZ007
        except ValueError:
            raise SourceChanged(f"{self.path} is not a date and time") from None
        return local.replace(tzinfo=SOURCE_ZONE).astimezone(UTC)

    def amount(self) -> Decimal:
        """Money as the Base writes it: ``60000000,00``."""
        try:
            return Decimal(self.text().replace(" ", "").replace(",", "."))
        except InvalidOperation:
            raise SourceChanged(f"{self.path} is not an amount") from None


def _optional_text(node: Node, key: str) -> str | None:
    found = node.optional(key)
    return None if found is None else found.text()


def _name_of(node: Node, key: str) -> str | None:
    """The ``name`` of a small dictionary entry such as a category, if there is one."""
    found = node.optional(key)
    return None if found is None else found["name"].text()


def parse_search(payload: object) -> tuple[tuple[NoticeSummary, ...], int]:
    """One page of search results, and how many results the search has in all."""
    data = Node(payload, "search")["data"]
    summaries = tuple(
        NoticeSummary(
            id=entry["id"].integer(),
            title=entry["title"].free_text(),
            deadline=entry["submission_deadline"].instant(),
        )
        for entry in data["advertisements"].each()
    )
    return summaries, data["meta"]["total"].integer()


def parse_notice(payload: object) -> Notice:
    # The outer "advertisement" is one version of the notice. The inner one is
    # the notice itself, which keeps its id and number across versions.
    version = Node(payload, "notice")["data"]["advertisement"]
    notice = version["advertisement"]
    buyer = version["advertiser_address_details"]
    return Notice(
        id=notice["id"].integer(),
        number=notice["number"].text(),
        version=version["id"].integer(),
        status=version["status"]["label"].text(),
        title=version["title"].free_text(),
        buyer=Buyer(
            name=buyer["name"].text(),
            identifier_kind=_optional_text(buyer, "identification_number_type"),
            identifier=_optional_text(buyer, "identification_number"),
        ),
        published_on=version["publication_date"].day(),
        deadline=version["submission_deadline"].instant(),
        changed_at=version["modified_at"].instant(),
        partial_offers=version["partial_offer_allowed"].boolean(),
        orders=tuple(_order(order) for order in version["orders"].each()),
        attachments=tuple(file["name"].free_text() for file in version["attachments"].each()),
    )


def _order(order: Node) -> Order:
    value = order.optional("estimated_value")
    return Order(
        title=order["title"].free_text(),
        estimated_value=None if value is None else value.amount(),
        items=tuple(_item(item) for item in order["order_items"].each()),
        criteria=tuple(
            Criterion(
                text=criterion["description"].free_text(),
                is_price=criterion["price_criterion"].boolean(),
            )
            for criterion in order["evaluation_criteria"].each()
        ),
    )


def _item(item: Node) -> Item:
    return Item(
        description=item["description"].free_text(),
        category=_name_of(item, "category"),
        subcategory=_name_of(item, "subcategory"),
        cpv=tuple(
            Cpv(code=cpv["code"].text(), name=cpv["name"].text())
            for cpv in item["cpv_items"].each()
        ),
        places=tuple(
            Place(
                country=_optional_text(place, "country"),
                voivodeship=_optional_text(place, "voivodeship"),
                poviat=_optional_text(place, "poviat"),
                commune=_optional_text(place, "commune"),
                locality=_optional_text(place, "locality"),
            )
            for place in item["fulfillment_places"].each()
        ),
        conditions=tuple(
            Condition(
                kind=_name_of(condition, "type"),
                text=condition["description"].free_text(),
            )
            for condition in item["participation_conditions"].each()
        ),
    )

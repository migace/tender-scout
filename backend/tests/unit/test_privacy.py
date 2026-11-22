from __future__ import annotations

import pytest

from tender_scout.domain.privacy import without_contact_details


@pytest.mark.parametrize(
    ("text", "kept"),
    [
        (
            "Oferty należy przesłać na adres jan.kowalski@fundacja.example.pl do piątku.",
            "Oferty należy przesłać na adres [e-mail] do piątku.",
        ),
        ("Pytania: biuro+zamowienia@firma-szkoleniowa.pl", "Pytania: [e-mail]"),
        ("Kontakt tel. 512 345 678 w godz. 8-16", "Kontakt tel. [telefon] w godz. 8-16"),
        ("Telefon: +48 32 123-45-67.", "Telefon: [telefon]."),
        ("tel.: (32) 123 45 67, kom. 600100200", "tel.: [telefon], kom. [telefon]"),
    ],
)
def test_addresses_and_phone_numbers_are_taken_out(text: str, kept: str) -> None:
    assert without_contact_details(text) == kept


@pytest.mark.parametrize(
    "text",
    [
        # Long numbers that are not phone numbers, and that a bidder needs.
        "NIP 5472203701, REGON 123456789",
        "Wartość zamówienia: 120 000 000,00 zł",
        "Kod CPV 80500000-9, umowa nr 73/ARZ/FESL.05.04",
        "Co najmniej 100 godzin szkoleń w okresie 2023-2026.",
        # A word that only ends like a label.
        "Hotel 3 500 600 metrów od dworca",
    ],
)
def test_other_numbers_stay(text: str) -> None:
    assert without_contact_details(text) == text

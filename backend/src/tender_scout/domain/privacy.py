"""Keeping people's contact details out of what is stored.

The contact people of a notice have fields of their own, and those are never
read. Buyers also type addresses and phone numbers into free text, and this
takes those out. It does not find names: a name in a sentence stays, and
ADR 0001 says so.
"""

from __future__ import annotations

import re

E_MAIL = "[e-mail]"
PHONE = "[telefon]"

_E_MAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# Only a number that the text itself calls a phone number. Notices are full of
# other long numbers (tax numbers, amounts, CPV codes) that must stay.
_PHONE = re.compile(
    r"(?P<label>\b(?:tel|telefon\w*|kom|fax|faks)\b\.?\s*:?\s*)"
    r"(?P<number>\+?\(?\d[\d \-()]{6,17}\d)",
    re.IGNORECASE,
)


def without_contact_details(text: str) -> str:
    text = _E_MAIL.sub(E_MAIL, text)
    return _PHONE.sub(lambda found: f"{found['label']}{PHONE}", text)

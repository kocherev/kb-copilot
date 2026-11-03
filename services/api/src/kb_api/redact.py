"""Strip contact details and card numbers before text is stored or sent on."""

import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
CARD = re.compile(r"(?<![\w-])(?:\d[ -]?){12,18}\d(?![\w-])")
# A date such as 2026-11-02 is not a phone number.
PHONE = re.compile(r"(?<![\w-])(?!\d{4}-\d{2}-\d{2}\b)\+?\d[\d ().-]{5,}\d(?![\w-])")


def redact(text: str) -> str:
    text = EMAIL.sub("[email]", text)
    text = CARD.sub("[card]", text)
    return PHONE.sub("[phone]", text)

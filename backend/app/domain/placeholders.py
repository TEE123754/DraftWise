"""Unfilled form fields are missing values, never values that can differ.

Shared by the rules extractor and the AI path so neither can report "TBA" as a real port.
"""

import re

from app.domain.models import ExtractedField, Extraction

# "", "N/A", "TBA", "to be advised", or a blank line such as "____MT".
_PLACEHOLDER = re.compile(
    r"^(?:|n/?a|null|none|unknown|-+|tba|tbd|tbc|pending"
    r"|to be (?:advised|confirmed|determined|nominated|declared))\W*$|_{2,}",
    re.I,
)


def is_placeholder(value: str | None) -> bool:
    return value is None or bool(_PLACEHOLDER.search(value.strip()))


def clear_placeholders(extraction: Extraction) -> Extraction:
    """Return the extraction with placeholder values turned back into missing fields."""
    fields = {
        name: ExtractedField() if field.state == "present" and is_placeholder(field.raw_value) else field
        for name, field in extraction.fields.items()
    }
    return extraction.model_copy(update={"fields": fields})

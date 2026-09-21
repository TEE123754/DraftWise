"""Bounded shipping-domain senses with source spans, not general language claims."""

import re

from app.services.classification import segment_email


def email_senses(subject, body):
    current = segment_email(subject, body)[1]["text"]
    shipping = bool(
        re.search(r"\b(shipping|draft|bill of lading|containers?|shipment)\b", current, re.I)
    )
    rows = []
    for match in re.finditer(r"\b(SI|B/?L|POD|POL)\b", current, re.I):
        term = match[0].upper().replace("/", "")
        senses = {
            "SI": "shipping instructions",
            "BL": "bill of lading",
            "POL": "port of loading",
            "POD": "port of discharge",
        }
        # POD can also mean proof of delivery; a bare acronym needs a nearby port cue.
        context = current[max(0, match.start() - 60) : match.end() + 60]
        resolved = shipping and (
            term not in {"POD", "POL"}
            or bool(re.search(r"\b(port|loading|discharge)\b", context, re.I))
        )
        rows.append(
            {
                "term": match[0],
                "sense": senses[term] if resolved else None,
                "state": "resolved" if resolved else "needs_review",
                "quote": context,
                "start": match.start(),
                "end": match.end(),
                "segment": "current",
                "reason": "Shipping context and nearby labels"
                if resolved
                else "Insufficient context for this acronym",
            }
        )
    return rows


def field_senses(extraction):
    return [
        {
            "field": str(name),
            "state": field.state,
            "reason": "Anchored field label and units; missing or conflicting evidence is retained",
            "evidence": [e.model_dump() for e in field.evidence],
        }
        for name, field in extraction.fields.items()
    ]

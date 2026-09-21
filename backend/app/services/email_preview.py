"""What the inbox preview shows about one email: how it was classified and the SI | BL | Email table.

Pure and local, like `email_state`: it takes rows already read from the database, does no I/O and
never calls AI. The Email column only reports whether a value the email states agrees with the
documents. It never changes the review state, which comes from the stored verification report.
"""

from app.domain.models import FIELDS, FieldName
from app.services.normalization import normalize

FIELD_LABELS = {
    FieldName.SHIPPER: "Shipper",
    FieldName.CONSIGNEE: "Consignee",
    FieldName.NOTIFY: "Notify party",
    FieldName.POL: "Port of loading",
    FieldName.POD: "Port of discharge",
    FieldName.CONTAINERS: "Container count",
    FieldName.WEIGHT: "Gross weight (kg)",
}

METHOD_LABELS = {
    "rules": "Rules",
    "ai": "AI",
    "rule_fallback": "Rules (AI was unavailable)",
    "human": "Reviewer",
}

REASON_LABELS = {
    "comparison_action": "Asks for the draft BL to be checked or compared",
    "new_si_action": "Asks for shipping instructions to be created or supplied",
    "billing_action": "Raises a billing or charges question",
    "informational": "Informational: no action is requested",
    "irrelevant": "Not related to shipping documents",
    "conflicting_intent": "The email asks for more than one thing, so a person should decide",
}

QUOTE_LIMIT = 240


def _clip(text: str | None) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= QUOTE_LIMIT else text[: QUOTE_LIMIT - 1] + "…"


def _span_ids(stored) -> tuple[list[str], str | None]:
    """The evidence column holds a list of span IDs (worker) or the whole classification (demo seed)."""
    if isinstance(stored, dict):
        return list(stored.get("evidence_span_ids") or []), stored.get("reason_code")
    return [item for item in (stored or []) if isinstance(item, str)], None


def classification_summary(classification: dict | None, segments: list[dict]) -> dict | None:
    """Category, who or what decided it, why, and the email text it rests on."""
    if not classification:
        return None
    meta = classification.get("run_metadata") or {}
    span_ids, stored_reason = _span_ids(classification.get("evidence"))
    if classification.get("decided_by") == "human":
        method = "human"
    else:
        method = meta.get("method") if meta.get("method") in METHOD_LABELS else "rules"

    quotes = [
        {"id": item["id"], "text": _clip(item.get("text"))}
        for item in meta.get("evidence") or []
        if isinstance(item, dict) and item.get("id") and item.get("text")
    ]
    if not quotes:
        by_id = {segment["id"]: segment for segment in segments}
        quotes = [
            {"id": span, "text": _clip(by_id[span].get("text"))}
            for span in span_ids
            if span in by_id and by_id[span].get("text")
        ]
    reason_code = meta.get("reason_code") or stored_reason
    return {
        "category": None if classification.get("ambiguous") else classification.get("category"),
        "ambiguous": bool(classification.get("ambiguous")),
        "method": method,
        "method_label": METHOD_LABELS[method],
        "fallback_reason": meta.get("fallback_reason"),
        "reason_code": reason_code,
        "reason": REASON_LABELS.get(reason_code) or (reason_code or "").replace("_", " ") or None,
        "human_reason": meta.get("reason") if method == "human" else None,
        "evidence": quotes,
    }


def _side(output: dict | None, field: FieldName) -> dict:
    """One document's value for one field: its state, the value and the quote it came from."""
    if output is None:
        return {"state": "no_document", "value": None, "quote": None}
    cell = (output.get("fields") or {}).get(field.value) or {}
    state = cell.get("state") or "missing"
    evidence = cell.get("evidence") or []
    shown = cell.get("raw_value") if state == "present" else None
    if state == "ambiguous":
        shown = "; ".join(cell.get("alternatives") or []) or None
    return {
        "state": state,
        "value": shown,
        "quote": _clip(evidence[0].get("quote")) if evidence else None,
    }


def _email_mark(field: FieldName, cell: dict, document_values: list) -> str:
    """`match` when the email's value equals every document value, `differs` when it differs from
    any, `unchecked` when there is nothing reliable to check it against."""
    known = [str(value) for value in document_values if value is not None]
    if not known or cell["state"] != "present" or not cell["value"]:
        return "unchecked"
    stated = normalize(field, cell["value"], cell["quote"] or "").value
    if stated is None:
        return "unchecked"
    return "match" if all(str(stated) == value for value in known) else "differs"


def field_table(
    report: dict | None,
    si_output: dict | None,
    bl_output: dict | None,
    email_fields: dict | None,
) -> dict:
    """The seven fields side by side: SI, BL and what the email itself says.

    `report` is the latest verification report row (its `status` and `report.comparisons`); the
    per-field decision and explanation come from it, never from a fresh comparison here.
    """
    decisions = {
        item.get("field"): item for item in ((report or {}).get("report") or {}).get("comparisons", [])
    }
    email_output = {"fields": email_fields} if email_fields else None
    rows = []
    for field in FIELDS:
        comparison = decisions.get(field.value) or {}
        email = _side(email_output, field)
        if email["state"] == "no_document":  # the email is always there; it may just not state the field
            email["state"] = "missing"
        email["mark"] = _email_mark(
            field,
            email,
            [(comparison.get("si") or {}).get("normalized"), (comparison.get("bl") or {}).get("normalized")],
        )
        rows.append(
            {
                "field": field.value,
                "label": FIELD_LABELS[field],
                "decision": comparison.get("decision"),
                "explanation": comparison.get("explanation") if comparison.get("decision") not in (None, "match") else None,
                "si": _side(si_output, field),
                "bl": _side(bl_output, field),
                "email": email,
            }
        )
    return {
        "status": report["status"] if report else None,
        "documents": {"si": si_output is not None, "bl": bl_output is not None},
        "rows": rows,
    }

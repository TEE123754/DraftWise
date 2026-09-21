"""CSV export of verification reports: one row per email and field, with the reason for each flag."""

import csv
import io

COLUMNS = (
    "email_id",
    "subject",
    "report_status",
    "field",
    "decision",
    "si_value",
    "bl_value",
    "confidence",
    "severity",
    "handled_by",
    "next_step",
    "explanation",
    "si_evidence",
    "bl_evidence",
    "rule",
)

_NEXT_STEP = {
    "mismatch": "Confirm the difference, then ask the carrier to amend the BL",
    "partial_match": "Names are similar: confirm they are the same party or approve an equivalence",
    "missing": "Find the value in the source documents and enter it",
    "uncertain": "Check the source evidence and confirm or correct the value",
}


def _safe(value) -> str:
    """Emails are untrusted text; a leading formula character would run when the file opens in Excel."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _quote(output: dict | None, field: str) -> str:
    evidence = ((output or {}).get("fields", {}).get(field) or {}).get("evidence") or []
    return " | ".join(item["quote"] for item in evidence[:2] if item.get("quote"))


def _handling(row: dict) -> tuple[str, str]:
    if row["decision"] == "match":
        if row["rule"] == "consignee_order_clause_v1":
            # Informational: the names agree. It is not counted as a defect or a review item.
            return "Automated", "Optional: confirm the BL type (negotiable or straight) with the carrier"
        return "Automated", "None"
    return "Human review", _NEXT_STEP.get(row["decision"], "Review the field")


def report_rows(email: dict, report: dict, outputs: dict, *, include_matches: bool) -> list[list[str]]:
    """The rows for one email's latest report. `outputs` maps extraction id to the stored extraction."""
    rows = []
    for comparison in report["comparisons"]:
        if comparison["decision"] == "match" and not include_matches:
            continue
        handled_by, next_step = _handling(comparison)
        field = comparison["field"]
        si, bl = comparison["si"], comparison["bl"]
        rows.append(
            [
                _safe(email["external_id"]),
                _safe(email["subject"]),
                report["status"],
                field,
                comparison["decision"],
                _safe(si["raw"]),
                _safe(bl["raw"]),
                f"{comparison['confidence']:.2f}",
                comparison["severity"],
                handled_by,
                next_step,
                _safe(comparison["explanation"]),
                _safe(_quote(outputs.get(si["extraction_id"]), field)),
                _safe(_quote(outputs.get(bl["extraction_id"]), field)),
                comparison["rule"],
            ]
        )
    return rows


def to_csv(rows: list[list[str]]) -> bytes:
    """UTF-8 with a byte-order mark so Excel reads non-Latin party names correctly."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")

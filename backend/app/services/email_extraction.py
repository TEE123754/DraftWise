"""Conservative email field extraction with exact body offsets and prose fallback.

Extraction order (highest priority first):
  1. Labelled key:value pairs in the current body segment
  2. Prose patterns in the body (unlabelled natural-language matches)
  3. Prose patterns applied to the subject line (fills remaining missing fields)
"""

import hashlib
import re

from app.domain.models import (
    Evidence,
    ExtractedField,
    Extraction,
    FieldName,
    ParsedDocument,
    SourceBlock,
)
from app.services.classification import segment_email
from app.services.extraction import extract_labelled

PROSE_PATTERNS: list[tuple[FieldName, re.Pattern]] = [
    (
        FieldName.WEIGHT,
        re.compile(r"(?<!net\s)\b(?:gross\s*weight|gw|gwt)\s*[:=-]?\s*([0-9.,\s]+(?:kg|kgs|mt|metric\s*tonnes?|tonnes?|lbs?))\b", re.I),
    ),
    (
        FieldName.CONTAINERS,
        re.compile(r"\b(?:container\s*count|no\.\s*of\s*containers?|containers?|cntrs?)\s*[:=-]\s*(\d{1,6}\s*(?:[x×]\s*(?:20|40|45)\s*(?:hc|gp|hq|dv|reefer))?|\d{1,6}\s*(?:containers?|cntrs?))\b", re.I),
    ),
    (
        FieldName.POL,
        re.compile(r"\b(?:port\s*of\s*loading|loading\s*port|load\s*port|pol)\s*[:=-]?\s*([A-Za-z0-9\s,/.-]{2,40})(?=[,\n\r;/]|\b(?:pod|to|dest|discharge)\b|$)", re.I),
    ),
    (
        FieldName.POD,
        re.compile(r"\b(?:port\s*of\s*discharge|discharge\s*port|pod|destination|dest)\s*[:=-]?\s*([A-Za-z0-9\s,/.-]{2,40})(?=[,\n\r;/]|\b(?:pol|from|loading)\b|$)", re.I),
    ),
    (
        FieldName.SHIPPER,
        re.compile(r"\b(?:shipper|exporter)\s*[:=-]\s*([A-Za-z0-9\s,.-]{3,80})(?=[,\n\r;]|\b(?:consignee|notify)\b|$)", re.I),
    ),
    (
        FieldName.CONSIGNEE,
        re.compile(r"\b(?:consignee|buyer)\s*[:=-]\s*([A-Za-z0-9\s,.-]{3,80})(?=[,\n\r;]|\b(?:notify|shipper)\b|$)", re.I),
    ),
    (
        FieldName.NOTIFY,
        re.compile(r"\b(?:notify(?:\s*party)?)\s*[:=-]\s*([A-Za-z0-9\s,.-]{3,80})(?=[,\n\r;]|\b(?:consignee|shipper)\b|$)", re.I),
    ),
]

# Patterns applied to the subject line only. A port is taken from a subject only when it is
# explicitly labelled ("POL: SGSIN / POD: CNSHA", "Port of Discharge: Rotterdam"). Bare "to",
# "from" or "destination" are ordinary words there: on the 520 supplied emails every value found
# that way was wrong ("TO CONFIRM DOCS" gave a port of discharge of CONFIRM).
_SUBJ_VALUE = r"([^;|,\n]{2,40}?)(?=\s+/\s|\s+-\s|\s*[;|,]|\s*$)"
_SUBJ_POL = re.compile(rf"\b(?:port\s+of\s+loading|loading\s+port|pol)\s*[:=]\s*{_SUBJ_VALUE}", re.I)
_SUBJ_POD = re.compile(rf"\b(?:port\s+of\s+discharge|discharge\s+port|pod)\s*[:=]\s*{_SUBJ_VALUE}", re.I)
# BL number embedded in subject, e.g. "DRAFT BL - MSKU1234567" or "BL# ABC123456789"
_SUBJ_BL_NUM = re.compile(
    r"\b(?:b/?l\s*(?:no\.?|#|number)?\s*[-:]?\s*|draft\s+b/?l\s*[-:]?\s*)([A-Z0-9]{6,20})\b",
    re.I,
)
# SI reference in subject, e.g. "SI - REF/2024/001" or "SI REQUEST - ABC"
_SUBJ_SI_REF = re.compile(
    r"\bsi\s*(?:request|ref|reference|no\.?|#)?\s*[-:]?\s*([A-Za-z0-9/\-]{3,30})\b",
    re.I,
)

SUBJECT_PATTERNS: list[tuple[FieldName, re.Pattern]] = [
    (FieldName.POL, _SUBJ_POL),
    (FieldName.POD, _SUBJ_POD),
]


def extract_email_body(email_id: str, subject: str, body: str) -> dict:
    current = segment_email(subject, body)[1]["text"]
    source_id = f"email:{email_id}:body"
    blocks = []
    offset = 0
    for line_number, line in enumerate(current.splitlines(keepends=True), 1):
        text = line.rstrip("\r\n")
        if text.strip():
            blocks.append(
                SourceBlock(
                    id=f"{source_id}:{line_number}",
                    source_id=source_id,
                    text=text,
                    locator={
                        "type": "email_body",
                        "line": line_number,
                        "start": offset,
                        "end": offset + len(text),
                    },
                )
            )
        offset += len(line)
    document = ParsedDocument(
        source_id=source_id,
        sha256=hashlib.sha256(body.encode()).hexdigest(),
        format="txt",
        parser_version="email-labelled-v1",
        blocks=tuple(blocks),
    )
    extraction = extract_labelled(document).model_copy(update={"document_type": "UNKNOWN"})

    # Step 1: Check for missing fields that can be extracted from prose in the body
    updated_fields = dict(extraction.fields)
    prose_found = False
    for field_name, pattern in PROSE_PATTERNS:
        current_field = updated_fields.get(field_name)
        if current_field and current_field.state != "missing":
            continue
        for block in blocks:
            match = pattern.search(block.text)
            if match:
                raw = match.group(1).strip().rstrip(",;/ ")
                if raw and raw.casefold() not in {"n/a", "null", "none", "unknown", "-"}:
                    updated_fields[field_name] = ExtractedField(
                        raw_value=raw,
                        state="present",
                        evidence=(Evidence(block_id=block.id, quote=match.group(0).strip()),),
                    )
                    prose_found = True
                    break

    if prose_found:
        extraction = extraction.model_copy(update={"fields": updated_fields})

    # Step 2: Apply subject-line patterns to fill any still-missing fields.
    # Body results always take priority — we only touch fields that remain "missing".
    subject_source_id = f"email:{email_id}:subject"
    subject_found = False
    if subject and subject.strip():
        for field_name, pattern in SUBJECT_PATTERNS:
            current_field = updated_fields.get(field_name)
            if current_field and current_field.state != "missing":
                continue
            match = pattern.search(subject)
            if match:
                raw = match.group(1).strip().rstrip(",;/ ")
                if raw and raw.casefold() not in {"n/a", "null", "none", "unknown", "-"}:
                    updated_fields[field_name] = ExtractedField(
                        raw_value=raw,
                        state="present",
                        evidence=(
                            Evidence(
                                block_id=f"{subject_source_id}:1",
                                quote=match.group(0).strip(),
                            ),
                        ),
                    )
                    subject_found = True

    if subject_found:
        extraction = extraction.model_copy(update={"fields": updated_fields})

    method = (
        "labelled_email_fields_v1"
        if not prose_found and not subject_found
        else "prose_email_fields_v1" if prose_found
        else "subject_email_fields_v1"
    )

    return {
        "extraction": extraction.model_dump(mode="json"),
        "source": document.model_dump(mode="json"),
        "quoted_history_excluded": len(current) < len(body),
        "requires_source_confirmation": True,
        "method": method,
    }


def reconcile_with_attachment(
    attachment_extraction: Extraction, body_extraction: Extraction
) -> tuple[Extraction, list[str]]:
    """Reconcile attachment and email body extractions.

    Attachment is authoritative; if an attachment is missing a field that
    the email body contains, promote it with a review flag.
    """
    notes = []
    reconciled_fields = dict(attachment_extraction.fields)
    for field_name in FieldName:
        att_field = attachment_extraction.fields.get(field_name)
        body_field = body_extraction.fields.get(field_name)
        if (not att_field or att_field.state != "present") and (body_field and body_field.state == "present"):
            reconciled_fields[field_name] = body_field
            notes.append(f"Field {field_name.value} promoted from email body: '{body_field.raw_value}'")
        elif att_field and att_field.state == "present" and body_field and body_field.state == "present":
            if att_field.raw_value != body_field.raw_value:
                notes.append(
                    f"Body/attachment discrepancy on {field_name.value}: "
                    f"attachment='{att_field.raw_value}' vs body='{body_field.raw_value}'"
                )
    return attachment_extraction.model_copy(update={"fields": reconciled_fields}), notes


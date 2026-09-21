import re

from app.ai.grounding import ground_extraction
from app.domain.models import (
    FIELDS,
    Evidence,
    ExtractedField,
    Extraction,
    FieldName,
    ParsedDocument,
)
from app.domain.placeholders import is_placeholder

# Labels are anchored. Net/VGM/package values cannot accidentally satisfy required totals.
LABELS = {
    FieldName.SHIPPER: r"shipper(?:/exporter|\s*\(principal or seller\)|\s+name)?|exporter|consignor",
    # A draft BL's "To the Order of" line is its consignee entry, as "(Non-Negotiable)" is on an SI.
    FieldName.CONSIGNEE: (
        r"consignee(?:\s*\(non-negotiable\))?(?:\s*/\s*buyer)?|buyer\s*\(consignee\)"
        r"|receiver|to\s+the\s+order\s+of"
    ),
    FieldName.NOTIFY: r"(?:also\s+)?notify(?:\s+party(?:/intermediate consignee)?|\s+address)?",
    FieldName.POL: (
        r"port\s+of\s+loading(?:\s*\(pol\))?|(?:load|loading)\s+port|place\s+of\s+loading|pol"
    ),
    FieldName.POD: (
        r"port\s+of\s+discharge(?:\s*\(pod\))?|discharge\s+port|destination\s+port"
        r"|port\s+of\s+destination|pod"
    ),
    FieldName.CONTAINERS: (
        r"container\s+count|no\.?\s+of\s+containers(?:\s+or\s+packages)?|number\s+of\s+containers"
        r"|total\s+containers|(?:qty|quantity)\s+of\s+containers|containers?\s+(?:qty|quantity)|containers"
    ),
    # "nn" is what a PDF prints where a bilingual label's Chinese glyphs had no font.
    FieldName.WEIGHT: (
        r"(?:total\s+)?gross\s+(?:weight|wt|mass)(?:nn)?(?:\s*\((?:kgs?|mt)\))?|g\.?w\.?"
    ),
}


# Bilingual forms add a translation after the label, e.g. "Consignee (收货人)".
_TRANSLATION_NOTE = re.compile("\\s*[(\uff08][^()\uff08\uff09]*[\u3400-\u9fff][^()\uff08\uff09]*[)\uff09]")
_CJK = re.compile("[\u3000-\u303f\u3400-\u9fff]")
_DOCX_CELL = re.compile(r"(?P<row>.+:row:\d+):cell:(?P<cell>\d+):\d+")
_INLINE = re.compile("([^:\uff1a\\n]*)[:\uff1a]([^\\n]+)")


def _label_text(text: str) -> str:
    """A label without its translation: 'Consignee (收货人)' or 'Gross Weight毛重(KGS)'.

    Only ever applied to the label, so Chinese characters in a value are preserved.
    """
    return _CJK.sub("", _TRANSLATION_NOTE.sub("", text))


def _same_row_value(block, following) -> bool:
    """A label and its value are only paired when the layout says they sit side by side."""
    if block.locator.get("type") == "xlsx":
        return (
            following.locator.get("sheet") == block.locator.get("sheet")
            and following.locator.get("row") == block.locator.get("row")
        )
    if block.locator.get("type") == "docx":
        left = _DOCX_CELL.fullmatch(str(block.locator.get("path", "")))
        right = _DOCX_CELL.fullmatch(str(following.locator.get("path", "")))
        return bool(
            left
            and right
            and left["row"] == right["row"]
            and int(right["cell"]) == int(left["cell"]) + 1
        )
    return False


def identify_role(document: ParsedDocument) -> str:
    opening = document.blocks[:12]
    # Spreadsheet sheet names ("S.I.", "BL") are part of how a workbook labels itself.
    sheets = {str(block.locator["sheet"]) for block in opening if block.locator.get("sheet")}
    header = "\n".join([*(block.text for block in opening), *sorted(sheets)]).casefold()
    # "Bill of Lading Instruction" is the instruction (SI), not the draft BL it asks for.
    instruction = r"\b(?:bill of lading|b/?l) instructions?\b"
    patterns = {
        "SI": (
            rf"\bshipping instructions?\b|\bbooking instructions?\b|\bletter of instructions?\b"
            rf"|{instruction}|(?<![a-z])s\.i\.(?![a-z])"
        ),
        "BL": r"\bbill of lading\b|\b(?:draft\s+b/?l|b/?l\s+draft)\b",
        "INVOICE": r"\bcommercial invoice\b",
        "PACKING_LIST": r"\bpacking list\b",
        "CERTIFICATE": r"\bcertificate of origin\b",
    }
    without_instruction = re.sub(instruction, " ", header)
    roles = [
        role
        for role, pattern in patterns.items()
        if re.search(pattern, without_instruction if role == "BL" else header)
    ]
    return roles[0] if len(roles) == 1 else "UNKNOWN"


def extract_labelled(document: ParsedDocument) -> Extraction:
    candidates = {field: [] for field in FIELDS}
    for index, block in enumerate(document.blocks):
        inline = _INLINE.fullmatch(block.text)  # "Label: value" on one line
        label_only = _label_text(block.text)
        for field, label in LABELS.items():
            if (
                inline
                and inline[2].strip()
                and re.fullmatch(rf"\s*(?:{label})\s*", _label_text(inline[1]), re.I)
            ):
                raw, evidence = inline[2].strip(), [Evidence(block_id=block.id, quote=block.text)]
            elif re.fullmatch(rf"\s*(?:{label})\s*[:：]?\s*", label_only, re.I) and index + 1 < len(
                document.blocks
            ):
                following = document.blocks[index + 1]
                # Only a label/value pair side by side in a table row or spreadsheet row is safe.
                if not _same_row_value(block, following):
                    continue
                raw = following.text
                evidence = [
                    Evidence(block_id=block.id, quote=block.text),
                    Evidence(block_id=following.id, quote=following.text),
                ]
            elif (
                block.locator.get("type") == "pdf_page"
                and (spaced := re.fullmatch(rf"\s*(?:{label})\s+(\S.*?)\s*", block.text, re.I))
            ):
                # PDF text layers often print "Label value" with no colon; other formats keep
                # the stricter colon or side-by-side-cell forms.
                raw, evidence = spaced[1], [Evidence(block_id=block.id, quote=block.text)]
            else:
                continue
            if is_placeholder(raw):
                continue
            if (
                field == FieldName.CONTAINERS
                and "packages" in block.text.casefold()
                and not re.search(r"\d+\s*[x×]\s*(?:20|40|45)", raw, re.I)
            ):
                continue
            candidates[field].append((raw, evidence))
    fields = {}
    for field, values in candidates.items():
        unique = {value for value, _ in values}
        if not values:
            fields[field] = ExtractedField()
        elif len(unique) > 1:
            fields[field] = ExtractedField(
                state="ambiguous",
                alternatives=tuple(sorted(unique)[:5]),
                evidence=tuple(e for _, evidence in values for e in evidence)[:20],
            )
        else:
            raw, evidence = values[0]
            fields[field] = ExtractedField(state="present", raw_value=raw, evidence=tuple(evidence))
    result = Extraction(
        document_id=document.source_id,
        document_type=identify_role(document),
        fields=fields,
        warnings=document.warnings,
    )
    ground_extraction(result, document)
    return result

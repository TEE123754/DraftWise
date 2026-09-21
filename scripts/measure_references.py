"""Measure the reference matcher on the supplied emails and attachments. Offline: no database, no AI.

    python scripts/measure_references.py            # prints a summary and writes artifacts/quality/references-measure.json

Reads only inbox/*.json and the attachments (never any answer key). It reports how often an email cites an
identifier that its own documents also carry ("matches its documents"), how often it cites one that they do
not ("flagged"), and how many identifiers would link an attachment-less email to a *different* email's
documents ("suggestions"), by the labelled patterns the app uses and by a wider "generic code" pattern.
"""

import collections
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.config import Settings  # noqa: E402
from app.parsers.registry import parse_document  # noqa: E402
from app.services.classification import classify_explicit, segment_email  # noqa: E402
from app.services.dataset_import import open_source  # noqa: E402
from app.services.references import references  # noqa: E402

# Two capital letters or more, then six digits or more, e.g. SIN525534192. Voyage codes and dates do not fit.
GENERIC = re.compile(r"\b([A-Z]{2,5}\d{6,12})\b")


def generic(text):
    return [{"kind": "generic", "code": code, "quote": code} for code in GENERIC.findall(text)]


def main():
    settings = Settings()
    settings.resolve_dataset_path()
    source = open_source(settings.demo_dataset_path)
    emails = source.emails()
    doc_text: dict[str, str] = {}
    unreadable = 0
    for email in emails:
        parts = []
        for path in email.attachments:
            try:
                document = parse_document(source.read(path), source_id=path, settings=settings)
                parts.append("\n".join(block.text for block in document.blocks))
            except Exception:  # noqa: BLE001 - counted, not hidden
                unreadable += 1
        doc_text[email.email_id] = "\n".join(parts)

    def cited(email):
        current = "\n".join(s["text"] for s in segment_email(email.subject, email.body) if s["id"] in {"subject", "current"})
        return current

    out = {"emails": len(emails), "attachments": sum(len(e.attachments) for e in emails), "unreadable_attachments": unreadable}
    for name, extract in (("labelled", references), ("generic", generic)):
        own = {e.email_id: {(r["kind"], r["code"]) for r in extract(doc_text[e.email_id])} for e in emails}
        owners = collections.defaultdict(set)
        for email_id, keys in own.items():
            for key in keys:
                owners[key].add(email_id)
        with_files = [e for e in emails if e.attachments and doc_text[e.email_id]]
        without = [e for e in emails if not e.attachments]
        stats = collections.Counter()
        for e in with_files:
            keys = {(r["kind"], r["code"]) for r in extract(cited(e))}
            if not keys:
                stats["cites_nothing"] += 1
            elif keys & own[e.email_id]:
                stats["matches_own_documents"] += 1
            else:
                stats["cites_but_not_in_own_documents"] += 1
            if any(len(owners.get(k, ())) > 1 for k in own[e.email_id]):
                stats["own_identifier_also_in_another_email"] += 1
            if keys - own[e.email_id] and any(owners.get(k, set()) - {e.email_id} for k in keys - own[e.email_id]):
                stats["cites_another_emails_identifier"] += 1
        bl_without = [e for e in without if (classify_explicit(e.subject, e.body) or None) and classify_explicit(e.subject, e.body).category == "BL_COMPARISON"]
        suggestions = 0
        for e in bl_without:
            keys = {(r["kind"], r["code"]) for r in extract(cited(e))}
            if any(owners.get(k, set()) - {e.email_id} for k in keys):
                suggestions += 1
        out[name] = {
            "emails_with_readable_documents": len(with_files),
            **dict(stats),
            "comparison_emails_without_attachments": len(bl_without),
            "link_suggestions_for_those": suggestions,
        }
    target = ROOT / "artifacts" / "quality" / "references-measure.json"
    target.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

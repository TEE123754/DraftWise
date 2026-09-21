"""A deliberately tiny live-AI check: 10 hand-written emails and 4 unseen documents (at most 14 calls).

    python scripts/spot_check_ai.py

Calls run one at a time with a pause, and the run stops after two rate-limit errors in a row so it
cannot burn quota. The emails were written by hand, not generated from the held-out templates.
"""

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_heldout as E  # noqa: E402
from app.domain.errors import DomainError  # noqa: E402
from app.domain.placeholders import clear_placeholders  # noqa: E402
from app.services.classification import classify_explicit  # noqa: E402

FRESH = [
    ("BL_COMPARISON", "Pls double-check", "Guys, attaching what we sent the carrier and what they sent back. Could someone eyeball the two for differences before we sign off?", ["attachments/a_SI.txt", "attachments/a_BL.txt"]),
    ("BL_COMPARISON", "Consignee dispute", "Our customer says the consignee on the carrier's draft looks wrong. Could you reconcile it against the instructions we gave you?", ["attachments/b_SI.txt", "attachments/b_BL.pdf"]),
    ("SI_REQUEST", "New booking Ningbo", "Hi, we have a new booking, 2x40 from Ningbo. Can you set up the shipping instruction so we can fill it in?", []),
    ("SI_REQUEST", "Voyage 214E", "Kindly issue the SI template for voyage 214E, thank you.", []),
    ("INVOICE_QUERY", "Debit note", "The amount on your debit note doesn't tally with the quotation. Please review the charges.", []),
    ("INVOICE_QUERY", "Draft BL fee", "Why was I charged USD 75 for the draft bill of lading amendment? I need a refund.", []),
    ("GENERAL", "Gate closure", "FYI the terminal gate will be closed for maintenance on Saturday morning.", []),
    ("GENERAL", "Greetings", "Happy Diwali to you and your family from all of us.", []),
    ("SPAM", "Cheap LED lights", "Dear Sir/Madam, we are a factory offering very cheap LED lights. Download our catalogue at http://bit.ly/led-offer today.", []),
    ("SPAM", "Account closing", "Your account will be closed within 24 hours. Confirm your password here immediately to keep access.", []),
]


async def main():
    settings = E.Settings()
    provider = E.create_provider(settings)
    if provider is None:
        raise SystemExit("No AI provider configured")
    truth = json.loads((E.DATA / "truth.json").read_text(encoding="utf-8"))
    emails = {json.loads(p.read_text(encoding="utf-8"))["email_id"]: json.loads(p.read_text(encoding="utf-8"))
              for p in (E.DATA / "inbox").glob("*.json")}
    src = E.open_source(str(E.DATA))
    cache = E.load_cache()
    limited, calls = 0, 0

    async def call(make):
        nonlocal limited, calls
        if limited >= 2:
            return None
        calls += 1
        try:
            out = await asyncio.wait_for(make(), 90)
            limited = 0
            await asyncio.sleep(5)
            return out
        except DomainError as exc:
            limited = limited + 1 if exc.code == "PROVIDER_RATE_LIMITED" else 0
            return {"error": exc.code}
        except Exception as exc:  # noqa: BLE001
            return {"error": type(exc).__name__}

    print("== fresh hand-written emails: rules vs live AI")
    right_ai = right_rules = answered = 0
    for gold, subject, body, attachments in FRESH:
        rules = classify_explicit(subject, body)
        out = await call(lambda: provider.classify(subject, body, attachments))
        ai = out[0] if out and not isinstance(out, dict) else None
        note = out["error"] if isinstance(out, dict) else ("skipped" if out is None else "")
        answered += ai is not None
        right_ai += bool(ai and ai.category == gold and not ai.ambiguous)
        right_rules += bool(rules and rules.category == gold)
        print(f"  {gold:14s} rules={rules.category if rules else 'abstain':14s} ai={(ai.category if ai else note):14s} | {subject}")
    print(f"  rules correct {right_rules}/10 | AI correct {right_ai}/{answered} answered")

    print("== four documents the AI has not seen")
    todo = [(eid, p) for eid, t in E.eligible_docs(truth) if t.get("review_reason") != "missing_value"
            for p in emails[eid]["attachments"] if "extraction" not in cache["extract"].get(p, {})]
    picked, seen = [], set()
    for eid, p in todo:
        ext = p.rsplit(".", 1)[-1]
        if ext not in seen or (ext == "pdf" and sum(q.endswith(".pdf") for _, q in picked) < 2):
            seen.add(ext)
            picked.append((eid, p))
        if len(picked) == 4:
            break
    ok = total = 0
    for eid, path in picked:
        document = E.parse(src, path, settings)
        out = await call(lambda: provider.extract(document))
        if out is None or isinstance(out, dict):
            print(f"  {path}: {'skipped' if out is None else out['error']}")
            continue
        extraction = clear_placeholders(out[0])
        role = "si" if "_SI" in path else "bl"
        wrong = [f for f in E.FIELDS if not E.field_correct(f, extraction.fields.get(f), truth[eid][role][f])]
        ok += 7 - len(wrong)
        total += 7
        print(f"  {path}: {7 - len(wrong)}/7 fields correct {('wrong: ' + str(wrong)) if wrong else ''}")
    print(f"  AI extraction {ok}/{total} fields on unseen documents")
    print(f"total provider calls made this run: {calls}")
    await provider.close()


asyncio.run(main())

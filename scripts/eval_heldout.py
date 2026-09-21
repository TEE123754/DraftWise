"""Evaluate rules and live AI on the held-out set built by scripts/build_heldout.py.

    python scripts/eval_heldout.py            # rules only, offline, no provider calls
    python scripts/eval_heldout.py --ai       # also calls the configured AI provider (uses quota)

AI answers are cached in artifacts/heldout/ai_cache.json, so re-scoring never repeats a call.
The set was written independently of the supplied dataset; truth.json holds its answers.
"""

import argparse
import asyncio
import collections
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.ai.provider import create_provider  # noqa: E402
from app.config import Settings  # noqa: E402
from app.domain.errors import DomainError  # noqa: E402
from app.domain.models import Extraction  # noqa: E402
from app.domain.placeholders import clear_placeholders  # noqa: E402
from app.parsers.registry import parse_document  # noqa: E402
from app.services import pipeline  # noqa: E402
from app.services.classification import Classification, classify_explicit  # noqa: E402
from app.services.dataset_import import open_source  # noqa: E402
from app.services.extraction import extract_labelled  # noqa: E402
from app.services.normalization import containers, party, weight  # noqa: E402

DATA = ROOT / "artifacts" / "heldout"
CACHE = DATA / "ai_cache.json"
FIELDS = ["shipper", "consignee", "notify_party", "port_of_loading", "port_of_discharge",
          "container_count", "gross_weight_kg"]
CATEGORIES = ["BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"]


def load_cache():
    return json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {"classify": {}, "extract": {}}


def parse(src, path, settings):
    return parse_document(src.read(path), source_id=path, settings=settings)


def eligible_docs(truth):
    """Attachments whose extraction can be judged field by field."""
    for eid, t in truth.items():
        if "si" in t and t.get("review_reason") not in ("unreadable",):
            yield eid, t


async def call_ai(emails, truth, src, settings, cache, timeout, pause=4):
    provider = create_provider(settings)
    if provider is None:
        raise SystemExit("No AI provider is configured in backend/.env")
    gate = asyncio.Semaphore(1)  # one call at a time: the provider rate-limits bursts
    started = time.monotonic()

    def done(entry):
        return entry is not None and "error" not in entry

    async def guarded(make):
        """Run one provider call; back off and retry on rate limits. Returns (result | error, seconds)."""
        async with gate:
            for attempt in range(4):
                t0 = time.monotonic()
                try:
                    out = await asyncio.wait_for(make(), timeout)
                    await asyncio.sleep(pause)
                    return out, round(time.monotonic() - t0, 1)
                except DomainError as exc:
                    if exc.code == "PROVIDER_RATE_LIMITED" and attempt < 3:
                        await asyncio.sleep(30 * (attempt + 1))
                        continue
                    return {"error": exc.code}, round(time.monotonic() - t0, 1)
                except Exception as exc:  # noqa: BLE001 - recorded, not hidden
                    return {"error": type(exc).__name__}, round(time.monotonic() - t0, 1)

    async def classify(email):
        key = email["email_id"]
        if done(cache["classify"].get(key)):
            return
        out, seconds = await guarded(lambda: provider.classify(email["subject"], email["body"], email["attachments"]))
        if isinstance(out, dict):
            cache["classify"][key] = {**out, "seconds": seconds}
        else:
            cache["classify"][key] = {"category": out[0].category, "ambiguous": out[0].ambiguous, "seconds": seconds}
        CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")

    async def extract(path):
        if done(cache["extract"].get(path)):
            return
        try:
            document = parse(src, path, settings)
        except Exception as exc:  # noqa: BLE001
            cache["extract"][path] = {"error": f"parse:{type(exc).__name__}"}
            return
        out, seconds = await guarded(lambda: provider.extract(document))
        if isinstance(out, dict):
            cache["extract"][path] = {**out, "seconds": seconds}
        else:
            cache["extract"][path] = {"extraction": out[0].model_dump(mode="json"), "seconds": seconds}
        CACHE.write_text(json.dumps(cache, indent=1), encoding="utf-8")

    by_id = {e["email_id"]: e for e in emails}
    paths = [p for eid, _ in eligible_docs(truth) for p in by_id[eid]["attachments"]]
    todo = sum(not done(cache["classify"].get(e["email_id"])) for e in emails) + sum(
        not done(cache["extract"].get(p)) for p in paths)
    print(f"AI calls still to make: {todo} (successful cached results are skipped)")
    await asyncio.gather(*[classify(e) for e in emails], *[extract(p) for p in paths])
    await provider.close()
    print(f"AI calls finished in {time.monotonic() - started:.0f}s")


def norm(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").casefold())


def field_correct(field, extracted, truth_value):
    """Was the value read correctly? Lenient about spelling variants, strict about the value itself."""
    if extracted is None or extracted.state != "present" or not extracted.raw_value:
        return False
    raw = extracted.raw_value
    context = " ".join(e.quote for e in extracted.evidence)
    if field in ("shipper", "consignee", "notify_party"):
        a, b = party(raw).value or "", party(truth_value).value or ""
        return bool(a) and (a == b or norm(b) in norm(a) or norm(a) in norm(b))
    if field in ("port_of_loading", "port_of_discharge"):
        return norm(truth_value) in norm(raw)
    if field == "container_count":
        return containers(raw).value == truth_value
    return weight(raw, context).value == str(truth_value)


def extraction_accuracy(truth, docs, only=None):
    """docs: {path: Extraction|None}. Per-field [correct, total]; `only` limits it to those paths."""
    per = {f: [0, 0] for f in FIELDS}
    for eid, t in eligible_docs(truth):
        if t.get("review_reason") == "missing_value":
            continue
        for role, path in zip(("si", "bl"), t["attachments"], strict=False):
            if only is not None and path not in only:
                continue
            ext = docs.get(path)
            for f in FIELDS:
                per[f][1] += 1
                if ext is not None and field_correct(f, ext.fields.get(f), t[role][f]):
                    per[f][0] += 1
    return per


def predictions(emails, src, settings, classifier=None, filler=None):
    original = (pipeline.classify_intent_safe, pipeline.fill_missing_with_ai)
    if classifier:
        pipeline.classify_intent_safe = classifier
    if filler:
        pipeline.fill_missing_with_ai = filler
    try:
        out = {}
        for e in emails:
            try:
                r = pipeline.process_email_record(email=dict(e), read_attachment_bytes=src.read, settings=settings)
                out[e["email_id"]] = r.prediction.model_dump(mode="json")
            except DomainError:
                out[e["email_id"]] = None  # abstained: intent could not be decided
        return out
    finally:
        pipeline.classify_intent_safe, pipeline.fill_missing_with_ai = original


def score(preds, truth):
    n = len(truth)
    cat_ok = sum(1 for k, t in truth.items() if preds[k] and preds[k]["category"] == t["category"])
    abstain = sum(1 for p in preds.values() if p is None)
    bl = [k for k, t in truth.items() if t["category"] == "BL_COMPARISON"]
    status_ok = sum(1 for k in bl if preds[k] and preds[k]["status"] == truth[k]["status"])
    gold_defect = [k for k in bl if truth[k]["status"] == "MISMATCH"]
    pred_defect = [k for k in bl if preds[k] and preds[k]["status"] == "MISMATCH"]
    caught = [k for k in gold_defect if k in pred_defect]
    exact = [k for k in caught if sorted(preds[k]["defect_fields"]) == sorted(truth[k]["defect_fields"])]
    false_alarms = [k for k in pred_defect if k not in gold_defect]
    gold_rev = [k for k in bl if truth[k]["status"] == "NEEDS_REVIEW"]
    pred_rev = [k for k in bl if preds[k] and preds[k]["status"] == "NEEDS_REVIEW"]
    rev_hit = [k for k in gold_rev if k in pred_rev]
    return {
        "classification": f"{cat_ok}/{n} ({cat_ok / n:.0%}), {abstain} abstained",
        "status (BL emails)": f"{status_ok}/{len(bl)} ({status_ok / len(bl):.0%})",
        "defects caught": f"{len(caught)}/{len(gold_defect)}; exact fields {len(exact)}/{len(gold_defect)}",
        "false alarms (mismatch on clean/other)": f"{len(false_alarms)} {sorted(false_alarms)}",
        "review recall / precision": f"{len(rev_hit)}/{len(gold_rev)} / {len(rev_hit)}/{len(pred_rev)}",
    }


def show(title, block):
    print(f"\n=== {title}")
    for k, v in block.items():
        print(f"  {k:40s} {v}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ai", action="store_true", help="call the live AI provider (uses quota)")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--no-calls", action="store_true", help="score cached AI answers only; make no provider calls")
    args = parser.parse_args()
    args.ai = args.ai or args.no_calls

    src = open_source(str(DATA))
    emails = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((DATA / "inbox").glob("*.json"))]
    truth = json.loads((DATA / "truth.json").read_text(encoding="utf-8"))
    for eid, t in truth.items():
        t["attachments"] = next(e for e in emails if e["email_id"] == eid)["attachments"]
    live = Settings()
    offline = live.model_copy(update={"morpheus_api_key": None, "gemini_api_key": None})
    print(f"held-out set: {len(emails)} emails, {sum(len(e['attachments']) for e in emails)} attachments")

    # 1. Rules only, exactly as the benchmark runs them.
    rules = predictions(emails, src, offline)
    show("RULES ONLY (offline)", score(rules, truth))
    per_cat = collections.defaultdict(lambda: [0, 0])
    for k, t in truth.items():
        per_cat[t["category"]][1] += 1
        per_cat[t["category"]][0] += bool(rules[k] and rules[k]["category"] == t["category"])
    print("  per-category correct:", {c: f"{a}/{b}" for c, (a, b) in per_cat.items()})
    rule_docs = {}
    for eid, t in eligible_docs(truth):
        for p in t["attachments"]:
            try:
                rule_docs[p] = extract_labelled(parse(src, p, offline))
            except Exception:  # noqa: BLE001
                rule_docs[p] = None
    pf = extraction_accuracy(truth, rule_docs)
    print("  rules extraction, fields read correctly:",
          f"{sum(a for a, _ in pf.values())}/{sum(b for _, b in pf.values())}",
          {f: f"{a}/{b}" for f, (a, b) in pf.items()})

    if not args.ai:
        print("\n(run with --ai to measure the live AI classifier and extractor)")
        return
    cache = load_cache()
    if not args.no_calls:
        asyncio.run(call_ai(emails, truth, src, live, cache, args.timeout))

    # 2. AI classification alone, on all emails.
    cls = cache["classify"]
    errors = [k for k, v in cls.items() if "error" in v]
    ok = sum(1 for k, t in truth.items() if cls.get(k, {}).get("category") == t["category"] and not cls[k].get("ambiguous"))
    print(f"\n=== AI CLASSIFICATION ALONE (all {len(truth)} emails)")
    print(f"  correct {ok}/{len(truth)} ({ok / len(truth):.0%}); provider errors/timeouts: {len(errors)} {sorted(set(cls[k]['error'] for k in errors))}")
    secs = sorted(v["seconds"] for v in cls.values() if "seconds" in v)
    print(f"  latency seconds: median {secs[len(secs) // 2]}, max {secs[-1]}")
    wrong = [(k, truth[k]["category"], cls[k].get("category"), cls[k].get("ambiguous")) for k in truth
             if k in cls and "error" not in cls[k] and (cls[k]["category"] != truth[k]["category"] or cls[k].get("ambiguous"))]
    print("  wrong or ambiguous:", wrong)

    # 3. AI extraction alone, on parseable documents.
    ai_docs = {}
    for path, v in cache["extract"].items():
        ai_docs[path] = clear_placeholders(Extraction.model_validate(v["extraction"])) if "extraction" in v else None
    ext_errors = collections.Counter(v["error"] for v in cache["extract"].values() if "error" in v)
    answered = {p for p, e in ai_docs.items() if e is not None}
    af = extraction_accuracy(truth, ai_docs, only=answered)
    rf = extraction_accuracy(truth, rule_docs, only=answered)
    print(f"\n=== AI EXTRACTION ALONE ({len(answered)} documents answered; errors: {dict(ext_errors)})")
    print("  AI fields read correctly:   ", f"{sum(a for a, _ in af.values())}/{sum(b for _, b in af.values())}",
          {f: f"{a}/{b}" for f, (a, b) in af.items()})
    print("  rules on the same documents:", f"{sum(a for a, _ in rf.values())}/{sum(b for _, b in rf.values())}",
          {f: f"{a}/{b}" for f, (a, b) in rf.items()})
    esecs = sorted(v["seconds"] for v in cache["extract"].values() if "seconds" in v)
    if esecs:
        print(f"  latency seconds: median {esecs[len(esecs) // 2]}, max {esecs[-1]}")

    # 4. The app's assisted mode: rules first, AI only for undecided emails and unread fields.
    original_safe = pipeline.classify_intent_safe

    def assisted_classifier(subject, body):
        decided = classify_explicit(subject, body)
        if decided:
            return decided
        for e in emails:
            if e["subject"] == subject and e["body"] == body:
                hit = cls.get(e["email_id"])
                if hit and "error" not in hit:
                    return Classification(category=hit["category"], ambiguous=hit["ambiguous"],
                                          evidence_span_ids=("current",), reason_code="conflicting_intent" if hit["ambiguous"] else "informational")
        return original_safe(subject, body)

    def assisted_fill(extraction, document, settings, ai=None):
        proposed = ai_docs.get(document.source_id)
        if proposed is None:
            return extraction
        fields = dict(extraction.fields)
        for name in extraction.fields:
            if extraction.fields[name].state == "missing" and proposed.fields[name].state == "present":
                fields[name] = proposed.fields[name]
        return extraction.model_copy(update={"fields": fields})

    assisted = predictions(emails, src, offline, classifier=assisted_classifier, filler=assisted_fill)
    show("ASSISTED (rules first; AI for undecided emails and unread fields)", score(assisted, truth))
    merged = {p: (rule_docs.get(p) if rule_docs.get(p) else None) for p in rule_docs}
    for p, ext in list(merged.items()):
        proposed = ai_docs.get(p)
        if ext is not None and proposed is not None:
            fields = dict(ext.fields)
            for name in ext.fields:
                if ext.fields[name].state == "missing" and proposed.fields[name].state == "present":
                    fields[name] = proposed.fields[name]
            merged[p] = ext.model_copy(update={"fields": fields})
    mf = extraction_accuracy(truth, merged)
    print("  assisted extraction, fields read correctly:",
          f"{sum(a for a, _ in mf.values())}/{sum(b for _, b in mf.values())}",
          {f: f"{a}/{b}" for f, (a, b) in mf.items()})
    (DATA / "eval_results.json").write_text(json.dumps({"rules": rules, "assisted": assisted}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()


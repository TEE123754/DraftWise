"""How well does the AI classifier do, next to the rules, on emails whose answers are known?

The labelled sample is the held-out set (`scripts/build_heldout.py`): 60 emails written independently of
the supplied dataset, spread over all five categories, with their answers in `truth.json`. The
official 520-email sample is never used here, so this measures generalisation, not memory.

Scoring is pure; loading reads the held-out folder and its cached AI answers, and costs nothing.
"""

import json
import math
from pathlib import Path

from app.services.classification import classify_explicit
from app.services.dataset_import import open_source

CATEGORIES = ("BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM")


def load_heldout(root: Path):
    """(truth, emails, cached AI answers) or None when the folder is not shipped (container images)."""
    try:
        truth = json.loads((root / "truth.json").read_text(encoding="utf-8"))
        emails = {item.email_id: item for item in open_source(root).emails()}
    except (OSError, ValueError):
        return None
    try:
        cache = json.loads((root / "ai_cache.json").read_text(encoding="utf-8")).get("classify", {})
    except (OSError, ValueError):
        cache = {}
    return {key: value["category"] for key, value in truth.items()}, emails, cache


def _rate(numerator, denominator):
    return round(numerator / denominator, 4) if denominator else None


def _percentile(values, share):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(share * len(ordered)) - 1)]


def usable(answer) -> bool:
    """An AI answer that names one category. Errors and 'ambiguous' answers are not predictions."""
    return bool(answer) and "error" not in answer and not answer.get("ambiguous") and bool(answer.get("category"))


def score_classifier(truth: dict[str, str], emails: dict, ai: dict[str, dict]) -> dict:
    """Rules, AI and rules-then-AI accuracy over the labelled sample.

    `ai` maps email ID to {"category", "ambiguous", "seconds"} or {"error": code}; an ID with no entry
    was not asked. Rates are over what was actually measured, and every count is returned with them.
    """
    rules_call = {}
    for email_id in truth:
        email = emails[email_id]
        decided = classify_explicit(email.subject, email.body)
        rules_call[email_id] = decided.category if decided and not decided.ambiguous else None

    asked = [email_id for email_id in truth if email_id in ai]
    ai_call = {email_id: ai[email_id]["category"] if usable(ai[email_id]) else None for email_id in asked}
    seconds = [ai[e]["seconds"] for e in asked if usable(ai[e]) and isinstance(ai[e].get("seconds"), (int, float))]

    n = len(truth)
    rules_decided = [e for e in truth if rules_call[e] is not None]
    rules_right = [e for e in rules_decided if rules_call[e] == truth[e]]
    ai_answered = [e for e in asked if ai_call[e] is not None]
    ai_right = [e for e in ai_answered if ai_call[e] == truth[e]]
    combined_right = 0
    combined_decided = 0
    for email_id in truth:
        pick = rules_call[email_id] or ai_call.get(email_id)
        if pick is not None:
            combined_decided += 1
            combined_right += pick == truth[email_id]

    per_category = {}
    for category in CATEGORIES:
        members = [e for e in truth if truth[e] == category]
        per_category[category] = {
            "total": len(members),
            "rules_correct": sum(rules_call[e] == category for e in members),
            "ai_correct": sum(ai_call.get(e) == category for e in members),
        }
    return {
        "sample_size": n,
        "rules": {
            "correct": len(rules_right),
            "abstained": n - len(rules_decided),
            "wrong": len(rules_decided) - len(rules_right),
            "accuracy": _rate(len(rules_right), n),
            "accuracy_when_decided": _rate(len(rules_right), len(rules_decided)),
        },
        "ai": {
            "asked": len(asked),
            "correct": len(ai_right),
            "wrong": len(ai_answered) - len(ai_right),
            "unusable": len(asked) - len(ai_answered),
            "accuracy": _rate(len(ai_right), len(asked)),
            "unusable_rate": _rate(len(asked) - len(ai_answered), len(asked)),
            "latency_seconds": {
                "mean": round(sum(seconds) / len(seconds), 1) if seconds else None,
                "p95": _percentile(seconds, 0.95),
                "max": max(seconds) if seconds else None,
            },
        },
        "combined": {
            "correct": combined_right,
            "undecided": n - combined_decided,
            "accuracy": _rate(combined_right, n),
        },
        "per_category": per_category,
    }

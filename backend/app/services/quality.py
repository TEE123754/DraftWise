"""Evaluation only: callers provide frozen predictions and independent labels."""

from collections import Counter
from math import log2
from statistics import mean

CATEGORIES = ("BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM")


def score_predictions(expected, predictions):
    rows = {r["id"]: r for r in predictions}
    matrix = {a: {b: 0 for b in (*CATEGORIES, "ABSTAIN")} for a in CATEGORIES}
    fields, comparisons, latencies = [], [], []
    for truth in expected:
        result = rows.get(truth["id"], {})
        predicted = result.get("category") or "ABSTAIN"
        if predicted not in CATEGORIES:
            predicted = "ABSTAIN"
        matrix[truth["category"]][predicted] += 1
        for field, value in truth.get("fields", {}).items():
            fields.append(result.get("fields", {}).get(field) == value)
        for field, value in truth.get("comparisons", {}).items():
            comparisons.append(result.get("comparisons", {}).get(field) == value)
        if result.get("latency_ms") is not None:
            latencies.append(result["latency_ms"])
    count = len(expected)
    abstained = sum(r["ABSTAIN"] for r in matrix.values())
    per_class = {}
    for category in CATEGORIES:
        tp = matrix[category][category]
        predicted = sum(r[category] for r in matrix.values())
        actual = sum(matrix[category].values())
        per_class[category] = {
            "precision": tp / predicted if predicted else None,
            "recall": tp / actual if actual else None,
            "support": actual,
        }
    return {
        "sample_count": count,
        "coverage": (count - abstained) / count if count else None,
        "accuracy": sum(matrix[c][c] for c in CATEGORIES) / count if count else None,
        "abstention_rate": abstained / count if count else None,
        "per_class": per_class,
        "confusion_matrix": matrix,
        "extraction_accuracy": mean(fields) if fields else None,
        "extraction_field_count": len(fields),
        "comparison_accuracy": mean(comparisons) if comparisons else None,
        "comparison_field_count": len(comparisons),
        "mean_latency_ms": mean(latencies) if latencies else None,
    }


def distribution(labels):
    counts = Counter(labels)
    return {c: counts[c] / len(labels) if labels else 0 for c in CATEGORIES}


def divergence(a, b):
    result = 0
    for c in CATEGORIES:
        p, q = a.get(c, 0), b.get(c, 0)
        m = (p + q) / 2
        if p:
            result += p * log2(p / m) / 2
        if q:
            result += q * log2(q / m) / 2
    return result


def assess_windows(baseline, earlier, latest, minimum=20, threshold=0.15):
    if not baseline:
        return {
            "state": "baseline_required",
            "reason": "Create a baseline from human-reviewed classifications",
        }
    if min(len(earlier), len(latest)) < minimum:
        return {
            "state": "insufficient_data",
            "required_per_window": minimum,
            "window_sizes": [len(earlier), len(latest)],
        }
    shifts = [divergence(baseline, distribution(w)) for w in (earlier, latest)]
    return {
        "state": "suspected_shift" if all(s >= threshold for s in shifts) else "stable",
        "divergence": shifts,
        "threshold": threshold,
        "window_sizes": [len(earlier), len(latest)],
        "concept_drift_confirmed": False,
        "reason": "Category distribution alone cannot confirm concept drift",
    }

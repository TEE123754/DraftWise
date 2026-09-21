"""Scores classifier predictions against a reference label workbook.

The default reference, shipping_verification_results.xlsx, is this project's own generated report,
not an organizer answer key. Agreement with it is a regression check, not measured accuracy, and
the report says so unless --independent-reference is passed for a genuinely independent label set.
Measured accuracy comes from the organizer scoring server (scripts/benchmark.py run --submit).
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl

BASE_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = Path(__file__).resolve().parents[1]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("score_benchmark")


def score_benchmark(
    predictions_path: Path | None = None,
    ground_truth_path: Path | None = None,
    output_report_path: Path | None = None,
    independent_reference: bool = False,
):
    preds_file = predictions_path or (BASE_DIR / "artifacts/benchmarks/ai-classifier-run-01/predictions.jsonl")
    gt_file = ground_truth_path or (BASE_DIR / "shipping_verification_results.xlsx")
    report_out = output_report_path or (BASE_DIR / "artifacts/quality/report-v2.json")

    if not preds_file.exists():
        logger.error("Predictions file not found at %s", preds_file)
        sys.exit(1)

    logger.info("Loading reference labels from: %s", gt_file)
    expected = {}
    if gt_file.exists():
        wb = openpyxl.load_workbook(gt_file, data_only=True)
        ws = wb["All_520_Emails"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0]:
                expected[str(row[0])] = {
                    "category": str(row[3]) if row[3] else "UNKNOWN",
                    "status": str(row[4]) if row[4] else None,
                }
        wb.close()
        logger.info("Loaded %d reference labels", len(expected))
    else:
        logger.warning("Reference file not found at %s", gt_file)

    # Read predictions
    predictions = []
    with open(preds_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                predictions.append(json.loads(line.strip()))

    total = len(predictions)
    logger.info("Loaded %d predictions to score", total)

    rule_total = sum(1 for p in predictions if p.get("method") == "rule")
    ai_total = sum(1 for p in predictions if p.get("method") == "ai")
    fallback_total = sum(1 for p in predictions if p.get("method") == "fallback")

    # Metrics
    matched_gt = 0
    correct = 0
    correct_by_method = defaultdict(int)
    total_by_method = defaultdict(int)

    cat_tp = defaultdict(int)
    cat_fp = defaultdict(int)
    cat_fn = defaultdict(int)
    cat_support = defaultdict(int)

    for p in predictions:
        eid = p["email_id"]
        pred_cat = p.get("category")
        method = p.get("method", "unknown")
        total_by_method[method] += 1

        if eid in expected:
            matched_gt += 1
            exp_cat = expected[eid]["category"]
            cat_support[exp_cat] += 1

            if pred_cat == exp_cat:
                correct += 1
                correct_by_method[method] += 1
                cat_tp[exp_cat] += 1
            else:
                cat_fp[pred_cat] += 1
                cat_fn[exp_cat] += 1

    accuracy = round(correct / max(matched_gt, 1), 4)

    # Per-category precision/recall/f1
    categories = sorted(set(list(cat_support.keys()) + list(cat_tp.keys()) + list(cat_fp.keys())))
    category_metrics = {}
    for cat in categories:
        tp = cat_tp[cat]
        fp = cat_fp[cat]
        fn = cat_fn[cat]
        sup = cat_support[cat]
        prec = round(tp / max(tp + fp, 1), 4)
        rec = round(tp / max(tp + fn, 1), 4)
        f1 = round(2 * prec * rec / max(prec + rec, 0.0001), 4)
        category_metrics[cat] = {
            "support": sup,
            "precision": prec,
            "recall": rec,
            "f1": f1,
        }

    report = {
        "reference": {"source": gt_file.name, "independent": independent_reference},
        "dataset": {
            "total_emails": total,
            "reference_evaluated": matched_gt,
        },
        "overall": {
            "accuracy": accuracy,
            "abstention_rate": round(fallback_total / max(total, 1), 4),
            "coverage": round((total - fallback_total) / max(total, 1), 4),
        },
        "by_method": {
            "rule": {
                "count": rule_total,
                "accuracy": round(correct_by_method["rule"] / max(total_by_method["rule"], 1), 4),
            },
            "ai": {
                "count": ai_total,
                "accuracy": round(correct_by_method["ai"] / max(total_by_method["ai"], 1), 4) if ai_total else None,
            },
            "fallback": {
                "count": fallback_total,
                "accuracy": round(correct_by_method["fallback"] / max(total_by_method["fallback"], 1), 4) if fallback_total else None,
            },
        },
        "categories": category_metrics,
    }

    report_out.parent.mkdir(parents=True, exist_ok=True)
    report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("Quality report saved to: %s", report_out)
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--independent-reference",
        action="store_true",
        help="Declare that the reference labels were not produced by this pipeline.",
    )
    args = parser.parse_args()
    score_benchmark(args.predictions, args.reference, args.output, args.independent_reference)

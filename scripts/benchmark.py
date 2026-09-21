#!/usr/bin/env python3
"""Benchmark runner, validator, and scoreboard submission client for SDOC hackathon."""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

# Ensure backend modules can be imported
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import httpx
from app.config import Settings
from app.domain.errors import DomainError
from app.domain.models import FIELDS
from app.services.dataset_import import open_source
from app.services.pipeline import process_email_record

VALID_CATEGORIES = {"BL_COMPARISON", "SI_REQUEST", "INVOICE_QUERY", "GENERAL", "SPAM"}
VALID_STATUSES = {"OK", "MISMATCH", "NEEDS_REVIEW"}
VALID_REASONS = {"wrong_doc_type", "missing_attachment", "unreadable", "missing_value"}
VALID_FIELDS = {f.value for f in FIELDS}


def render_bar(val: float, width: int = 24) -> str:
    n = int(round(val * width))
    return "█" * n + "·" * (width - n)


def cmd_run(args: argparse.Namespace) -> int:
    source_uri = args.source
    output_dir = Path(args.output) if args.output else Path("artifacts/benchmarks/latest")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading inbox records from: {source_uri}")
    src = open_source(source_uri)
    try:
        emails = src.emails()
        total_available = len(emails)
        if args.limit and args.limit > 0:
            emails = emails[: args.limit]

        print(f"Ingested {len(emails)} emails (out of {total_available} available)")
        settings = Settings()
        if not args.ai:
            # The pipeline builds a live provider from the environment whenever a document has
            # several unreadable fields. Benchmarks are offline and reproducible unless --ai is given.
            settings = settings.model_copy(update={"morpheus_api_key": None, "gemini_api_key": None})
        print(f"AI extraction fallback: {'ENABLED (live provider calls)' if args.ai else 'disabled (offline)'}")
        submission: dict[str, Any] = {}
        timings: dict[str, float] = {}
        stage_counts = {"BL_COMPARISON": 0, "SI_REQUEST": 0, "INVOICE_QUERY": 0, "GENERAL": 0, "SPAM": 0}
        defect_counts = {"OK": 0, "MISMATCH": 0, "NEEDS_REVIEW": 0}

        unresolved: list[str] = []
        start_time = time.monotonic()
        for idx, item in enumerate(emails, 1):
            email_dict = item.model_dump(by_alias=True)
            t0 = time.monotonic()
            try:
                res = process_email_record(
                    email=email_dict,
                    read_attachment_bytes=src.read,
                    settings=settings,
                )
            except DomainError as exc:
                if exc.code != "UNRESOLVED_CLASSIFICATION":
                    raise
                # Ambiguous intent is never scored as a guess: leave it out of the submission.
                unresolved.append(item.email_id)
                continue
            elapsed = time.monotonic() - t0
            timings[res.email_id] = round(elapsed, 4)

            pred_dict = res.prediction.model_dump(mode="json")
            submission[res.email_id] = pred_dict
            stage_counts[res.prediction.category] = stage_counts.get(res.prediction.category, 0) + 1
            defect_counts[res.prediction.status] = defect_counts.get(res.prediction.status, 0) + 1

            if idx % 25 == 0 or idx == len(emails):
                print(f"  Processed {idx}/{len(emails)} emails ({idx/len(emails)*100:.1f}%)", flush=True)

        total_elapsed = time.monotonic() - start_time
        print(f"\nCompleted in {total_elapsed:.2f}s ({total_elapsed/len(emails)*1000:.1f}ms/email)", flush=True)
        print(f"Categories: {stage_counts}", flush=True)
        print(f"Statuses:   {defect_counts}", flush=True)
        if unresolved:
            print(f"Unresolved classification (omitted from submission): {len(unresolved)}", flush=True)

        # Write output files
        submission_path = output_dir / "submission.json"
        submission_path.write_text(json.dumps(submission, indent=2), encoding="utf-8")
        print(f"Saved submission to {submission_path}", flush=True)

        meta = {
            "source": source_uri,
            "emails_count": len(emails),
            "total_time_seconds": round(total_elapsed, 3),
            "ai_fallback": bool(args.ai),
            "stage_counts": stage_counts,
            "defect_counts": defect_counts,
            "unresolved_classification": unresolved,
        }
        (output_dir / "manifest.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

        if args.submit:
            print("\nSubmitting to benchmark harness...")
            return submit_payload(submission, source_uri, output_dir)

        return 0
    finally:
        src.close()


def validate_submission_dict(submission: dict, expected_ids: set[str] | None = None) -> list[str]:
    errors = []
    if not isinstance(submission, dict):
        return ["Submission must be a JSON dictionary keyed by email_id"]

    if expected_ids is not None:
        sub_ids = set(submission.keys())
        missing = expected_ids - sub_ids
        extra = sub_ids - expected_ids
        if missing:
            errors.append(f"Missing {len(missing)} expected email IDs: e.g. {sorted(missing)[:5]}")
        if extra:
            errors.append(f"Extra {len(extra)} unexpected email IDs: e.g. {sorted(extra)[:5]}")

    for email_id, p in submission.items():
        if not isinstance(p, dict):
            errors.append(f"Email {email_id} prediction is not an object")
            continue
        cat = p.get("category")
        status = p.get("status")
        reason = p.get("review_reason")
        has_defect = p.get("has_defect")
        defects = p.get("defect_fields")

        if cat not in VALID_CATEGORIES:
            errors.append(f"{email_id}: invalid category '{cat}'")
        if status not in VALID_STATUSES:
            errors.append(f"{email_id}: invalid status '{status}'")
        if reason is not None and reason not in VALID_REASONS:
            errors.append(f"{email_id}: invalid review_reason '{reason}'")
        if not isinstance(has_defect, bool):
            errors.append(f"{email_id}: has_defect must be a boolean")
        if not isinstance(defects, (list, tuple)):
            errors.append(f"{email_id}: defect_fields must be a list")
        else:
            invalid_fields = set(defects) - VALID_FIELDS
            if invalid_fields:
                errors.append(f"{email_id}: invalid defect_fields {invalid_fields}")

        # Invariant checks
        if status == "MISMATCH":
            if not has_defect or not defects or reason is not None:
                errors.append(f"{email_id}: MISMATCH requires has_defect=True, non-empty defects, and null reason")
        elif status == "OK":
            if has_defect or defects or reason is not None:
                errors.append(f"{email_id}: OK requires has_defect=False, empty defects, and null reason")
        elif status == "NEEDS_REVIEW":
            if has_defect or defects or reason is None:
                errors.append(f"{email_id}: NEEDS_REVIEW requires has_defect=False, empty defects, and non-null reason")

    return errors


def cmd_validate(args: argparse.Namespace) -> int:
    sub_path = Path(args.submission)
    if not sub_path.is_file():
        print(f"Error: submission file not found at {sub_path}", file=sys.stderr)
        return 1

    sub_data = json.loads(sub_path.read_text(encoding="utf-8"))
    expected_ids = None

    if args.source:
        src = open_source(args.source)
        try:
            expected_ids = {e.email_id for e in src.emails()}
        finally:
            src.close()

    errors = validate_submission_dict(sub_data, expected_ids)
    if errors:
        print(f"Validation FAILED with {len(errors)} errors:")
        for err in errors[:20]:
            print(f"  - {err}")
        if len(errors) > 20:
            print(f"  ... and {len(errors) - 20} more errors")
        return 1

    print(f"Validation PASSED: {len(sub_data)} records strictly conform to benchmark submission schema.")
    return 0


def submit_payload(submission: dict, source_url: str, output_dir: Path | None = None) -> int:
    # Ensure source_url points to the HTTP endpoint
    url = source_url.rstrip("/")
    if not url.startswith(("http://", "https://")):
        print(f"Error: Submission requires an HTTP server origin (e.g. http://localhost:8080). Got: {source_url}", file=sys.stderr)
        return 1

    target = f"{url}/submit"
    print(f"Sending POST request to {target}...")
    try:
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(target, json=submission)
            if resp.status_code != 200:
                print(f"Submission failed ({resp.status_code}): {resp.text}", file=sys.stderr)
                return 1
            result = resp.json()
    except Exception as exc:
        print(f"Error connecting to server at {target}: {exc}", file=sys.stderr)
        return 1

    print("=" * 62)
    print("           SDOC HACKATHON BENCHMARK SCOREBOARD")
    print("=" * 62)
    if "final_score" in result:
        fs = result["final_score"]
        print(f"\n  ★ FINAL SCORE:      {fs:.4f}  {render_bar(fs)}")
    if "stage1" in result:
        s1 = result["stage1"]
        print(f"\n  STAGE 1 · Email classification")
        print(f"    accuracy:         {s1.get('accuracy', 0):.3f}  {render_bar(s1.get('accuracy', 0))}")
        print(f"    macro-F1:         {s1.get('macro_f1', 0):.3f}  {render_bar(s1.get('macro_f1', 0))}")
    if "stage3" in result:
        s3 = result["stage3"]
        print(f"\n  STAGE 3 · Discrepancy comparison")
        print(f"    defect-F1:        {s3.get('defect_f1', 0):.3f}  {render_bar(s3.get('defect_f1', 0))}")
        print(f"    field-F1:         {s3.get('field_f1', 0):.3f}  {render_bar(s3.get('field_f1', 0))}")
        exact = s3.get("exact_match_rate", 0)
        print(f"    defect precision: {s3.get('defect_precision', 0):.3f}  {render_bar(s3.get('defect_precision', 0))}")
        print(f"    defect recall:    {s3.get('defect_recall', 0):.3f}  {render_bar(s3.get('defect_recall', 0))}")
        print(f"    exact-match:      {exact:.3f}  {render_bar(exact)}")
    if "reliability" in result:
        rel = result["reliability"]
        print(f"\n  RELIABILITY · Human escalation")
        print(f"    recall:           {rel.get('escalation_recall', 0):.3f}  {render_bar(rel.get('escalation_recall', 0))}")
        print(f"    precision:        {rel.get('escalation_precision', 0):.3f}  {render_bar(rel.get('escalation_precision', 0))}"
              f"  ({rel.get('pred_review', 0)} sent to review, {rel.get('gold_review', 0)} needed)")
    if "end_to_end" in result:
        e2e = result["end_to_end"]
        print(f"\n  END-TO-END RATE:    {e2e.get('rate', 0):.3f}  {render_bar(e2e.get('rate', 0))}"
              f"  ({e2e.get('success', 0)}/{e2e.get('total', 0)} defects caught with exact fields)")

    print("=" * 62)

    if output_dir:
        sb_path = output_dir / "scoreboard.json"
        sb_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Saved scoreboard to {sb_path}")

    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    sub_path = Path(args.submission)
    if not sub_path.is_file():
        print(f"Error: submission file not found at {sub_path}", file=sys.stderr)
        return 1
    sub_data = json.loads(sub_path.read_text(encoding="utf-8"))
    return submit_payload(sub_data, args.source, sub_path.parent)


def main() -> int:
    # The scoreboard prints box and star characters; a cp1252 Windows console would crash on them
    # before the scoreboard is saved.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="SDOC Verification & Benchmarking Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run command
    run_parser = subparsers.add_parser("run", help="Run end-to-end pipeline across an inbox")
    run_parser.add_argument("--source", default="http://localhost:8080", help="Data source: HTTP origin, local folder, or archive")
    run_parser.add_argument("--config", default="benchmark/pipeline-v1.json", help="Path to pipeline configuration")
    run_parser.add_argument("--output", default="artifacts/benchmarks/run-001", help="Directory to save run artifacts")
    run_parser.add_argument("--limit", type=int, default=None, help="Limit number of emails to process (for quick testing)")
    run_parser.add_argument("--submit", action="store_true", help="Automatically submit result after run completes")
    run_parser.add_argument("--ai", action="store_true", help="Allow live AI extraction fallback (uses provider quota; default is offline)")

    # validate command
    val_parser = subparsers.add_parser("validate", help="Validate a submission file against the schema")
    val_parser.add_argument("submission", help="Path to submission.json")
    val_parser.add_argument("--source", default=None, help="Optional source to verify email ID completeness")

    # submit command
    sub_parser = subparsers.add_parser("submit", help="Submit an existing submission to the scoring server")
    sub_parser.add_argument("submission", help="Path to submission.json")
    sub_parser.add_argument("--source", default="http://localhost:8080", help="Scoring server HTTP origin")

    args = parser.parse_args()
    if args.command == "run":
        return cmd_run(args)
    if args.command == "validate":
        return cmd_validate(args)
    if args.command == "submit":
        return cmd_submit(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

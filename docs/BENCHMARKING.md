# Benchmarking

[Repository overview](../README.md) · [Implementation plan](../IMPLEMENTATION_PLAN.md)


## 1 Actual provided harness contract

Keep the organizer server separate from the application API. Docker Compose service `inbox` maps host port 8080 to container port 8000. `DATA_DIR=/data`, `GROUND_TRUTH=/secrets/ground_truth.json`; input mounts are read-only. `/ground_truth` exists in server code but is disabled unless `REVEAL_GT=1`; never enable it or use it from product/evaluation code. The archive's default mount also contains the answer-key file under `data_v2`; pipeline ingestion must explicitly allowlist `inbox/`, `attachments/` and `sample_submission.json` rather than scanning every JSON file.

| Harness endpoint | Exact behavior |
|---|---|
| GET `/health` | `{status:"ok",emails:520,scoring_available:true}` when correctly mounted |
| GET `/emails` | JSON array of complete inbox records |
| GET `/emails/{email_id}` | One input record; 404 if absent |
| GET `/attachments/{path}` | Attachment bytes; use `/attachments/email_004_SI.txt`, not a duplicated prefix |
| GET `/sample_submission` | Email-ID-keyed defaults; not reference answers |
| POST `/submit` | Email-ID-keyed JSON object directly, without `predictions` wrapper |

The supplied loader's `read_bytes()` supports binary inputs; `read_text()` is only safe for text. `Inbox(local_dir).submit()` raises an error because submission needs HTTP. Build an adapter around the loader's interface and use `read_bytes` for PDFs/office files. URL-encode attachment paths and confine local file resolution with `Path.resolve().is_relative_to(root)`, not vulnerable string-prefix checks.

## 2 Export schema and example

The authoritative JSON Schema is [shared/schemas/submission.schema.json](../shared/schemas/submission.schema.json).

```json
{
  "email_example_a":{"category":"BL_COMPARISON","status":"MISMATCH","review_reason":null,"has_defect":true,"defect_fields":["container_count"]},
  "email_example_b":{"category":"BL_COMPARISON","status":"NEEDS_REVIEW","review_reason":"missing_attachment","has_defect":false,"defect_fields":[]},
  "email_example_c":{"category":"INVOICE_QUERY","status":"OK","review_reason":null,"has_defect":false,"defect_fields":[]}
}
```

The example illustrates shape, not predictions for actual emails. Before submission, assert exported keys equal the dataset email-ID set exactly; assert five category values, three statuses, and seven permitted field names. `MISMATCH` requires comparison category, `has_defect=true`, a nonempty sorted unique field set and null reason. `OK` requires false/empty/null. `NEEDS_REVIEW` requires comparison category, false/empty and a supported reason. Do not rely on the server to validate all of this: its top-level validation only checks that the body is a JSON object.

Map internal reasons conservatively: wrong document → `wrong_doc_type`; missing source → `missing_attachment`; corrupt/exhausted OCR → `unreadable`; absent/ambiguous required value → `missing_value`. Pair ambiguity or a classification-only review has no exact harness representation. Mark that run item as unsupported for export until resolved or publish an explicitly documented lossy mapping (`missing_value` for unresolved pair evidence) in diagnostics. Never silently turn provider outages into `unreadable`; finish/retry the run or mark it incomplete.

## 3 Local workflow and network topology

Run these commands from the extracted organizer Docker bundle and the planned project root respectively:

```bash
# In the extracted organizer bundle; leave scoring source unmodified.
docker compose up --build -d
curl --fail http://localhost:8080/health

# Planned project CLI: this script is to be implemented, not supplied by the kit.
python scripts/benchmark.py run \
  --source http://localhost:8080 \
  --config benchmark/pipeline-v1.json \
  --output artifacts/benchmarks/run-001
python scripts/benchmark.py validate \
  artifacts/benchmarks/run-001/submission.json \
  --source http://localhost:8080
curl --fail --request POST http://localhost:8080/submit \
  --header 'Content-Type: application/json' \
  --data-binary @artifacts/benchmarks/run-001/submission.json
```

Use `httpx.AsyncClient` with connect/read deadlines and bounded download concurrency in the runner. Save `manifest.json`, `config.json`, `submission.json`, `scoreboard.json`, stage timings and errors under one run directory, then upload authorized results to Supabase through the application API. Artifact names here specify future implementation output; this plan does not include fabricated benchmark results.

Default local benchmark execution imports the same Python pipeline package as the worker. It does not fork business logic. A cloud-triggered benchmark can enqueue a local-runner job; a registered local process polls with a scoped credential, runs the same package and submits results. If no local runner is connected, return 503 with setup guidance. Never point Railway at `localhost:8080` expecting to reach a laptop. If colocated in Docker, use service DNS (`http://inbox:8000`); host-side runs use `http://localhost:8080`. Do not expose the scoring server publicly merely to bridge this boundary.

## 4 Scoring mathematics from `server/scoring.py`

For TP/FP/FN: precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = 2PR/(P+R); the supplied scorer returns zero for undefined denominators. Preserve this convention when reproducing metric tests.

| Metric | Actual implementation |
|---|---|
| Stage 1 accuracy | Correct category over all truth emails; missing prediction defaults to `GENERAL` |
| Stage 1 macro-F1 | Unweighted average F1 over all five categories |
| Stage 3 defect-F1 | Email-level defect detection on truth comparison cases excluding truth `NEEDS_REVIEW`; predicted defect is gated by predicted comparison category |
| Stage 3 field-F1 | Micro-aggregated set overlap of defect fields; false positive fields count |
| Stage 3 exact-match rate | Exact equality of predicted and reference defect-field sets on included comparison cases |
| End-to-end rate | Among true defective comparison cases: category correct AND `has_defect` true AND exact defect-field set |
| Reliability | Precision/recall/F1 of predicted `NEEDS_REVIEW` versus truth review status, plus caught counts grouped by truth reason |

```text
final_score = 0.30 * stage1.macro_f1
            + 0.20 * stage3.defect_f1
            + 0.50 * end_to_end.rate
```

Scores are fractions in [0,1]; multiply by 100 only for display. Field-F1 and review F1 are diagnostics, not terms in the headline formula. The reliability function currently checks status alone: despite its docstring, it does not enforce category routing or compare the submitted reason to the gold reason. `per_reason.caught` groups by the gold reason and is not predicted reason accuracy. Build stricter independent tests for category/status/reason consistency instead of exploiting this gap.

The scorer returns aggregates and a category confusion matrix, not per-email reference answers. The UI can show per-email predictions/evidence and manually reviewed errors; it cannot claim to know which hidden-reference cases failed from aggregate scores alone. Ground truth is absent from application storage, provider prompts, caches and Git.

## 5 Known dataset limitations and honest reporting

The dataset README says main-set comparison requests without attachments are labelled `OK` with no defects, while explicit missing-attachment edge cases are labelled `NEEDS_REVIEW`. Operationally, both may require a pending/review state. Classify from intent and escalate missing evidence consistently; do not branch on email number, generator internals, or hidden labels to obtain different outcomes. This may lower measured escalation precision while leaving defect-catching metrics unaffected; show the documented limitation beside review metrics.

The README also labels valid image-only scan examples as unreadable. Visual inspection confirms at least one supplied scan is legible. If OCR recovers all seven fields reliably, a real comparison is valid product behavior even when the frozen reliability annotation expects escalation. Do not disable OCR to fit that convention. Record the scan's source evidence and explain the annotation difference. Malformed PDFs remain unreadable after bounded recovery.

`sample_submission.json` defaults every record to `GENERAL`/`OK`; it must never supply predicted category. Filenames expose SI/BL hints but wrong-type examples deliberately violate them. Dataset distributions and repeated templates can make reported scores optimistic; test variants with renamed attachments, shuffled IDs, new entities and reordered layouts.

## 6 Regression testing and acceptance gates

Maintain three distinct suites:

1. **Pure deterministic tests:** placeholder handling, decimal separators, unit conversion, container sums, port alias ambiguity, party qualifier preservation, exact field-set export and decision aggregation.
2. **Input-only integration tests:** every supplied file format, malformed PDF, image-only scan, missing attachment, wrong role, ambiguous pair, prompt injection in body/document text, provider 429/timeout, worker death before/after commit and duplicate submissions. Test DB/RLS and Storage authorization with two workspaces.
3. **Independent labelled evaluation:** manually annotate a development/holdout corpus from source evidence. Split by shipment/near-duplicate family before prompt tuning. Record annotator disagreement and adjudication. Keep automated and human-assisted run results separate.

Minimum release gates are behavioral: 100% inputs either produce a valid result or a visible typed failure; no false `OK` with missing required evidence; 100% schema-valid export with complete ID coverage; no cross-workspace reads/writes; worker restart recovery without duplicate artifacts; stale review writes rejected; malformed files do not crash the API. Proposed quality targets, subject to measurement: ≥0.95 category macro-F1, ≥0.95 field-F1 on the independent comparable holdout, and zero observed false clearances in the failure suite. Report sample sizes and confidence intervals rather than claiming these targets were achieved.

Use paired baseline comparison on identical manifests; fail CI on deterministic invariant violations and statistically/materially meaningful accuracy regressions. Live-provider tests are opt-in and quota-bounded; ordinary CI replays sanitized fixtures with provider mocks. Never add an LLM call to every unit test. Use Promptfoo locally for schema/grounding/prompt-injection assertions and model/prompt comparison; Python tests remain the scoring authority. [Promptfoo repository](https://github.com/promptfoo/promptfoo).

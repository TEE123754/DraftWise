# Local pipeline and email extraction

Email detail responses now include `body_extraction`. The Inbox detail panel shows seven labelled shipping fields with quoted evidence, missing states and conflicting alternatives. Character offsets refer to the original body. Subject and quoted history are excluded from field values. These are informational candidates, never automatically promoted to an authoritative SI. Unlabelled prose remains a review limitation.

The input-only offline pipeline supports directory, static ZIP and loopback HTTP sources through the existing dataset adapters. It uses local classification rules; unresolved intent stays unresolved and does not become GENERAL. Comparison requests use bounded document parsing, content-supported roles and the existing verifier. Parser/OCR failures produce review outcomes rather than aborting subsequent records.

From the repository root:

```powershell
backend/.venv/Scripts/python.exe scripts/benchmark.py run --source sdoc-hackathon-bundle.zip --output artifacts/benchmarks/my-new-run
```

The output directory must be new. Add `--limit 10` for a smoke run. Outputs are `manifest.json`, `results.jsonl`, `timings.json`, `summary.json`, and `partial_predictions.json` when IDs remain unresolved. `submission.json` is written only with full prediction coverage; this does not imply prediction accuracy. Email extraction evidence is included in results, so keep run artifacts private.

No provider calls or evaluator submission occur. The validate/submit subcommands, evaluated five-category classification, supervised training, HTTP harness acceptance and durable worker integration remain pending. No accuracy score is claimed. The ten-email smoke run and 89 backend/PostgreSQL tests passed; the frontend production build and a synthetic live email-body API check passed.

Full local baseline completed: 520 processed, 99 rule-supported predictions and 421 unresolved classifications. No parser errors were observed among routed documents; this does not validate parsing every attachment. Results are in ignored `artifacts/benchmarks/local-pipeline-full-01`. Submission readiness is false. No reference labels or evaluator internals were read.

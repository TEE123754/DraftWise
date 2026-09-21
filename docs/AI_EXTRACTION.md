# AI extraction

[Repository overview](../README.md) · [Implementation plan](../IMPLEMENTATION_PLAN.md)


## 1 Typed engine and prompt versioning

Use `google-genai` behind `StructuredAIClient.classify()`, `.identify_document()`, `.extract()` and `.assess_equivalence()`. Maintain a capability registry for selected model IDs: structured-output support, image/PDF support, request size, account quota, and availability. Configure `GEMINI_MODEL`; select a currently available free-tier model only after a startup schema/image smoke test. The reviewed pricing lists `gemini-3.1-flash-lite` with a free tier, but account availability and quotas must be verified at deployment. [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing).

Use provider-native JSON schema mode and Pydantic v2 `extra='forbid'` models with strict domain validation. A provider's schema subset may require inlining `$defs`; retain the full canonical schema for local validation. Do not strip Markdown or search for JSON inside arbitrary prose as the normal success path. Schema-valid output still needs grounding and semantic validation. [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/structured-output).

Each inference records provider/model, prompt SHA-256, schema version, input hash, parser version, latency, token usage where supplied, attempt number, and safety/refusal outcome. Cache only within a workspace. Prompts are files reviewed with code; thresholds and aliases are versioned configuration.

## 2 Canonical extraction JSON Schema

This is the model's raw extraction contract. Numeric values remain strings until a deterministic Decimal/integer normalizer resolves units and separators. Confidence is computed by the application; the model cannot award itself an acceptance probability.

The authoritative JSON Schema is [shared/schemas/extraction.schema.json](../shared/schemas/extraction.schema.json).

Domain validators enforce: `document_id` equals requested source; all evidence IDs belong to that source; `present` implies a non-placeholder raw value and at least one verified evidence block; `missing`/`unreadable` imply null raw value; ambiguous alternatives are retained, not silently chosen. Unknown keys, NaN, numeric overflow, repeated JSON object keys, or oversized strings fail validation. Parse JSON with duplicate-key rejection before Pydantic validation.

## 3 Reusable prompt templates

`prompts/classify.v1.txt`:

Reusable prompt: [prompts/classify.v1.txt](../prompts/classify.v1.txt).

`prompts/extract.v1.txt`:

Reusable prompt: [prompts/extract.v1.txt](../prompts/extract.v1.txt).

`prompts/equivalence.v1.txt`:

Reusable prompt: [prompts/equivalence.v1.txt](../prompts/equivalence.v1.txt).

ClassificationResult is a strict object with required `category` (five-value enum), `ambiguous` (boolean), `evidence_span_ids` (array of supplied IDs), and `reason_code` (enum: comparison_action, new_si_action, billing_action, informational, irrelevant, conflicting_intent). EquivalenceResult uses a strict relation enum, bounded evidence IDs and bounded reason code; no freeform chain-of-thought is requested or stored.

## 4 Grounding and multimodal extraction

SourceBlock contains `id`, `source_id`, `text`, `kind`, and typed `locator`: PDF page/bounding box; DOCX paragraph/table/row/cell; XLSX sheet/cell range; email character offsets. Preserve a normalization map so whitespace-normalized quotes can be traced to original text.

Text extraction verifies quotes by substring within cited blocks. OCR blocks keep engine confidence and coordinates. For vision, pass page images with application-issued page IDs; model outputs page-scoped quotes, which are matched to independent OCR when possible. Image-only visual assertions without text confirmation remain lower-confidence candidates for human review. Never fabricate precise boxes from a model's guessed coordinates.

For long documents, chunk by pages/sections with repeated header context and stable source IDs. Extract candidates per chunk, then reconcile deterministically by field scope and explicit totals. Two conflicting present values become `ambiguous`; never use last-write-wins. Multiple document extraction is a batch of isolated jobs, not a prompt asking the model to merge shipments.

## 5 Retry and confidence policy

One initial model call plus at most two follow-up calls per extraction stage. Transient 429/5xx/network failures use bounded exponential backoff with full jitter and `Retry-After`; daily quota exhaustion pauses jobs until reset. A schema failure gets one focused re-request with validation errors and original evidence. A grounding failure can request a targeted crop/OCR retry. Authentication/configuration errors fail visibly without retries. Provider refusal remains a failed attempt; do not repeatedly rephrase to bypass it. No provider fallback may incur charges when `FREE_ONLY=true`.

Compute a field evidence score `q = 0.35*grounding + 0.25*readability + 0.20*label_alignment + 0.20*source_agreement`, each component in [0,1]. Source agreement means independently parsed/OCR-supported candidates, not repeated calls to the same model. These coefficients are initial engineering settings. Missing grounding caps q at 0.49; conflicting candidates cap q at 0.59; missing values score 0. A human-confirmed value has `reviewer_confirmed=true`, not an invented statistical probability of 1.

Initial automatic acceptance gate: q ≥ 0.90 for numeric and port fields; q ≥ 0.85 for exact/approved-alias party matches. Lower scores trigger targeted fallback then review. Report confidence uses the minimum required field-pair confidence so strong fields cannot hide one weak field. Show “evidence quality” until reliability calibration exists. Fit calibration on an independently annotated development set, hold out shipment families, and measure selective error versus coverage before describing scores as probabilities.

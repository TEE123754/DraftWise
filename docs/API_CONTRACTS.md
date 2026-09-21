# API contracts

[Repository overview](../README.md) · [Implementation plan](../IMPLEMENTATION_PLAN.md)


## 1 Shared contract conventions

Base path `/api/v1`; endpoint paths below are relative to it. HTTPS in deployment. All business endpoints require `Authorization: Bearer <Supabase access token>` and `X-Workspace-Id`; backend verifies signature/JWKS, issuer, audience, expiry and membership. Browser workspace selection is not authorization. JWT verification caches rotating keys with bounded refresh, not decoded-payload trust.

POST processing endpoints require `Idempotency-Key` (1–128 characters). Store request SHA-256 with the key and operation; same key/same payload returns the existing job; different payload returns 409. Standard async response is 202 with `Location: /api/v1/jobs/{job_id}`. GET job exposes the typed result or a resource link once complete. IDs shown below are illustrative UUIDs.

```json
{
  "job_id": "10000000-0000-4000-8000-000000000001",
  "state": "queued",
  "status_url": "/api/v1/jobs/10000000-0000-4000-8000-000000000001"
}
```

Every error uses this schema: `{error:{code:string,message:string,request_id:uuid,retryable:boolean,details:object}}`. Common errors for authenticated endpoints: 401 invalid/missing session; 403 insufficient role; 404 missing or inaccessible resource; 409 state/idempotency conflict; 422 schema/domain validation; 429 quota with `Retry-After`; 503 unavailable DB/required dependency. Never expose whether another workspace owns a requested ID.

```json
{"error":{"code":"STALE_REVIEW","message":"This review has changed. Reload before saving.","request_id":"90000000-0000-4000-8000-000000000001","retryable":false,"details":{"current_version":4}}}
```

All Pydantic request objects forbid extra keys. JSON fields represented in shorthand tables are typed by [the extraction schema](../shared/schemas/extraction.schema.json) and [the verification schema](../shared/schemas/verification.schema.json); nullable fields are explicit, not omitted accidentally. Case and amendment extensions are defined in [Feature contracts](FEATURE_CONTRACTS.md).

## 2 POST `/classify`

Request schema: `{email_id:uuid, reprocess:boolean=false}`. Operator/admin. Email must exist with finalized body; reprocess schedules a new classification revision. Attachment readiness does not block intent classification.

```json
{"email_id":"20000000-0000-4000-8000-000000000001","reprocess":false}
```

Response: 202 JobAccepted as above. Completed job result schema: `{classification_id:uuid,email_id:uuid,category:EmailCategory,ambiguous:boolean,confidence:number[0,1],decided_by:rule|ai|human,evidence_span_ids:string[],next_action:verify|review|none}`.

```json
{"classification_id":"30000000-0000-4000-8000-000000000001","email_id":"20000000-0000-4000-8000-000000000001","category":"BL_COMPARISON","ambiguous":false,"confidence":0.94,"decided_by":"ai","evidence_span_ids":["body:0:58"],"next_action":"verify"}
```

Endpoint errors: 404 email absent; 409 conflicting idempotency payload; 422 empty unusable input. Provider failure occurs in the job result with a typed retry state, not as a falsely successful classification.

## 3 POST `/extract`

Request schema: `{attachment_ids:uuid[1..20], role_hints:map<uuid,SI|BL|UNKNOWN>={}, reprocess:boolean=false}`. Operator/admin. All IDs must be validated sources in one workspace; hints must refer to IDs in the request. Model role detection can disagree with hints and trigger review.

```json
{"attachment_ids":["40000000-0000-4000-8000-000000000001"],"role_hints":{"40000000-0000-4000-8000-000000000001":"SI"},"reprocess":false}
```

Response 202 JobAccepted; result schema `{items:[{attachment_id:uuid,extraction_id:uuid|null,state:succeeded|needs_review|failed,error_code:string|null}]}`. Detailed extraction available at `GET /extractions/{id}`.

```json
{"items":[{"attachment_id":"40000000-0000-4000-8000-000000000001","extraction_id":"50000000-0000-4000-8000-000000000001","state":"succeeded","error_code":null}]}
```

Errors: 404 inaccessible attachment; 409 upload pending/quarantined; 415 unsupported validated format; 422 duplicate IDs/invalid hints; parser failures become per-item typed outcomes. Batch processing does not discard successful items because another file fails.

## 4 POST `/verify`

Request schema: `{email_id:uuid,si_extraction_id:uuid|null=null,bl_extraction_id:uuid|null=null,policy_version:string="v1"}`. Operator/admin. If IDs are provided, both are required and must be valid role-compatible revisions associated with this email or a confirmed shipment. If omitted, the service resolves/extracts candidates and can produce a missing-source review report. Unapproved policy versions return 422.

```json
{"email_id":"20000000-0000-4000-8000-000000000001","si_extraction_id":"50000000-0000-4000-8000-000000000001","bl_extraction_id":"50000000-0000-4000-8000-000000000002","policy_version":"v1"}
```

Response 202 JobAccepted. Result `{verification_id:uuid,status:OK|MISMATCH|NEEDS_REVIEW,revision:integer,report_url:string}`:

```json
{"verification_id":"60000000-0000-4000-8000-000000000001","status":"MISMATCH","revision":1,"report_url":"/api/v1/verification/60000000-0000-4000-8000-000000000001"}
```

Errors: 404 email/extraction inaccessible; 409 non-comparison classification or unresolved explicit pair; 422 same source used twice, invalid role, incompatible shipment or stale policy. Missing required values are a 202→`NEEDS_REVIEW` business result, not HTTP 500.

## 5 POST `/benchmark`

Request schema: `{dataset_id:string,config_version:string,mode:automated|human_assisted="automated",baseline_run_id:uuid|null=null}`. Admin. Dataset ID resolves to a server-configured immutable manifest. Arbitrary scorer URLs and filesystem paths are prohibited.

```json
{"dataset_id":"provided-v2","config_version":"pipeline-v1","mode":"automated","baseline_run_id":null}
```

Response 202 includes `{job_id:uuid,benchmark_id:uuid,state:"queued",execution_location:local|server}`. Example:

```json
{"job_id":"10000000-0000-4000-8000-000000000002","benchmark_id":"70000000-0000-4000-8000-000000000001","state":"queued","execution_location":"local"}
```

GET `/benchmarks/{id}` returns `{id,state,dataset_sha256,config_sha256,mode,metrics:ScorerResult|null,diagnostics:object,completed_at:datetime|null}`. `ScorerResult` has `stage1`, `stage3`, `reliability`, `end_to_end`, `weights`, `final_score:number[0,1]`, `n_emails:integer`; persist the exact response from [Benchmarking](BENCHMARKING.md) without synthesizing absent measurements. Errors: 404 dataset/baseline absent; 409 active-run limit; 422 invalid config; 503 no authorized runner connected. A cloud Railway process cannot reach the user's `localhost:8080`.

## 6 GET `/verification/{id}`

Request: UUID path; optional `include_evidence:boolean=false`. Viewer or higher. Response 200 uses the complete report schema in [Verification engine](VERIFICATION_ENGINE.md); embedded evidence is separately authorized and size-bounded. `ETag` identifies immutable report hash. Errors: 404 report inaccessible, 422 invalid ID. A processing job without a report is retrieved via `/jobs/{id}`, not represented as an empty successful report.

Example report (illustrative values):

```json
{
  "id":"60000000-0000-4000-8000-000000000001",
  "email_id":"email_example",
  "revision":1,
  "status":"MISMATCH",
  "complete":true,
  "review_reasons":[],
  "confidence":0.94,
  "comparisons":[
    {"field":"shipper","si":{"raw":"Example Export Ltd","normalized":"example export ltd","extraction_id":"50000000-0000-4000-8000-000000000001"},"bl":{"raw":"EXAMPLE EXPORT LTD","normalized":"example export ltd","extraction_id":"50000000-0000-4000-8000-000000000002"},"decision":"match","severity":"none","confidence":0.98,"rule":"identity_exact_v1","explanation":"Party identity matches after case normalization.","evidence_ids":["si:b1","bl:b1"]},
    {"field":"consignee","si":{"raw":"Example Import Ltd","normalized":"example import ltd","extraction_id":"50000000-0000-4000-8000-000000000001"},"bl":{"raw":"Example Import Ltd","normalized":"example import ltd","extraction_id":"50000000-0000-4000-8000-000000000002"},"decision":"match","severity":"none","confidence":0.98,"rule":"identity_exact_v1","explanation":"Consignee identity matches.","evidence_ids":["si:b2","bl:b2"]},
    {"field":"notify_party","si":{"raw":"Example Import Ltd","normalized":"example import ltd","extraction_id":"50000000-0000-4000-8000-000000000001"},"bl":{"raw":"Example Import Ltd","normalized":"example import ltd","extraction_id":"50000000-0000-4000-8000-000000000002"},"decision":"match","severity":"none","confidence":0.97,"rule":"identity_exact_v1","explanation":"Notify party identity matches.","evidence_ids":["si:b3","bl:b3"]},
    {"field":"port_of_loading","si":{"raw":"Port Klang, Malaysia","normalized":"MYPKG","extraction_id":"50000000-0000-4000-8000-000000000001"},"bl":{"raw":"MYPKG","normalized":"MYPKG","extraction_id":"50000000-0000-4000-8000-000000000002"},"decision":"match","severity":"none","confidence":0.96,"rule":"approved_port_alias_v1","explanation":"Both values resolve to the approved port code MYPKG.","evidence_ids":["si:b4","bl:b4"]},
    {"field":"port_of_discharge","si":{"raw":"Singapore","normalized":"SGSIN","extraction_id":"50000000-0000-4000-8000-000000000001"},"bl":{"raw":"Singapore","normalized":"SGSIN","extraction_id":"50000000-0000-4000-8000-000000000002"},"decision":"match","severity":"none","confidence":0.96,"rule":"approved_port_alias_v1","explanation":"Discharge ports match.","evidence_ids":["si:b5","bl:b5"]},
    {"field":"container_count","si":{"raw":"3 x 40HC","normalized":3,"extraction_id":"50000000-0000-4000-8000-000000000001"},"bl":{"raw":"4 x 40HC","normalized":4,"extraction_id":"50000000-0000-4000-8000-000000000002"},"decision":"mismatch","severity":"high","confidence":0.94,"rule":"integer_exact_v1","explanation":"Container count differs: SI 3; BL 4.","evidence_ids":["si:b6","bl:b6"]},
    {"field":"gross_weight_kg","si":{"raw":"22,000 KG","normalized":"22000","extraction_id":"50000000-0000-4000-8000-000000000001"},"bl":{"raw":"22 MT","normalized":"22000","extraction_id":"50000000-0000-4000-8000-000000000002"},"decision":"match","severity":"none","confidence":0.97,"rule":"decimal_unit_exact_v1","explanation":"Both values equal 22000 kg after unit conversion.","evidence_ids":["si:b7","bl:b7"]}
  ]
}
```

## 7 GET `/review-queue`

Request query schema: `state:open|claimed|resolved|dismissed=open`, `reason:string?`, `assigned_to:uuid?`, `limit:integer[1,100]=25`, `cursor:opaque-string?`. Reviewer/admin; viewers can receive a read-only scoped view if explicitly configured. Response: `{items:ReviewSummary[],next_cursor:string|null}`; each summary includes `id,email_id,report_id,reason,priority,state,version,assigned_to,created_at`.

```json
{"items":[{"id":"80000000-0000-4000-8000-000000000001","email_id":"20000000-0000-4000-8000-000000000001","report_id":null,"reason":"missing_attachment","priority":70,"state":"open","version":1,"assigned_to":null,"created_at":"2026-09-18T08:00:00Z"}],"next_cursor":null}
```

Errors: 422 invalid/expired cursor or filters, 403 insufficient role. Empty queue is 200 with `items:[]`.

## 8 PATCH `/review/{id}`

Request is a discriminated union by `action`. All actions require `expected_version:integer>=1` and `rationale:string[1..2000]`. `claim` requires no patch. `correct` requires a nonempty `corrections` array of `{extraction_id:uuid,field:FieldName,raw_value:string,evidence_ids:string[]}`. `confirm` requires `report_id`. `replace` requires `attachment_id` of a finalized source. `dismiss` requires rationale and cannot turn incomplete data into `OK`. `reclassify` requires `category:EmailCategory`. Reviewer/admin; assignee conflict returns 409.

```json
{"action":"correct","expected_version":3,"rationale":"The labelled total in cell B11 is legible.","corrections":[{"extraction_id":"50000000-0000-4000-8000-000000000001","field":"gross_weight_kg","raw_value":"22,000 KG","evidence_ids":["si:Sheet1:B11"]}]}
```

Response 200: `{review_id:uuid,version:integer,state:ReviewState,reverification_job_id:uuid|null}`. Corrections create revisions and queue re-verification; queue remains `claimed` until a completed report resolves the issue.

```json
{"review_id":"80000000-0000-4000-8000-000000000001","version":4,"state":"claimed","reverification_job_id":"10000000-0000-4000-8000-000000000003"}
```

Errors: 409 stale version/already claimed; 422 unsupported field, evidence not in source, empty rationale, or attempt to confirm an incomplete report. Use an atomic `UPDATE ... WHERE version=:expected` and append the review action/new extraction/job in the same transaction. A stale edit never partially writes.

## 9 GET `/health`

No request body, no authentication. Liveness response 200: `{"status":"ok","version":"pipeline-v1"}`. Do not expose secrets, dataset labels or credentials. `GET /ready` returns 200 `{"status":"ready","database":"ok","storage":"configured","worker":"active"}` or 503 with safe dependency status if DB/worker is unavailable. Provider quota status is an operational settings metric; it does not make liveness fail. Minimal public health is separate from authenticated diagnostic detail.

## 10 Supporting endpoints required for a working product

| Endpoint | Request schema/example | Success response schema/example | Validation and errors |
|---|---|---|---|
| POST `/emails` | `{external_id:"manual-1",from:"ops@example.com",subject:"Check draft",body:"Please compare",source_namespace:"manual"}` | 201 `{id:uuid}` | Operator; external ID uniqueness; length limits; 409 same identity/different content; 422 malformed input |
| GET `/emails` | `?category=BL_COMPARISON&limit=25&cursor=...` | 200 `{items:[{id,external_id,subject,category,processing_state,business_status}],next_cursor}` | Viewer; validated filters; 422 invalid cursor |
| GET `/emails/{id}` | UUID path | 200 `{id,external_id,from,subject,body,attachments:[],classification:null,latest_report_id:null,jobs:[]}` | Viewer; 404 inaccessible ID |
| POST `/uploads` | `{email_id:uuid,filename:"SI.pdf",mime_type:"application/pdf",byte_size:12345}` | 201 `{attachment_id:uuid,upload_url:string,expires_at:datetime}` | Operator; filename sanitized; 413 size; 415 MIME; 404 parent |
| POST `/uploads/{id}/complete` | `{sha256:"64 lowercase hex characters"}` | 200 `{attachment_id:uuid,state:"validated"}` | Server independently recomputes hash/MIME; 409 hash mismatch/pending bytes; 413 limit; 415 unsupported |
| GET `/attachments/{id}/preview` | `?page=1` for PDF | 200 `{url:string,expires_at:datetime,locator_type:"pdf_page"}` or typed source blocks for office/text | Viewer; 404 no source; 422 page invalid; no public URL |
| GET `/extractions/{id}` | UUID path | 200 `{id,revision,output:ExtractionResult,normalized_fields:[],run_metadata:{}}` | Viewer; 404 inaccessible; redact provider internals |
| GET `/jobs/{id}` | UUID path | 200 `{id,state,stage,attempt,result:null,error:null,updated_at:datetime}` | Viewer; 404 inaccessible; errors use safe typed structure |
| POST `/jobs/{id}/retry` | `{reason:"Provider quota restored"}` | 202 JobAccepted | Operator; 409 non-retryable/currently running; preserve prior attempts |
| GET `/jobs/{id}/events` | `?after=123` or `Last-Event-ID` | SSE `id:124`, JSON `data:{stage:"extract",state:"running"}` | Viewer; bounded stream; 404; reconnect with cursor; polling fallback |
| GET `/benchmarks/{id}` | UUID path | 200 BenchmarkRun from [API contracts](API_CONTRACTS.md) | Viewer; 404 inaccessible |
| POST `/benchmarks/{id}/results` | `{manifest_sha256:string,submission_sha256:string,metrics:ScorerResult,diagnostics:object}` | 200 `{id:uuid,state:"succeeded"}` | Admin/local runner; immutable matching run/config; 409 already finalized; 422 hash/schema mismatch |
| GET `/settings` | No body | 200 `{policy_version:"v1",free_only:true,provider_ready:true,limits:{}}` | Admin; never return keys; common auth errors |
| PATCH `/settings` | `{expected_version:1,policy_version:"v1",limits:{max_pages:20}}` | 200 `{version:2}` | Admin; 409 stale; 422 unsafe/unsupported limits; secrets are deployment env only |

SSE connects directly to Railway with authorized fetch streaming; native EventSource cannot attach arbitrary authorization headers. Avoid access tokens in query strings. Polling every 2 seconds for active jobs, backing off to 10 seconds, is the default and is sufficient for the free deployment.

## 11 Inbox, AI budget and quality endpoints (inbox redesign)

The list and detail rows in section 10 are richer than shown there. Every email carries the review state the server derived for it.

| Endpoint | Request | Response | Notes |
|---|---|---|---|
| GET `/emails` | `state`, `category`, `q`, `unresolved`, `attention=true`, `trash`, `limit` (1-100), `offset` | `{items:[{id,display_id,external_id,subject,sender,body_preview,category,classified_by,documents:{count,si,bl,other,unread},case,job_state,state,state_label,tone,reasons:[{code,label,fields?}],action:{kind,title}}],total,next_cursor}` | Viewer. Filters and search run on the server, so `total` and paging are exact. `display_id` is the email's own ID (`email_007`, `M-001` for manual mail), never a list position. `attention=true` keeps only states a person can act on, most urgent first. 422 for an unknown `state`. |
| GET `/emails/counts` | none | `{total,by_state:{...},by_category:{...}}` | Viewer. States and categories each sum to `total`. |
| GET `/emails/{id}` | UUID | the row above plus `attachments`, `extractions`, `classification_summary:{category,method,method_label,reason,evidence:[{id,text}]}`, `field_table:{status,documents,rows:[{field,label,decision,explanation,si,bl,email:{state,value,quote,mark}}]}`, `reference_check:{status,cited:[{code,kind,quote,in_documents}]}` | Viewer. `field_table` uses the stored report's own extractions; the `email` column only says whether a value the email states agrees with the documents. `reference_check` is advisory and never links or changes state. |
| GET `/quality/ai-usage` | none | `{scope:"day"\|"demo_session",used,budget,remaining}` | Viewer. Live AI calls against today's workspace budget (`AI_DAILY_BUDGET`) or a demo session's allowance. |
| GET `/quality/ai-classifier` | none | `{available,message,plan:{sample_size,answered,to_call,estimated_seconds},usage,provider_configured,latest:{status,source,sample_size,calls_made,metrics,error}}` | Viewer. `metrics` holds rules, AI and rules-then-AI accuracy, the unusable-output rate, latency and per-category counts on the labelled held-out set. `available:false` when the set is not shipped. |
| POST `/quality/ai-classifier/evaluate` | `{mode:"cached"\|"live",confirm_calls:int}` | the run | Administrator. `cached` re-scores from AI answers already saved and makes no calls. `live` needs `confirm_calls` equal to the calls the plan shows (409 `CONFIRM_CALLS`), enough budget (409 `AI_BUDGET_TOO_LOW`), a configured provider (503) and no run in progress (409 `RUN_IN_PROGRESS`); it then runs paced in the background. |
| POST `/chat` | `{message,page?:{path,email_id?,case_id?}}` | `{answer,citations:[{caseId}\|{emailId,label}],source,method}` | Viewer. Rule-routed and free: "this email/case", "what needs my attention", "which emails are missing documents" use the open page and the inbox. Ids from another workspace are never described. |

Token policy: rules run first everywhere. Live AI is used only when the rules cannot decide or the user asks; each distinct input is answered once (cached per workspace), and a workspace may make `AI_DAILY_BUDGET` live calls a day (demo sessions have their own smaller allowance). Past the limit the caller falls back to the rules (`AI_BUDGET_REACHED`).

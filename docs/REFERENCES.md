# Reference architecture and third-party decisions

[Repository overview](../README.md) · [Implementation plan](../IMPLEMENTATION_PLAN.md)

## 1 Reference architecture decisions

The requested [404-Brain-Not-Found-Recruiter repository](https://github.com/Xiaoming0313883/404-Brain-Not-Found-Recruiter) was inspected at commit `be3bf1de3451d266d923089785c9479ce6e4add3`. Relevant inspected files include `README.md`, `backend/app/services/agents/graph.py`, `base.py`, `backend/app/database.py`, `backend/railway.json` and `src/app/api.ts`.

| Observed pattern | Apply here | Deliberate adaptation |
|---|---|---|
| FastAPI routes/services/config separation | Clear backend boundaries and settings validation | Add typed repositories and durable transaction boundaries |
| Versioned graph state with guardrail/tool/event nodes and bounded steps | A bounded, observable processing trace | Fixed business pipeline; no LLM supervisor choosing arbitrary tools |
| Server-only Supabase client and startup configuration checks | Fail clearly for missing configuration | Add tenant constraints and independent JWT/membership checks |
| Vercel frontend and Railway backend | Same hosting split required by this brief | Reference frontend is React/Vite; implement Next.js App Router, not its SPA rewrite/VITE variables |
| JSON parser helper strips fences/thinking blocks | Recognition that provider output needs validation | Replace permissive extraction with native JSON schema and grounding checks |
| Railway starts on hard-coded port 8000 | Container deployment reference | Bind to Railway's supplied `PORT` and add readiness/worker lifecycle |

GitHub metadata reported no repository license. Treat this repository as architecture reference, not a source to copy verbatim; write original implementation. Keep third-party library notices and pin versions/commits. The competition's originality requirement means understanding a pattern does not authorize submitting another team's code or design.

Additional inspected primary repositories: [FastAPI full-stack template](https://github.com/fastapi/full-stack-fastapi-template) for API/config/test organization, [pdfplumber](https://github.com/jsvine/pdfplumber) for layout evidence, [Tesseract](https://github.com/tesseract-ocr/tesseract) for local OCR, [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) for explicit string matching, [Supabase SSR](https://github.com/supabase/ssr) for session integration, and [Promptfoo](https://github.com/promptfoo/promptfoo) for prompt regression tests. Adopt their relevant capabilities without replacing the mandatory stack or assuming their default authentication/deployment choices fit this system.

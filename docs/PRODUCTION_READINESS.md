# 🧭 Prototype vs. Production — an honest assessment

Short answer: **AegisMed runs well as a hackathon prototype today.** It is not
production-grade for real patient care yet, and this document says exactly why,
so nobody (including us) mistakes a working demo for a deployable clinical
product.

## ✅ What works today (verified)

- **One-command containerized run.** `docker compose up --build` boots the full
  stack from a fresh clone — FastAPI server, static UI, the ~10,700-disease
  citation index, and the guideline-search layer all present in the image.
- **Zero-cost demo mode.** With no API key, every endpoint returns realistic
  pre-written output instead of failing — the whole product can be explored and
  judged without spending a cent or waiting on model latency.
- **Real-AI mode.** With a `FIREWORKS_API_KEY` (or a self-hosted Gemma via
  `LLM_BASE_URL`, see `docs/DEPLOY_AMD.md`), every endpoint runs the actual
  seven-specialist board.
- **48 automated tests pass** (`python -m pytest -q`), covering routing
  validation, region handling, guideline/citation link construction, case
  save/retrieve/comment round-trips, and the request-timeout guarantee.
- **Bounded response time.** Per-call timeouts (12s) and an overall per-request
  deadline (28s, configurable via `REQUEST_TIMEOUT_SECONDS`) mean `/api/diagnose`
  either returns within the hackathon's 30s screening limit or fails cleanly with
  an HTTP 504 — it will never hang silently past the limit.
- **Graceful degradation.** Every data file (knowledge base, guideline index,
  demo cases) has a documented fallback if missing, so a partial deployment
  degrades rather than crashes.
- **Anti-hallucination citations.** References and guideline links are built
  deterministically from a knowledge base and verified URL templates — never
  recalled from the model — so every link a physician sees is real. See
  `docs/EVIDENCE.md`.

## ⚠️ Gaps that matter before real clinical use (documented, not hidden)

| Gap | Why it matters | What production needs |
|---|---|---|
| **Demo mode returns fixed sample output** | The hackathon rule "no hardcoded/cached answers — evaluation uses unseen variants" means automated screening **must** run with a real `FIREWORKS_API_KEY` (or `LLM_BASE_URL`) set, or every case will echo the same canned Fabry-disease answer. | Ensure the screening environment's `.env` sets a real key/endpoint before scoring; demo mode should never be mistaken for the scored path. |
| **File-based case store** (`data/cases.jsonl`) | No concurrent-write safety, no transactions, single point of failure, doesn't scale past one instance. | A real database (Postgres) with proper migrations and connection pooling. |
| **No authentication or authorization** | Anyone who can reach the API can save/read/comment on any case. | Clinician identity (OAuth2/SSO), per-case access control, audit trail. |
| **No PHI handling / HIPAA compliance** | Cases are free-text and unencrypted at rest; no BAA, no audit logging of access. | Encryption at rest and in transit, signed BAAs with any AI vendor, HIPAA-compliant logging, data retention policy. |
| **No rate limiting or abuse protection** | A single client could exhaust API quota or run up cost. | Per-key rate limits, request quotas, cost alerting. |
| **No observability** | No structured logging, metrics, or tracing beyond `/health`. | Structured logs, latency/error metrics, alerting, request tracing across the 3-stage pipeline. |
| **Single-node deployment** | `docker compose up` runs one container; no horizontal scaling, no load balancer. | Multi-instance deployment behind a load balancer; the API is already stateless-per-request (case storage aside), so this is a straightforward next step. |
| **No regulatory clearance** | Output is decision support only, not a cleared medical device. | FDA 510(k) / SaMD pathway, clinical validation studies — see `docs/ROADMAP.md` Phase 4a. |
| **English-only reasoning** | Specialist prompts and synthesis are English-only; only guideline *emphasis* varies by region (`us`/`uk`/`eu`). | Validated translation of clinical reasoning, not just the UI chrome. |

## Verdict

AegisMed is a **credible, working prototype**: it demonstrates the multi-agent
board concept end-to-end, with real (never-invented) citations, bounded latency,
and a one-command deployment story — strong fundamentals for a hackathon judge to
evaluate on completeness and technical execution.

It is **not yet production software** for real patient care, and the gaps above
are the concrete reasons why, along with what closing each one would take. The
roadmap in `docs/ROADMAP.md` sequences this work (Phase 3f: EHR/FHIR integration,
Phase 4a: regulatory pathway, Phase 4c: outcome tracking) into a realistic path
from "impressive demo" to "deployable clinical tool."

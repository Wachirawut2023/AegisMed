# 📄 AegisMed — Project Summary & Product Journey

One page that sums up every report in this repo and walks through the product
end to end. Start here; follow the links for depth.

## The problem, in one sentence

Patients with complex or rare presentations wait **5–7 years on average** for a
correct diagnosis, because the knowledge needed to catch them is scattered
across specialties no single physician holds all at once.

## The idea, in one sentence

Recreate a **multidisciplinary case conference** — the gold-standard way
hospitals actually solve hard cases — as software a doctor can convene in
60 seconds, with seven AI specialist agents instead of seven busy humans.

## The product journey (what actually happens)

1. **A physician enters a case** — symptoms, history, labs, age, sex — in the
   web UI or via `POST /api/diagnose`.
2. **The intake agent** (`aegismed/intake.py`) reviews it first and asks up to 4
   high-value clarifying questions (timeline, family history, exposures, prior
   tests) — like a clinician taking a focused history. The physician answers or
   skips.
3. **The router/retrieval agent** (`aegismed/retrieval.py`) does two jobs in one
   call: extracts key phenotypes + candidate diseases (grounded with real
   Orphanet/OMIM/PubMed/GARD links from `aegismed/knowledge.py`), and decides
   which of the seven specialists this case actually needs (smart routing —
   Medical Genetics always included, full board on any doubt).
4. **The relevant specialists run in parallel** (`aegismed/specialists.py` +
   `orchestrator.py`, `asyncio.gather`) — Cardiology, Neurology, Medical
   Genetics, Immunology & Rheumatology, Infectious Disease, Endocrinology &
   Metabolism, Hematology-Oncology. Each independently says what it sees, or
   "nothing in my domain" — a confident non-answer is treated as valuable, not
   a failure.
5. **The synthesis agent** (the "board chair") merges every opinion into one
   ranked differential diagnosis, flags rare diseases `[RARE]`, states where
   specialists agree/disagree, the single most valuable next test, immediate
   safety actions, and a do-not-miss warning.
6. **Verified citations attach automatically** (`aegismed/knowledge.py`,
   `aegismed/guidelines.py`) — never asked of the model, always real URLs. A
   `region` parameter (`us`/`uk`/`eu`) reorders the same verified guideline
   sources to foreground the most relevant authority (e.g. NICE first for UK).
7. **The physician reviews, prints, or saves** the result. Saved cases
   (`POST /api/cases/save`) get a `case_id`, support team comments for
   case-conference follow-up, and can be listed/filtered by specialty.
8. **Teaching mode** (`POST /api/teaching/case`) runs the same board but also
   compares against an instructor's expected diagnosis — built for medical
   school case-conference simulations.

Every request completes within a **28-second bounded budget** (configurable via
`REQUEST_TIMEOUT_SECONDS`, hard-capped well under the hackathon's 30s screening
limit) — see `docs/PRODUCTION_READINESS.md`.

## Where AMD fits

- **Default path:** Fireworks AI serves Gemma on **AMD Instinct MI300X** GPUs —
  every inference call already runs on AMD hardware with zero extra setup.
- **Self-hosted path:** point `LLM_BASE_URL` at Gemma running on your own **AMD
  Developer Cloud** GPU instance (vLLM/Ollama) — the app and the model both run
  on AMD infrastructure you provision. Full steps: `docs/DEPLOY_AMD.md`.

## The reports in this repo, summarized

| Doc | What it covers | Read it if you want to know... |
|---|---|---|
| [`README.md`](../README.md) | Quickstart, config, project layout | How to run it in 5 minutes |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Zero-background walkthrough of every file and concept | How the multi-agent pipeline actually works, line by line |
| [`EVIDENCE.md`](EVIDENCE.md) | The anti-hallucination citation system | Why every link the app shows is real, never invented |
| [`DATA_AND_EVAL.md`](DATA_AND_EVAL.md) | How to build the eval dataset and score the board | How we prove accuracy with public rare-disease datasets |
| [`API.md`](API.md) | Full endpoint reference with request/response shapes | How to integrate AegisMed into another product |
| [`PRODUCT_OVERVIEW.md`](PRODUCT_OVERVIEW.md) | Deep product spec: use cases, deployment scenarios, limitations | The full feature set and who it's for (solo clinician, med school, hospital, telehealth) |
| [`MARKET_EXPANSION.md`](MARKET_EXPANSION.md) & [`MARKET_EXPANSION_SUMMARY.md`](MARKET_EXPANSION_SUMMARY.md) | Go-to-market thinking, geographic/vertical expansion | The business case and market sizing |
| [`ROADMAP.md`](ROADMAP.md) | Phased plan from prototype to regulated product | What's next: FHIR/EHR integration, FDA/HIPAA pathway, ML feedback loop |
| [`PRODUCTION_READINESS.md`](PRODUCTION_READINESS.md) | **New.** Honest prototype-vs-production gap analysis | Exactly what's solid today vs. what real clinical deployment still needs |
| [`DEPLOY_AMD.md`](DEPLOY_AMD.md) | **New.** Both AMD deployment paths, step by step | How to run AegisMed (and Gemma) on AMD Developer Cloud |
| [`HACKATHON_GUIDE.md`](HACKATHON_GUIDE.md) | Event rules, timeline, judging criteria | The hackathon logistics |
| [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) | Submission form mirror | The final tick-box list before submitting |

## Verification snapshot (this pass)

- ✅ `python -m pytest -q` — **48/48 tests pass** (demo mode, no network).
- ✅ App boots and every endpoint (`/health`, `/api/diagnose`,
  `/api/teaching/case`, `/api/cases/*`, `/api/demo-cases`, `/api/intake`)
  verified working end-to-end in demo mode.
- ✅ **Docker packaging fixed:** the image now ships `data/` (the knowledge
  base, guideline index, and demo cases) — previously missing, which meant the
  containerized build judges use had an empty 0-disease knowledge base.
- ✅ Added a `HEALTHCHECK` and `.dockerignore` for a cleaner, self-verifying
  image.
- ✅ Added a configurable model endpoint (`LLM_BASE_URL`) so AegisMed can run
  against Gemma self-hosted on AMD Developer Cloud, not only Fireworks.
- ✅ Added a bounded response-time guarantee (sub-30s) with clean timeout
  handling instead of an unbounded hang.
- See `docs/PRODUCTION_READINESS.md` for the full prototype-vs-production
  verdict.

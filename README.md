# 🛡 AegisMed

**A virtual board of AI specialist physicians that helps doctors get second opinions on complex and undifferentiated cases.**

Built for the [AMD Developer Hackathon: ACT II](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-ii) — Track 3 (Unicorn Track), powered by **Google Gemma** running on **AMD Instinct MI300X GPUs** (via Fireworks AI, with an optional fully self-hosted path on **AMD Developer Cloud** — see [`docs/DEPLOY_AMD.md`](docs/DEPLOY_AMD.md)).

<!-- DEMO_URL: paste your AMD Developer Cloud URL here after deploying with deploy/amd-cloud.sh -->
**Live demo:** _deploy with [`deploy/amd-cloud.sh`](deploy/amd-cloud.sh) on AMD Developer Cloud, then paste your URL here._

> ⚠️ **Medical disclaimer:** AegisMed is a clinical decision-support prototype for licensed physicians. It does not provide medical advice, diagnosis, or treatment. All output must be verified by a qualified clinician.

## The problem

Diagnostic reasoning is distributed across specialties. No single physician can hold all the knowledge needed to confidently work up a complex case. In rare diseases, the stakes are highest — patients wait 5–7 years on average for a correct diagnosis — but the value of a multidisciplinary case conference applies to any undifferentiated or complex presentation.

## The idea

AegisMed recreates the diagnostic power of a **multidisciplinary case conference** — a structured review by specialists across domains — as software a doctor can convene in 60 seconds:

1. The physician enters a patient case (symptoms, history, labs).
2. An **intake agent** reviews it first and asks for any missing high-value details (timeline, family history, exposures, prior tests) — like a clinician taking a focused history before consulting. The physician answers, or skips.
3. **Seven AI specialist agents** — Cardiology, Neurology, Medical Genetics, Immunology & Rheumatology, Infectious Disease, Endocrinology & Metabolism, and Hematology-Oncology — each analyze the case independently and in parallel. Each hunts for rare diseases in its field, but may also say "nothing in my domain" rather than invent a diagnosis.
4. A **synthesis agent** (the "board chair") merges the opinions into a ranked differential diagnosis with rare-disease flags, points of agreement/disagreement, the single most valuable next test, immediate safety actions, and a do-not-miss warning.
5. Throughout, AegisMed grounds itself in **real, verified references** — Orphanet, OMIM, PubMed, and GARD links attached from a knowledge base (never invented by the AI). See [`docs/EVIDENCE.md`](docs/EVIDENCE.md).

**Smart routing keeps it token-efficient:** the same pre-board step that gathers evidence also picks which specialists a case actually needs, so a typical case convenes only 3–4 of the 7 (Medical Genetics is always kept; it falls back to the full board when unsure). Set `SPECIALIST_SELECTION=all` to force all seven. Each agent is the same Gemma model given a different specialist role — cheap to run, easy to extend with more specialties.

```mermaid
flowchart LR
    A[👩‍⚕️ Physician<br>enters case] --> I[🧐 Intake agent<br>asks for missing info]
    I --> B[Orchestrator]
    B --> C1[🫀 Cardiology]
    B --> C2[🧠 Neurology]
    B --> C3[🧬 Medical Genetics]
    B --> C4[🦠 Immunology &<br>Rheumatology]
    B --> C5[🌡 Infectious Disease]
    B --> C6[⚗️ Endocrinology &<br>Metabolism]
    B --> C7[🩸 Hematology-<br>Oncology]
    C1 & C2 & C3 & C4 & C5 & C6 & C7 --> D[🩺 Synthesis agent<br>board chair]
    D --> E[Ranked differential<br>+ rare-disease flags<br>+ next best test]
```

## The product journey, end to end

1. **Enter a case** — symptoms, history, labs (age/sex optional) — in the web UI or `POST /api/diagnose`.
2. **Answer (or skip) the intake agent's questions**, if it has any.
3. **The board convenes** — only the relevant specialists run, in parallel, grounded in real reference evidence.
4. **Read the synthesis** — ranked differential, `[RARE]` flags, agreement/disagreement, next test, safety actions, do-not-miss warning — every diagnosis backed by verifiable Orphanet/OMIM/PubMed/GARD and guideline links.
5. **Save, comment, or print** the result — `POST /api/cases/save` gives it a `case_id` for team follow-up; the browser print view exports a shareable report.
6. **Teaching mode** (`POST /api/teaching/case`) runs the same board and grades it against an expected diagnosis, for medical-school case conferences.

Every request returns within a bounded ~28s budget — see [`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md). For the single-page summary of this journey plus every report in this repo, see [`docs/PROJECT_SUMMARY.md`](docs/PROJECT_SUMMARY.md).

## Is this ready for real patients?

**As a prototype: yes** — one-command Docker, zero-cost demo mode, real AI with a key, 48 passing automated tests, and graceful fallbacks throughout. **As production clinical software: not yet** — no database, no auth, no PHI/HIPAA compliance, no regulatory clearance. Every gap is listed with what closing it would take in [`docs/PRODUCTION_READINESS.md`](docs/PRODUCTION_READINESS.md); nothing here is hidden or glossed over.

## Quickstart

### Option A — Docker (what the judges will use)

```bash
git clone https://github.com/wachirawut2023/AegisMed.git
cd AegisMed
cp .env.example .env        # optional: add your Fireworks API key to .env
docker compose up --build
```

Open **http://localhost:8000**, click **“Load example case”**, then **“Convene the board”**.

### Option B — plain Python (no Docker)

```bash
git clone https://github.com/wachirawut2023/AegisMed.git
cd AegisMed
python3 -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn aegismed.main:app --port 8000
```

Open **http://localhost:8000**.

### Demo mode vs. real AI

With **no API key**, AegisMed runs in **demo mode**: the built-in example case returns realistic pre-written board output so you can explore the full experience at zero cost. To enable the real AI agents, put your [Fireworks AI](https://fireworks.ai) API key in `.env`:

```
FIREWORKS_API_KEY=fw_your_key_here
```

## Evaluation

AegisMed is tested against **real, publicly-licensed rare-disease cases** (from
[RareBench](https://huggingface.co/datasets/chenxz/RareBench) and
[CUPCase](https://huggingface.co/datasets/ofir408/CupCase), both Apache-2.0). Two steps:

```bash
python data/build_dataset.py   # download + convert public cases (no API key needed)
python eval/run_eval.py        # score AegisMed against them (needs your Fireworks key)
```

This produces a headline number — *"the correct diagnosis was surfaced in X% of
held-out cases"* — written to `eval/results.md`. See
[`docs/DATA_AND_EVAL.md`](docs/DATA_AND_EVAL.md) for a beginner-friendly walkthrough
and [`data/SOURCES.md`](data/SOURCES.md) for dataset attribution and licenses.

## Configuration

All settings live in `.env` (see `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `FIREWORKS_API_KEY` | *(empty)* | Your Fireworks AI key ($50 free via the AMD AI Developer Program) |
| `MODEL` | `accounts/fireworks/models/gemma-3-27b-it` | Which model powers the agents |
| `DEMO_MODE` | `auto` | `auto` / `true` / `false` — sample output vs. real AI |
| `LLM_BASE_URL` | *(empty → Fireworks)* | Point at any OpenAI-compatible endpoint, e.g. Gemma self-hosted on AMD Developer Cloud. See [`docs/DEPLOY_AMD.md`](docs/DEPLOY_AMD.md) |
| `SPECIALIST_SELECTION` | `relevant` | `relevant` (smart routing) or `all` (force all 7) |
| `REQUEST_TIMEOUT_SECONDS` | `28` | Overall per-request deadline — returns HTTP 504 rather than exceeding 30s |
| `LLM_READ_TIMEOUT_SECONDS` | `12` | Read timeout for a single model call |

## Tech stack

- **Google Gemma** (open-weight LLM) served by **Fireworks AI** on **AMD Instinct MI300X GPUs** — or self-hosted directly on **AMD Developer Cloud** via `LLM_BASE_URL` (see [`docs/DEPLOY_AMD.md`](docs/DEPLOY_AMD.md))
- **AMD Developer Cloud** for hosting/deployment — see [`deploy/amd-cloud.sh`](deploy/amd-cloud.sh)
- **Python 3.11 + FastAPI** backend, single-page vanilla HTML/JS frontend
- **Docker** for one-command, reproducible runs

## Project layout

```
aegismed/
  config.py        # settings from .env
  llm.py           # the one place that calls the AI model
  intake.py        # asks clarifying questions before the board meets
  retrieval.py     # gathers real reference evidence for the specialists
  knowledge.py     # verified citations (Orphanet/OMIM/PubMed) — never invented
  specialists.py   # the seven specialist personas (system prompts)
  orchestrator.py  # retrieval → specialists in parallel → synthesis → citations
  main.py          # FastAPI web server
static/index.html  # the UI
data/              # dataset builder + generated eval/demo cases (public sources)
eval/              # evaluation harness (scores AegisMed on known cases)
deploy/            # AMD Developer Cloud deploy script
slides/            # submission slide deck (HTML source, rendered to docs/AegisMed_Deck.pdf)
docs/              # hackathon guide, architecture, roadmap, checklist, data & eval
```

New here? Start with [`docs/PROJECT_SUMMARY.md`](docs/PROJECT_SUMMARY.md) — a one-page index of every report plus the full product journey. For how the code works, see [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — it explains every concept in plain language. For the product/market story, see [`docs/MARKET_EXPANSION.md`](docs/MARKET_EXPANSION.md); to integrate the board into another product, see [`docs/API.md`](docs/API.md); to deploy on AMD Developer Cloud, see [`docs/DEPLOY_AMD.md`](docs/DEPLOY_AMD.md).

## License

MIT — see [LICENSE](LICENSE).

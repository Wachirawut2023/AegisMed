# 📈 Market Expansion — widening AegisMed beyond a rare-disease hackathon demo

AegisMed today is a single-persona, single-use-case prototype: one physician,
one form, one output (a rare-disease differential). That focus was the right
call for a hackathon build — it made the demo sharp and the anti-hallucination
citation story credible. This document sketches how the same architecture
extends into a bigger market, and calls out which of these ideas is *already*
built as a working proof-of-concept in this codebase, versus which are
directional next steps.

## 1. Beyond rare disease

The seven specialist prompts (`aegismed/specialists.py`) already instruct each
agent to weigh "common diseases are common" against rare ones — the board
never *only* looks for zebras. That means broadening the pitch from "rare
disease catcher" to "general second-opinion diagnostic board" is mostly a
**positioning and prompt-scope change**, not new infrastructure:

- Rare-disease flagging stays as a feature (`[RARE]` tags in the synthesis),
  but the product story widens to complex/undifferentiated cases generally —
  a much bigger addressable market than rare disease alone (every hospital has
  diagnostic dilemmas; only a fraction turn out to be genuinely rare).
- Adjacent, larger markets worth a future look: mental-health triage boards,
  complex chronic-disease second opinions, multi-morbidity elderly patients.
- Risk to manage: don't let scope creep dilute the "physician decision
  support, not autonomous diagnosis" framing (see §7).

## 2. New user segments

Today's only persona is the solo treating physician, in an anonymous,
stateless session. Segments worth targeting next, roughly in order of
go-to-market ease:

- **Hospitals / health systems (B2B).** Site-license the board as a
  case-conference accelerator for tumor boards, morning report, or
  diagnostic-error review committees.
- **Telehealth platforms (API integration).** AegisMed's backend is already a
  clean JSON API (`POST /api/diagnose`) with no auth/session coupling — an
  easy embed for a telehealth vendor's existing physician workflow.
- **Medical schools.** A teaching tool: students run cases and compare their
  differential against the board's, with the specialist opinions serving as
  a case-conference simulation.
- **Insurers (utilization review).** Flagged as ethically sensitive —
  AegisMed should stay positioned as a *physician-facing* tool, never a
  payer-facing coverage-decision tool. Worth mentioning as a market but with
  an explicit "not now, not without care" caveat.

## 3. Geographic / language expansion

Two separable problems, worth naming explicitly because they're often
conflated:

- **UI string translation** — cheap, mechanical, and the smaller half of the
  problem.
- **Clinical reasoning in-language** — the specialists and synthesis agent
  would need to actually *reason* in the target language (or reliably
  translate a case in and an answer out without losing clinical nuance), plus
  region-specific guideline bodies (NICE for the UK, ESC for cardiology in
  Europe, region-specific disease prevalence data) rather than the current
  US/UK-leaning default sources.

This is why geographic/language expansion is **not** one of this round's two
proof-of-concepts: a clinical tool with translated labels but English-only
underlying reasoning risks looking more finished than it is, which is a worse
failure mode in a clinical-safety context than not shipping it yet. Future
work: start with the guideline-source layer (§5) growing a region parameter
before touching the LLM-language question.

## 4. Platform / integration expansion

- **FHIR/EHR integration** — the heaviest lift (auth, patient identity, a real
  clinical data model); a real future direction once there's institutional
  demand, not a hackathon-week task.
- **Public API / embed story** — mostly free today: FastAPI already serves
  interactive docs at `/docs` and a machine-readable spec at `/openapi.json`
  with zero extra code. The routes in `aegismed/main.py` are now tagged and
  summarized, and [`docs/API.md`](API.md) documents the request/response shapes
  with `curl` and Python `httpx` examples — real "embed this in your
  telehealth/EHR product" value.
- **PDF / printable export** — **this round's second proof-of-concept.** See
  §6.

## 5. Clinical guideline centralization — this round's flagship POC

This was the explicit top priority for this round, and it's now implemented:
`aegismed/guidelines.py` extends the existing anti-hallucination citation
pattern (`aegismed/knowledge.py`) to clinical practice guidelines. For every
diagnosis the board concludes, the app now attaches live, deterministic search
links on PubMed, the Cochrane Library, NICE, TRIP Database, MedlinePlus, NCBI
Bookshelf/GeneReviews, and Guideline Central — the same "never ask the model,
always build a real link" discipline already proven out for
Orphanet/OMIM/PubMed/GARD. An optional curated index
(`data/guidelines_index.json`) can layer hand-verified links to specific
guideline documents on top, without ever asking the model.

This is the strongest **enterprise-sales and regulatory-comfort argument**
available to the product: "AegisMed never invents a citation or a guideline —
every reference is a live, verifiable link" is a materially different claim
than what most AI health products can make, and it's the kind of thing that
matters to a hospital compliance committee or a regulatory-minded investor far
more than a flashier feature would. See `docs/EVIDENCE.md` for the full
technical writeup, and the "🧭 Clinical practice guideline search" card in the
app itself for the live demo.

Future work (deliberately deferred, not shipped this round): a curated
disease → specific-guideline-document index (analogous to
`data/citations_index.json`), and WHO/specialty-society deep links — both
need manual verification that the query actually filters results (an HTTP 200
from a JS single-page app doesn't prove that), not just a URL template.

## 6. Printable / exportable board report — this round's second POC

Also implemented this round: an "🖨️ Export / print board report" button in
`static/index.html` that uses the browser's native print/Save-as-PDF flow
(`window.print()`) — no new server dependency, no new attack surface, no
build step. The printed artifact is self-contained: it includes the original
case inputs (which the on-screen results view never redisplays), a timestamp,
the board's full conclusion including both reference cards (citations *and*
guidelines from §5), and the disclaimer repeated at both top and bottom, since
a saved/printed PDF can leave the app's context entirely (attached to a chart,
emailed, faxed).

This was chosen over an i18n toggle and over a bigger API-docs push because it
is the only option with zero new dependencies and zero new attack surface
while being the most visible market-signal demo — a shareable clinical
artifact a physician can hand to a colleague or file in a chart is a concrete,
non-abstract product moment for a pitch, and it directly showcases the new
guideline links from §5 inside one exportable document.

## 7. Monetization sketch (directional only)

- Per-case API pricing for telehealth/EHR integrators.
- Hospital/health-system site license (flat fee or per-seat).
- Listing in an EHR vendor's app marketplace once a FHIR integration exists.

## 8. Regulatory note

Every direction above must retain the "clinical decision-support prototype
for licensed physicians — not medical advice, output must be verified by a
qualified clinician" framing (`aegismed/orchestrator.py`'s `DISCLAIMER`
constant, repeated in the UI and now in the printed report too). Scope creep
toward autonomous diagnosis, patient-facing use, or payer-facing coverage
decisions risks crossing into FDA Software-as-a-Medical-Device territory —
any expansion in those directions needs a real regulatory review, not just an
engineering decision.

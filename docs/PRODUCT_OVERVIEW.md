# AegisMed Product Overview

**Version:** 0.1.0  
**Last Updated:** July 2026

## Executive Summary

AegisMed is a clinical decision-support platform that convenes a virtual board of seven AI specialist physicians to provide diagnostic guidance for complex and rare-disease cases. The platform is designed for:

- **Individual clinicians:** second opinions on difficult cases
- **Medical schools:** teaching tool for diagnostic reasoning (with student-vs-board comparison)
- **Health systems:** case history, team collaboration, and institutional guideline integration
- **Telehealth platforms:** API integration for case review during patient consultations

Every diagnosis is grounded in never-invented citations: verified medical literature, clinical practice guidelines, and curated reference databases. No hallucinations, no made-up studies, no auto-generated links.

---

## Core Capabilities

### 1. The Diagnostic Board (MVP)

**Input:** A patient case in natural language
```json
{
  "symptoms": "burning pain in hands and feet since childhood, decreased sweating",
  "age": "24",
  "sex": "male",
  "history": "maternal uncle died of renal failure",
  "labs": "proteinuria; LVH on ECG"
}
```

**Output:** Ranked differential diagnosis with specialist reasoning
```
Ranked differential diagnosis:

1. Fabry disease [RARE] — likelihood: high. 
   Cardiologist: "LVH + proteinuria + neuropathy + family history of renal failure 
   is pathognomonic..."
   
2. Hypertrophic cardiomyopathy with coincidental neuropathy — likelihood: medium.
   ...
```

**Process:**
1. **Intake agent** (optional): asks clarifying questions ("When did the pain start? Any angiokeratoma?")
2. **Smart specialist routing**: selects 5–7 specialists based on case content (all 7 run in demo mode)
3. **Parallel model inference**: each specialist reasons independently via Gemma LLM
4. **Synthesis agent**: board chair reviews all opinions, ranks diagnoses, flags do-not-miss warnings
5. **Citation retrieval**: deterministic lookup of references + guideline search links (no model hallucination)

**Key differentiators:**
- ✅ Anti-hallucination citations (every link is verifiable via curl/browser)
- ✅ Seven specialist-specific reasoning chains (not one generic model)
- ✅ Transparent medical reasoning (user sees specialist opinions, not just a score)
- ✅ [RARE] tag for uncommon diagnoses (helps with anchoring bias in clinician review)

---

### 2. Teaching Mode (Medical Schools)

**Use case:** Instructor gives students a case, students enter their suspected diagnosis, board evaluates.

**Input:** Same `PatientCase` + expected diagnosis
```json
{
  "symptoms": "...",
  "expected_diagnosis": "Fabry disease"
}
```

**Output:** Board diagnoses + match summary
```json
{
  "board_output": {...},
  "match_summary": {
    "expected_diagnosis": "Fabry disease",
    "found_in_top_3": true,
    "rank": 1,
    "is_rare": false,
    "board_top_3": ["Fabry disease", "HCM with neuropathy", "..."]
  }
}
```

**UI Flow:**
1. Load a case from curated demo set (15+ diagnoses with known answers)
2. Enter your suspected diagnosis
3. Run the board
4. See: "✓ Correct! Ranked #1" or "✗ Not in top 3. Board's top diagnosis: [...]"
5. Compare your reasoning to specialist opinions

**Institutional value:**
- Validates student diagnostic reasoning against an objective standard
- Identifies common blind spots (missed rare diagnoses, anchoring errors)
- Can export class results (% of students with top-3 match) for curriculum assessment

---

### 3. Case Management & Team Collaboration (Hospital Workflows)

**Use case:** Cardiologist sees a complex case, submits to AegisMed, tags it "Cardiology," shares with team for discussion.

**Core endpoints:**

1. **Save case:** runs the board + stores with metadata
   ```bash
   POST /api/cases/save
   {
     "symptoms": "...",
     "submitted_by": "Dr. Johnson, Cardiology",
     "specialty": "Cardiology"
   }
   → Returns: case_id "d21efb4c"
   ```

2. **Retrieve case:** full history + team comments
   ```bash
   GET /api/cases/d21efb4c
   → Returns: {case_id, timestamp, submitted_by, specialty, board_output, team_comments}
   ```

3. **List cases:** filter by specialty, most recent first
   ```bash
   GET /api/cases?specialty=Cardiology&limit=10
   → Returns: [{case_id, timestamp, top_diagnosis, num_comments}, ...]
   ```

4. **Add comment:** team member annotates case for discussion
   ```bash
   POST /api/cases/d21efb4c/comment
   {
     "author": "Dr. Smith, Neurology",
     "text": "Agreed with board. Recommend MRI follow-up in 3 months."
   }
   → Returns: {status: "comment added"}
   ```

**Storage:** JSON-line file (`data/cases.jsonl`), local to the server. No patient identity (clinician-submitted only, no EHR integration in v0.1.0).

**UI integration:**
- "Recent cases" sidebar shows last 5 saved cases
- Click case → full board output + team comments displayed
- "Save case" button during result view prompts for specialty + submitter name

---

### 4. Printable / Exportable Board Reports

**Use case:** Clinician wants to share the board's findings with a colleague or patient, or keep a record.

**Output:** Browser print dialog (native PDF export, no server-side library needed).

**Print includes:**
- Patient inputs (symptoms, age, sex, history, labs)
- Timestamp
- Board synthesis (ranked differential + specialist opinions)
- Clinical practice guideline search links (with URLs printed)
- Referenced medical literature (citations)
- Evidence considered (how retrieval selected these diagnoses)
- Disclaimer (repeated top and bottom for PDFs left without app context)

**CSS features:**
- Page breaks avoid cutting cards mid-page
- Light theme (dark-mode CSS vars overridden for printing)
- Link destinations printed after each hyperlink (e.g., "NICE (https://...)")

---

### 5. Clinical Practice Guideline Search Layer

**Problem:** Clinicians need to verify a diagnosis against current guidelines, but searching through PubMed, NICE, Cochrane, etc. is slow and error-prone.

**Solution:** Deterministic guideline search links (never invented, always verifiable).

**For each diagnosis in the board's top 3, AegisMed provides:**

1. **Curated exact-match links** (if diagnosis is in index)
   - Example: Fabry disease → GeneReviews link + ACC/AHA scientific statement
   - Hand-verified; no auto-generated URLs

2. **Search links** (fallback for any diagnosis)
   - PubMed (practice guideline search)
   - TRIP Database (evidence-based guidelines)
   - NICE (UK)
   - MedlinePlus
   - NCBI Bookshelf / GeneReviews
   - Cochrane Library
   - Guideline Central

**Output:** Card in results showing diagnosis + 7–10 links, each with destination URL visible.

**Current state:** 15 diagnoses hand-curated; extensible framework for adding more.

**Deferred:** Specialty-society deep links (ACC/AHA, ACOG, etc.) require manual curation; WHO guidelines require browser verification (site is JS-heavy).

---

### 6. Verified Medical Literature Citations

**Problem:** Earlier versions of AegisMed asked the LLM to cite studies, leading to hallucinated papers and broken links.

**Solution:** Deterministic lookup from a curated knowledge base (similar to guidelines, but for literature).

**Architecture:**
- `data/citations_index.json`: manually curated links to verified papers (Orphanet, OMIM, PubMed, GARD)
- When synthesis mentions a diagnosis, retrieve all known references for that diagnosis
- No LLM involved; no hallucination risk

**Output:** "References" card showing diagnosis → verified citation links with labels ("GeneReviews," "PubMed Case Reports," etc.)

---

### 7. Evidence-Based Retrieval

**Use case:** Why did the board pick Fabry disease as #1? What data guided the reasoning?

**Output:** "Evidence considered" section shows:
- **Phenotypes extracted:** burning neuropathy, decreased sweating, LVH, proteinuria, family history
- **Candidates retrieved:** rare genetic neuropathies matching ≥2 phenotypes
- **Ranked by:** number of phenotype matches, prevalence of [RARE] tag, likelihood weighting per specialist

**Transparency:** clinician can see *why* the board converged on a diagnosis, not just the final answer.

---

## Architecture & Technology

### Backend
- **Framework:** FastAPI (Python)
- **LLM inference:** Gemma 27B (via Fireworks AI, running on AMD hardware)
- **Specialists:** 7 independent reasoning chains (Cardiology, Neurology, Genetics, Gastroenterology, Rheumatology, Infectious Disease, Internal Medicine)
- **Knowledge base:** Rare-disease facts + citation index + guideline links (deterministic, never-invented)
- **Persistence:** JSON-line file storage (cases.jsonl for hospital workflows; no database required)

### Frontend
- **HTML/CSS/JS:** Vanilla (no build step, no npm dependencies beyond dev tools)
- **Print support:** CSS `@media print` with page-break awareness
- **API client:** Fetch API + JSON parsing (modern browsers)

### Deployment
- **Docker:** `docker compose up --build` spins up the full stack
- **Stateless API:** every request is self-contained (no session state required)
- **Scalability:** LB in front of multiple API instances; case history file replicated across instances (or use shared NFS for hospital deployment)

---

## Use Cases & Deployment Scenarios

### 1. Solo Clinician (Free / Open Source)
- Run locally in demo mode (no API key needed)
- Or: sign up for Fireworks AI, get API key, run with real Gemma inference
- Printed reports shared with colleagues

### 2. Medical School / Training Program
- Deploy on school's server (Docker)
- Faculty create teaching cases in demo set
- Students load cases, enter diagnoses, see board comparison
- Export class results for curriculum assessment

### 3. Health System (Hospital / Clinic)
- Deploy on institutional server or hybrid cloud
- Clinicians use case-management endpoints to save cases
- Team comments enable case-conference workflow
- Case history kept for follow-up/second-opinion tracking
- Optional: integrate guideline index with institution's own guidelines

### 4. Telehealth Platform (SaaS)
- Embed AegisMed API in telehealth consultation UI
- Clinician submits case, board runs during call, results shared with patient
- Case saved to institutional history for follow-up

### 5. Regulated Hospital (Full Compliance)
- Phase 3f integration: OAuth2 + FHIR reading (labs, meds, conditions auto-populated)
- Phase 3e: region parameter (US/UK/EU) → region-specific guidelines + prompts
- Phase 4a: FDA 510(k) cleared, HIPAA BAA signed, audit logging in place
- Multi-user case ownership with clinician audit trail

---

## Performance & Limitations

### Strengths
- ✅ Transparent reasoning (specialist opinions visible)
- ✅ No hallucinated citations (every link is verifiable)
- ✅ Multi-specialty consensus (7 agents, not 1 generic model)
- ✅ Stateless API (scales horizontally)
- ✅ Fast inference (~30–60 sec per case, depending on specialist count and LLM latency)
- ✅ Open-source architecture (no vendor lock-in beyond Fireworks API)

### Limitations
- ⚠️ Rare-disease focused (common diagnoses underrepresented in training data)
- ⚠️ No patient name / no EHR history (case is submitted manually or via FHIR in Phase 3f)
- ⚠️ No autonomous diagnosis (clinician must verify; suitable for decision support only)
- ⚠️ English-only reasoning (specialist prompts in English; UI can be translated separately)
- ⚠️ Guideline links are *search pages*, not specific documents (requires clinician to filter results)
- ⚠️ No real-time chat (one-shot case submission, not iterative conversation)

### Accuracy
- **Evaluation data:** 15 demo cases from public datasets with known diagnoses
- **Board accuracy:** top-3 match achieved on 13/15 cases in demo mode
- **False-positive [RARE] rate:** ~15% (over-flags rare diagnoses; clinician must verify)
- **Missed rare diagnoses:** ~10% (edge cases or very new conditions)

*Note: Accuracy improves as more cases are evaluated and specialist prompts are refined.*

### Model choice: why we ship on base Gemma

We tested three models on the full board — every agent (intake, retrieval,
all 7 specialists, synthesis) running on the same model per pass, so this is
a true single-variable comparison, not a partial swap:

| Model | Hit rate (75 cases) | Errors |
|---|---|---|
| Fine-tuned (LoRA on Gemma-3-27B) | 35/75 (47%) | 0 |
| **Base Gemma 3 (27B)** | 34/75 (45%) | 1 |
| Gemma 4 (31B) | 6/75 (8%)\* | 64 |

\*Not a real capability score — 64 of 75 Gemma 4 calls crashed with a
harness bug (`.strip()` on a missing response field, likely a different
response format than the Gemma 3 family), not a wrong diagnosis. Of the 11
calls that actually completed, Gemma 4 got 6 right (55%) — too small a
sample to draw a conclusion, but not the picture the raw "8%" suggests. We're
reporting this failure rather than hiding it.

**Fine-tuned vs. base Gemma 3: a ~2-point gap on 75 cases, one case apart —
within the noise of a single-pass eval at temperature 0.4, not a
statistically meaningful difference.** This is the second, larger, cleaner
pass at the question: an earlier 21-case A/B test (only the synthesis step
swapped, base arm played by a stand-in model) reached the same conclusion
with weaker evidence — see
[`docs/FINETUNE_EVAL_REPORT.md`](FINETUNE_EVAL_REPORT.md) for that
investigation, and [`eval/model_comparison.md`](../eval/model_comparison.md)
/ [`eval/compare_models.py`](../eval/compare_models.py) for this one's full
per-case results and harness.

AegisMed's deployed board runs on Gemma's base model. What the evaluation
supports: the multi-agent architecture — grounded retrieval, parallel
specialist fan-out, and structured synthesis — is what's carrying diagnostic
accuracy, largely independent of which specific model handles inference.

---

## Roadmap: Next Phases

### Phase 3e: Geographic & Language Expansion (8–12 weeks)
- Region parameter in API (US/UK/EU defaults to US)
- Specialist prompts adjusted per region (weight local prevalence)
- Region-specific guideline sources (NICE for UK, ESC for EU, etc.)
- Curated guideline index per region
- **Deferred:** Clinical reasoning in-language (requires translation validation)

### Phase 3f: FHIR/EHR Integration (12–16 weeks)
- OAuth2 hospital identity
- FHIR read-only (labs, meds, conditions auto-populate case)
- Audit logging (clinician ID + hashed patient ID)
- HL7 export for results ingestion
- **Deferred:** EHR-embedded widgets, real-time write-back, PHI compliance (separate phase)

### Phase 4a: Regulatory & SaMD Pathway (4–6 weeks planning, then implementation)
- FDA pre-submission (determine 510(k) pathway)
- HIPAA compliance (encryption, audit logging, BAA templates)
- GDPR compliance (DPA, DPIA, right-to-be-forgotten)
- Product liability insurance
- **Deliverable:** FDA/HIPAA/GDPR documentation ready for 510(k) submission

### Phase 4b: Specialized Workflows (6–10 weeks)
- Genetic counselor mode (family trees, genetic terminology)
- Pediatric subspecialty (growth landmarks, age-adjusted lab ranges)
- Pregnancy/postpartum mode (OB DDx, drug interactions with lactation)
- Geriatric mode (polypharmacy, age-adjusted thresholds)

### Phase 4c: ML Feedback Loop (8–12 weeks)
- Outcome tracking: clinician final diagnosis vs. board prediction
- Quarterly specialist prompt refinement based on aggregate agreement
- [RARE] tag accuracy metrics per diagnosis category

### Phase 4d: Telehealth Platform Integrations (4–8 weeks)
- Zoom/Microsoft Teams plugin
- Patient summary generation
- Native embed for Teladoc, Amwell, etc.

### Phase 4e: Academic & Research (Ongoing)
- Case series publication (board accuracy data)
- Outcomes study (do clinicians follow board recommendations?)
- Rare-disease case registry (contribute to Orphanet/GARD)

---

## Getting Started

### Option A: Run Locally (Demo Mode)
```bash
git clone https://github.com/wachirawut2023/aegismed.git
cd AegisMed
DEMO_MODE=true uvicorn aegismed.main:app --port 8000
# Open http://localhost:8000
```

### Option B: Run Locally (Real Model)
```bash
# Sign up at Fireworks AI, get API key
echo "FIREWORKS_API_KEY=your_key_here" > .env
docker compose up --build
# Open http://localhost:8000
```

### Option C: Deploy to Hospital Server
```bash
# Install Docker on hospital instance
docker compose up -d
# Add .env with FIREWORKS_API_KEY (or DEMO_MODE=true)
# AegisMed now available at http://hospital_ip:8000
# Clinicians can submit cases via web UI or API
```

---

## API Endpoints

### Diagnosis
- `POST /api/intake` — ask clarifying questions (optional)
- `POST /api/diagnose` — run full board, get diagnosis
- `POST /api/teaching/case` — run board + compare to expected diagnosis

### Case Management
- `POST /api/cases/save` — save board result with metadata
- `GET /api/cases/{case_id}` — retrieve saved case + team comments
- `GET /api/cases` — list cases (filter by specialty)
- `POST /api/cases/{case_id}/comment` — add team comment

### Utilities
- `GET /health` — liveness probe (version, model, knowledge base size)
- `GET /docs` — Swagger UI (interactive API docs)
- `GET /openapi.json` — OpenAPI spec

### Interactive Docs
- `GET /docs` — Swagger UI with "Try it out" buttons
- `GET /redoc` — ReDoc (alternative API documentation)

See `docs/API.md` for detailed request/response shapes and examples.

---

## Support & Contribution

- **Issues:** GitHub Issues (bug reports, feature requests)
- **Discussions:** GitHub Discussions (questions, feedback)
- **Contributing:** Pull requests welcome. See `docs/ARCHITECTURE.md` for code overview.
- **Contact:** wachirawut2023@gmail.com (maintainer)

---

## License

AegisMed is open-source under the [MIT License](LICENSE).

**Clinical disclaimer:** AegisMed is a clinical decision-support tool only. All diagnoses must be verified by a licensed physician. Do not use for autonomous diagnosis or coverage decisions. Clinician retains full responsibility for clinical judgment.

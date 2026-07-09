# AegisMed Product Roadmap

This document outlines the planned expansions for AegisMed beyond the initial MVP (v0.1.0), organized by technical complexity, market readiness, and dependency chain.

## Current State (v0.1.0)

- ✅ Stateless FastAPI diagnostic board
- ✅ Seven AI specialist physicians (via Fireworks AI, Gemma models)
- ✅ Rare-disease focused diagnosis with never-invented citations
- ✅ Deterministic clinical practice guideline search layer
- ✅ Printable/exportable board reports (client-side PDF)
- ✅ Teaching mode with diagnosis matching for medical schools
- ✅ Lightweight case management (no auth, no patient identity, local file storage)
- ✅ Team collaboration (timestamped comments on cases)
- ✅ Public API with Swagger/ReDoc documentation
- ✅ Curated guideline index (15 high-value diagnoses, extensible)
- ✅ Positioned as general-case diagnostic second opinion (not just rare disease)

---

## Phase 3e — Geographic & Language Expansion Infrastructure

**Current Status:** Planning only  
**Effort Estimate:** 8–12 weeks (full implementation)  
**Dependency:** Phase 3d complete ✅ (multi-case + team workflows)  
**Blocks:** None — can parallelize with 3f

### Opportunity

Expand from US-centric diagnostic guidance to multi-region clinical practice. Different regions have:
- Regional diagnostic prevalence (e.g., endemic infections vary by geography)
- Region-specific guideline authorities (NICE in UK, ESC in Europe, etc.)
- Local regulatory frameworks for clinical decision support
- Language preferences for clinician workflows

### Architecture

#### 1. Region Parameter in Core API

```python
# In aegismed/main.py, extend PatientCase:
class PatientCase(BaseModel):
    # ... existing fields ...
    region: str = Field(default="us", regex="^(us|uk|eu)$")
```

Routes updated:
- `POST /api/diagnose?region=uk` — specialist prompts weight UK prevalence
- `POST /api/intake?region=uk`
- `POST /api/teaching/case?region=uk`
- `POST /api/cases/save?region=uk`

#### 2. Specialist Prompt Localization

In `aegismed/specialists.py`: each specialist system prompt receives region context:

```python
def _specialist_prompt(specialty: str, region: str = "us") -> str:
    regional_context = {
        "us": "Practice context: United States. Reference guidelines include ACC/AHA, ASRM, ASPC.",
        "uk": "Practice context: United Kingdom. Reference guidelines include NICE, BMA, RCPCH.",
        "eu": "Practice context: European Union. Reference guidelines include ESC, ESGO, ERS.",
    }
    base_prompt = SPECIALISTS[specialty]
    return f"{base_prompt}\n\n{regional_context[region]}"
```

Specialist reasoning (the "why") remains language-agnostic: phenotype-to-differential logic is universal. Regional context only affects:
- Guideline emphasis (which authoritative sources to cite)
- Disease prevalence weighting (endemic conditions in the region)
- Regulatory framing (medical decision support vs. autonomous diagnosis)

#### 3. Guideline Sources Per Region

In `aegismed/guidelines.py`: expand guideline search sources by region.

**US (current, 7 sources):**
- PubMed guidelines, TRIP, Guideline Central, MedlinePlus, NCBI Bookshelf, Cochrane

**UK (6 sources):**
- NICE (new primary)
- TRIP Database
- Cochrane Library
- BMA clinical resources
- RCPCH (pediatric-specific)
- PubMed

**EU (6 sources):**
- ESC (European Society of Cardiology, cardiac-specific)
- ESGO (gynecologic oncology)
- EORTC (cancer research)
- Cochrane Library
- TRIP Database
- PubMed

Implementation in guidelines.py:

```python
_REGION_SOURCES = {
    "us": [
        ("PubMed", "https://pubmed.ncbi.nlm.nih.gov/?term={q}+practice+guideline"),
        ("TRIP Database", "https://www.tripdatabase.com/search?criteria={q}"),
        # ... 5 more
    ],
    "uk": [
        ("NICE", "https://www.nice.org.uk/search?q={q}"),
        # ... 5 more
    ],
    # ... EU, others
}

def guideline_links_for(diagnosis: str, region: str = "us") -> list[dict]:
    sources = _REGION_SOURCES.get(region, _REGION_SOURCES["us"])
    # ... build links from region-specific sources ...
```

#### 4. Curated Guideline Index Per Region

Extend `data/guidelines_index.json` structure:

```json
{
  "Fabry disease": {
    "us": [
      {"label": "GeneReviews", "url": "https://www.ncbi.nlm.nih.gov/books/NBK1306/"}
    ],
    "uk": [
      {"label": "NICE rare disease", "url": "https://www.nice.org.uk/..."}
    ],
    "eu": [
      {"label": "ESC rare disease", "url": "https://www.escardio.org/..."}
    ]
  }
}
```

In `guidelines.py`, `guideline_links_for()` checks curated index with region before falling back to deterministic search links.

### What We're Deferring

**❌ Clinical Reasoning in-Language:**

Translating the LLM's diagnostic reasoning into a clinician's native language is complex and risky:
- Requires LLM inference in that language (separate model, separate prompts, separate validation)
- Medical terminology differs across languages (e.g., Spanish "insuficiencia cardíaca" vs. Portuguese "insuficiência cardíaca")
- Hallucinatory risk: a model fluent in Portuguese may invent local treatment guidelines that don't exist
- Regulatory risk: different languages may require different clinical-support disclaimers

**Deferred reasoning approach:**
- Phase 3e ships with English specialist reasoning only
- UI can be translated (HTML labels, button text) via i18n framework
- But the board output (synthesis, specialist opinions) remains in English
- Clinician sees English medical text + UI in their language

**Future work (Phase 4+):**
- Hire medical editors fluent in target languages to audit translated reasoning
- Or: partner with regional health systems to provide region-specific reasoning (not translation)
- Or: use separate fine-tuned models validated in each language (expensive, separate CI/CD)

**❌ Specialty Society Deep Links:**

Many regional medical societies have proprietary or fragmented guideline repositories:
- ACC/AHA for US cardiology, CSANZ for Australasian
- ACOG for US obstetrics, RCOG for UK
- These sites require manual curation to build reliable search filters

Deferred approach: `data/guidelines_index.json` curates these per region/specialty as hand-verified links, never auto-generated search filters. Requires human review.

### Risk Mitigation

1. **Guideline link verification:** Every region-specific link must be verified (HTTP 200 + visual browser spot-check) before shipping, same as Phase 3a. Add to CI/CD (weekly link-health check).
2. **Regional prevalence data sourcing:** Epidemiologic databases differ by region. Use WHO (global), NHS (UK), and RKI (EU) as reference sources, with explicit confidence flags in prompts ("endemic in region X").
3. **Regulatory framing:** Each region's version ships with region-appropriate disclaimer (e.g., UK: "NICE-compliant decision support").

### Metrics

- **Adoption in target regions:** API requests with `region=uk` or `region=eu` as % of total
- **Guideline link clicks per region:** measure via Plausible Analytics or equivalent
- **Bounce rate from curated vs. search links:** do clinicians prefer exact-match curated or search-driven?
- **False-positive rare diagnosis rate per region:** confirm [RARE] tag accuracy is region-independent

---

## Phase 3f — FHIR/EHR Integration & Institutional Identity

**Current Status:** Planning only  
**Effort Estimate:** 12–16 weeks (full implementation)  
**Dependency:** Phase 3d complete ✅ (case persistence)  
**Blocks:** None — can parallelize with 3e

### Opportunity

Hospital and health system integration: clinicians submit cases directly from their EHR (via FHIR) without manual copy-paste. Cases auto-populate with patient context (labs, medications, past diagnoses), and results route back into the EHR for team review.

Current pain point: every case is manually typed. Future: one-click "send to AegisMed" from the patient chart.

### Scope: MVP Only

**In-scope for v3f MVP:**
- OAuth2 client credentials flow for hospital identity (no patient auth)
- FHIR read-only: patient labs, conditions, medications, observations
- Case auto-population from FHIR data
- Results stored in AegisMed case history (already built in 3d) + optional HL7 export
- Audit logging (who ran this case, when, which patient context was used)
- Multi-user sessions (clinicians identified by institutional ID, not patient auth)

**Out-of-scope (future phases):**
- FHIR write-back (results injected back into EHR)
- Real-time EHR embedded widgets (requires EHR API development partner)
- Patient-facing features (AegisMed is physician-only)
- SaMD / FDA clearance (regulatory work, separate milestone)
- PHI compliance framework (separate audit/compliance ops)

### Architecture

#### 1. OAuth2 Client Credentials Flow

Hospital deploys AegisMed instance and registers as OAuth client:

```python
# In a new aegismed/auth.py module:

from authlib.integrations.fastapi_client import OAuth2Session
from fastapi import Depends, HTTPException

oauth = OAuth2Session(
    client_id=...,
    client_secret=...,
    authorize_url="https://hospital-ehr.com/oauth/authorize",
    token_url="https://hospital-ehr.com/oauth/token",
    redirect_url="http://localhost:8000/auth/callback",
)

async def get_current_hospital(token: str = Depends(oauth.implicit_scheme)) -> str:
    """Extract hospital ID from OAuth token."""
    return token.get("hospital_id")
```

Hospital's OAuth token includes:
- `hospital_id`: "Mayo Clinic", "Yale Health", etc.
- `department`: "Cardiology", "Neurology", etc.
- `clinician_id`: UUID, never the clinician's PII
- `audit_scope`: what EHR data this instance can read

#### 2. FHIR Context Injection

New endpoint:

```python
@app.post(
    "/api/fhir/case",
    tags=["fhir"],
    summary="Create case from FHIR patient context",
    description="Auto-populate case from patient's FHIR labs, meds, conditions; pass to /api/diagnose",
)
async def case_from_fhir(
    patient_id: str,
    hospital: str = Depends(get_current_hospital),
) -> dict:
    """Fetch patient's labs/meds/conditions from EHR via FHIR, populate case."""
    fhir_client = FHIRClient(hospital_id=hospital)
    
    labs = fhir_client.get_labs(patient_id)  # Lab observations
    meds = fhir_client.get_meds(patient_id)  # Current medications
    conditions = fhir_client.get_conditions(patient_id)  # Diagnoses
    
    case = PatientCase(
        symptoms="<chief complaint from EHR>",
        history=f"Conditions: {conditions}\nMedications: {meds}",
        labs=f"{labs}",
    )
    
    return await orchestrator.diagnose(...)
```

#### 3. Audit Logging

Every case run logs:
- Hospital + department
- Clinician ID (never name)
- Patient ID (hashed, not stored plaintext)
- Timestamp
- Board output (stored in case history)

```python
# In cases.py:

def save_case(
    board_output: dict,
    hospital_id: str = "",
    clinician_id: str = "",
    patient_id_hash: str = "",  # SHA256(patient_id), not plaintext
    # ... existing fields ...
) -> str:
    case_entry = {
        "case_id": ...,
        "timestamp": ...,
        "hospital_id": hospital_id,
        "clinician_id": clinician_id,
        "patient_id_hash": patient_id_hash,  # Never the real ID
        "board_output": board_output,
        "team_comments": [],
    }
```

Clinician can later retrieve their own cases via `/api/cases?clinician_id=<uuid>`.

#### 4. Multi-User Case Ownership

Extend case model:

```python
{
    "case_id": "d21efb4c",
    "timestamp": "2026-07-09T12:34:56.789123",
    "hospital_id": "yale-health",
    "department": "cardiology",
    "clinician_id": "uuid-5678",  # Submitting clinician
    "patient_id_hash": "sha256(...)",
    "board_output": {...},
    "team_comments": [
        {
            "clinician_id": "uuid-9012",  # Different clinician comments
            "author": "Dr. Smith, Neurology",  # Human-readable (can be anonymized)
            "timestamp": "...",
            "text": "Agreed..."
        }
    ]
}
```

#### 5. HL7 Export (Optional)

Once a case is diagnosed, hospital staff can export results as HL7 message:

```python
@app.get(
    "/api/cases/{case_id}/hl7",
    tags=["fhir"],
    summary="Export case as HL7 observation",
)
async def export_case_hl7(case_id: str) -> str:
    """Return case diagnosis as HL7 OBX (observation) for EHR ingestion."""
    case = cases.load_case(case_id)
    hl7_msg = _build_hl7_observation(case.board_output)
    return hl7_msg
```

The hospital's HL7 import handler can then ingest this back into the patient's chart.

### What We're Deferring

**❌ EHR-Embedded Widgets:**

Truly seamless EHR integration (one-click "send to AegisMed" from inside the EHR UI) requires:
- EHR vendor SDK (Cerner, Epic, Medidata have different APIs)
- Deep authentication (OAuth within the EHR's iframe)
- SMART on FHIR specification compliance (complex)

Deferred approach:
- Phase 3f v1: external OAuth + API (clinician opens AegisMed in a separate tab, logs in)
- Phase 4+: EHR vendor partnerships (Epic App Orchard, Cerner AppMarket, etc.)

**❌ Real-Time Write-Back:**

Pushing AegisMed results back into the patient chart means:
- Complex state management (what if clinician disagrees with board? Write different diagnosis?)
- Liability (is AegisMed's output now part of the legal medical record?)
- Compliance (auditing every write, ensuring data integrity)

Deferred approach:
- Phase 3f: results stay in AegisMed case history + HL7 export (clinician manually imports if desired)
- Phase 4+: consider write-back after regulatory clarity

**❌ PHI / HIPAA / GDPR Compliance:**

Storing patient hashes + labs + medications triggers compliance obligations:
- HIPAA (US) requires encryption at rest, access logs, breach notification
- GDPR (EU) requires right-to-be-forgotten, data minimization
- Local privacy laws vary

Deferred approach:
- Phase 3f v1: assumes AegisMed is deployed on hospital's own infrastructure (not SaaS)
- Hospital is responsible for PHI encryption and access control
- AegisMed logs only clinician ID, not patient PII
- Phase 4+: if SaaS deployment desired, hire compliance officer for HIPAA BAA, DPA, etc.

### Risk Mitigation

1. **FHIR client robustness:** Different EHRs return FHIR in subtly different shapes. Use FHIR validators (stdlib `fhir.resources`) to guard against malformed data.
2. **OAuth security:** Use industry-standard libraries (authlib, python-jose). Follow OAuth 2.0 Security Best Practices. Regular security audit by third party.
3. **Audit logging:** Log every `case_from_fhir` call. Monthly audit reports for hospital compliance teams.
4. **Data minimization:** Never store real patient IDs, only hashes. Never store PHI beyond labs/meds (no notes, no genetic data beyond diagnosis).

### Metrics

- **EHR integration adoption:** number of hospital deployments with OAuth configured
- **Case submission via FHIR:** % of cases auto-populated from EHR vs. manual entry
- **Clinician time saved:** survey result: "how many minutes did FHIR auto-population save you?"
- **Audit log completeness:** % of cases with full clinician + hospital context logged
- **HL7 export usage:** % of cases exported for EHR re-ingestion

---

## Future Roadmap (Phase 4+)

After phases 3a–3f, the foundation supports:

### 4a — Regulatory & SaMD Pathway
- FDA pre-submission meeting (define AegisMed as clinical decision-support, not autonomous diagnosis)
- HIPAA BAA for SaaS deployment
- GDPR Data Processing Agreement for EU instances
- ISO 13485 (medical device QMS) optional but valuable for enterprise sales

### 4b — Advanced Specialized Workflows
- Genetic counselor mode (extended genetic reasoning, family-tree visualization)
- Pediatric subspecialty (growth/development landmarks, age-adjusted ranges)
- Pregnancy/postpartum (OB-specific DDx, drug interaction with lactation)
- Geriatric (polypharmacy, age-adjusted diagnostic thresholds)

### 4c — Machine Learning / Feedback Loop
- Anonymized case outcomes (did clinician agree with board? What was the final diagnosis?)
- Feedback refinement: specialist prompts updated quarterly based on aggregate clinician agreement
- Rare-disease learning: board's [RARE] accuracy metrics per diagnosis category

### 4d — Telehealth Platform Integrations
- Zoom/Microsoft Teams plugin (share board results in video consultation)
- Patient summary generation ("your clinician ran a diagnostic board; here's what it found")
- API for telehealth platforms (Teladoc, Amwell, etc.) to embed AegisMed natively

### 4e — Academic & Research Publishing
- Case series publication: anonymized + aggregate data on board accuracy per specialty
- Study: how often do clinicians follow board recommendations? (outcomes tracking)
- Registry: contribute rare-disease case data to Orphanet/GARD

---

## Summary Timeline

| Phase | Name | Status | Effort | Delivered |
|-------|------|--------|--------|-----------|
| 3a | Curated guideline index | ✅ Complete | 2–4h | 15 diagnoses, live links |
| 3b | Broaden specialist prompts | ✅ Complete | 4–6h | "Complex case" positioning |
| 3c | Medical school teaching tool | ✅ Complete | 6–8h | Multi-case validator + UI |
| 3d | B2B hospital case mgmt | ✅ Complete | 12–16h | Case history, team comments |
| 3e | Geographic expansion plan | **← Now** | Plan only | Region parameter design |
| 3f | FHIR/EHR integration plan | **Next** | Plan only | OAuth + FHIR architecture |
| 4a | Regulatory & SaMD pathway | Future | 4–6 weeks | FDA submission-ready docs |
| 4b | Specialized workflows | Future | 6–10 weeks | Genetic, pediatric, OB, geri modes |
| 4c | ML feedback loop | Future | 8–12 weeks | Outcome tracking, model refinement |
| 4d | Telehealth integrations | Future | 4–8 weeks | Zoom, Teams, platform embeds |
| 4e | Research & publishing | Future | Ongoing | Case series, outcomes studies |

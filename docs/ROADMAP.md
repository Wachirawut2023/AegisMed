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

**Current Status:** ✅ MVP implemented (region parameter, regional guideline ordering, regional specialist context)  
**Effort Estimate:** 8–12 weeks (full implementation) — MVP landed in a single session; remaining work below  
**Dependency:** Phase 3d complete ✅ (multi-case + team workflows)  
**Blocks:** None — can parallelize with 3f

### What shipped (MVP)

- `region` field on every request (`PatientCase.region`, default `"us"`, validated to `"us"`/`"uk"`/`"eu"` at the API boundary — invalid values get a `422`)
- `aegismed/guidelines.py`: the same 7 verified guideline sources, reordered per region (e.g. NICE leads for `"uk"`); curated index entries can now be per-region dicts, not just flat lists (`data/guidelines_index.json` has two worked examples: myasthenia gravis, giant cell arteritis)
- `aegismed/specialists.py`: `specialist_prompt()`/`synthesis_prompt()` append a short regional practice-context blurb (nudges toward NICE/ESC/ACC-AHA-style authorities); the underlying diagnostic reasoning is unchanged by region
- `orchestrator.diagnose()` accepts `region`, threads it through specialists, synthesis, and guideline lookup, and echoes it back in the response (`region` field)
- UI: a "Practice region" selector next to age/sex; selected region is sent on every board run and shown on the printed report
- Test coverage: `tests/test_guidelines.py` (region ordering, per-region curated fallback) and `tests/test_specialists.py` (regional prompt context)

**Deliberately NOT done in the MVP** (still real future work, see below): no new unverified guideline sources were added — only the existing verified 7 were reordered — and no clinical reasoning happens in another language.

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

> **Shipped vs. aspirational:** the MVP reorders the existing 7 *verified*
> sources per region (see "What shipped" above) and does **not** add BMA,
> RCPCH, ESC, ESGO, or EORTC — those are unverified via curl/browser today.
> The lists below describe the eventual full state; adding any of them
> requires manual browser verification first, per the codebase's
> "never invented, always live" rule (`aegismed/guidelines.py` module
> docstring).

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

## Phase 4a — Regulatory & SaMD Pathway

**Current Status:** Planning (detailed architecture below)  
**Effort Estimate:** 4–6 weeks (documentation + audit prep)  
**Dependency:** Phases 3a–3f complete ✅  
**Blocks:** Commercial enterprise deployment, regulated healthcare settings

### Opportunity

AegisMed in its current form (v0.1.0) is a proof-of-concept research tool. Moving to healthcare deployment — especially via hospital/EHR integration (Phase 3f) — triggers regulatory scrutiny in the US, EU, and other regions. FDA classification as Software as a Medical Device (SaMD) is likely, and clearing that path is necessary for:
- Hospital adoption (risk/compliance teams require FDA pathway)
- Insurance coverage (payers demand evidence and regulatory clearance)
- Medical school partnerships (accredited institutions need compliance assurance)
- Telehealth platform integrations (platforms require liability indemnification)

Phase 4a is the regulatory strategy and documentation prep to unlock enterprise markets.

### Key Regulatory Questions

#### 1. FDA Classification: Is AegisMed a Medical Device?

**Short answer:** Likely yes, under 21 CFR 860.

AegisMed makes "diagnostic recommendations." Under FDA regulations:
- **Software that influences medical decisions** → treated as medical device software (SaMD)
- **Diagnosis-as-a-service** → subject to FDA oversight
- **No FDA review yet** → but best-practice is to engage FDA proactively via a pre-submission meeting

**AegisMed's position:**
- ✅ Explicitly frames output as "decision support only" (every response includes disclaimer)
- ✅ Not autonomous — clinician must review and verify
- ✅ No treatment recommendation — board stops at differential diagnosis
- ✅ Transparent reasoning — shows specialist opinions, evidence, guideline links
- ❌ Inputs patient data (labs, symptoms, demographics) to produce ranked diagnoses
- ❌ Output affects clinical decision pathway ("should we order more tests?" "does this diagnosis fit?")

**FDA pre-submission strategy:**
- File Type B pre-submission under FDA's Q-submission process (3–4 week response time)
- Present: product description, intended use, regulatory pathway, risk analysis, predicate devices
- Ask FDA: "Is this device subject to 510(k) vs. PMA?" (likely 510(k) — less onerous)
- Expected response: "Yes, SaMD; 510(k) pathway recommended with [specific data requirements]"

#### 2. 510(k) Pathway: What Data Is Required?

If FDA recommends 510(k), the submission requires:

**Predicate Device Identification:**
- Identify an already-cleared diagnostic AI tool (e.g., IBM Watson for Oncology, Tempus AI clinical research)
- Show substantial equivalence in intended use, technology, and safety/effectiveness profile

**Software Documentation (IEC 62304):**
- Software development plan (design, architecture, unit/integration/system testing)
- Cybersecurity documentation (threat assessment, mitigation)
- Verification & validation testing (does the software do what it claims?)
- Post-market surveillance plan (how will you track safety/effectiveness in real use?)

**Clinical Evidence:**
- Evaluation data: board's diagnostic accuracy on real rare-disease cases
- Comparison to standard of care (do clinicians follow the board more than their own reasoning?)
- Safety data: false-positive rate, missed diagnoses, adverse event potential

**Risk Analysis (ISO 14971):**
- Hazard analysis: what could go wrong? (hallucinated diagnosis, outdated guideline links, model drift)
- Mitigation: how do you prevent/detect/respond? (regular guideline updates, disclaimer visibility, outcome monitoring)

#### 3. HIPAA Compliance: What's Required for Hospital Deployment?

Hospitals demand HIPAA Business Associate Agreement (BAA) before any AegisMed instance touches patient data.

**HIPAA requirements:**
- **Encryption at rest:** patient labs/conditions must be encrypted in database (AES-256 minimum)
- **Encryption in transit:** TLS 1.2+ for all network comms
- **Access control:** clinician authentication (OAuth2 + MFA recommended), audit logging of who accessed what case
- **Audit logging:** every case submission, every comment, every export logged with timestamp + clinician ID + IP
- **Data retention:** policies on how long case histories are stored (e.g., "delete after 1 year" or "retain for statute of limitations")
- **Breach notification:** process for detecting/notifying breaches within 60 days

**AegisMed's current state (v0.1.0):**
- ❌ No encryption at rest (cases.jsonl is plaintext)
- ❌ No clinician authentication (anyone with network access can submit)
- ❌ Minimal audit logging (no IP tracking, no access control)
- ❌ No data retention policy

**Phase 4a deliverables for HIPAA readiness:**
1. **Security infrastructure audit:** hire third-party security firm to assess gaps
2. **Encryption implementation:** add AES-256 at rest + TLS enforcement
3. **Audit logging system:** implement structured logging (JSON + centralized log storage)
4. **HIPAA Business Associate Agreement template:** legal doc for hospital contracts
5. **Risk Assessment (HIPAA Security Rule § 164.308(a)):** document risk matrix + mitigation
6. **Incident Response Plan:** what happens if a case file is accessed without authorization?

#### 4. GDPR: What's Required for EU Hospital Deployment?

EU hospitals also need compliance — GDPR is stricter than HIPAA in some ways.

**GDPR requirements (parallel to HIPAA):**
- **Data subject rights:** clinician can request what data is stored about "their" patient (even if pseudonymous)
- **Data minimization:** collect only data strictly necessary (⚠️ current design stores full labs/meds — must justify)
- **Right to be forgotten:** patient (via clinician/hospital) can request deletion; must comply in reasonable time
- **Data Processing Agreement (DPA):** hospital is data controller, AegisMed is processor; must sign binding DPA
- **Data Protection Impact Assessment (DPIA):** evaluate risks to individuals (data breach, misuse, etc.)

**AegisMed's current state:**
- ⚠️ Stores patient context (labs, conditions) as plaintext in cases.jsonl → GDPR concern
- ✅ No direct patient names (only clinician ID + hashed patient ID per Phase 3f design)
- ❌ No DPIA; no DPA template

**Phase 4a deliverables for GDPR readiness:**
1. **Data Protection Impact Assessment:** formal DPIA per GDPR Article 35
2. **Data Processing Agreement template:** legal doc for hospital contracts
3. **Anonymization review:** confirm patient-context storage complies with anonymization standards (ISO 20460)
4. **Right-to-be-forgotten implementation:** API endpoint to delete all cases for a pseudonymized patient within 30 days

#### 5. Insurance / Medical Legal Liability

Insurers expect certain standards before covering AegisMed usage.

**Liability questions:**
- **Malpractice insurance:** does AegisMed have product liability coverage? (Yes — obtained before deployment)
- **Indemnification:** if a clinician follows the board's diagnosis and it's wrong, who's liable? (AegisMed's disclaimer says "clinician must verify," but legal clarity helps)
- **Evidence of efficacy:** what's the board's diagnostic accuracy? (use eval results from Phase 1)
- **Safety metrics:** false-positive rate? Missed diagnoses? (track via outcomes monitoring)

**Phase 4a deliverables:**
1. **Product liability insurance policy:** minimum $2M coverage, cyber liability rider
2. **Indemnification clause:** standard language in hospital contracts
3. **Efficacy evidence package:** publish/present board accuracy data (medical journal submission via Phase 4e)

### Implementation Strategy

#### Phase 4a Timeline: Weeks 1–4

**Week 1: Pre-submission prep**
- Hire FDA regulatory consultant (1–2 day engagement, $5–10K)
- Draft pre-submission package: product description, intended use statement, risk profile
- Identify 3–5 predicate devices for 510(k) comparison

**Week 2: FDA engagement**
- File Type B pre-submission (Q-submission via FDA's eSTAR portal)
- Kick off security audit with third-party firm (Coalfire, Schellman, etc.; 2–4 week engagement)

**Week 3: HIPAA/GDPR prep while waiting for FDA response**
- Draft HIPAA Business Associate Agreement (template from legal)
- Draft GDPR Data Processing Agreement
- Create Data Protection Impact Assessment (DPIA form + risk matrix)

**Week 4: Documentation & internal readiness**
- Software documentation (architecture, design, test coverage) per IEC 62304
- Risk analysis per ISO 14971 (hazard table + mitigations)
- Incident response playbook
- Audit logging infrastructure review

**Post-Week 4:**
- Receive FDA pre-submission response (estimate 3 weeks from filing)
- Security audit final report + remediation plan (estimate 2–3 weeks)
- Begin remediation work on HIPAA/encryption gaps (Weeks 5–6)
- Draft 510(k) submission (Weeks 6–8)

### What Gets Deferred to Phase 5+

**❌ FDA 510(k) Submission:** Phase 4a *prepares* for submission but doesn't file yet. Filing happens when:
- Security audit remediation is complete
- Clinical evidence is mature (sufficient outcome data from Phase 3d/3f deployments)
- Predicate device equivalence is established

**❌ ISO 13485 Certification (full QMS):** Optional for FDA 510(k) but valuable for enterprise sales. Requires:
- Documented design controls, verification/validation, complaint handling, traceability
- Internal audit program
- Management review
- Estimated 3–6 month effort post-clearance

**❌ International approvals (CE mark, PMCF, etc.):** EU In Vitro Diagnostic Directive (IVDR) or Medical Device Directive (MDD) varies by region. Scope creeps. Phase 4a focuses on FDA + HIPAA/GDPR for US + EU hospital deployment.

### Risk Mitigation for Phase 4a

1. **FDA engagement risk:** If FDA classifies AegisMed as higher-risk device, 510(k) might not suffice → could require PMA (Premarket Approval) with clinical trials. *Mitigation:* engage early via pre-submission to get clarity.

2. **Security audit findings:** Third-party audit might reveal major gaps (e.g., no encryption, SQL injection risk in case storage). *Mitigation:* budget for 4–8 week remediation post-audit; use Agile security fixes (prioritize by CVSS score).

3. **Liability insurance cost:** Depending on claim history + product risk, premiums could be $10–30K/year. *Mitigation:* shop multiple carriers; get quotes early.

4. **Legal liability for incorrect diagnosis:** Even with disclaimer, if AegisMed's recommendation is widely followed and turns out to be wrong, litigation risk exists. *Mitigation:* strong evidence of decision-support (clinician review), transparent reasoning, and outcome tracking reduce liability exposure.

### Success Metrics (Phase 4a)

- ✅ FDA pre-submission meeting held; response received with clear 510(k) pathway
- ✅ Security audit completed; no critical (CVSS 9+) findings; medium findings remediation plan in place
- ✅ HIPAA/GDPR compliance assessment done; BAA + DPA templates drafted
- ✅ 510(k) submission-ready documentation complete (IEC 62304, risk analysis, predicate comparison)
- ✅ Product liability insurance policy obtained
- ✅ Zero data breaches; audit logging in place on production instances

---

## Future Roadmap (Phase 4b+)

After Phase 4a regulatory clarity is obtained:

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
| 3e | Geographic expansion | ✅ MVP shipped | ~1 day (MVP) | `region` param, regional guideline ordering, regional specialist context |
| 3f | FHIR/EHR integration plan | ✅ Complete | Plan only | OAuth + FHIR architecture |
| 4a | Regulatory & SaMD pathway | **← Now** | Plan only | FDA/HIPAA/GDPR strategy |
| 4b | Specialized workflows | Future | 6–10 weeks | Genetic, pediatric, OB, geri modes |
| 4c | ML feedback loop | Future | 8–12 weeks | Outcome tracking, model refinement |
| 4d | Telehealth integrations | Future | 4–8 weeks | Zoom, Teams, platform embeds |
| 4e | Research & publishing | Future | Ongoing | Case series, outcomes studies |

# 🔌 AegisMed API — integration guide

AegisMed's diagnostic board is a plain JSON HTTP API with **no auth and no
session state** — every request is self-contained. That makes it easy to embed
in a telehealth workflow, an EHR sidebar, or an internal case-review tool. This
page documents the two endpoints an integrator actually needs.

> ⚠️ **Clinical decision-support only.** Responses must be verified by a
> licensed physician. Do not surface AegisMed output directly to patients or use
> it for autonomous diagnosis or coverage decisions.

Interactive, always-current docs are served by the app itself:

- Swagger UI: `GET /docs`
- ReDoc: `GET /redoc`
- OpenAPI spec: `GET /openapi.json`

## Request shape — `PatientCase`

Both `POST` endpoints accept the same JSON body:

| Field | Type | Required | Notes |
|---|---|---|---|
| `symptoms` | string | **yes** | 10–8000 chars. The presenting complaint. |
| `age` | string | no | Free text, e.g. `"24"` or `"6 months"`. ≤ 20 chars. |
| `sex` | string | no | e.g. `"male"` / `"female"`. ≤ 20 chars. |
| `history` | string | no | Past illnesses, medications, family history. ≤ 8000 chars. |
| `labs` | string | no | Labs, imaging, ECG, etc. ≤ 8000 chars. |
| `clarifications` | string | no | Answers to intake questions, appended to the case. ≤ 8000 chars. |

## `POST /api/intake` — ask for missing details (optional)

Returns high-value clarifying questions before the board runs. You can skip this
and call `/api/diagnose` directly.

```json
{
  "ready": false,
  "questions": [
    {"question": "When did the burning pain first start?", "why": "Age of onset narrows the differential."}
  ],
  "demo_mode": true
}
```

Collect the physician's answers, join them into one text block, and pass them as
`clarifications` to `/api/diagnose`.

## `POST /api/diagnose` — convene the board

Runs the full board and returns everything the UI renders. Response shape:

| Field | Type | Meaning |
|---|---|---|
| `synthesis` | string | The board chair's briefing: ranked differential, next test, safety actions, do-not-miss warning. |
| `specialist_opinions` | array of `{specialty, opinion}` | Each consulted specialist's written analysis. |
| `references` | array of `{diagnosis, links:[{label,url}]}` | Verified disease-reference links (Orphanet/OMIM/PubMed/GARD). |
| `guideline_references` | array of `{diagnosis, links:[{label,url}]}` | Live clinical practice guideline **search** links (PubMed, Cochrane, NICE, TRIP, MedlinePlus, NCBI Bookshelf, Guideline Central). |
| `evidence` | `{phenotypes, candidates}` | What the retrieval step flagged and looked up. |
| `routing` | `{selected_specialties, skipped_specialties, total_specialties}` | Which specialists smart routing convened. |
| `disclaimer` | string | The clinical-use disclaimer — display it wherever you surface output. |
| `demo_mode` | bool | `true` when running on canned sample output (no API key configured). |
| `demo_banner` | string | Banner text to show in demo mode. |

All fields are additive and stable; new fields may be added over time, so parse
defensively (ignore unknown keys).

### curl

```bash
curl -s -X POST http://localhost:8000/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{
        "age": "24",
        "sex": "male",
        "symptoms": "burning pain in hands and feet since childhood, decreased sweating",
        "history": "maternal uncle died of renal failure",
        "labs": "proteinuria; LVH on ECG"
      }'
```

### Python (httpx)

```python
import httpx

case = {
    "age": "24",
    "sex": "male",
    "symptoms": "burning pain in hands and feet since childhood, decreased sweating",
    "history": "maternal uncle died of renal failure",
    "labs": "proteinuria; LVH on ECG",
}

resp = httpx.post("http://localhost:8000/api/diagnose", json=case, timeout=120)
resp.raise_for_status()
data = resp.json()

print(data["synthesis"])
for ref in data["guideline_references"]:
    print(ref["diagnosis"], "→", [l["url"] for l in ref["links"]])
```

A diagnostic run makes several model calls and can take up to a minute — set a
generous client timeout (the example uses 120s).

---

## `POST /api/teaching/case` — teaching mode (compare to expected diagnosis)

For classroom and simulation workflows: the board runs normally, but also compares
the board's ranked diagnoses against an expected (correct) diagnosis. Returns the
full diagnostic output plus a `match_summary` showing whether the expected diagnosis
appeared in the top 3, its rank, and the board's top-3 diagnoses for comparison.

**Request:** `PatientCase` plus:

| Field | Type | Required | Notes |
|---|---|---|---|
| `expected_diagnosis` | string | **yes** | The student's or instructor's expected diagnosis. ≤ 200 chars. |

**Response:** Everything from `/api/diagnose`, plus:

| Field | Type | Meaning |
|---|---|---|
| `match_summary` | object | Comparison metrics (see below). |

`match_summary` structure:

```json
{
  "expected_diagnosis": "Fabry disease",
  "found_in_top_3": true,
  "rank": 1,
  "is_rare": false,
  "board_top_3": ["Fabry disease", "Hypertrophic cardiomyopathy with coincidental neuropathy", "..."]
}
```

- `found_in_top_3`: whether the expected diagnosis appears in the board's top 3.
- `rank`: position (1–3) if found; null otherwise.
- `is_rare`: whether the diagnosis was tagged [RARE] by the board.
- `board_top_3`: the board's ranked top-three diagnoses for reference.

### curl

```bash
curl -s -X POST http://localhost:8000/api/teaching/case \
  -H "Content-Type: application/json" \
  -d '{
        "age": "24",
        "sex": "male",
        "symptoms": "burning pain in hands and feet since childhood, decreased sweating",
        "history": "maternal uncle died of renal failure",
        "labs": "proteinuria; LVH on ECG",
        "expected_diagnosis": "Fabry disease"
      }' | jq '.match_summary'
```

### Python (httpx)

```python
import httpx

case = {
    "age": "24",
    "sex": "male",
    "symptoms": "burning pain in hands and feet since childhood, decreased sweating",
    "history": "maternal uncle died of renal failure",
    "labs": "proteinuria; LVH on ECG",
    "expected_diagnosis": "Fabry disease",  # Added for teaching mode
}

resp = httpx.post("http://localhost:8000/api/teaching/case", json=case, timeout=120)
resp.raise_for_status()
data = resp.json()

match = data["match_summary"]
if match["found_in_top_3"]:
    print(f"✓ Correct! Ranked #{match['rank']}")
else:
    print(f"✗ Not in top 3. Board's top diagnosis: {match['board_top_3'][0]}")
```

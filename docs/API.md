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

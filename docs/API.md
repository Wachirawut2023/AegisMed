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
| `region` | string | no | `"us"` (default) / `"uk"` / `"eu"`. Reorders which verified guideline sources are foregrounded and nudges specialists to reference region-appropriate authorities (e.g. NICE for `"uk"`). Invalid values are rejected with `422`. |

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
| `guideline_references` | array of `{diagnosis, links:[{label,url}]}` | Live clinical practice guideline **search** links (PubMed, Cochrane, NICE, TRIP, MedlinePlus, NCBI Bookshelf, Guideline Central), ordered per the request's `region`. |
| `region` | string | The practice region actually used (`"us"`/`"uk"`/`"eu"`) — echoes back the validated request field. |
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

### Practice region (`region`)

Pass `"region": "uk"` or `"region": "eu"` to reorder guideline sources for that
practice context (e.g. NICE leads for `"uk"`) and nudge specialists toward
region-appropriate authorities. Defaults to `"us"` if omitted; any other value
is rejected with `422`.

```bash
curl -s -X POST http://localhost:8000/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{
        "symptoms": "burning pain in hands and feet since childhood, decreased sweating",
        "region": "uk"
      }' | jq '.region, .guideline_references[0].links[0]'
```

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

---

## Case Management — Team Workflows & Case History

For hospital and institution use: save board results with metadata, retrieve them for
case-conference follow-up, and append team comments for collaborative case discussion.

All case data is stored locally on the server; cases are identified by a short unique ID.
No auth, no patient identity, no PHI — just case lookup and team collaboration primitives.

---

## `POST /api/cases/save` — save a board result with metadata

Runs a diagnostic board (same as `/api/diagnose`) and saves the result with optional
metadata about who submitted it and what specialty is involved. Returns a `case_id`
that can be used to retrieve the case later.

**Request:** `PatientCase` plus:

| Field | Type | Required | Notes |
|---|---|---|---|
| `submitted_by` | string | no | e.g. "Dr. Smith, Cardiology" — identifies the submitter |
| `specialty` | string | no | e.g. "Cardiology" — primary specialty for filtering |

**Response:**

| Field | Type | Meaning |
|---|---|---|
| `case_id` | string | Unique ID for this case (short UUID) |
| `status` | string | "saved" |
| `board_output` | object | Full diagnostic output (same as `/api/diagnose`) |

### curl

```bash
curl -s -X POST http://localhost:8000/api/cases/save \
  -H "Content-Type: application/json" \
  -d '{
        "age": "24",
        "sex": "male",
        "symptoms": "burning pain in hands and feet since childhood",
        "history": "maternal uncle died of renal failure",
        "labs": "proteinuria; LVH on ECG",
        "submitted_by": "Dr. Johnson, Cardiology",
        "specialty": "Cardiology"
      }' | jq '.case_id'
```

---

## `GET /api/cases/{case_id}` — retrieve a saved case

Fetches the full case history including the board output, metadata, and all team comments.

**Response:**

| Field | Type | Meaning |
|---|---|---|
| `case_id` | string | The case ID |
| `timestamp` | string | ISO 8601 timestamp when the case was saved |
| `submitted_by` | string | Submitter name/title |
| `specialty` | string | Primary specialty |
| `board_output` | object | Full diagnostic output (see `/api/diagnose` response) |
| `team_comments` | array | Comments appended by team members (see below) |

**team_comments** structure:

```json
[
  {
    "timestamp": "2026-07-09T12:34:56.789123",
    "author": "Dr. Smith, Neurology",
    "text": "Agreed with board. Recommend MRI follow-up in 3 months."
  }
]
```

### curl

```bash
curl -s http://localhost:8000/api/cases/d21efb4c | jq '{case_id, submitted_by, specialty, team_comments}'
```

---

## `GET /api/cases` — list saved cases

Lists case summaries (not full board output), optionally filtered by specialty.
Most recent first.

**Query parameters:**

| Param | Type | Notes |
|---|---|---|
| `specialty` | string | Filter by specialty (e.g. "Cardiology") |
| `limit` | int | Max results to return (default: 50) |

**Response:** Array of case summaries:

```json
[
  {
    "case_id": "d21efb4c",
    "timestamp": "2026-07-09T12:34:56.789123",
    "submitted_by": "Dr. Johnson, Cardiology",
    "specialty": "Cardiology",
    "top_diagnosis": "Fabry disease",
    "num_comments": 1
  }
]
```

### curl

```bash
curl -s 'http://localhost:8000/api/cases?specialty=Cardiology&limit=5' | jq '.[] | {case_id, specialty, top_diagnosis}'
```

---

## `POST /api/cases/{case_id}/comment` — append a team comment

Adds a timestamped comment from a team member to a case for case-conference discussion,
follow-up notes, or outcome tracking.

**Request:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `author` | string | **yes** | e.g. "Dr. Smith, Neurology" |
| `text` | string | **yes** | Comment text; ≤ 1000 chars |

**Response:**

```json
{
  "status": "comment added",
  "case_id": "d21efb4c"
}
```

### curl

```bash
curl -s -X POST http://localhost:8000/api/cases/d21efb4c/comment \
  -H "Content-Type: application/json" \
  -d '{
        "author": "Dr. Smith, Neurology",
        "text": "Agreed with board conclusion. Recommend MRI follow-up in 3 months."
      }' | jq '.'
```

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
| `deliberation` | `{draft_synthesis, peer_review}` | The board's process: the chair's preliminary draft, and each specialist's round-2 rebuttal (`peer_review` is an array of `{specialty, comment}`) before the chair issued the final `synthesis` above. Optional UI transparency — `synthesis` itself already reflects the outcome. |
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

## `POST /api/diagnose/stream` — convene the board (streaming)

Same request/response as `/api/diagnose`, but streams progress as Server-Sent
Events instead of waiting silently for the full ~1-minute round-trip. Each
line is `data: <json>\n\n`. Events, in order:

| `event` | Fields | Meaning |
|---|---|---|
| `specialist_done` | `specialty, completed, total` | One round-1 specialist finished (completion order, not roster order). |
| `draft_synthesis_done` | — | The chair's preliminary differential is ready. |
| `peer_review_done` | `specialty, completed, total` | One specialist finished reviewing the draft (round 2). |
| `final_synthesis_done` | — | The chair's final differential (post-peer-review) is ready. |
| `final` | `data` | The complete result — identical shape to `/api/diagnose`'s response. Always the last event. |
| `error` | `message` | A model/network failure mid-stream (mirrors `/api/diagnose`'s `502`, but the HTTP status is already `200` since streaming started — check for this event). |

### Python (httpx)

```python
import json
import httpx

case = {"symptoms": "burning pain in hands and feet since childhood, decreased sweating"}

with httpx.stream("POST", "http://localhost:8000/api/diagnose/stream", json=case, timeout=120) as resp:
    for line in resp.iter_lines():
        if not line.startswith("data:"):
            continue
        event = json.loads(line[len("data:"):].strip())
        if event["event"] == "final":
            print(event["data"]["synthesis"])
        elif event["event"] == "error":
            raise RuntimeError(event["message"])
        else:
            print(event["event"], event.get("specialty", ""))
```

---

## `POST /api/diagnose/followup` — ask a follow-up question

After the board delivers its differential, ask a follow-up question (e.g. a
"what if the labs also showed X?" hypothetical) grounded in the case and the
board's own reasoning. Stateless — no `case_id` lookup — so send back the
`synthesis`, `specialist_opinions`, and `evidence` you already received from
`/api/diagnose` (or the `final` event of `/api/diagnose/stream`).

**Request:** `PatientCase` plus:

| Field | Type | Required | Notes |
|---|---|---|---|
| `synthesis` | string | **yes** | The board's final synthesis, from a prior `/api/diagnose` call. |
| `specialist_opinions` | array of `{specialty, opinion}` | no | From the same prior call — gives the richest grounding. |
| `evidence` | `{phenotypes, candidates}` | no | From the same prior call. |
| `question` | string | **yes** | 3–2000 chars. |
| `previous_qa` | array of `{question, answer}` | no | Prior exchanges in this consult, for multi-turn follow-ups. Max 20. |

**Response:**

| Field | Type | Meaning |
|---|---|---|
| `answer` | string | The follow-up answer, under 200 words. |
| `demo_mode` | bool | `true` when running on canned sample output. |

### curl

```bash
curl -s -X POST http://localhost:8000/api/diagnose/followup \
  -H "Content-Type: application/json" \
  -d '{
        "symptoms": "burning pain in hands and feet since childhood, decreased sweating",
        "synthesis": "... (from a prior /api/diagnose response) ...",
        "specialist_opinions": [],
        "question": "What if the creatinine had continued to rise despite hydration?"
      }' | jq '.answer'
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

Saves the board result the client **already holds** (from `/api/diagnose` or the
`final` event of `/api/diagnose/stream`) — the board is **not** recomputed here,
so what's saved matches exactly what the physician reviewed. The original case
input and any follow-up Q&A already asked are stored alongside it. Returns a
`case_id` for later retrieval.

**Request:** `PatientCase` plus:

| Field | Type | Required | Notes |
|---|---|---|---|
| `board_output` | object | **yes** | The full diagnostic output from a prior `/api/diagnose` call. A `400` is returned if omitted. |
| `submitted_by` | string | no | e.g. "Dr. Smith, Cardiology" — identifies the submitter |
| `specialty` | string | no | e.g. "Cardiology" — primary specialty for filtering |
| `followup_qa` | array of `{question, answer}` | no | Follow-up exchanges already asked before saving. Max 50. |

The `PatientCase` fields (age/sex/symptoms/…) are stored as the case input so a
loaded case can still ground follow-up questions.

**Response:**

| Field | Type | Meaning |
|---|---|---|
| `case_id` | string | Unique ID for this case (short UUID) |
| `status` | string | "saved" |
| `board_output` | object | Echoes back the saved output |

### curl

```bash
curl -s -X POST http://localhost:8000/api/cases/save \
  -H "Content-Type: application/json" \
  -d '{
        "age": "24",
        "sex": "male",
        "symptoms": "burning pain in hands and feet since childhood",
        "board_output": { "...": "from a prior /api/diagnose response" },
        "submitted_by": "Dr. Johnson, Cardiology",
        "specialty": "Cardiology"
      }' | jq '.case_id'
```

---

## `GET /api/cases/{case_id}` — retrieve a saved case

Fetches the full case history including the board output, the original case
input, follow-up Q&A, metadata, and all team comments.

**Response:**

| Field | Type | Meaning |
|---|---|---|
| `case_id` | string | The case ID |
| `timestamp` | string | ISO 8601 timestamp when the case was saved |
| `submitted_by` | string | Submitter name/title |
| `specialty` | string | Primary specialty |
| `case_input` | object | The original case fields (age/sex/symptoms/…) the board saw. |
| `board_output` | object | Full diagnostic output (see `/api/diagnose` response) |
| `followup_qa` | array | Follow-up exchanges (`{timestamp, question, answer}`) for this consult. |
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

---

## `POST /api/cases/{case_id}/followup` — persist a follow-up Q&A

Appends a follow-up question and its answer (already obtained from
`/api/diagnose/followup`) to a saved case, so the consult thread is kept with
the case for later review.

**Request:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | string | **yes** | The follow-up question; ≤ 2000 chars |
| `answer` | string | **yes** | The answer from `/api/diagnose/followup`; ≤ 4000 chars |

**Response:**

```json
{
  "status": "followup added",
  "case_id": "d21efb4c"
}
```

### curl

```bash
curl -s -X POST http://localhost:8000/api/cases/d21efb4c/followup \
  -H "Content-Type: application/json" \
  -d '{
        "question": "What if the creatinine had continued to rise?",
        "answer": "That would raise the urgency of the renal workup ..."
      }' | jq '.'
```

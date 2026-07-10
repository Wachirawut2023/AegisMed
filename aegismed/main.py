"""The web server — the front door of AegisMed.

Routes:
  GET  /                 the web page (static/index.html)
  GET  /health           simple "is it running?" check, used by Docker and judges
  POST /api/diagnose     receives the patient case, runs the board, returns JSON
  POST /api/teaching/case  for teaching mode: runs board + compares to expected diagnosis
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import __version__, cases, config, intake, knowledge, llm, orchestrator
from .demo_data import EXAMPLE_CASE

TAGS_METADATA = [
    {"name": "diagnosis", "description": "The core board: intake questions and the full diagnostic run."},
    {"name": "cases", "description": "Built-in and curated example cases for demos and testing."},
    {"name": "team", "description": "Case history & team collaboration: save, retrieve, and comment on past cases."},
    {"name": "meta", "description": "Service metadata and health checks for integrators and orchestration."},
]

app = FastAPI(
    title="AegisMed",
    description=(
        "A virtual board of AI specialist physicians for rare-disease diagnosis "
        "support. Clinical decision-support only — every response must be verified "
        "by a licensed physician. See docs/API.md for an integration guide."
    ),
    version=__version__,
    openapi_tags=TAGS_METADATA,
)

# Allow the Firebase-hosted frontend (a different origin than this backend) to
# call the API. ALLOWED_ORIGINS is a comma-separated list in .env; defaults to
# "*" so local/demo use keeps working without any config.
_origins = [o.strip() for o in config.ALLOWED_ORIGINS.split(",") if o.strip()] or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class PatientCase(BaseModel):
    age: str = Field(default="", max_length=20)
    sex: str = Field(default="", max_length=20)
    symptoms: str = Field(..., min_length=10, max_length=8000)
    history: str = Field(default="", max_length=8000)
    labs: str = Field(default="", max_length=8000)
    # Answers to the intake agent's questions, appended to the case for diagnosis.
    clarifications: str = Field(default="", max_length=8000)
    # Practice region: shifts which guideline authorities are foregrounded and
    # which the specialists are nudged to cite. See docs/ROADMAP.md Phase 3e.
    region: str = Field(default="us", pattern="^(us|uk|eu)$")
    # Optional: judge's own Fireworks API key. If provided, this is used instead
    # of the server's default key. Useful for hackathons where judges have their
    # own Fireworks accounts. Leave empty to use the shared server key.
    api_key: str = Field(default="", max_length=200)


class TeachingCase(PatientCase):
    # The student's or instructor's expected diagnosis to compare against the board.
    expected_diagnosis: str = Field(..., min_length=1, max_length=200)


class SaveCaseRequest(PatientCase):
    # Optional metadata for case storage.
    submitted_by: str = Field(default="", max_length=100)
    specialty: str = Field(default="", max_length=50)
    # Optional: a board result already computed by /api/diagnose or
    # /api/teaching/case. If provided, it is saved as-is instead of running the
    # board again — this keeps the saved case identical to what the physician
    # reviewed on screen (the board is non-deterministic outside demo mode, so
    # re-running it could silently save a different result than was shown).
    board_output: dict | None = Field(default=None)


class CommentRequest(BaseModel):
    # A team comment on an existing case.
    author: str = Field(..., min_length=1, max_length=100)
    text: str = Field(..., min_length=1, max_length=1000)


@app.get("/", tags=["meta"], summary="Web UI", include_in_schema=False)
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get(
    "/health",
    tags=["meta"],
    summary="Health check",
    description="Liveness probe for Docker/uptime checks. Reports version, demo mode, model, and knowledge-base size.",
)
async def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "demo_mode": config.demo_mode(),
        "model": config.MODEL,
        "knowledge_base_diseases": knowledge.kb_size(),
    }


@app.get(
    "/api/example-case",
    tags=["cases"],
    summary="Built-in example case",
    description="The single hard-coded sample case used by the 'Load example case' button.",
)
async def example_case() -> dict:
    """The built-in sample case used by the 'Load example case' button."""
    return EXAMPLE_CASE


DEMO_CASES_FILE = Path(__file__).resolve().parent.parent / "data" / "demo_cases.json"


@app.get(
    "/api/demo-cases",
    tags=["cases"],
    summary="Curated demo cases",
    description="Real cases from public datasets (with known diagnoses) for the demo dropdown.",
)
async def demo_cases() -> list[dict]:
    """Curated real cases from public datasets for the demo dropdown.

    Returns a short list of {label, age, sex, symptoms, history, labs,
    expected_diagnosis}. Falls back to the single built-in example if the
    dataset has not been built yet (run: python data/build_dataset.py).
    """
    if DEMO_CASES_FILE.exists():
        cases = json.loads(DEMO_CASES_FILE.read_text(encoding="utf-8"))
        return [
            {
                "label": f"{c.get('source', 'case')}: {c['expected_diagnosis']}",
                "age": c.get("age", ""),
                "sex": c.get("sex", ""),
                "symptoms": c.get("symptoms", ""),
                "history": c.get("history", ""),
                "labs": c.get("labs", ""),
                "expected_diagnosis": c.get("expected_diagnosis", ""),
            }
            for c in cases
        ]
    return [{"label": "Example: Fabry disease", **EXAMPLE_CASE, "expected_diagnosis": "Fabry disease"}]


@app.post(
    "/api/intake",
    tags=["diagnosis"],
    summary="Intake: ask for missing details",
    description="Runs one quick model call that returns high-value clarifying questions (or none). Optional — you may skip straight to /api/diagnose.",
)
async def intake_questions(case: PatientCase) -> dict:
    """Intake step: ask the physician for missing high-value details, if any.

    Returns {ready, questions:[{question, why}], demo_mode}. The UI shows the
    questions, collects answers, and sends them back to /api/diagnose as
    `clarifications`. Runs one quick model call (not the full board).
    """
    try:
        return await intake.gather_questions(
            age=case.age,
            sex=case.sex,
            symptoms=case.symptoms,
            history=case.history,
            labs=case.labs,
            api_key=case.api_key,
        )
    except llm.LLMError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


@app.post(
    "/api/diagnose",
    tags=["diagnosis"],
    summary="Convene the board",
    description="Runs the full diagnostic board and returns the ranked differential, specialist opinions, verified citations, and clinical-guideline search links.",
)
async def diagnose(case: PatientCase) -> dict:
    try:
        return await orchestrator.diagnose(
            age=case.age,
            sex=case.sex,
            symptoms=case.symptoms,
            history=case.history,
            labs=case.labs,
            clarifications=case.clarifications,
            region=case.region,
            api_key=case.api_key,
        )
    except llm.LLMError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


@app.post(
    "/api/teaching/case",
    tags=["diagnosis"],
    summary="Teaching case evaluation",
    description="Runs the diagnostic board and compares the board's top diagnoses against an expected (correct) diagnosis. Returns the full board output plus match metrics for classroom or teaching scenarios.",
)
async def teaching_case(case: TeachingCase) -> dict:
    """Teaching mode: run the board and compare against an expected diagnosis.

    Returns the full board output plus a match_summary showing whether the
    expected diagnosis appears in the board's top 3, its rank, and [RARE] status.
    Useful for medical school case-conference simulations.
    """
    try:
        board_output = await orchestrator.diagnose(
            age=case.age,
            sex=case.sex,
            symptoms=case.symptoms,
            history=case.history,
            labs=case.labs,
            clarifications=case.clarifications,
            region=case.region,
            api_key=case.api_key,
        )

        # Extract the diagnoses from the board's synthesis.
        synthesis = board_output.get("synthesis", "")
        diagnoses = knowledge.extract_diagnoses(synthesis, limit=6)

        # Normalize the expected diagnosis for comparison (case-insensitive, trim punctuation).
        expected_normalized = knowledge._normalize(case.expected_diagnosis)

        # Find if and where the expected diagnosis appears in the board's output.
        rank = None
        is_rare = False
        for i, diagnosis in enumerate(diagnoses[:3], start=1):
            if knowledge._normalize(diagnosis) == expected_normalized:
                rank = i
                is_rare = "[RARE]" in diagnosis
                break

        match_summary = {
            "expected_diagnosis": case.expected_diagnosis,
            "found_in_top_3": rank is not None,
            "rank": rank,
            "is_rare": is_rare,
            "board_top_3": diagnoses[:3],
        }

        return {
            **board_output,
            "match_summary": match_summary,
        }
    except llm.LLMError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


@app.post(
    "/api/cases/save",
    tags=["team"],
    summary="Save a case for later review",
    description="Saves the result of a board run with optional metadata. Returns a case_id for later retrieval and team discussion.",
)
async def save_case_result(req: SaveCaseRequest) -> dict:
    """Save a completed board result for case-conference follow-up or team review.

    If `board_output` is provided (the result of a prior /api/diagnose or
    /api/teaching/case call), it is saved as-is. Otherwise the board is run on
    the provided case fields. Saves with metadata (who submitted it, what
    specialty). Returns a case_id for retrieval, printing, or team comments.
    """
    try:
        board_output = req.board_output or await orchestrator.diagnose(
            age=req.age,
            sex=req.sex,
            symptoms=req.symptoms,
            history=req.history,
            labs=req.labs,
            clarifications=req.clarifications,
            region=req.region,
        )

        case_id = cases.save_case(
            board_output=board_output,
            submitted_by=req.submitted_by,
            specialty=req.specialty,
        )

        return {
            "case_id": case_id,
            "status": "saved",
            "board_output": board_output,
        }
    except llm.LLMError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err


@app.get(
    "/api/cases/{case_id}",
    tags=["team"],
    summary="Retrieve a saved case",
    description="Fetches the full case history including the original board output, metadata, and all team comments.",
)
async def get_case(case_id: str) -> dict:
    """Retrieve a saved case by ID, including board output and all team comments.

    Returns the case entry with board_output, metadata, and team_comments array.
    """
    case = cases.load_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    return case


@app.get(
    "/api/cases",
    tags=["team"],
    summary="List saved cases",
    description="Fetches a summary list of saved cases, optionally filtered by specialty. Most recent first.",
)
async def list_cases_endpoint(specialty: str = "", limit: int = 50) -> list[dict]:
    """List saved cases, optionally filtered by specialty (e.g. 'Cardiology').

    Returns case summaries: case_id, timestamp, specialty, submitted_by, and
    top_diagnosis. Full board output is retrieved via /api/cases/{case_id}.
    """
    return cases.list_cases(specialty=specialty, limit=limit)


@app.post(
    "/api/cases/{case_id}/comment",
    tags=["team"],
    summary="Add a team comment to a case",
    description="Appends a timestamped comment from a team member to a case for case-conference discussion.",
)
async def add_comment(case_id: str, comment: CommentRequest) -> dict:
    """Append a team comment to a saved case.

    Each comment includes a timestamp, author name, and text.
    Useful for case-conference follow-up, second-opinion notes, or outcome tracking.
    """
    success = cases.append_comment(
        case_id=case_id,
        author=comment.author,
        text=comment.text,
    )
    if not success:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")
    return {"status": "comment added", "case_id": case_id}

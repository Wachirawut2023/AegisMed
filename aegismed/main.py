"""The web server — the front door of AegisMed.

Three routes:
  GET  /             the web page (static/index.html)
  GET  /health       simple "is it running?" check, used by Docker and judges
  POST /api/diagnose receives the patient case, runs the board, returns JSON
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import __version__, config, intake, knowledge, llm, orchestrator
from .demo_data import EXAMPLE_CASE

TAGS_METADATA = [
    {"name": "diagnosis", "description": "The core board: intake questions and the full diagnostic run."},
    {"name": "cases", "description": "Built-in and curated example cases for demos and testing."},
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

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


class PatientCase(BaseModel):
    age: str = Field(default="", max_length=20)
    sex: str = Field(default="", max_length=20)
    symptoms: str = Field(..., min_length=10, max_length=8000)
    history: str = Field(default="", max_length=8000)
    labs: str = Field(default="", max_length=8000)
    # Answers to the intake agent's questions, appended to the case for diagnosis.
    clarifications: str = Field(default="", max_length=8000)


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
        )
    except llm.LLMError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

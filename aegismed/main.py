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

app = FastAPI(
    title="AegisMed",
    description="A virtual board of AI specialist physicians for rare-disease diagnosis support.",
    version=__version__,
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


@app.get("/")
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "demo_mode": config.demo_mode(),
        "model": config.MODEL,
        "knowledge_base_diseases": knowledge.kb_size(),
    }


@app.get("/api/example-case")
async def example_case() -> dict:
    """The built-in sample case used by the 'Load example case' button."""
    return EXAMPLE_CASE


DEMO_CASES_FILE = Path(__file__).resolve().parent.parent / "data" / "demo_cases.json"


@app.get("/api/demo-cases")
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


@app.post("/api/intake")
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


@app.post("/api/diagnose")
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

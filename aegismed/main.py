"""The web server — the front door of AegisMed.

Three routes:
  GET  /             the web page (static/index.html)
  GET  /health       simple "is it running?" check, used by Docker and judges
  POST /api/diagnose receives the patient case, runs the board, returns JSON
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import __version__, config, llm, orchestrator
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
    }


@app.get("/api/example-case")
async def example_case() -> dict:
    """The built-in sample case used by the 'Load example case' button."""
    return EXAMPLE_CASE


@app.post("/api/diagnose")
async def diagnose(case: PatientCase) -> dict:
    try:
        return await orchestrator.diagnose(
            age=case.age,
            sex=case.sex,
            symptoms=case.symptoms,
            history=case.history,
            labs=case.labs,
        )
    except llm.LLMError as err:
        raise HTTPException(status_code=502, detail=str(err)) from err

"""Configuration — reads settings from the .env file (or real environment variables).

Nothing here is AI-specific: it just answers three questions for the rest of the app:
  1. Which Google Cloud project/region should we call Vertex AI in (if any)?
  2. Which model should we ask for?
  3. Are we in demo mode (canned sample answers, no API calls, zero cost)?
"""

import os

from dotenv import load_dotenv

# Read the .env file in the project folder, if it exists.
load_dotenv()

# The GCP project Vertex AI calls are billed to. No API key: aegismed/llm.py
# authenticates with Application Default Credentials — the Cloud Run
# service's attached service account when deployed, or
# `gcloud auth application-default login` locally.
GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
GOOGLE_CLOUD_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1").strip()

# Google's Gemini model, served by Vertex AI. Swap via VERTEX_MODEL in .env —
# check the Vertex AI Model Garden / docs for the current model IDs available
# in your region.
VERTEX_MODEL: str = os.getenv("VERTEX_MODEL", "gemini-2.5-flash").strip()

_VERTEX_API_URL_TEMPLATE = (
    "https://{location}-aiplatform.googleapis.com/v1/projects/{project}"
    "/locations/{location}/publishers/google/models/{model}:generateContent"
)


def vertex_api_url() -> str:
    """The Vertex AI generateContent endpoint for the configured project/model."""
    return _VERTEX_API_URL_TEMPLATE.format(
        location=GOOGLE_CLOUD_LOCATION,
        project=GOOGLE_CLOUD_PROJECT,
        model=VERTEX_MODEL,
    )


def demo_mode() -> bool:
    """Decide whether to use canned sample answers instead of the real AI.

    DEMO_MODE=true  -> always demo
    DEMO_MODE=false -> always real AI
    DEMO_MODE=auto  -> demo only when no GOOGLE_CLOUD_PROJECT is configured
                       (the default)
    """
    setting = os.getenv("DEMO_MODE", "auto").strip().lower()
    if setting == "true":
        return True
    if setting == "false":
        return False
    return not GOOGLE_CLOUD_PROJECT


def specialist_selection() -> str:
    """How many specialists to convene per case.

    SPECIALIST_SELECTION=relevant -> run only the specialists the router picks
                                     as relevant (the default; saves model calls)
    SPECIALIST_SELECTION=all      -> always run the full board (e.g. for demos)
    """
    setting = os.getenv("SPECIALIST_SELECTION", "relevant").strip().lower()
    return "all" if setting == "all" else "relevant"


def rate_limit_per_minute() -> int:
    """Max requests per client IP per minute on the costly/mutating endpoints.

    RATE_LIMIT_PER_MINUTE=0 disables rate limiting entirely (e.g. local dev).
    """
    raw = os.getenv("RATE_LIMIT_PER_MINUTE", "20").strip()
    try:
        return int(raw)
    except ValueError:
        return 20


_DEFAULT_MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB


def max_request_body_bytes() -> int:
    """Max raw request body size in bytes, rejected before any JSON parsing.

    Pydantic's per-field max_length only applies AFTER Starlette has already
    read the whole body into memory, so it can't stop an oversized body from
    being buffered in the first place. This is checked earlier, by
    aegismed.bodylimit's ASGI middleware.
    """
    raw = os.getenv("MAX_REQUEST_BODY_BYTES", str(_DEFAULT_MAX_BODY_BYTES)).strip()
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_MAX_BODY_BYTES
    return value if value > 0 else _DEFAULT_MAX_BODY_BYTES

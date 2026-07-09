"""Configuration — reads settings from the .env file (or real environment variables).

Nothing here is AI-specific: it just answers three questions for the rest of the app:
  1. What is the Fireworks API key (if any)?
  2. Which model should we ask for?
  3. Are we in demo mode (canned sample answers, no API calls, zero cost)?
"""

import os

from dotenv import load_dotenv

# Read the .env file in the project folder, if it exists.
load_dotenv()

FIREWORKS_API_KEY: str = os.getenv("FIREWORKS_API_KEY", "").strip()

# Google's Gemma model hosted on Fireworks AI (running on AMD hardware).
# Swap via the MODEL variable in .env once launch-day models are confirmed.
MODEL: str = os.getenv("MODEL", "accounts/fireworks/models/gemma-3-27b-it").strip()

# The default managed endpoint: Fireworks AI, which serves Gemma on AMD Instinct
# MI300X GPUs — so out of the box every inference call already runs on AMD silicon.
FIREWORKS_API_URL: str = "https://api.fireworks.ai/inference/v1/chat/completions"

# OpenAI-compatible base URL for the chat model. Defaults to Fireworks. Set this
# to point AegisMed at ANY OpenAI-compatible server — e.g. Gemma self-hosted on an
# AMD Developer Cloud GPU instance via vLLM or Ollama (see docs/DEPLOY_AMD.md):
#     LLM_BASE_URL=http://<your-amd-instance>:8000/v1
# The value may include or omit a trailing "/chat/completions"; we normalize both.
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "").strip()


def chat_completions_url() -> str:
    """The full chat-completions URL to POST to.

    Uses LLM_BASE_URL when set (self-hosted / AMD Developer Cloud path), otherwise
    the default Fireworks endpoint. Accepts a base URL with or without the
    "/chat/completions" suffix and with or without a trailing slash.
    """
    base = LLM_BASE_URL or FIREWORKS_API_URL
    base = base.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"


def _int_env(name: str, default: int, minimum: int = 1) -> int:
    """Read an integer env var, falling back to `default` on missing/invalid."""
    try:
        return max(minimum, int(os.getenv(name, str(default)).strip()))
    except (ValueError, AttributeError):
        return default


# Read timeout for a single model call (seconds). Kept tight so no one upstream
# call can dominate the request budget. The board's critical path is 3 sequential
# calls, so this must stay well under REQUEST_TIMEOUT_SECONDS.
def llm_read_timeout() -> int:
    return _int_env("LLM_READ_TIMEOUT_SECONDS", 12)


# Overall wall-clock budget for one /api/diagnose (and teaching) request. The
# hackathon requires responses under 30s; we default to 28s and abort cleanly
# rather than silently exceed it.
def request_timeout() -> int:
    return _int_env("REQUEST_TIMEOUT_SECONDS", 28)


def demo_mode() -> bool:
    """Decide whether to use canned sample answers instead of the real AI.

    DEMO_MODE=true  -> always demo
    DEMO_MODE=false -> always real AI
    DEMO_MODE=auto  -> demo only when no API key is configured (the default)
    """
    setting = os.getenv("DEMO_MODE", "auto").strip().lower()
    if setting == "true":
        return True
    if setting == "false":
        return False
    return not FIREWORKS_API_KEY


def specialist_selection() -> str:
    """How many specialists to convene per case.

    SPECIALIST_SELECTION=relevant -> run only the specialists the router picks
                                     as relevant (the default; saves model calls)
    SPECIALIST_SELECTION=all      -> always run the full board (e.g. for demos)
    """
    setting = os.getenv("SPECIALIST_SELECTION", "relevant").strip().lower()
    return "all" if setting == "all" else "relevant"

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

FIREWORKS_API_URL: str = "https://api.fireworks.ai/inference/v1/chat/completions"

# Optional: a fine-tuned Fireworks model to use as the default "--finetuned"
# model in eval/compare_models.py (see docs/DATA_AND_EVAL.md "Comparing models").
FINETUNED_MODEL_DEFAULT: str = os.getenv("FINETUNED_MODEL", "").strip()


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

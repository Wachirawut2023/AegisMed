"""The single place where AegisMed talks to the AI model.

Every "agent" in this project is just one call to this function with a
different system prompt. We use the Fireworks AI API (the models run on AMD
hardware), which follows the same request format as the OpenAI chat API:
you send a list of messages, you get the model's reply back as text.
"""

import httpx

from . import config, demo_data


class LLMError(Exception):
    """Raised when the AI service cannot be reached or returns an error."""


async def chat(
    system_prompt: str, user_prompt: str, agent_name: str = "", model: str | None = None,
    max_tokens: int = 1024,
) -> str:
    """Send one question to the model and return its answer as plain text.

    In demo mode this returns pre-written sample output instead (zero cost,
    no API key needed) so the whole app can be tried and demonstrated offline.

    `model` lets a caller override which model/adapter handles this specific
    call (e.g. routing only the synthesis agent through a fine-tuned model
    while every other agent keeps using the base `config.MODEL`). Defaults
    to `config.MODEL` when not given.

    `max_tokens` may need raising for "reasoning" models, which write their
    visible chain-of-thought directly into the reply before their actual
    answer — cut off too early, `content` may be truncated mid-thought or
    (with some models) missing entirely.
    """
    if config.demo_mode():
        if agent_name == "intake":
            return demo_data.DEMO_INTAKE
        if agent_name == "synthesis":
            return demo_data.DEMO_SYNTHESIS
        return demo_data.DEMO_SPECIALIST_OPINIONS.get(
            agent_name,
            "Demo mode: no sample answer available for this agent.",
        )

    payload = {
        "model": model or config.MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,   # low = more focused, less "creative" — right for medicine
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {config.FIREWORKS_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                config.FIREWORKS_API_URL, json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
            # Some reasoning models omit `content` entirely if cut off before
            # finishing their visible chain-of-thought — degrade to "" rather
            # than KeyError, matching every caller's existing fail-open handling.
            return (data["choices"][0]["message"].get("content") or "").strip()
    except httpx.HTTPStatusError as err:
        raise LLMError(
            f"Fireworks AI returned an error ({err.response.status_code}). "
            "Check your FIREWORKS_API_KEY and MODEL in the .env file."
        ) from err
    except httpx.HTTPError as err:
        raise LLMError(f"Could not reach Fireworks AI: {err}") from err

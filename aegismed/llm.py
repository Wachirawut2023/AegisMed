"""The single place where AegisMed talks to the AI model.

Every "agent" in this project is just one call to this function with a
different system prompt. We use the Fireworks AI API (the models run on AMD
hardware), which follows the same request format as the OpenAI chat API:
you send a list of messages, you get the model's reply back as text.
"""

import asyncio
import random

import httpx

from . import config, demo_data


class LLMError(Exception):
    """Raised when the AI service cannot be reached or returns an error."""


# Retry transient failures (server errors, rate limits, connection blips) with
# exponential backoff + jitter. A 4xx other than 429 means the request itself
# is bad (auth, payload) — retrying it would just fail the same way again, so
# those raise immediately instead of burning attempts.
_MAX_ATTEMPTS = 3
_BASE_DELAY_SECONDS = 1.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_retryable(err: httpx.HTTPError) -> bool:
    if isinstance(err, httpx.HTTPStatusError):
        return err.response.status_code in _RETRYABLE_STATUS_CODES
    return True  # connection errors, timeouts, etc. are always worth a retry


async def chat(system_prompt: str, user_prompt: str, agent_name: str = "") -> str:
    """Send one question to the model and return its answer as plain text.

    In demo mode this returns pre-written sample output instead (zero cost,
    no API key needed) so the whole app can be tried and demonstrated offline.

    Transient failures (rate limits, server errors, dropped connections) are
    retried with exponential backoff before giving up.
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
        "model": config.MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,   # low = more focused, less "creative" — right for medicine
        "max_tokens": 1024,
    }
    headers = {
        "Authorization": f"Bearer {config.FIREWORKS_API_KEY}",
        "Content-Type": "application/json",
    }

    last_err: httpx.HTTPError | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    config.FIREWORKS_API_URL, json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPError as err:
            last_err = err
            if not _is_retryable(err) or attempt == _MAX_ATTEMPTS - 1:
                break
            delay = _BASE_DELAY_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)
        except (KeyError, IndexError, TypeError) as err:
            # The API returned 200 but not the shape we expect — not worth
            # retrying since a malformed response won't self-correct.
            raise LLMError(f"Fireworks AI returned an unexpected response shape: {err}") from err

    if isinstance(last_err, httpx.HTTPStatusError):
        raise LLMError(
            f"Fireworks AI returned an error ({last_err.response.status_code}). "
            "Check your FIREWORKS_API_KEY and MODEL in the .env file."
        ) from last_err
    raise LLMError(f"Could not reach Fireworks AI: {last_err}") from last_err

"""The single place where AegisMed talks to the AI model.

Every "agent" in this project is just one call to this function with a
different system prompt. We use the Fireworks AI API (the models run on AMD
hardware), which follows the same request format as the OpenAI chat API:
you send a list of messages, you get the model's reply back as text.
"""

import asyncio

import httpx

from . import config, demo_data


class LLMError(Exception):
    """Raised when the AI service cannot be reached or returns an error."""


# Transient failures worth retrying: rate limiting and server-side errors.
# Anything else (400/401/404/422 etc.) is a config/auth problem that a retry
# can never fix, so those raise immediately.
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 3          # 1 initial try + 2 retries
_BACKOFF_SECONDS = [1, 3]  # delay before attempt 2, then before attempt 3


async def chat(
    system_prompt: str,
    user_prompt: str,
    agent_name: str = "",
    *,
    max_tokens: int = 1024,
    temperature: float = 0.4,
) -> str:
    """Send one question to the model and return its answer as plain text.

    In demo mode this returns pre-written sample output instead (zero cost,
    no API key needed) so the whole app can be tried and demonstrated offline.

    Transient failures (rate limits, 5xx, connection/timeout errors) are
    retried with a short backoff; auth/validation errors are not, since
    retrying those can never succeed.
    """
    if config.demo_mode():
        if agent_name == "intake":
            return demo_data.DEMO_INTAKE
        if agent_name == "draft_synthesis":
            return demo_data.DEMO_DRAFT_SYNTHESIS
        if agent_name == "final_synthesis":
            return demo_data.DEMO_SYNTHESIS
        if agent_name.startswith("peer_review:"):
            specialty = agent_name.split(":", 1)[1]
            return demo_data.DEMO_PEER_REVIEW.get(
                specialty, "Demo mode: no sample rebuttal available for this agent.",
            )
        if agent_name == "followup":
            return demo_data.DEMO_FOLLOWUP_ANSWER
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
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    headers = {
        "Authorization": f"Bearer {config.FIREWORKS_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    config.FIREWORKS_API_URL, json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as err:
            if err.response.status_code not in _RETRYABLE_STATUS or attempt == _MAX_ATTEMPTS:
                raise LLMError(
                    f"Fireworks AI returned an error ({err.response.status_code}). "
                    "Check your FIREWORKS_API_KEY and MODEL in the .env file."
                ) from err
        except httpx.HTTPError as err:
            if attempt == _MAX_ATTEMPTS:
                raise LLMError(f"Could not reach Fireworks AI: {err}") from err
        await asyncio.sleep(_BACKOFF_SECONDS[attempt - 1])

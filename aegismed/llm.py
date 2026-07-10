"""The single place where AegisMed talks to the AI model.

Every "agent" in this project is just one call to this function with a
different system prompt. The default is the Fireworks AI API (the models run
on AMD hardware), which follows the same request format as the OpenAI chat
API: you send a list of messages, you get the model's reply back as text.
LLM_API_URL can point this at any OpenAI-compatible endpoint instead (e.g. a
self-hosted vLLM server), with an optional fallback endpoint for resilience.
"""

import httpx

from . import config, demo_data


class LLMError(Exception):
    """Raised when the AI service cannot be reached or returns an error."""


async def _call(url: str, model: str, key: str, system_prompt: str, user_prompt: str) -> str:
    """POST one chat-completion request to an OpenAI-compatible endpoint."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,   # low = more focused, less "creative" — right for medicine
        "max_tokens": 1024,
    }
    headers = {"Content-Type": "application/json"}
    # Self-hosted endpoints (e.g. vLLM with no --api-key) don't require this
    # header at all; only send it when there's actually a key to send.
    if key:
        headers["Authorization"] = f"Bearer {key}"

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as err:
        raise LLMError(
            f"{url} returned an error ({err.response.status_code}) for model {model}."
        ) from err
    except httpx.HTTPError as err:
        raise LLMError(f"Could not reach {url}: {err}") from err


async def chat(system_prompt: str, user_prompt: str, agent_name: str = "", api_key: str = "") -> str:
    """Send one question to the model and return its answer as plain text.

    In demo mode this returns pre-written sample output instead (zero cost,
    no API key needed) so the whole app can be tried and demonstrated offline.

    If api_key is provided, use it instead of the server's default FIREWORKS_API_KEY.

    If the primary call (LLM_API_URL/MODEL) fails and FALLBACK_MODEL is set,
    retries once against the fallback endpoint before giving up — e.g. a
    serverless Fireworks model as a safety net behind a self-hosted primary
    that might be down or still cold-starting.
    """
    if config.demo_mode(api_key):
        if agent_name == "intake":
            return demo_data.DEMO_INTAKE
        if agent_name == "synthesis":
            return demo_data.DEMO_SYNTHESIS
        return demo_data.DEMO_SPECIALIST_OPINIONS.get(
            agent_name,
            "Demo mode: no sample answer available for this agent.",
        )

    # Use provided API key, or fall back to server's default
    key_to_use = (api_key or config.FIREWORKS_API_KEY).strip()

    try:
        return await _call(config.LLM_API_URL, config.MODEL, key_to_use, system_prompt, user_prompt)
    except LLMError as primary_err:
        if not config.FALLBACK_MODEL:
            raise
        try:
            return await _call(
                config.FALLBACK_API_URL, config.FALLBACK_MODEL, config.FALLBACK_API_KEY,
                system_prompt, user_prompt,
            )
        except LLMError as fallback_err:
            raise LLMError(
                f"Primary model failed ({primary_err}); fallback also failed ({fallback_err})."
            ) from fallback_err

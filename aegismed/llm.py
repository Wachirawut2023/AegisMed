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


# Short calls (triage/intake/records lookup) return small JSON or Q&A text, so a
# tight token cap keeps them fast without hurting quality. The reasoning agents
# (specialists, synthesis) get the full budget for a complete answer.
_SHORT_CALL_AGENTS = {"retrieval", "intake", "auto_answer"}
_SHORT_MAX_TOKENS = 512
_FULL_MAX_TOKENS = 1024


async def chat(system_prompt: str, user_prompt: str, agent_name: str = "") -> str:
    """Send one question to the model and return its answer as plain text.

    In demo mode this returns pre-written sample output instead (zero cost,
    no API key needed) so the whole app can be tried and demonstrated offline.

    Talks to any OpenAI-compatible chat endpoint (config.chat_completions_url()):
    Fireworks AI by default (Gemma on AMD Instinct MI300X), or a self-hosted Gemma
    on an AMD Developer Cloud GPU via LLM_BASE_URL. See docs/DEPLOY_AMD.md.
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

    max_tokens = _SHORT_MAX_TOKENS if agent_name in _SHORT_CALL_AGENTS else _FULL_MAX_TOKENS
    payload = {
        "model": config.MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,   # low = more focused, less "creative" — right for medicine
        "max_tokens": max_tokens,
    }
    headers = {"Content-Type": "application/json"}
    # Send the bearer token only when we have one. A self-hosted vLLM/Ollama server
    # on AMD Developer Cloud typically needs no key, while Fireworks requires it.
    if config.FIREWORKS_API_KEY:
        headers["Authorization"] = f"Bearer {config.FIREWORKS_API_KEY}"

    # Tight timeouts so no single call can blow the request's sub-30s budget.
    timeout = httpx.Timeout(config.llm_read_timeout(), connect=5.0)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                config.chat_completions_url(), json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except httpx.HTTPStatusError as err:
        raise LLMError(
            f"The model endpoint returned an error ({err.response.status_code}). "
            "Check your FIREWORKS_API_KEY / LLM_BASE_URL and MODEL in the .env file."
        ) from err
    except httpx.HTTPError as err:
        raise LLMError(f"Could not reach the model endpoint: {err}") from err

"""Unit tests for the LLM client layer (aegismed/llm.py).

Demo mode is deterministic and network-free (already touched indirectly by
other test files); the real Fireworks HTTP path is exercised here with a
scripted fake `httpx.AsyncClient` so no test ever makes a real network call.
"""

import httpx
import pytest

from aegismed import demo_data, llm

pytestmark = pytest.mark.anyio


class _ScriptedAsyncClient:
    """Stand-in for httpx.AsyncClient: returns/raises whatever it's given."""

    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self._exc is not None:
            raise self._exc
        return self._response


def _patch_client(monkeypatch, **kwargs) -> _ScriptedAsyncClient:
    fake_client = _ScriptedAsyncClient(**kwargs)
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda *a, **kw: fake_client)
    return fake_client


# --- demo mode --------------------------------------------------------------


async def test_chat_demo_mode_returns_canned_intake(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    text = await llm.chat("system", "user", agent_name="intake")
    assert text == demo_data.DEMO_INTAKE


async def test_chat_demo_mode_returns_canned_synthesis(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    text = await llm.chat("system", "user", agent_name="synthesis")
    assert text == demo_data.DEMO_SYNTHESIS


async def test_chat_demo_mode_returns_canned_specialist_opinion(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    text = await llm.chat("system", "user", agent_name="Cardiology")
    assert text == demo_data.DEMO_SPECIALIST_OPINIONS["Cardiology"]


async def test_chat_demo_mode_unknown_agent_falls_back(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    text = await llm.chat("system", "user", agent_name="not-a-real-agent")
    assert text == "Demo mode: no sample answer available for this agent."


# --- real Fireworks call path -----------------------------------------------


async def test_chat_real_success_sends_messages_and_strips_reply(monkeypatch):
    request = httpx.Request("POST", "https://api.fireworks.ai/inference/v1/chat/completions")
    response = httpx.Response(
        200,
        request=request,
        json={"choices": [{"message": {"content": "  Likely Fabry disease.  "}}]},
    )
    fake_client = _patch_client(monkeypatch, response=response)
    monkeypatch.setenv("DEMO_MODE", "false")

    result = await llm.chat("system prompt", "user prompt", agent_name="Cardiology")

    assert result == "Likely Fabry disease."
    assert len(fake_client.calls) == 1
    sent = fake_client.calls[0]["json"]
    assert sent["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "user prompt"},
    ]


async def test_chat_http_status_error_raises_llmerror_with_status_code(monkeypatch):
    request = httpx.Request("POST", "https://api.fireworks.ai/inference/v1/chat/completions")
    response = httpx.Response(500, request=request, text="internal error")
    _patch_client(monkeypatch, response=response)
    monkeypatch.setenv("DEMO_MODE", "false")

    with pytest.raises(llm.LLMError, match="500"):
        await llm.chat("system", "user")


async def test_chat_network_error_raises_llmerror(monkeypatch):
    _patch_client(monkeypatch, exc=httpx.ConnectError("connection refused"))
    monkeypatch.setenv("DEMO_MODE", "false")

    with pytest.raises(llm.LLMError, match="Could not reach Fireworks AI"):
        await llm.chat("system", "user")

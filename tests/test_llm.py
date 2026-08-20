"""Unit tests for the LLM client layer (aegismed/llm.py).

Demo mode is deterministic and network-free (already touched indirectly by
other test files); the real Fireworks HTTP path is exercised here with a
scripted fake `httpx.AsyncClient` so no test ever makes a real network call.
"""

import httpx
import pytest

from aegismed import demo_data, llm

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    """Retry backoff would otherwise add real multi-second delays to tests."""
    async def instant_sleep(_seconds):
        return None

    monkeypatch.setattr(llm.asyncio, "sleep", instant_sleep)


class _ScriptedAsyncClient:
    """Stand-in for httpx.AsyncClient: returns/raises whatever it's given.

    Each call to `post()` pops the next entry from a queue of responses/
    exceptions (a single value repeats forever, for the "always fails" case).
    """

    def __init__(self, response=None, exc=None, sequence=None):
        self._sequence = list(sequence) if sequence is not None else None
        self._response = response
        self._exc = exc
        self.calls: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self._sequence is not None:
            outcome = self._sequence.pop(0) if len(self._sequence) > 1 else self._sequence[0]
        elif self._exc is not None:
            outcome = self._exc
        else:
            outcome = self._response
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _patch_client(monkeypatch, **kwargs) -> _ScriptedAsyncClient:
    fake_client = _ScriptedAsyncClient(**kwargs)
    monkeypatch.setattr(llm.httpx, "AsyncClient", lambda *a, **kw: fake_client)
    return fake_client


def _response(status: int, **kwargs) -> httpx.Response:
    request = httpx.Request("POST", "https://api.fireworks.ai/inference/v1/chat/completions")
    return httpx.Response(status, request=request, **kwargs)


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
    fake_client = _patch_client(monkeypatch, response=_response(500, text="internal error"))
    monkeypatch.setenv("DEMO_MODE", "false")

    with pytest.raises(llm.LLMError, match="500"):
        await llm.chat("system", "user")

    # A 500 is retryable, so it should have exhausted every attempt.
    assert len(fake_client.calls) == llm._MAX_ATTEMPTS


async def test_chat_network_error_raises_llmerror(monkeypatch):
    fake_client = _patch_client(monkeypatch, exc=httpx.ConnectError("connection refused"))
    monkeypatch.setenv("DEMO_MODE", "false")

    with pytest.raises(llm.LLMError, match="Could not reach Fireworks AI"):
        await llm.chat("system", "user")

    assert len(fake_client.calls) == llm._MAX_ATTEMPTS


# --- retry / backoff ----------------------------------------------------------


async def test_chat_retries_server_error_then_succeeds(monkeypatch):
    ok = _response(200, json={"choices": [{"message": {"content": "Fabry disease."}}]})
    fake_client = _patch_client(monkeypatch, sequence=[_response(503, text="busy"), ok])
    monkeypatch.setenv("DEMO_MODE", "false")

    result = await llm.chat("system", "user")

    assert result == "Fabry disease."
    assert len(fake_client.calls) == 2


async def test_chat_retries_network_error_then_succeeds(monkeypatch):
    ok = _response(200, json={"choices": [{"message": {"content": "ok"}}]})
    fake_client = _patch_client(
        monkeypatch, sequence=[httpx.ConnectError("connection refused"), ok]
    )
    monkeypatch.setenv("DEMO_MODE", "false")

    result = await llm.chat("system", "user")

    assert result == "ok"
    assert len(fake_client.calls) == 2


async def test_chat_does_not_retry_client_error(monkeypatch):
    fake_client = _patch_client(monkeypatch, response=_response(401, text="bad key"))
    monkeypatch.setenv("DEMO_MODE", "false")

    with pytest.raises(llm.LLMError, match="401"):
        await llm.chat("system", "user")

    # 401 (auth) won't fix itself on retry, so only one attempt should be made.
    assert len(fake_client.calls) == 1


async def test_chat_raises_llmerror_on_malformed_response_without_retry(monkeypatch):
    malformed = _response(200, json={"unexpected": "shape"})
    fake_client = _patch_client(monkeypatch, response=malformed)
    monkeypatch.setenv("DEMO_MODE", "false")

    with pytest.raises(llm.LLMError, match="unexpected response shape"):
        await llm.chat("system", "user")

    assert len(fake_client.calls) == 1

"""Unit tests for the request-body-size ASGI middleware (aegismed/bodylimit.py).

Uses a bare hand-rolled downstream ASGI app rather than the real FastAPI app,
so these exercise the middleware's own logic in isolation:
  - the Content-Length fast path builds and sends its own 413 response
    (there's no ExceptionMiddleware in this synthetic stack to do it for us)
  - the streaming fallback raises HTTPException, which a bare app doesn't
    catch either — so the test catches it directly.
The full-stack version (a real oversized POST against the real app, letting
FastAPI's ExceptionMiddleware convert that HTTPException into an actual 413
HTTP response) is covered in test_main.py.
"""

import pytest
from fastapi import HTTPException

from aegismed.bodylimit import MaxBodySizeMiddleware

pytestmark = pytest.mark.anyio


async def _echo_app(scope, receive, send):
    """Reads the whole body, then responds 200 with the byte count."""
    body = b""
    more_body = True
    while more_body:
        message = await receive()
        body += message.get("body", b"")
        more_body = message.get("more_body", False)
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": str(len(body)).encode()})


def _http_scope(content_length: int | None) -> dict:
    headers = []
    if content_length is not None:
        headers.append((b"content-length", str(content_length).encode()))
    return {"type": "http", "headers": headers}


def _receive_from(chunks: list[bytes]):
    """A receive() that yields one http.request message per chunk."""
    remaining = list(chunks)

    async def receive():
        body = remaining.pop(0) if remaining else b""
        return {"type": "http.request", "body": body, "more_body": bool(remaining)}

    return receive


class _Collector:
    def __init__(self):
        self.messages = []

    async def __call__(self, message):
        self.messages.append(message)


async def test_rejects_declared_oversized_body_without_calling_downstream(monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "100")
    called = False

    async def _should_not_run(scope, receive, send):
        nonlocal called
        called = True

    middleware = MaxBodySizeMiddleware(_should_not_run)
    send = _Collector()
    await middleware(_http_scope(content_length=1000), _receive_from([b"x" * 1000]), send)

    assert called is False
    assert send.messages[0]["status"] == 413


async def test_allows_body_within_limit(monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "100")
    middleware = MaxBodySizeMiddleware(_echo_app)
    send = _Collector()

    await middleware(_http_scope(content_length=10), _receive_from([b"x" * 10]), send)

    assert send.messages[0]["status"] == 200
    assert send.messages[1]["body"] == b"10"


async def test_rejects_understated_content_length_mid_stream(monkeypatch):
    """Content-Length lied (or was absent) — the streaming cap still catches it."""
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "10")
    middleware = MaxBodySizeMiddleware(_echo_app)
    send = _Collector()

    # No Content-Length header at all, but the actual stream exceeds the cap.
    with pytest.raises(HTTPException) as exc_info:
        await middleware(_http_scope(content_length=None), _receive_from([b"x" * 5, b"y" * 20]), send)

    assert exc_info.value.status_code == 413


async def test_malformed_content_length_header_falls_back_to_streaming_check(monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "100")
    scope = {"type": "http", "headers": [(b"content-length", b"not-a-number")]}
    middleware = MaxBodySizeMiddleware(_echo_app)
    send = _Collector()

    await middleware(scope, _receive_from([b"x" * 10]), send)

    assert send.messages[0]["status"] == 200


async def test_non_http_scope_passes_through_untouched(monkeypatch):
    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "1")
    called_with = {}

    async def _lifespan_app(scope, receive, send):
        called_with["scope"] = scope

    middleware = MaxBodySizeMiddleware(_lifespan_app)
    await middleware({"type": "lifespan"}, _receive_from([]), _Collector())

    assert called_with["scope"] == {"type": "lifespan"}

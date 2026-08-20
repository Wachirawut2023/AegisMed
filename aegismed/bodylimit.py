"""Reject oversized request bodies before FastAPI/Pydantic ever reads them.

Pydantic's per-field `max_length` only validates AFTER Starlette has already
buffered the entire request body into memory — so a client sending a huge
body still costs memory and CPU regardless of how tightly any individual
field is bounded. This is a plain ASGI middleware (not Starlette's
BaseHTTPMiddleware, which buffers the whole body itself before your code
ever sees it) so it can reject a declared-oversized body immediately, and
cut off an actual oversized one mid-stream even if Content-Length was
absent or understated.
"""

from fastapi import HTTPException

from . import config


class MaxBodySizeMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        max_bytes = config.max_request_body_bytes()

        # Fast path: the client declared an oversized body up front. Reject
        # here, before self.app() is even entered, so we must build the ASGI
        # response ourselves — there's no route/ExceptionMiddleware downstream
        # yet to hand an HTTPException to.
        headers = dict(scope.get("headers") or [])
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared = int(content_length)
            except ValueError:
                declared = None
            if declared is not None and declared > max_bytes:
                await self._reject(send)
                return

        # Slow path: cap the actual bytes read, in case Content-Length was
        # missing or understated. This raises from inside request body
        # parsing (deep within self.app()), where FastAPI's ExceptionMiddleware
        # is still on the call stack and turns an HTTPException into a
        # proper 413 response for us — so no manual response-building here.
        total = 0

        async def guarded_receive():
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > max_bytes:
                    raise HTTPException(status_code=413, detail="Request body too large.")
            return message

        await self.app(scope, guarded_receive, send)

    @staticmethod
    async def _reject(send):
        await send({
            "type": "http.response.start",
            "status": 413,
            "headers": [(b"content-type", b"application/json")],
        })
        await send({
            "type": "http.response.body",
            "body": b'{"detail":"Request body too large."}',
        })

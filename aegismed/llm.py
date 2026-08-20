"""The single place where AegisMed talks to the AI model.

Every "agent" in this project is just one call to this function with a
different system prompt. We use Vertex AI's Gemini API — Google Cloud's
managed, pay-per-token model hosting, called over the same chat-style
request/response shape every agent already expected. Authentication is
Application Default Credentials, not an API key: on Cloud Run the service's
attached service account handles it automatically; locally,
`gcloud auth application-default login` does it once.
"""

import asyncio
import random
import threading

import google.auth
import google.auth.exceptions
import google.auth.transport.requests
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

_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

# google-auth's Credentials object caches its token and knows when it's
# expired, so we keep one process-wide instance instead of re-authenticating
# on every call. Guarded by a lock since refresh() mutates it and multiple
# requests can be in flight (each handled via asyncio.to_thread) at once.
_credentials_lock = threading.Lock()
_credentials: "google.auth.credentials.Credentials | None" = None


def _get_access_token() -> str:
    """Return a valid OAuth2 access token via Application Default Credentials.

    Blocking (does I/O and, on first use, a filesystem/metadata-server
    lookup), so callers must run it off the event loop — see
    asyncio.to_thread below.
    """
    global _credentials
    with _credentials_lock:
        if _credentials is None:
            _credentials, _ = google.auth.default(scopes=_SCOPES)
        if not _credentials.valid:
            _credentials.refresh(google.auth.transport.requests.Request())
        return _credentials.token


def _is_retryable(err: httpx.HTTPError) -> bool:
    if isinstance(err, httpx.HTTPStatusError):
        return err.response.status_code in _RETRYABLE_STATUS_CODES
    return True  # connection errors, timeouts, etc. are always worth a retry


async def chat(system_prompt: str, user_prompt: str, agent_name: str = "") -> str:
    """Send one question to the model and return its answer as plain text.

    In demo mode this returns pre-written sample output instead (zero cost,
    no Google Cloud project needed) so the whole app can be tried and
    demonstrated offline.

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

    try:
        access_token = await asyncio.to_thread(_get_access_token)
    except google.auth.exceptions.GoogleAuthError as err:
        raise LLMError(
            f"Could not get Google Cloud credentials: {err}. Run "
            "`gcloud auth application-default login` locally, or deploy to "
            "Cloud Run, where the attached service account handles this "
            "automatically (make sure it has the roles/aiplatform.user role)."
        ) from err

    payload = {
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "generationConfig": {
            "temperature": 0.4,  # low = more focused, less "creative" — right for medicine
            "maxOutputTokens": 1024,
        },
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    last_err: httpx.HTTPError | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.post(
                    config.vertex_api_url(), json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except httpx.HTTPError as err:
            last_err = err
            if not _is_retryable(err) or attempt == _MAX_ATTEMPTS - 1:
                break
            delay = _BASE_DELAY_SECONDS * (2 ** attempt) + random.uniform(0, 0.5)
            await asyncio.sleep(delay)
        except (KeyError, IndexError, TypeError) as err:
            # The API returned 200 but not the shape we expect — not worth
            # retrying since a malformed response won't self-correct.
            raise LLMError(f"Vertex AI returned an unexpected response shape: {err}") from err

    if isinstance(last_err, httpx.HTTPStatusError):
        raise LLMError(
            f"Vertex AI returned an error ({last_err.response.status_code}). "
            "Check GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION, and "
            "VERTEX_MODEL in the .env file, and that the calling identity "
            "has the roles/aiplatform.user IAM role."
        ) from last_err
    raise LLMError(f"Could not reach Vertex AI: {last_err}") from last_err

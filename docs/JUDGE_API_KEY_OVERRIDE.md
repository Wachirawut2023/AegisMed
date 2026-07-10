# Judge API Key Override

## Overview

AegisMed supports **optional per-user API key override**, allowing judges and users to provide their own Fireworks AI API keys if they prefer to use their own credits instead of the shared server key.

## Use Cases

1. **Hackathon judges with own Fireworks accounts** — Use personal credits instead of depleting the shared pool
2. **Cost control** — Track charges separately per judge
3. **Fallback flexibility** — If the shared key runs out or has issues, individual judges can still run the board

## How It Works

### Default Behavior (Recommended)

By default, the server uses the shared `FIREWORKS_API_KEY` from `.env`:

```bash
docker compose up --build
# All users/judges use the shared key automatically
```

**Advantages:**
- ✅ No credential management needed
- ✅ No security risk to individual judges
- ✅ Simple deployment
- ✅ One centralized cost center

### Optional: Judge-Provided API Key

Judges can optionally provide their own Fireworks API key via the web UI:

1. Open AegisMed in the browser (http://localhost:8000)
2. Scroll to **"🔑 Use your own Fireworks API key (optional)"** section
3. Enter your Fireworks API key (starts with `fw_`)
4. Click **"Convene the board"**

**⚠️ Security Considerations:**

- Your API key will be transmitted over the network — use HTTPS in production
- The key is included in API request bodies (not ideal, but encrypted by TLS)
- It may appear in server logs (ask administrators about their logging policy)
- Do not share screenshots or logs that contain API keys
- **Recommendation:** Only use this in a trusted environment (local testing, private hackathon, etc.)

## API Integration

### Request Format

Include `api_key` in the JSON payload when calling the API directly:

```bash
curl -X POST http://localhost:8000/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "symptoms": "Fatigue and shortness of breath",
    "history": "...",
    "labs": "...",
    "api_key": "fw_your_key_here"
  }'
```

### Endpoints Supporting API Key Override

- `POST /api/intake` — Intake questions
- `POST /api/diagnose` — Full board diagnosis
- `POST /api/teaching/case` — Teaching mode with comparison
- `POST /api/cases/save` — Save a case (uses the API key from the case data)

### Fallback Behavior

If `api_key` is empty or not provided:
- **Default:** Uses the server's `FIREWORKS_API_KEY` from `.env`
- **Demo mode:** Uses pre-written sample output (no API calls)

## Implementation Details

### Backend Flow

1. Each API request includes optional `api_key` field in the `PatientCase` model
2. The API endpoints thread this key through to `orchestrator.diagnose()`
3. The orchestrator passes it to `llm.chat()` for each specialist
4. `llm.chat()` uses the provided key if present, otherwise falls back to `config.FIREWORKS_API_KEY`

### File Changes

- `aegismed/llm.py` — `chat()` now accepts optional `api_key` parameter
- `aegismed/intake.py` — `gather_questions()` passes `api_key` through
- `aegismed/orchestrator.py` — `diagnose()` threads `api_key` to all specialist calls
- `aegismed/main.py` — `PatientCase` model now has `api_key` field
- `static/index.html` — New collapsible section to enter personal API key with warnings

## For Hackathon Judges

### Option A: Use Shared Server Key (Recommended)

```bash
# Just run the Docker container — no setup needed
docker compose up --build
open http://localhost:8000
```

Charges go to the organizer's Fireworks account. Nothing to set up.

### Option B: Use Your Own API Key

1. [Sign up for Fireworks AI](https://fireworks.ai) and get an API key
2. Run the server (as above)
3. In the web UI, click **"🔑 Use your own Fireworks API key"**
4. Paste your key and click **"Convene the board"**

Charges go to your own Fireworks account.

## Security Best Practices

1. **HTTPS only** — Never send API keys over unencrypted HTTP
2. **Trusted networks** — Only use personal keys in environments you trust
3. **Temporary use** — If using a personal key, disable it after the hackathon/session
4. **Don't log keys** — Check your server's logging policy
5. **Prefer shared keys** — For production deployments, use the server's centralized key

## Troubleshooting

**"API key rejected" or "Invalid API key" errors:**
- Check that your key starts with `fw_`
- Verify the key hasn't expired or been revoked on Fireworks' dashboard
- Ensure there are no extra spaces or line breaks in the key

**"Rate limited" or API errors:**
- If using a shared key with many judges, you may hit rate limits
- Individual judges can switch to personal keys to avoid this
- Contact Fireworks support if issues persist

**"No space left on device" or model load failures:**
- These are server-side issues, not related to API key selection
- Contact the hackathon administrators

## See Also

- [`docs/API.md`](API.md) — Full API integration guide
- [`README.md`](../README.md) — Project overview and deployment
- [Fireworks AI](https://fireworks.ai) — Sign up for your own account

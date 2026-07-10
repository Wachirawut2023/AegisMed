# Deploying AegisMed: Firebase Hosting (frontend) + Cloud Run (backend)

Firebase Hosting only serves static files — it cannot hold your Fireworks
API key or run the Python backend. So this deployment splits AegisMed into
two pieces that judges access as a single seamless web app:

```
Judges' browser
      │
      ▼
Firebase Hosting  (static/index.html — public, no secrets)
      │  fetch("https://aegismed-xxxxx.run.app/api/diagnose")
      ▼
Cloud Run          (FastAPI backend — holds FIREWORKS_API_KEY)
      │
      ▼
Fireworks AI (Gemma model)
```

Judges only ever see the Firebase Hosting URL. They never see or need an
API key — the backend on Cloud Run holds the shared key and makes all
Fireworks calls on their behalf.

## Prerequisites

- A Google account (Firebase and Cloud Run are both Google Cloud products)
- `gcloud` CLI installed: https://cloud.google.com/sdk/docs/install
- `firebase` CLI installed: `npm install -g firebase-tools`
- Your Fireworks API key

## Step 1 — Deploy the backend to Cloud Run

From the repo root:

```bash
gcloud auth login
gcloud config set project YOUR_GCP_PROJECT_ID

gcloud run deploy aegismed \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars FIREWORKS_API_KEY=fw_your_key_here,DEMO_MODE=false
```

`--source .` builds the existing `Dockerfile` and deploys it — no extra
build config needed. `--allow-unauthenticated` lets judges' browsers reach
it without a Google-account login prompt.

When it finishes, note the service URL it prints, e.g.:

```
Service URL: https://aegismed-abc123-uc.a.run.app
```

Verify it's alive:

```bash
curl https://aegismed-abc123-uc.a.run.app/health
```

You should see `{"status":"ok", "demo_mode": false, ...}`.

### Restricting CORS (recommended once you know your Firebase URL)

By default the backend allows any origin (`ALLOWED_ORIGINS=*`). Once you've
deployed the frontend in Step 3 and know its URL, lock CORS down to just
that origin so no other site can call your backend and spend your Fireworks
credits:

```bash
gcloud run services update aegismed \
  --region us-central1 \
  --set-env-vars ALLOWED_ORIGINS=https://YOUR-PROJECT.web.app,https://YOUR-PROJECT.firebaseapp.com
```

(Firebase Hosting gives you both a `.web.app` and `.firebaseapp.com` URL for
the same site — include both.)

## Step 2 — Point the frontend at the backend

Edit `static/index.html` and set `API_BASE` to the Cloud Run URL from Step 1
(search for `const API_BASE = ""`):

```javascript
const API_BASE = "https://aegismed-abc123-uc.a.run.app";
```

Leave it as `""` only if frontend and backend share the same origin (e.g.
plain Docker/local runs) — in that case relative `/api/...` paths already
work and no change is needed.

## Step 3 — Deploy the frontend to Firebase Hosting

```bash
firebase login
firebase use --add          # pick/create your Firebase project
firebase deploy --only hosting
```

`firebase.json` (already in the repo) points Hosting at the `static/`
folder — no build step, no separate `public/` copy needed.

Firebase prints your live URL, e.g.:

```
Hosting URL: https://your-project.web.app
```

**Give this URL to judges.** That's the whole prototype — no setup, no API
key, no Docker required on their end.

## Step 4 — Lock down CORS (if you skipped it in Step 1)

Now that you have the Firebase URL, go back and run the
`gcloud run services update ... ALLOWED_ORIGINS=...` command from Step 1 so
only your frontend can call the backend.

## Updating after a code change

```bash
# Backend changed (aegismed/*.py):
gcloud run deploy aegismed --source . --region us-central1

# Frontend changed (static/index.html):
firebase deploy --only hosting
```

Each redeploy reuses the same URLs — nothing judges have bookmarked breaks.

## Cost control

- Cloud Run bills per request/compute-time, not per idle hour — a hackathon
  demo weekend costs cents to a few dollars.
- Fireworks charges are the same as any other deployment: shared key, shared
  bill. Judges never enter their own key unless you point them at the
  optional field (see `docs/JUDGE_API_KEY_OVERRIDE.md`).
- Set a Cloud Run max-instances cap to bound worst-case cost:
  ```bash
  gcloud run services update aegismed --region us-central1 --max-instances=3
  ```

## Troubleshooting

**Judges see "Failed to fetch" / network error in the browser console:**
- Check `API_BASE` in `static/index.html` matches your actual Cloud Run URL exactly (no trailing slash).
- Check CORS: open browser dev tools → Network tab → look for a CORS error. If present, verify `ALLOWED_ORIGINS` on Cloud Run includes your exact Firebase URL (both `.web.app` and `.firebaseapp.com`).

**Backend returns 502 "Fireworks AI returned an error":**
- Your Fireworks credits may be depleted — check https://fireworks.ai/account
- Verify the env var made it through: `gcloud run services describe aegismed --region us-central1 --format="value(spec.template.spec.containers[0].env)"`

**Cloud Run deploy fails with a build error:**
- Make sure you're running the command from the repo root (where `Dockerfile` lives).
- Check `gcloud builds log` for the failing build ID it prints.

## See Also

- [`docs/JUDGE_API_KEY_OVERRIDE.md`](JUDGE_API_KEY_OVERRIDE.md) — letting judges optionally use their own Fireworks key instead of the shared one
- [`docs/API.md`](API.md) — API reference
- [Cloud Run docs](https://cloud.google.com/run/docs)
- [Firebase Hosting docs](https://firebase.google.com/docs/hosting)

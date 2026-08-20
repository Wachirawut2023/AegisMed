# 🚀 Portfolio deployment — Firebase + Cloud Run + Vertex AI (scale-to-zero)

This is a *second* deployment target, added after the hackathon, for showing
AegisMed as a live portfolio piece without paying for an always-on server.
It does not replace the hackathon story in the main [README](../README.md) —
that submission ran on AMD Developer Cloud with Fireworks AI (Gemma on AMD
hardware), and that history stays as-is. This doc covers where the **public
demo link** lives now, which since this migration runs entirely on Google
Cloud: Vertex AI for inference, Cloud Run for the app, Firebase for the
frontend.

## The one insight that makes this free-when-idle

People assume "the model" means a GPU instance you have to keep running.
**It doesn't, here.** Look at `aegismed/llm.py`: every AI call in AegisMed is
an HTTP request to Vertex AI's Gemini API — a *fully managed*, pay-per-token
endpoint. There is no GPU box of yours to leave running, so there is nothing
to "drain your money" on that side no matter how AegisMed is deployed.

The only thing that actually runs continuously — and could cost money 24/7
— is the small FastAPI container in this repo (`aegismed/main.py`, already
Dockerized). That's a lightweight orchestrator: it serves the page, calls
Vertex AI, and returns JSON. It's a perfect fit for a platform that scales
to **zero** running instances when nobody's using it, and starts one up in a
couple of seconds when a request arrives.

That platform is **Cloud Run**.

## Architecture

```mermaid
flowchart LR
    V[Portfolio visitor] -->|clicks your link| FH[Firebase Hosting<br>static/index.html]
    FH -->|"/api/** and /health<br>same-origin rewrite"| CR[Cloud Run: aegismed<br>min-instances = 0]
    CR -->|only while handling a request,<br>authenticated via ADC — no API key| VX[Vertex AI Gemini API<br>pay-per-token]
    CR -.->|idle, no traffic| Z[0 instances running<br>$0 compute cost]
```

- **Firebase Hosting** serves `static/index.html` (free tier: 10 GB storage /
  360 MB per day transfer — far more than a portfolio link needs) and,
  via a `rewrite` rule in `firebase.json`, transparently proxies `/api/**`
  and `/health` to the Cloud Run service. Same origin, so the browser's
  existing `fetch('/api/diagnose')` calls in `static/index.html` need **no
  changes**, and the CSP (`connect-src 'self'`) still holds — no CORS
  config needed anywhere.
- **Cloud Run** runs the existing `Dockerfile` as-is. With `min-instances=0`
  (the default — this repo sets it explicitly to make the intent obvious),
  Cloud Run kills the last container a short idle period after the last
  request and bills **nothing** while at zero. The next visitor's request
  triggers a cold start (a few seconds for this app) and gets served.
- **Vertex AI** serves the Gemini model itself — fully managed, pay-per-token,
  no idle cost, nothing to turn on or off. It's the Google Cloud equivalent
  of what Fireworks AI did for the hackathon build, so moving the whole app
  onto Google Cloud (as opposed to splitting inference across a different
  vendor) was a straightforward swap in one file.

Net effect: **when nobody has your portfolio link open, this costs $0.**
When someone visits, it wakes up automatically, answers, and goes back to
sleep — no manual start/stop, no forgotten running instance.

## No API key, anywhere

The Fireworks-based build needed `FIREWORKS_API_KEY`. This one needs no key
at all — `aegismed/llm.py` authenticates to Vertex AI with **Application
Default Credentials (ADC)**:

- **On Cloud Run**, the service's attached identity (its runtime service
  account) authenticates automatically. `scripts/deploy.sh` grants that
  account the `roles/aiplatform.user` IAM role, which is all Vertex AI
  needs — there's no secret to generate, store, or rotate.
- **Locally**, run `gcloud auth application-default login` once; after that,
  `aegismed/llm.py` picks up your own Google Cloud identity the same way.

## One-time setup

You need a Google Cloud project (Firebase Hosting and Cloud Run can live in
the same project — go to https://console.firebase.google.com and either
create a new project or "add Firebase" to an existing GCP project).

```bash
# Install the CLIs if you don't have them
npm install -g firebase-tools
# gcloud: https://cloud.google.com/sdk/docs/install

# Authenticate both
gcloud auth login
firebase login

# Point this repo's Firebase config at your project
firebase use --add   # pick your project, alias it "default"
# or edit .firebaserc directly and replace YOUR_FIREBASE_PROJECT_ID
```

`scripts/deploy.sh` itself enables the required APIs (Cloud Run, Cloud
Build, Vertex AI) and grants the Vertex AI IAM role, so there's nothing
further to do here — just run the deploy.

If `firebase.json`'s hosting `rewrites` region (`us-central1`) doesn't match
where you deploy the Cloud Run service, update both to agree — the region
in `firebase.json` and the `--region` flag below must match.

## Deploy

```bash
PROJECT_ID=your-gcp-project \
REGION=us-central1 \
  ./scripts/deploy.sh
```

This runs real Vertex AI inference by default (`DEMO_MODE=auto`, and the
script always sets `GOOGLE_CLOUD_PROJECT`, so `auto` resolves to "on"). No
key to provide — see above. This runs three things (see `scripts/deploy.sh`
for the exact commands):

1. Enable APIs + grant the Cloud Run service account `roles/aiplatform.user`.
2. `gcloud run deploy` — builds the existing `Dockerfile` with Cloud Build
   and deploys it with `--min-instances 0`.
3. `firebase deploy --only hosting` — publishes `static/index.html` and the
   `/api/**` → Cloud Run rewrite.

You'll get a `*.web.app` / `*.firebaseapp.com` URL (or attach a custom
domain in the Firebase console) — that's the link to put in your portfolio.

Redeploying later (after code changes) is the same one command.

Prefer zero per-request cost over live inference? Force the canned demo
instead:

```bash
DEMO_MODE=true PROJECT_ID=your-gcp-project REGION=us-central1 ./scripts/deploy.sh
```

Every request then returns the built-in board output with no Vertex AI call
at all — visitors see the identical polished example case, and the "no idle
cost" story becomes "no cost, period."

## Keeping the cost near zero even with real inference on

A public link can, in theory, be hit by more than your intended visitors. A
few things already bound the worst case:

- **`--max-instances 3`** in `scripts/deploy.sh` caps how many concurrent
  Cloud Run containers can ever run, so a traffic spike can't scale
  unboundedly.
- **`RATE_LIMIT_PER_MINUTE`** (already in `aegismed/config.py`, default 20)
  throttles the expensive endpoints per client IP.
- Gemini Flash-tier models are priced per token and are inexpensive for
  short clinical-case prompts; a board run is a handful of calls (a few
  thousand tokens total), so realistic portfolio traffic — a hiring
  committee clicking through a few cases — costs a small fraction of a
  cent. Still, set a **budget alert** as a backstop: Cloud Console →
  Billing → Budgets & alerts → create a small budget (e.g. $5) with an
  email alert. Costs nothing itself and catches anything unexpected.

## Known limitation: case storage isn't durable here

`aegismed/cases.py` saves "Save case" results to a local file
(`data/cases.jsonl`) inside the container. Cloud Run's filesystem is
ephemeral — it's wiped when an idle instance scales to zero, and a traffic
spike can spin up more than one instance with separate copies. That's fine
for demoing the board itself, but don't rely on "Save case" persisting
between visits on this deployment. (Swapping that module for Firestore
would fix it, but is a separate change — out of scope here unless you want
that feature to actually work for visitors.)

## Cold start expectations

The first request after a period of no traffic takes a bit longer (typically
a few seconds) while Cloud Run starts a fresh container — this FastAPI app
has no heavyweight startup work, so it's fast to boot. Every request after
that, while the instance stays warm, is normal speed. This is an acceptable
trade for a portfolio link that mostly gets occasional visits; there's
nothing to configure to avoid it without paying for `min-instances >= 1`
(which brings back the always-on cost you're trying to avoid).

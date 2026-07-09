# 🖥 Deploying AegisMed on AMD — both ways, step by step

Judging criterion #4 ("use of AMD platforms") is scored on how the project
*actually* uses AMD infrastructure, not just mentions it. AegisMed has **two**
genuine AMD-compute paths — pick one, or use both:

| Path | What runs on AMD | Effort | Best for |
|---|---|---|---|
| **A. Managed (default)** | Gemma inference, via Fireworks AI on **AMD Instinct MI300X** GPUs | Zero setup — this is what `FIREWORKS_API_KEY` already gives you | Fast to demo, no GPU quota needed |
| **B. Self-hosted** | Gemma inference AND the AegisMed app itself, both on **AMD Developer Cloud** | ~10–15 minutes | The strongest "meaningful use of AMD platforms" story |

Both are legitimate; B is the more impressive one for judges because nothing
touches a non-AMD server at all.

---

## Path A — Managed inference on AMD Instinct (default, already working)

No code changes needed — this is the out-of-the-box configuration.

```bash
cp .env.example .env
# Add your Fireworks AI key (from the AMD AI Developer Program, $50 free credit)
echo "FIREWORKS_API_KEY=fw_your_key_here" >> .env
docker compose up --build
```

Every `/api/diagnose` call now runs Gemma on **AMD Instinct MI300X** GPUs via
Fireworks AI's inference API. `/health` reports the active `endpoint` so you can
confirm this at a glance.

---

## Path B — Self-hosted Gemma on an AMD Developer Cloud GPU instance

This runs the model yourself, on AMD hardware you provision, with no third-party
inference service in the loop. AegisMed talks to it exactly like any
OpenAI-compatible server via the `LLM_BASE_URL` setting (see
`aegismed/config.py` / `aegismed/llm.py`).

### B1. Provision the GPU instance

1. Sign in to the **AMD Developer Cloud** console (credits come from the AMD AI
   Developer Program — see `docs/HACKATHON_GUIDE.md`).
2. Launch a GPU instance (an MI300X/MI250-class droplet). Open **inbound port
   8000** (the model server) and **8000** or another port for the AegisMed app
   if you're also using it for Path B's app hosting (see B3).
3. SSH in.

### B2. Serve Gemma with vLLM (OpenAI-compatible, ROCm-accelerated)

```bash
# On the AMD Developer Cloud GPU instance:
docker run -d --name gemma-vllm \
  --device=/dev/kfd --device=/dev/dri --group-add video \
  -p 8000:8000 \
  rocm/vllm:latest \
  --model google/gemma-3-27b-it \
  --host 0.0.0.0 --port 8000
```

(Swap the model for whatever Gemma size fits your GPU's memory; a smaller
`gemma-3-9b-it` works well on single-GPU instances. Ollama is an equally valid
OpenAI-compatible alternative if you prefer `ollama serve` over vLLM.)

Confirm it's serving:

```bash
curl http://localhost:8000/v1/models
```

### B3. Point AegisMed at it

On the machine running AegisMed (which can be the *same* AMD Developer Cloud
instance, or your local machine):

```bash
# .env
LLM_BASE_URL=http://<your-amd-instance-ip>:8000/v1
# no FIREWORKS_API_KEY needed — self-hosted vLLM/Ollama require no auth by default
```

Restart AegisMed. `GET /health` now reports:

```json
{"endpoint": "http://<your-amd-instance-ip>:8000/v1/chat/completions", ...}
```

That's the proof: every specialist call and the synthesis call are now served
by Gemma running on GPU hardware you provisioned on AMD Developer Cloud.

---

## Hosting the AegisMed app itself on AMD Developer Cloud

Independent of which inference path you pick, you can also host the **web app**
on an AMD Developer Cloud instance so judges get a live, clickable demo URL.
Use `deploy/amd-cloud.sh` (see the script's header comment for the exact
console steps: create instance → open port 8000 → clone repo → run the script).

<!-- DEMO_URL: paste your AMD Developer Cloud URL here after deploying -->
**Live demo:** _deploy with `deploy/amd-cloud.sh`, then paste your public URL here (and in the README)._

---

## Verifying which AMD path is active

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "demo_mode": false,
  "model": "accounts/fireworks/models/gemma-3-27b-it",
  "endpoint": "https://api.fireworks.ai/inference/v1/chat/completions",
  "request_timeout_seconds": 28,
  "knowledge_base_diseases": 10670
}
```

`endpoint` tells you at a glance whether you're on Path A (`api.fireworks.ai`)
or Path B (your own AMD Developer Cloud host).

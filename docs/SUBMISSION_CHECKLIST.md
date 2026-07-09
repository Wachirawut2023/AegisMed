# ✅ Submission Checklist

Mirror of the lablab.ai submission form. Everything must be done **before
Sat July 11, 4:00 PM UTC (11:00 PM Thailand)** — target ~6 PM Thailand to be safe.

## 📋 Basic information
- [ ] **Project title:** AegisMed
- [ ] **Short description** (1–2 sentences): e.g. *"A virtual board of AI specialist physicians — seven Gemma-powered agents that analyze a patient case in parallel and help doctors catch rare diseases years sooner."*
- [ ] **Long description:** problem (5–7 year diagnostic odyssey), how the multi-agent board works, the AMD/Fireworks/Gemma stack, market vision (reuse README text)
- [ ] **Technology & category tags:** AMD, Fireworks AI, Gemma, FastAPI, Python, Healthcare, Agents

## 📸 Visuals
- [ ] **Cover image** uploaded (professional, readable at thumbnail size)
- [ ] **Video presentation** uploaded/linked — shows the app actually working
- [ ] **Slide presentation** uploaded

## 💻 Code & demo
- [ ] **GitHub repository is PUBLIC** (check while logged out!)
- [ ] README has working setup + usage instructions (test on a machine that isn't yours)
- [ ] **Containerized:** `docker compose up --build` works from a fresh clone ⚠️ hard requirement
- [ ] **Demo application URL** is live (AMD Developer Cloud) and loads from another network
      — deploy with `deploy/amd-cloud.sh` (see `docs/DEPLOY_AMD.md`), then fill in the
      `<!-- DEMO_URL -->` placeholder at the top of `README.md`
- [ ] Demo URL entered in the form
- [ ] `.env` with your real API key is **NOT** in the repo (it's gitignored — verify anyway)
- [ ] Response time per request is under 30s (verified: `REQUEST_TIMEOUT_SECONDS=28` deadline,
      see `docs/PRODUCTION_READINESS.md`)

## ⚖️ Compliance
- [ ] Work is original, built during/for this hackathon
- [ ] MIT-license-compliant (repo is MIT; Gemma is Apache 2.0 ✅)
- [ ] Medical disclaimer visible in app and README

## 🏆 Prize eligibility
- [ ] Track 3 — Unicorn Track selected
- [ ] Gemma used via Fireworks/AMD and **mentioned explicitly** in video + description (for the $2,000 "Best AMD-Hosted Gemma Project" prize)
- [ ] AMD platform usage (Fireworks-on-AMD + AMD Developer Cloud hosting) **stated clearly** in the description — judges score criterion #4 on this

## 🚀 Final button
- [ ] Submitted on lablab.ai and confirmation received

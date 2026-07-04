# 🗓 Day-by-Day Roadmap (July 4 → July 11)

All hackathon times below in **Thailand time (UTC+7)**; the deadline is
**Sat July 11, 11:00 PM** Thailand time. Rule of thumb: **finish features by
July 9 evening** — the last two days belong to the demo, video, and submission.

## ✅ Before kickoff

### Fri July 4 — accounts & first run
- [ ] Sign up on **lablab.ai** and **Enroll** in the hackathon
- [ ] Sign up for the **AMD AI Developer Program** and claim: $100 AMD cloud credits, $50 Fireworks credits
- [ ] Join the **lablab.ai Discord** and **AMD Discord**
- [ ] Clone this repo and run it in demo mode (README Option B), click **Load example case** → **Convene the board**
- [ ] Read `docs/ARCHITECTURE.md` (20 minutes — makes everything else easy)

### Sat July 5 — first real AI call
- [ ] Create a **Fireworks AI** account / API key (via the AMD program benefits)
- [ ] Put the key in `.env`, restart, run the example case with the **real** model
- [ ] Compare demo vs. real output; tweak a specialist prompt in `specialists.py` and see the effect
- [ ] If you have Docker installed: verify `docker compose up --build` works on your machine

### Sun July 6 (kickoff 11:00 PM Thailand) — launch night
- [ ] Watch the kickoff stream (Introduction to the Challenge, 11:15 PM)
- [ ] **Confirm Track 3 rules haven't changed** and note the confirmed model list
- [ ] If the Gemma model name differs from our default, update `MODEL` in `.env`
- [ ] Ask in Discord: how to redeem the extra participant credits

## 🔨 Build days

### Mon July 7 — make it yours + measure it
- [ ] Improve the specialist prompts with your own medical knowledge (this is your real edge — you understand the clinical reasoning)
- [ ] Build the evaluation data: `python data/build_dataset.py` (free, no API key)
- [ ] Run the eval with your API key: `python eval/run_eval.py` → get your headline accuracy number for the pitch (see `docs/DATA_AND_EVAL.md`)
- [ ] Skim the ❌ rows in `eval/results.md`; add missed synonyms to `data/aliases.json`
- [ ] Optional: add a 6th specialist (e.g., Endocrinology, Hematology) — one dict entry, then re-run the eval to see if the score improves

### Tue July 8 — deploy on AMD (judging criterion!)
- [ ] Create an **AMD Developer Cloud** instance (use your $100 credits; a small CPU droplet is enough to host the app — GPU only needed if you self-host the model)
- [ ] Install Docker on it, `git clone`, add `.env`, `docker compose up -d`
- [ ] You now have a **public demo URL** (http://YOUR_IP:8000) — save it for the submission
- [ ] Ask AMD engineers on Discord if stuck — that's what office hours are for

### Wed July 9 — polish & freeze
- [ ] UI polish: app name/tagline, favicon, maybe a logo (AI image tools are fine)
- [ ] Take good screenshots for the README and slides
- [ ] Freeze features tonight. Bugs only from here.

## 🎬 Demo days

### Thu July 10 — the pitch
- [ ] Make the **cover image** (1200×675 works well)
- [ ] Build the **slide deck** (~7 slides: problem → who suffers → the idea → live demo shots → tech/AMD stack → market → roadmap)
- [ ] Record the **video**: hook with the 5–7-year diagnosis statistic → show the example case running live → explain the seven specialist agents → the AMD/Gemma stack → the vision. Screen recording + voice-over is enough.
- [ ] Draft the short & long descriptions for the lablab.ai form

### Fri July 11 — submit EARLY (deadline 11:00 PM Thailand)
- [ ] Morning: final test of the public URL **from your phone** (different network!)
- [ ] Confirm the GitHub repo is **public** and README instructions work on a clean machine
- [ ] Go through `docs/SUBMISSION_CHECKLIST.md`, complete the lablab.ai form
- [ ] **Submit by ~6:00 PM Thailand time** — leave 5 hours of buffer
- [ ] Celebrate 🎉

## If you fall behind

Cut in this order (last item = cut first): extra specialists → debate round →
UI polish → self-hosted model. **Never cut:** working Docker run, public demo
URL, video, README accuracy. A small thing that runs beats a big thing that doesn't.

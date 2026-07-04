# 📖 Hackathon Guide — AMD Developer Hackathon: ACT II

Everything you need to know about the rules, distilled from the
[official event page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-ii).
Always double-check the **Event Schedule tab** on lablab.ai — it shows the
deadline in your local timezone and is kept up to date by the organizers.

## ⏰ Timeline

| Event | UTC | Thailand time (UTC+7) |
|---|---|---|
| Hackathon kickoff | Mon **Jul 6, 4:00 PM** | Mon Jul 6, **11:00 PM** |
| Intro to the challenge | Jul 6, 4:15 PM | Jul 6, 11:15 PM |
| Hackathon guide session | Jul 6, 4:35 PM | Jul 6, 11:35 PM |
| Discord Q&A | Jul 6, 5:00 PM | Jul 7, 12:00 AM |
| **End of submissions** | Sat **Jul 11, 4:00 PM** | Sat Jul 11, **11:00 PM** |

That's ~5 days of building. **Plan to submit at least half a day early** —
last-minute platform issues are the classic hackathon killer.

## ✍️ How to register (do this BEFORE kickoff)

1. Create an account on **[lablab.ai](https://lablab.ai)** and click **Enroll** on the
   [event page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-ii).
2. Sign up for the **[AMD AI Developer Program](https://www.amd.com/en/developer/ai-dev-program.html)** —
   required to be approved and to receive credits.
3. As a **new** AMD AI Developer Program member you can claim:
   - **$100** in AMD Developer Cloud GPU credits
   - **$50** in Fireworks AI API credits
   - 1 month of DeepLearning.AI Pro (free courses)
4. Join the **lablab.ai Discord** and the **AMD Discord** — announcements, launch-day
   model lists, and help from AMD engineers all happen there.
5. Extra compute/API credits for participants are distributed **at hackathon launch**.

Solo participation is explicitly allowed — "anyone with a passion for AI is welcome."

## 🏁 Our track: Track 3 — Unicorn Track

Build a **product- or startup-oriented project** using any open-source models and
frameworks together with **AMD GPUs and/or Fireworks AI**.

- **No leaderboard, no benchmark.** Human judges score you on:
  1. **Creativity & originality** — novel idea, new behaviors
  2. **Product/market potential** — is this a believable startup?
  3. **Completeness** — does it actually work, end to end?
  4. **Use of AMD platforms** — is AMD infrastructure meaningfully used?
- Prizes: 🥇 $2,500 / 🥈 $1,500 / 🥉 $1,000
- Think **startup pitch, not benchmark run** — the video and story matter as much
  as the code.

### 💎 Bonus prize we're targeting: "Best AMD-Hosted Gemma Project" ($2,000)

Use Google's **Gemma** open model in the project, accessed through **Fireworks AI**
or run on **AMD Developer Cloud**. AegisMed's agents are configured to use Gemma
by default (`MODEL` in `.env`), so we qualify automatically. No separate sign-up
needed — usage draws from your Fireworks credits.

## 📦 Submission requirements (hard rules)

Submitted through the lablab.ai platform before the deadline. Required:

- **Basic info:** project title, short description, long description, technology/category tags
- **Cover image** (make it look professional — it's the first thing judges see)
- **Video presentation** (the pitch — problem, demo, tech, vision)
- **Slide presentation**
- **Public GitHub repository** with a README containing setup + usage instructions
- **Demo application URL** (a live, clickable deployment)
- ⚠️ **All submissions MUST be containerized** (our Dockerfile handles this)
- The app **must be runnable using the README instructions** — judges will try
- Work must be **original** and **MIT-license-compliant** (our repo is MIT ✅)

See [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) for the tick-box version.

## 🧰 The technology, in one paragraph each

- **AMD Developer Cloud** — rented computers with powerful AMD GPUs, accessed
  through the browser. We use it to *host* AegisMed so judges get a live URL
  (this also scores the "Use of AMD platforms" criterion).
- **Fireworks AI** — a service that runs AI models on AMD hardware and lets your
  code use them through a simple internet API. You pay per usage from your $50
  credits; our app makes 6 model calls per case (≈ fractions of a cent each).
- **Gemma** — Google DeepMind's family of open AI models (Apache 2.0 licensed).
  "Open" means anyone may run it; we call it via Fireworks.
- **ROCm** — AMD's open-source software layer that lets AI frameworks (PyTorch
  etc.) run on AMD GPUs. Relevant if we later run a model ourselves on AMD
  Developer Cloud instead of calling Fireworks.

## ⚠️ Things that commonly disqualify or sink projects

- Submitting late (the platform closes — no exceptions)
- Private GitHub repo (must be **public**)
- Missing Dockerfile / app won't start from the README instructions
- No video or a video that never shows the working product
- Forgetting to actually *use* AMD platforms (judging criterion #4)

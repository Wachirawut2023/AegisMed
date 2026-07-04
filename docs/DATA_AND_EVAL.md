# 📊 Data & Evaluation — explained simply

This guide explains how AegisMed proves it actually works, using real public
data. No AI background needed.

## Why bother evaluating?

Anyone can build an app that *looks* smart. Judges (and users) want proof.
**Evaluation** means: take cases where the correct answer is already known,
run them through AegisMed, and count how often it got the right diagnosis.
That gives you one honest number for your pitch:

> "Across N held-out rare-disease cases from public medical datasets,
>  AegisMed surfaced the correct diagnosis in **X%** of them."

That sentence is far more convincing than "it seems to work well."

## The two-step workflow

```
Step 1: BUILD the data        Step 2: SCORE with the AI
python data/build_dataset.py  →  python eval/run_eval.py
(no API key needed)              (needs your Fireworks API key)
```

### Step 1 — Build the dataset (free, no API key)

```bash
python data/build_dataset.py
```

This downloads real rare-disease cases from public datasets (RareBench + CUPCase
— see [`../data/SOURCES.md`](../data/SOURCES.md)) and writes:

- **`data/eval_cases.jsonl`** — the test set. Each line is one case plus its
  known-correct diagnosis.
- **`data/demo_cases.json`** — a few readable cases that appear in the app's
  "Load example case" dropdown and are great for your demo video.
- **`data/aliases.json`** — alternate names per disease, so scoring is fair.

Each test case looks like this (simplified):

```json
{
  "source": "CUPCase",
  "symptoms": "A 26-year-old man presented with severe headache...",
  "expected_diagnosis": "Meningioma",
  "expected_aliases": ["meningioma"]
}
```

There are two *styles* of case, which makes your evaluation stronger:
- **coded** (from RareBench) — a precise list of symptoms, e.g. *"Ptosis;
  Seizure; Hypotonia; ..."*
- **narrative** (from CUPCase) — a real doctor's write-up in plain prose.

### Step 2 — Score AegisMed (needs the API key)

First put your Fireworks key in `.env` (see `.env.example`), then:

```bash
python eval/run_eval.py            # score every case
python eval/run_eval.py --limit 10 # quick test on 10 cases first
```

For each case it runs the full seven-specialist board, reads the board's answer,
and checks whether the correct diagnosis (or a known synonym) appears anywhere
in it. It prints a running tally and writes a report to **`eval/results.md`**:

```
## Headline: correct diagnosis surfaced in 41/60 = 68% of cases

| Source | Hit rate |
|---|---|
| CUPCase        | 11/15 (73%) |
| RareBench/LIRICAL | 9/15 (60%) |
...
```

> ⚠️ **You must set your API key for this to mean anything.** In demo mode the
> app always returns the same sample answer (Fabry disease), so every non-Fabry
> case "fails" and the score is meaningless. The script warns you when this
> happens — it's only testing that the plumbing works.

### The intake step during scoring

The eval mirrors the real app flow: for each case it first runs the **intake
agent** (the one that asks clarifying questions), then the board. Since there's
no human to answer during a batch run, an **auto-answer agent** replies to each
question using only what the case already contains (anything absent is marked
"Not documented"). The running log shows `(+3q)` when intake asked 3 questions.

- This makes the score reflect what real users experience (intake + board).
- It costs a couple of extra model calls per case. To score the raw case only —
  faster and cheaper — pass `--no-intake`:

```bash
python eval/run_eval.py --no-intake       # board only, no intake
python eval/run_eval.py                    # intake + board (default)
```

Running both is a nice experiment for your write-up: it shows whether the
intake step actually improves diagnostic accuracy.

### Cost note — smart routing

By default AegisMed convenes only the specialists relevant to each case, so eval
runs are cheaper than the full 7-specialist board. To compare accuracy at full
board vs smart routing, set the environment variable before running:

```bash
SPECIALIST_SELECTION=all python eval/run_eval.py     # full board
python eval/run_eval.py                               # smart routing (default)
```

If accuracy holds while calls drop, that's a strong efficiency result for your pitch.

## How "getting it right" is judged

The scorer marks a **hit** if the correct diagnosis — or any accepted synonym
from `aliases.json` — shows up in the board's output. It matches on text, so
it's approximate. Two honest caveats to mention if asked:

- It can **miss** a correct answer phrased very differently (undercount).
- It could **over-credit** a vague near-match.

Before quoting a number in your video, skim the ❌ rows in `eval/results.md` by
eye — sometimes AegisMed was actually right and just used different words.

## Ways to make the number better (during hackathon week)

1. **Improve the specialist prompts** in `aegismed/specialists.py` — this is the
   highest-leverage change and needs no data work.
2. **Add synonyms** to `data/aliases.json` (or wire in Orphanet/HPO synonym
   files — see `data/SOURCES.md`) so fair answers stop being marked wrong.
3. **Run a bigger test** with `--per-source 30`, or pull the large RareArena set
   locally (`--sources rarearena`) for a private stress test.

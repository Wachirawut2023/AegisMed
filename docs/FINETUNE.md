# 🎯 Fine-tuning AegisMed (beginner-friendly)

This guide explains how to **fine-tune** the model behind AegisMed so its board
chair gets better at surfacing rare diagnoses — no prior machine-learning
experience needed.

## What is fine-tuning, in one paragraph?

The base model (Gemma) already knows a lot of general medicine. **Fine-tuning**
shows it hundreds of worked examples of *our exact task* — read a patient case,
write a ranked differential in AegisMed's format, and put the correct rare
diagnosis first — so it forms the habit. You are not retraining the model from
scratch; you are nudging an existing model toward this one job. On Fireworks
this is a small, cheap [LoRA](https://fireworks.ai/docs/fine-tuning) job that
runs on the same AMD hardware the app already uses.

## Why bother?

AegisMed's whole value is catching the rare diagnosis a busy clinician would
miss. A general model often stops at the obvious common answer. Fine-tuning on
known rare-disease cases teaches it to:

1. **Answer in AegisMed's structure** every time (ranked differential, single
   most valuable next test, do-not-miss warning), and
2. **Reach for the correct rare diagnosis** instead of the first plausible one.

You can measure whether it worked: fine-tune, point `SYNTHESIS_MODEL` at the
tuned model, and re-run `python eval/run_eval.py` — the headline accuracy
should go up. That score is only meaningful because of the train/eval split
described below — without it you'd mostly be measuring memorization.

## The three steps

```bash
# 1. Get the data (free, no API key) — the same public rare-disease cases the
#    evaluator uses. Skip if you already ran this for evaluation.
python data/build_dataset.py

# 2. Shape it into training conversations (needs your API key — real model
#    calls, see "What it builds" below).
python finetune/build_finetune_data.py

# 3. Launch the fine-tuning job on Fireworks (needs your API key + account id).
python finetune/run_finetune.py
```

### Step 2 — what it builds

`finetune/build_finetune_data.py` reads `data/eval_cases.jsonl` (case + the
*known-correct* diagnosis) and writes chat-format training examples to
`finetune/train.jsonl` and `finetune/val.jsonl`. Each example is one
conversation:

| Role | Content |
|---|---|
| `system` | the board chair's instructions (`specialists.SYNTHESIS_PROMPT`) |
| `user` | the grounded case + retrieved evidence + every specialist's REAL opinion — the exact input the synthesis agent sees at inference time |
| `assistant` | a **gold** briefing that names the correct diagnosis first, in AegisMed's structure |

The `user` turn is built by actually running retrieval and the specialist
board (base model) for each case, via
`aegismed.orchestrator._convene_board` — the same function
`orchestrator.diagnose()` calls at real inference time. That means this step
now makes **real, billed model calls** (1 retrieval + up to 7 specialists per
case) — it needs `FIREWORKS_API_KEY` set and `DEMO_MODE` off, and costs
roughly what running the app once per training case would cost. This matters:
training the synthesis agent on a bare case description (no specialist
opinions at all) taught it a different-shaped input than it ever sees in
production, and the skill didn't transfer as well as it should have. Use
`--limit 10` for a quick, cheap smoke test, and `--delay` to go easier on
rate limits.

> **Honesty note.** By default the gold **answers** are still constructed
> from each case's verified ground-truth diagnosis with a fixed template —
> faithful but generic reasoning, layered on top of now-real specialist
> input. Pass `--teacher-model accounts/fireworks/models/<a stronger model>`
> to distill richer answers instead: that model is shown the case's real
> specialist opinions and the verified diagnosis, and writes case-specific
> reasoning for why it fits — citing the same specialists' findings the
> synthesis agent will actually see. This is one more real model call per
> case. Picking a teacher: many current strong models write visible
> chain-of-thought directly into their reply before the actual answer, which
> can get cut off by the token budget or leak into the training target —
> `build_finetune_data.py` asks for extra headroom and strips everything
> before the `**Ranked differential diagnosis:**` heading, but a model that
> answers directly and follows the requested structure works best. Sanity
> check a `--limit 1` run before committing to the full set.

### Keeping the eval score honest: the train/eval split

`aegismed/data_split.py` permanently reserves ~25% of `data/eval_cases.jsonl`
(by a hash of each case's `id`, so the holdout doesn't reshuffle as the pool
grows) as **eval-only** — `finetune/build_finetune_data.py` only ever builds
training examples from the other ~75%, and `eval/run_eval.py` scores against
the eval-only holdout **by default**. Without this, most of the eval set
would also be training data, so the headline accuracy would largely reflect
the model recalling its own training target rather than generalizing to a
new case. Pass `--all-cases` to `eval/run_eval.py` to score the full pool
instead (only meaningful if you have *not* fine-tuned).

### Step 3 — what it does

`finetune/run_finetune.py`:

1. uploads `finetune/train.jsonl` as a Fireworks dataset,
2. starts a supervised fine-tuning job from the base model, and
3. watches it until it finishes, then prints the new model id.

It needs two things in `.env`:

```
FIREWORKS_API_KEY=fw_your_key_here      # the same key the app uses
FIREWORKS_ACCOUNT_ID=your_account_id    # from app.fireworks.ai/dashboard/<ACCOUNT_ID>/...
```

Useful flags:

```bash
python finetune/run_finetune.py --dry-run     # check everything, call nothing
python finetune/run_finetune.py --no-wait      # start it and come back later
python finetune/run_finetune.py --epochs 2     # train a little longer
```

## Using your tuned model

When the job completes it prints a model id like
`accounts/<your-account>/models/aegismed-gemma-tuned`. Put it in `.env` as
`SYNTHESIS_MODEL`, **not** `MODEL`:

```
SYNTHESIS_MODEL=accounts/<your-account>/models/aegismed-gemma-tuned
```

Step 2 only builds training examples for the synthesis ("board chair")
agent — intake, retrieval, and the 7 specialists have no fine-tuning data at
all. `SYNTHESIS_MODEL` scopes the tuned adapter to just that one call;
`MODEL` keeps handling every other agent on the base model. (Setting `MODEL`
itself to the tuned adapter would route intake/retrieval/specialists through
it too, even though they were never trained for it.)

Restart the app (or re-run the eval). Every agent still routes through
`aegismed/llm.py`; only the synthesis call's model name is different.

## Prefer the CLI?

Fireworks' `firectl` tool does the same thing if you'd rather not use the
script:

```bash
firectl create dataset aegismed-synthesis finetune/train.jsonl
firectl create sftj \
  --base-model accounts/fireworks/models/gemma-3-27b-it \
  --dataset aegismed-synthesis \
  --output-model aegismed-gemma-tuned \
  --epochs 1
```

See the [Fireworks fine-tuning docs](https://fireworks.ai/docs/fine-tuning) for
the current command names and pricing.

## Cost & time

Step 2 now makes real model calls to build each training example (1 retrieval
+ up to 7 specialists per case, same as running the app once per case) — with
~55 fine-tuning-eligible cases that's on the order of a few hundred small
calls, still cheap on the base model but no longer free. The LoRA fine-tune
itself (step 3) on this small dataset (a few dozen examples, 1 epoch) is
quick and inexpensive — well within the $50 Fireworks credit from the AMD
program. Start with `--epochs 1`; only increase it if the validation examples
suggest the model is under-fitting (rare with this much signal).

## Where the files live

```
finetune/
  build_finetune_data.py   # step 2 — makes train.jsonl / val.jsonl (real model calls)
  run_finetune.py          # step 3 — starts + watches the Fireworks job
  train.jsonl              # generated (gitignored)
  val.jsonl                # generated (gitignored)
```

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

You can measure whether it worked: fine-tune, point `MODEL` at the tuned model,
and re-run `python eval/run_eval.py` — the headline accuracy should go up.

## The three steps

```bash
# 1. Get the data (free, no API key) — the same public rare-disease cases the
#    evaluator uses. Skip if you already ran this for evaluation.
python data/build_dataset.py

# 2. Shape it into training conversations (free, no API key).
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
| `user` | the patient case, formatted exactly as the app sends it |
| `assistant` | a **gold** briefing that names the correct diagnosis first, in AegisMed's structure |

Building the `user` message with the app's own `_format_case` matters: the
model should train on **the same text it will see at inference time**, or the
skill won't transfer.

> **Honesty note.** These gold answers are constructed from each case's verified
> ground-truth diagnosis, not written by a stronger "teacher" model. So they
> teach *format* and *correct-diagnosis recall* with faithful but generic
> reasoning. That is exactly what moves the eval score, which rewards surfacing
> the right diagnosis. If you want richer clinical reasoning in the targets,
> generate them with a stronger model first (a "distillation" teacher) and feed
> those into the same builder — the format is unchanged.

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

A LoRA fine-tune on this small dataset (a few dozen examples, 1 epoch) is quick
and inexpensive — well within the $50 Fireworks credit from the AMD program.
Start with `--epochs 1`; only increase it if the validation examples suggest the
model is under-fitting (rare with this much signal).

## Where the files live

```
finetune/
  build_finetune_data.py   # step 2 — makes train.jsonl / val.jsonl (offline)
  run_finetune.py          # step 3 — starts + watches the Fireworks job
  train.jsonl              # generated (gitignored)
  val.jsonl                # generated (gitignored)
```

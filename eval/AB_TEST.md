# A/B Testing Guide

Compare multiple models' performance on the same 75 rare-disease cases.

## Why a deployment is needed first

The base model `gemma-3-27b-it` is **not** served on Fireworks' free serverless
tier (`supportsServerless: false`), and a fine-tuned LoRA adapter is never
serverless on its own. If you call either directly you get `404 Model not
found`. So A/B testing runs against a **dedicated on-demand deployment**: one
GPU hosts the base weights and loads your LoRA adapter onto the *same* card
("Multi-LoRA"), which is also the fairest possible comparison — identical
hardware for both models.

`finetune/deploy.py` manages that GPU:

```bash
python finetune/deploy.py up      # rent an H100, load base + LoRA, write eval/ab_models.json
python finetune/deploy.py status  # is a GPU currently running (i.e. costing credit)?
python finetune/deploy.py down     # release the GPU — STOPS the credit meter
```

`up` writes `eval/ab_models.json` with the exact deployment-qualified model ids;
`compare_models.py` picks that file up automatically and targets the live GPU.

## Quick start (recommended)

`run_ab_test.sh` does the whole lifecycle — provision, validate on 15 cases,
run the full 75, then tear the GPU down (even on error or Ctrl-C):

```bash
bash eval/run_ab_test.sh
```

## Manual runs

```bash
python finetune/deploy.py up                                      # provision first
python eval/compare_models.py --models gemma3_base,gemma3_tuned   # full eval (~20 min)
python eval/compare_models.py --models gemma3_base,gemma3_tuned --limit 10  # quick
python finetune/deploy.py down                                     # ALWAYS release the GPU
```

> ⚠ The deployment bills credit for as long as it is up. It auto-scales to zero
> after ~5 minutes idle, but if a run is interrupted before teardown, run
> `python finetune/deploy.py down` (or `status` to check) so you stop paying.

## Output

Three files are written to `eval/`:

| File | Contents |
|---|---|
| `results_gemma3_tuned.md` | Full results for tuned Gemma 3 |
| `results_gemma4_base.md` | Full results for base Gemma 4 |
| `comparison.md` | Side-by-side analysis |

## What you'll see in comparison.md

**Headline accuracy:** which model caught the correct diagnosis more often?

**Per-source breakdown:** how do they perform on coded RareBench cases vs narrative CUPCase reports?

**Case-by-case wins:** 
- Cases both got right
- Cases only Gemma 4 caught
- Cases only tuned Gemma 3 caught
- Cases both missed

## Models available

Add more to `MODELS_TO_TEST` in `compare_models.py` to compare:

```python
MODELS_TO_TEST = {
    "gemma3_base": "accounts/fireworks/models/gemma-3-27b-it",
    "gemma3_tuned": "accounts/wachirawut2002-fqt88/models/aegismed-gemma-tuned",
    "gemma4_base": "accounts/fireworks/models/gemma-4-31b-it",
}
```

## Interpreting results

**If tuned Gemma 3 wins:** fine-tuning teaches the model to surface rare diagnoses better than a larger base model.

**If Gemma 4 wins:** the newer architecture + scale outweighs fine-tuning on a smaller model — might be worth tuning Gemma 4 too (when it becomes tunable on Fireworks).

**If they split:** they have different strengths — might want both in production for different case types.

## Cost

A/B testing is billed by **GPU time**, not per token, because it runs on a
dedicated deployment. One H100 80GB, single replica, is up for as long as the
deployment lives. The full base-vs-tuned A/B (both models × 75 cases, ~4 model
calls each) takes roughly 20–40 minutes of active GPU time.

Keep the bill down by always running `python finetune/deploy.py down` when you
finish — `run_ab_test.sh` does this for you automatically.

## Rate limiting

Use `--delay 0.5` if Fireworks rate-limits you (waits 0.5 seconds between cases).

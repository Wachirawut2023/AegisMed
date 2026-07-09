# A/B Testing Guide

Compare multiple models' performance on the same 75 rare-disease cases.

## Quick start

```bash
# Compare tuned Gemma 3 vs base Gemma 4 (full eval, ~20 minutes)
python eval/compare_models.py

# Quick test on 10 cases each (2 minutes)
python eval/compare_models.py --limit 10

# Test just base Gemma 3 vs tuned Gemma 3 (to isolate tuning effect)
python eval/compare_models.py --models gemma3_base,gemma3_tuned
```

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

Each full eval on all 75 cases calls the model ~250 times (75 cases × 3-4 agents + intake + synthesis). At Fireworks pricing, one full model test costs ~$0.50–$1.00.

Running both models: ~$1–$2 total.

## Rate limiting

Use `--delay 0.5` if Fireworks rate-limits you (waits 0.5 seconds between cases).

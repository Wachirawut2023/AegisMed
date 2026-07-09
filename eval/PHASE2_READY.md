# Phase 2: Multi-LoRA A/B Testing (READY TO RUN)

When Fireworks inference recovers, run this ONE command:

```bash
bash eval/run_ab_test.sh
```

This will:
1. Quick validation (15 cases, ~3 min)
2. Full evaluation (all 75 cases, ~20 min)

## What it tests

| Model | What | Effect |
|---|---|---|
| `gemma3_base` | Base model, no LoRA | Baseline |
| `gemma3_tuned` | Base + your LoRA adapter | With fine-tuning |
| **Comparison** | Difference | **Measures: Did fine-tuning help?** |

## Output files

```
eval/results_gemma3_base.md       ← Base model results
eval/results_gemma3_tuned.md      ← Tuned model results
eval/comparison.md                 ← Side-by-side analysis
```

## Status

Waiting for: Fireworks inference endpoint recovery
Branch: `claude/fine-tune-model-j9psx9`


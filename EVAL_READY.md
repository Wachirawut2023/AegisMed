# Evaluation Ready to Run

The fine-tuning and A/B testing framework is **complete and ready**. 
Waiting only for Fireworks' inference service to recover.

## What to run when the service is back:

### Option 1: Quick test (2 minutes, 15 cases)
```bash
python eval/compare_models.py --models gemma3_tuned,gemma4_base --limit 15
```

### Option 2: Full A/B test (20 minutes, all 75 cases)
```bash
bash eval/run_ab_test.sh
```

Or manually:
```bash
python eval/compare_models.py --models gemma3_tuned,gemma4_base
```

### Option 3: Test just the tuned model
```bash
# Single model eval
python eval/run_eval.py

# This measures: does fine-tuning help? (compares against base model manually)
```

## What you'll get

When complete:
- `eval/results_gemma3_tuned.md` — tuned model accuracy on 75 cases
- `eval/results_gemma4_base.md` — Gemma 4 base accuracy on same 75 cases  
- `eval/comparison.md` — side-by-side comparison showing:
  - Which model has better headline accuracy
  - Per-source breakdown (RareBench vs CUPCase)
  - Case-by-case wins (which diagnoses each model caught)

## Status

- ✅ Fine-tuning pipeline: complete, tested
- ✅ Fine-tuning job: ran successfully ($0.17 cost)
- ✅ Tuned model: created and in READY state
- ✅ A/B testing framework: built and ready
- ⏳ Fireworks inference: waiting for recovery

**GitHub branch:** `claude/fine-tune-model-j9psx9` (push-ready)

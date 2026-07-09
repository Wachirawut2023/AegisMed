#!/bin/bash
# Multi-LoRA A/B test: Base Gemma 3 vs Gemma 3 + your tuned LoRA
# Measures: Did fine-tuning help?
# Run this the moment Fireworks inference is back up.

set -e
cd "$(dirname "$0")/.."

echo "🧪 Starting Multi-LoRA A/B test"
echo "   Comparing: Base Gemma 3 vs Gemma 3 + tuned LoRA"
echo "   Question: Did fine-tuning improve performance?"
echo ""

# Quick test on 15 cases first (to verify it works)
echo "Step 1: Quick validation run (15 cases, ~3 min)"
python3 eval/compare_models.py --models gemma3_base,gemma3_tuned --limit 15

echo ""
echo "✓ Validation successful! Running full eval (all 75 cases)..."
echo ""

# Full comparison
echo "Step 2: Full evaluation (all 75 cases, ~20 min)"
python3 eval/compare_models.py --models gemma3_base,gemma3_tuned

echo ""
echo "✅ A/B test complete!"
echo ""
echo "Results:"
echo "  eval/results_gemma3_base.md   <- base model (no tuning)"
echo "  eval/results_gemma3_tuned.md  <- with your LoRA"
echo "  eval/comparison.md             <- impact analysis"
echo ""
echo "Open eval/comparison.md to see: Did your fine-tuning help?"

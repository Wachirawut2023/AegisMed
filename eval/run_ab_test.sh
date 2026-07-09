#!/bin/bash
# Quick A/B test: tuned Gemma 3 vs base Gemma 4
# Run this the moment Fireworks inference is back up.

set -e
cd "$(dirname "$0")/.."

echo "🧪 Starting A/B test: tuned Gemma 3 vs base Gemma 4"
echo ""

# Quick test on 15 cases first (to verify it works)
echo "Step 1: Quick validation run (15 cases, ~3 min)"
python3 eval/compare_models.py --models gemma3_tuned,gemma4_base --limit 15

echo ""
echo "✓ Validation successful! Running full eval (all 75 cases)..."
echo ""

# Full comparison
echo "Step 2: Full evaluation (all 75 cases, ~20 min)"
python3 eval/compare_models.py --models gemma3_tuned,gemma4_base

echo ""
echo "✅ A/B test complete!"
echo ""
echo "Results:"
echo "  eval/results_gemma3_tuned.md  <- tuned model details"
echo "  eval/results_gemma4_base.md   <- Gemma 4 base details"
echo "  eval/comparison.md             <- side-by-side analysis"
echo ""
echo "Open eval/comparison.md to see which model performed better."

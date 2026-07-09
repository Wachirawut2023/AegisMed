#!/bin/bash
# Multi-LoRA A/B test: Base Gemma 3 vs Gemma 3 + your tuned LoRA
# Measures: Did fine-tuning help?
#
# Neither the base model nor the tuned LoRA is served on Fireworks' free
# serverless tier, so this script rents a dedicated GPU (on-demand deployment),
# runs the comparison against it, then releases the GPU. The `trap` guarantees
# the GPU is torn down — and the credit meter stops — even if the eval fails or
# you Ctrl-C out.

set -e
cd "$(dirname "$0")/.."

echo "🧪 Multi-LoRA A/B test"
echo "   Comparing: Base Gemma 3 vs Gemma 3 + tuned LoRA"
echo "   Question: Did fine-tuning improve performance?"
echo ""

# Step 0: rent the GPU, load base + LoRA, write eval/ab_models.json.
echo "Step 0: Provisioning dedicated deployment (spends Fireworks credit)…"
python3 finetune/deploy.py up

# Always release the GPU when this script exits, for ANY reason.
trap 'echo ""; echo "Tearing down deployment…"; python3 finetune/deploy.py down' EXIT

echo ""
echo "Step 1: Quick validation run (15 cases, ~5 min)"
python3 eval/compare_models.py --models gemma3_base,gemma3_tuned --limit 15

echo ""
echo "✓ Validation successful! Running full eval (all 75 cases)…"
echo ""

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
# The trap above now tears down the deployment.

"""Deterministic, disjoint train/eval split for AegisMed's case pool.

Fine-tuning and evaluation must never share cases: finetune/build_finetune_data.py
trains toward a gold answer that names the correct diagnosis, so any case that
is both a training example and an eval case leaks the answer straight into the
eval score. Without this, eval/run_eval.py's headline accuracy mostly measures
memorization, not the model's ability to generalize to a new case.

The split is a hash of each case's stable `id`, not an index into the current
list or a shuffle of it, so it doesn't reshuffle existing cases' membership if
data/build_dataset.py adds more cases later — a case that was eval-only stays
eval-only.
"""

from __future__ import annotations

import hashlib

# Fraction of the case pool permanently reserved for evaluation only, never
# used to build fine-tuning examples.
EVAL_HOLDOUT_FRACTION = 0.25

# Bump this if the split itself needs to change; changing it reassigns cases.
_SALT = "aegismed-train-eval-split-v1"


def is_eval_only(case_id: str) -> bool:
    """True if this case id falls in the permanent eval-only holdout."""
    digest = hashlib.sha256(f"{_SALT}:{case_id}".encode("utf-8")).hexdigest()
    frac = int(digest[:8], 16) / 0xFFFFFFFF  # -> deterministic float in [0, 1)
    return frac < EVAL_HOLDOUT_FRACTION


def split_cases(cases: list[dict]) -> tuple[list[dict], list[dict]]:
    """Partition cases into (finetune_eligible, eval_only) — disjoint sets.

    finetune_eligible cases may be used to build fine-tuning examples.
    eval_only cases must never be, so eval/run_eval.py's score on them
    reflects generalization rather than memorized training targets.
    """
    finetune_eligible = [c for c in cases if not is_eval_only(c["id"])]
    eval_only = [c for c in cases if is_eval_only(c["id"])]
    return finetune_eligible, eval_only

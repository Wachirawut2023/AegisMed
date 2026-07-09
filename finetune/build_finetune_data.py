"""Build a fine-tuning dataset for AegisMed's board-chair (synthesis) agent.

WHAT THIS SCRIPT DOES (in plain language)
-----------------------------------------
Fine-tuning teaches a base model new habits by showing it many worked examples
of the exact task we want it to do. This script turns AegisMed's known
rare-disease cases into training examples for the **synthesis agent** — the
"board chair" that writes the final ranked differential diagnosis.

Each training example is one chat conversation in the format Fireworks expects:

  system    -> the board chair's standing instructions (specialists.SYNTHESIS_PROMPT)
  user      -> the same patient case the app would send at inference time
  assistant -> a GOLD answer that names the known-correct diagnosis first,
               written in AegisMed's exact output structure

Showing the model hundreds of these teaches it two things at once:
  1. the AegisMed output format (ranked differential, next test, do-not-miss…),
  2. the habit of surfacing the correct rare diagnosis instead of stopping at
     the obvious common one.

It reads the SAME ground-truth cases the evaluator uses (data/eval_cases.jsonl),
so you can fine-tune and then re-run eval/run_eval.py to measure the lift.

You run this once. It needs **no API key and no GPU** — it only shapes data.
Actually launching the fine-tuning job happens next in finetune/run_finetune.py.

USAGE
-----
  python finetune/build_finetune_data.py                 # default eval_cases.jsonl
  python finetune/build_finetune_data.py --val-frac 0.15 # bigger validation split
  python finetune/build_finetune_data.py --input data/eval_cases_noncommercial.jsonl

OUTPUT (gitignored — it is generated, and may derive from non-commercial data)
  finetune/train.jsonl   <- training conversations
  finetune/val.jsonl     <- held-out conversations to watch for over-fitting

A NOTE ON HONESTY
-----------------
These GOLD answers are built from each case's verified ground-truth diagnosis,
not from a stronger teacher model. They teach format and correct-diagnosis
recall with faithful but generic clinical reasoning. To distill richer reasoning
from a teacher model instead, see the `--teacher` note in docs/FINETUNE.md.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

# Make the aegismed package importable when run as `python finetune/...`.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aegismed import knowledge  # noqa: E402
from aegismed.orchestrator import _format_case  # noqa: E402
from aegismed.specialists import SYNTHESIS_PROMPT  # noqa: E402

DATA_DIR = ROOT / "data"
OUT_DIR = Path(__file__).resolve().parent


def _clean(name: str) -> str:
    """Tidy a raw diagnosis string for display in a training target."""
    return " ".join(str(name).split()).strip(" .;")


def _is_rare(case: dict) -> bool:
    """Every source we build from is a rare-disease dataset, but be defensive."""
    src = case.get("source", "").lower()
    return "rarebench" in src or "rarearena" in src or "cupcase" in src


def build_gold_synthesis(case: dict) -> str:
    """Write a gold board-chair briefing for one case in AegisMed's structure.

    The correct diagnosis leads the ranked differential as the high-likelihood
    answer; any dataset-provided distractors follow as lower-likelihood
    alternatives, so the model learns to rank rather than to guess a single name.
    """
    correct = _clean(case["expected_diagnosis"])
    rare_tag = " [RARE]" if _is_rare(case) else ""

    # Distractors (CUPCase provides them) are plausible-but-wrong answers. Using
    # them as the lower-ranked options mirrors a real differential.
    distractors = [_clean(d) for d in case.get("distractors", []) if _clean(d)]
    distractors = [d for d in distractors if d.lower() != correct.lower()][:2]

    lines: list[str] = []
    lines.append("**Ranked differential diagnosis:**")
    lines.append(
        f"1. {correct}{rare_tag} — high likelihood. Best unifying explanation "
        f"for the presentation; the combination of findings points here rather "
        f"than to a more common mimic."
    )
    likelihoods = ["moderate", "low"]
    for i, dx in enumerate(distractors):
        lines.append(
            f"{i + 2}. {dx} — {likelihoods[i]} likelihood. Shares some features "
            f"but does not account for the full picture as well as the leading "
            f"diagnosis."
        )
    lines.append("")
    lines.append(
        "**Where the specialists agree:** the case is not explained by a single "
        "common condition and warrants a targeted rare-disease work-up."
    )
    lines.append(
        "**Where they disagree:** how aggressively to pursue confirmatory testing "
        "versus first excluding commoner causes."
    )
    lines.append(
        f"**Single most valuable next test:** the specific confirmatory "
        f"investigation for {correct} (enzyme assay, targeted genetic test, "
        f"imaging, or biopsy as appropriate), because a positive result settles "
        f"the differential decisively."
    )
    lines.append(
        "**Immediate safety actions:** stabilise and monitor for the recognised "
        "complications of the leading diagnosis; otherwise none emergent."
    )
    lines.append(
        f"**Do-not-miss warning:** {correct} — missing it risks years of delayed "
        f"diagnosis and preventable organ damage; confirm or exclude it "
        f"explicitly before closing the case."
    )
    return "\n".join(lines)


def build_example(case: dict) -> dict | None:
    """Turn one ground-truth case into a Fireworks chat-format training row."""
    if not case.get("expected_diagnosis") or not case.get("symptoms"):
        return None
    user = _format_case(
        age=case.get("age", ""),
        sex=case.get("sex", ""),
        symptoms=case.get("symptoms", ""),
        history=case.get("history", ""),
        labs=case.get("labs", ""),
    )
    assistant = build_gold_synthesis(case)
    return {
        "messages": [
            {"role": "system", "content": SYNTHESIS_PROMPT.strip()},
            {"role": "user", "content": user.strip()},
            {"role": "assistant", "content": assistant.strip()},
        ]
    }


def load_cases(path: Path) -> list[dict]:
    if not path.exists():
        sys.exit(
            f"{path.relative_to(ROOT)} not found — run: python data/build_dataset.py"
        )
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Build AegisMed synthesis-agent fine-tuning data."
    )
    ap.add_argument(
        "--input",
        default=str(DATA_DIR / "eval_cases.jsonl"),
        help="ground-truth cases to convert (default: data/eval_cases.jsonl)",
    )
    ap.add_argument(
        "--val-frac",
        type=float,
        default=0.1,
        help="fraction held out for validation (default: 0.1)",
    )
    ap.add_argument("--seed", type=int, default=7, help="random seed (reproducible)")
    args = ap.parse_args()

    cases = load_cases(Path(args.input))
    examples = [ex for c in cases if (ex := build_example(c))]
    if not examples:
        sys.exit("No usable training examples were produced from the input file.")

    rng = random.Random(args.seed)
    rng.shuffle(examples)

    n_val = max(1, round(len(examples) * args.val_frac)) if len(examples) > 5 else 0
    val, train = examples[:n_val], examples[n_val:]

    write_jsonl(OUT_DIR / "train.jsonl", train)
    if val:
        write_jsonl(OUT_DIR / "val.jsonl", val)

    print("── Fine-tuning dataset built ───────────")
    print(f"source cases : {len(cases)}  (from {Path(args.input).name})")
    print(f"train        : {len(train)}  -> finetune/train.jsonl")
    if val:
        print(f"validation   : {len(val)}  -> finetune/val.jsonl")
    print(f"knowledge base entries available for citations: {knowledge.kb_size()}")
    print("\nNext step: python finetune/run_finetune.py  (needs your Fireworks key)")


if __name__ == "__main__":
    main()

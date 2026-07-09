"""Build a fine-tuning dataset for AegisMed's board-chair (synthesis) agent.

WHAT THIS SCRIPT DOES (in plain language)
-----------------------------------------
Fine-tuning teaches a base model new habits by showing it many worked examples
of the exact task we want it to do. This script turns AegisMed's known
rare-disease cases into training examples for the **synthesis agent** — the
"board chair" that writes the final ranked differential diagnosis.

Each training example is one chat conversation in the format Fireworks expects:

  system    -> the board chair's standing instructions (specialists.SYNTHESIS_PROMPT)
  user      -> the SAME input the synthesis agent sees at real inference time:
               the grounded case + retrieved evidence + BOARD ROSTER + every
               specialist's REAL opinion, produced by actually running
               retrieval and the specialist board (base model) for this case
  assistant -> a GOLD answer that names the known-correct diagnosis first,
               written in AegisMed's exact output structure

This means each training example costs real model calls to build (1 retrieval
+ up to 7 specialists per case, via aegismed.orchestrator._convene_board — the
exact same function aegismed/orchestrator.py:diagnose() calls) — it is NOT
free/offline like earlier versions of this script. Earlier this script paired
the gold answer with a bare case description and no specialist opinions at
all, which doesn't match what the synthesis agent actually reads at inference
time; the model was training on a different-shaped input than it would ever
see in production. Building the real input matters: the model should train on
the same text it will see at inference time, or the skill won't transfer.

It reads the SAME ground-truth cases the evaluator uses (data/eval_cases.jsonl)
but ONLY the fine-tuning-eligible portion of them: aegismed.data_split keeps a
permanent, disjoint holdout of cases reserved for eval/run_eval.py alone, so a
case's gold answer is never trained into the model that then gets scored on
that same case. Skipping this split is what made earlier eval numbers
untrustworthy — most of the eval set was also in the training set.

USAGE
-----
  python finetune/build_finetune_data.py                 # default eval_cases.jsonl
  python finetune/build_finetune_data.py --val-frac 0.15 # bigger validation split
  python finetune/build_finetune_data.py --input data/eval_cases_noncommercial.jsonl
  python finetune/build_finetune_data.py --limit 10      # quick, cheap smoke test
  python finetune/build_finetune_data.py --delay 1.0     # pause between cases
  python finetune/build_finetune_data.py \
      --teacher-model accounts/fireworks/models/deepseek-v4-pro  # richer gold answers

Needs FIREWORKS_API_KEY in .env (real model calls) — same key the app uses.
DEMO_MODE must be off (the default once a key is set): demo mode returns the
same canned specialist opinions for every case, which would actively poison
training data rather than just being a no-op.

OUTPUT (gitignored — it is generated, and may derive from non-commercial data)
  finetune/train.jsonl   <- training conversations
  finetune/val.jsonl     <- held-out conversations to watch for over-fitting

A NOTE ON HONESTY
-----------------
By default the GOLD (assistant) answers are built from each case's verified
ground-truth diagnosis with a fixed template, not from a stronger teacher
model — faithful but generic clinical reasoning. Pass `--teacher-model` to
distill richer, case-specific reasoning instead: a stronger model is shown
this case's REAL specialist opinions plus the verified diagnosis, and asked
to write the briefing as if its own reasoning had reached that answer, citing
the specific findings that support it. This adds one more real model call per
case (on top of retrieval + specialists) — see docs/FINETUNE.md.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from pathlib import Path

# Make the aegismed package importable when run as `python finetune/...`.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aegismed import config, data_split, knowledge, llm  # noqa: E402
from aegismed.orchestrator import _convene_board  # noqa: E402
from aegismed.specialists import SYNTHESIS_PROMPT  # noqa: E402

DATA_DIR = ROOT / "data"
OUT_DIR = Path(__file__).resolve().parent

# Appended to the real synthesis_input when distilling a gold answer from a
# teacher model: reveals the verified diagnosis and asks for case-specific
# reasoning instead of a guess, without the teacher admitting it was told.
_TEACHER_SUFFIX = """

---
TRAINING-DATA NOTE (not part of a real case; never mention this note or that
you were told the answer): you are helping build a training example for the
board-chair role above. The verified correct diagnosis for this case is:
{correct}

Write the full briefing in AegisMed's exact structure, reasoning as if your
own analysis had reached this diagnosis — cite SPECIFIC findings from the
case and from the specialists' opinions above that support it over the
alternatives. Be concrete and case-specific, not generic boilerplate.

Start your reply directly with the "**Ranked differential diagnosis:**"
heading — no preamble.
"""

# Reasoning models write visible chain-of-thought straight into the reply
# before their actual answer, regardless of "no preamble" instructions. Slice
# from the first structural heading so the training target is only the
# briefing itself, not the model's narrated thinking.
_BRIEFING_MARKER = "**Ranked differential diagnosis:**"

# Generous budget for a teacher call: reasoning models spend a lot of it on
# chain-of-thought before ever reaching the structured answer.
_TEACHER_MAX_TOKENS = 3072


def _extract_briefing(text: str) -> str:
    idx = text.find(_BRIEFING_MARKER)
    return text[idx:].strip() if idx != -1 else text.strip()


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


async def build_gold_synthesis_teacher(case: dict, synthesis_input: str, teacher_model: str) -> str:
    """Ask a stronger 'teacher' model to write the gold answer with real reasoning.

    Unlike build_gold_synthesis's fixed template, this reads the case's real
    specialist opinions (from _convene_board) and is told the verified
    diagnosis, then writes case-specific reasoning for why it fits — same
    output structure, richer and case-grounded content.
    """
    correct = _clean(case["expected_diagnosis"])
    prompt = synthesis_input + _TEACHER_SUFFIX.format(correct=correct)
    text = await llm.chat(
        SYNTHESIS_PROMPT, prompt, agent_name="synthesis-teacher", model=teacher_model,
        max_tokens=_TEACHER_MAX_TOKENS,
    )
    briefing = _extract_briefing(text)
    if _BRIEFING_MARKER not in text:
        print(f"  ! {case.get('id', '?')}: teacher reply never reached "
              f"'{_BRIEFING_MARKER}' — using raw reply as-is, inspect it")
    return briefing


async def build_example(case: dict, teacher_model: str | None = None) -> dict | None:
    """Turn one ground-truth case into a Fireworks chat-format training row.

    Actually runs retrieval + the specialist board (base model, real calls)
    for this case, so the `user` turn matches real synthesis-agent inference
    input exactly — same helper (`orchestrator._convene_board`) the live app
    uses in `orchestrator.diagnose()`. The `assistant` turn is the fixed
    template gold answer, unless `teacher_model` is given, in which case a
    stronger model distills a richer, case-specific gold answer instead.
    """
    if not case.get("expected_diagnosis") or not case.get("symptoms"):
        return None
    board = await _convene_board(
        age=case.get("age", ""), sex=case.get("sex", ""),
        symptoms=case.get("symptoms", ""), history=case.get("history", ""),
        labs=case.get("labs", ""),
    )
    if teacher_model:
        assistant = await build_gold_synthesis_teacher(case, board["synthesis_input"], teacher_model)
    else:
        assistant = build_gold_synthesis(case)
    return {
        "messages": [
            {"role": "system", "content": SYNTHESIS_PROMPT.strip()},
            {"role": "user", "content": board["synthesis_input"].strip()},
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


async def build_examples(
    cases: list[dict], delay: float, teacher_model: str | None = None
) -> tuple[list[dict], list[dict]]:
    """Build one training example per case, sequentially (real model calls).

    Returns (examples, failures) — failures are (case, error) pairs for cases
    that errored out; the case is skipped rather than aborting the whole run.
    """
    examples: list[dict] = []
    failures: list[tuple[dict, str]] = []
    for i, case in enumerate(cases, 1):
        try:
            example = await build_example(case, teacher_model=teacher_model)
        except Exception as err:  # noqa: BLE001 — report and continue the run
            failures.append((case, str(err)[:120]))
            print(f"  [{i}/{len(cases)}] ! {case.get('id', '?')}: {str(err)[:80]}")
            continue
        if example is None:
            print(f"  [{i}/{len(cases)}] · {case.get('id', '?')} (missing fields, skipped)")
            continue
        examples.append(example)
        print(f"  [{i}/{len(cases)}] ✓ {case.get('id', '?')}")
        if delay:
            time.sleep(delay)
    return examples, failures


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
    ap.add_argument(
        "--limit", type=int, default=None,
        help="only build from the first N fine-tuning-eligible cases (quick/cheap smoke test)",
    )
    ap.add_argument(
        "--delay", type=float, default=0.0,
        help="seconds to pause between cases (gentle on rate limits)",
    )
    ap.add_argument(
        "--teacher-model", default=None,
        help="if set, distill gold answers from this stronger model instead of "
             "the fixed template (e.g. accounts/fireworks/models/deepseek-v4-pro) "
             "— one extra real model call per case. Availability depends on your "
             "Fireworks account/catalog. Omit to keep the template gold answers.",
    )
    args = ap.parse_args()

    if config.demo_mode():
        sys.exit(
            "DEMO_MODE is on (or no FIREWORKS_API_KEY is set), so every specialist "
            "would return the same canned demo text regardless of the case. That "
            "would poison the training data rather than just being a no-op — set "
            "FIREWORKS_API_KEY (and DEMO_MODE=false or unset) in .env first. This "
            "step now makes real, billed model calls: 1 retrieval + up to 7 "
            "specialist calls per case."
        )

    all_cases = load_cases(Path(args.input))
    eligible, eval_only = data_split.split_cases(all_cases)
    if args.limit:
        eligible = eligible[: args.limit]

    print("── Building fine-tuning dataset (real model calls) ───────────")
    print(f"source cases        : {len(all_cases)}  (from {Path(args.input).name})")
    print(f"reserved for eval only, never trained on : {len(eval_only)}")
    print(f"fine-tuning-eligible : {len(eligible)}"
          + (f"  (using first {args.limit})" if args.limit else ""))
    print(f"gold answers         : "
          + (f"distilled from teacher {args.teacher_model}" if args.teacher_model
             else "fixed template (pass --teacher-model for richer, case-specific reasoning)"))
    print()

    examples, failures = asyncio.run(
        build_examples(eligible, args.delay, teacher_model=args.teacher_model)
    )
    if not examples:
        sys.exit("No usable training examples were produced.")

    rng = random.Random(args.seed)
    rng.shuffle(examples)

    n_val = max(1, round(len(examples) * args.val_frac)) if len(examples) > 5 else 0
    val, train = examples[:n_val], examples[n_val:]

    write_jsonl(OUT_DIR / "train.jsonl", train)
    if val:
        write_jsonl(OUT_DIR / "val.jsonl", val)

    print("\n── Fine-tuning dataset built ───────────")
    print(f"built        : {len(examples)}  (from {len(eligible)} eligible cases, "
          f"{len(failures)} failed)")
    print(f"train        : {len(train)}  -> finetune/train.jsonl")
    if val:
        print(f"validation   : {len(val)}  -> finetune/val.jsonl")
    print(f"knowledge base entries available for citations: {knowledge.kb_size()}")
    print(f"\n{len(eval_only)} cases were held out and never touched — score against "
          f"those with eval/run_eval.py for a trustworthy number.")
    print("\nNext step: python finetune/run_finetune.py  (needs your Fireworks key)")


if __name__ == "__main__":
    main()

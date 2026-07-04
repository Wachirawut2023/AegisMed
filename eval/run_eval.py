"""Score AegisMed against the evaluation cases.

WHAT THIS DOES (plain language)
-------------------------------
For every test case in data/eval_cases.jsonl it:
  1. sends the case through AegisMed's five-specialist board,
  2. reads the board's answer,
  3. checks whether the KNOWN-correct diagnosis appears anywhere in that answer.

Then it prints a score: "AegisMed named the correct rare diagnosis in X% of
cases." That single number is the headline you can put in your demo video.

IMPORTANT: this needs a real AI to be meaningful, so set your Fireworks API key
first (see .env). In demo mode the app always returns the same sample answer,
so the score is meaningless — the script will warn you and only test plumbing.

USAGE
-----
  python eval/run_eval.py                 # score every case
  python eval/run_eval.py --limit 10      # quick run on the first 10
  python eval/run_eval.py --delay 1.0     # pause between cases (rate limits)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

# Make the aegismed package importable when run as `python eval/run_eval.py`
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aegismed import config, orchestrator  # noqa: E402

DATA_DIR = ROOT / "data"
RESULTS = Path(__file__).resolve().parent / "results.md"

# Words too generic to help identify a specific disease.
_STOPWORDS = {
    "disease", "diseases", "syndrome", "disorder", "disorders", "deficiency",
    "type", "acid", "acidemia", "aciduria", "positive", "negative", "acute",
    "chronic", "congenital", "primary", "secondary", "the", "and", "with",
    "due", "gca", "of",
}


def _normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower())


def _significant_tokens(name: str) -> list[str]:
    return [t for t in _normalize(name).split()
            if len(t) >= 4 and t not in _STOPWORDS]


def is_hit(board_text: str, aliases: list[str]) -> bool:
    """True if any accepted spelling of the diagnosis is present in the output.

    Two ways to match (either counts):
      - the whole alias phrase appears as a substring, OR
      - every significant word of the alias appears somewhere in the text.
    """
    hay = _normalize(board_text)
    hay_tokens = set(hay.split())
    for alias in aliases:
        alias_n = _normalize(alias).strip()
        if len(alias_n) >= 5 and alias_n in hay:
            return True
        toks = _significant_tokens(alias)
        if toks and all(t in hay_tokens for t in toks):
            return True
    return False


def load_cases(limit: int | None) -> list[dict]:
    path = DATA_DIR / "eval_cases.jsonl"
    if not path.exists():
        sys.exit("data/eval_cases.jsonl not found — run: python data/build_dataset.py")
    cases = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return cases[:limit] if limit else cases


def load_alias_table() -> dict[str, list[str]]:
    path = DATA_DIR / "aliases.json"
    return json.loads(path.read_text()) if path.exists() else {}


async def score_case(case: dict, alias_table: dict) -> dict:
    result = await orchestrator.diagnose(
        age=case["age"], sex=case["sex"], symptoms=case["symptoms"],
        history=case["history"], labs=case["labs"],
    )
    board_text = result["synthesis"] + "\n" + "\n".join(
        o["opinion"] for o in result["specialist_opinions"])
    # accepted spellings = this case's aliases + any extra from the alias table
    aliases = set(case.get("expected_aliases", []))
    aliases.add(case["expected_diagnosis"])
    aliases.update(alias_table.get(case["expected_diagnosis"], []))
    hit = is_hit(board_text, sorted(aliases))
    return {"id": case["id"], "source": case["source"],
            "expected": case["expected_diagnosis"], "hit": hit}


async def main_async(args) -> None:
    cases = load_cases(args.limit)
    alias_table = load_alias_table()

    if config.demo_mode():
        print("⚠️  DEMO MODE: the app returns a fixed sample answer, so these")
        print("    scores are NOT meaningful. Set FIREWORKS_API_KEY in .env for")
        print("    a real evaluation. Running anyway to test the pipeline.\n")

    print(f"Scoring {len(cases)} cases with model: {config.MODEL}\n")
    rows = []
    for i, case in enumerate(cases, 1):
        try:
            row = await score_case(case, alias_table)
        except Exception as e:  # noqa: BLE001 — report and continue the run
            row = {"id": case["id"], "source": case["source"],
                   "expected": case["expected_diagnosis"], "hit": False,
                   "error": str(e)[:80]}
        rows.append(row)
        mark = "✓" if row["hit"] else "·"
        note = f"  ! {row['error']}" if row.get("error") else ""
        print(f"  [{i}/{len(cases)}] {mark} {row['expected'][:48]}{note}")
        if args.delay:
            time.sleep(args.delay)

    write_report(rows, alias_table)


def write_report(rows: list[dict], alias_table: dict) -> None:
    total = len(rows)
    hits = sum(r["hit"] for r in rows)
    pct = 100 * hits / total if total else 0

    # per-source breakdown
    per: dict[str, list[int]] = {}
    for r in rows:
        per.setdefault(r["source"], [0, 0])
        per[r["source"]][1] += 1
        per[r["source"]][0] += int(r["hit"])

    lines = ["# AegisMed evaluation results", ""]
    lines.append(f"**Model:** `{config.MODEL}`  ")
    lines.append(f"**Demo mode:** {config.demo_mode()} "
                 f"{'(scores not meaningful)' if config.demo_mode() else ''}  ")
    lines.append("")
    lines.append(f"## Headline: correct diagnosis surfaced in "
                 f"**{hits}/{total} = {pct:.0f}%** of cases")
    lines.append("")
    lines.append("| Source | Hit rate |")
    lines.append("|---|---|")
    for src, (h, n) in sorted(per.items()):
        lines.append(f"| {src} | {h}/{n} ({100*h/n:.0f}%) |")
    lines.append("")
    lines.append("## Per-case")
    lines.append("| Case | Source | Correct diagnosis | Found? |")
    lines.append("|---|---|---|---|")
    for r in rows:
        found = "✅" if r["hit"] else "❌"
        exp = r["expected"].replace("|", "/")
        lines.append(f"| {r['id']} | {r['source']} | {exp} | {found} |")
    lines.append("")
    lines.append("_“Found” means the correct diagnosis (or a known synonym) "
                 "appeared anywhere in the board's output. Matching is text-based "
                 "and approximate; skim mismatches by hand before trusting a number._")

    RESULTS.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n── Result: {hits}/{total} = {pct:.0f}% correct ──")
    print(f"Wrote {RESULTS.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate AegisMed on rare-disease cases.")
    ap.add_argument("--limit", type=int, default=None, help="only score the first N cases")
    ap.add_argument("--delay", type=float, default=0.0, help="seconds to pause between cases")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()

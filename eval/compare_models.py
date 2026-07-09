"""A/B test multiple models and compare their evaluation results.

WHAT THIS DOES
--------------
Runs the evaluator on different models, saves results separately, and produces
a side-by-side comparison report showing which model catches which diagnoses.

USAGE
-----
  python eval/compare_models.py
  python eval/compare_models.py --limit 20  # quick test on 20 cases
  python eval/compare_models.py --delay 0.5 # pause between cases

This will run eval on each model in MODELS_TO_TEST (see below) and write:
  eval/results_gemma3_tuned.md       <- tuned Gemma 3 results
  eval/results_gemma4_base.md        <- base Gemma 4 results
  eval/comparison.md                 <- side-by-side analysis

WHAT TO COMPARE
---------------
- Headline accuracy (X% of cases correct)
- Per-source performance (which dataset types?)
- Per-case wins (which model caught which diagnosis?)
- Model size vs accuracy tradeoff
- Cost/speed tradeoff
"""

from __future__ import annotations

import argparse
import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Models to compare: name -> MODEL env var value
MODELS_TO_TEST = {
    "gemma3_tuned": "accounts/wachirawut2002-fqt88/models/aegismed-gemma-tuned",
    "gemma4_base": "accounts/fireworks/models/gemma-4-31b-it",
    "gemma3_base": "accounts/fireworks/models/gemma-3-27b-it",
}


def run_eval_for_model(model_name: str, model_id: str, limit: int | None, delay: float) -> Path:
    """Run eval/run_eval.py with a specific model, return path to results.md."""
    import os
    import tempfile

    env = os.environ.copy()
    env["MODEL"] = model_id

    print(f"\n{'='*60}")
    print(f"Testing: {model_name} ({model_id})")
    print(f"{'='*60}")

    cmd = ["python", "eval/run_eval.py"]
    if limit:
        cmd.extend(["--limit", str(limit)])
    if delay:
        cmd.extend(["--delay", str(delay)])

    result = subprocess.run(
        cmd,
        cwd=ROOT,
        env=env,
        capture_output=False,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Eval failed for {model_name}")

    # Move results to model-specific file
    src = ROOT / "eval" / "results.md"
    dst = ROOT / "eval" / f"results_{model_name}.md"
    if src.exists():
        src.rename(dst)
    return dst


def parse_results_file(path: Path) -> dict:
    """Extract key metrics from a results.md file."""
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    data = {
        "file": str(path.relative_to(ROOT)),
        "model": path.stem.replace("results_", ""),
        "accuracy": "unknown",
        "by_source": {},
        "cases": [],
    }

    # Parse headline: "correct diagnosis surfaced in **X/Y = Z%** of cases"
    for line in lines:
        if "correct diagnosis surfaced in" in line and "=" in line:
            # Extract X, Y, and percentage
            parts = line.split("=")
            if len(parts) >= 2:
                pct = parts[-1].split("%")[0].strip()
                data["accuracy"] = pct

    # Parse per-source table
    in_source_table = False
    for line in lines:
        if "| Source | Hit rate |" in line:
            in_source_table = True
            continue
        if in_source_table and line.startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) == 2 and cells[0] not in ("Source", ""):
                src = cells[0]
                rate = cells[1].split("(")[0].strip() if "(" in cells[1] else cells[1]
                data["by_source"][src] = rate

        # Parse per-case table for hits/misses
        if "| Case | Source | Correct diagnosis | Found? |" in line:
            in_source_table = False
        if not in_source_table and line.startswith("| ") and "Case" not in line and "---" not in line:
            cells = [c.strip() for c in line.split("|")[1:-1]]
            if len(cells) == 4:
                data["cases"].append({
                    "id": cells[0],
                    "source": cells[1],
                    "diagnosis": cells[2],
                    "found": cells[3] == "✅",
                })

    return data


def write_comparison(results: dict[str, dict]) -> None:
    """Write a side-by-side comparison report."""
    out = ROOT / "eval" / "comparison.md"
    models = list(results.keys())

    lines = ["# A/B Test Comparison\n"]

    # Headline accuracy
    lines.append("## Headline Accuracy\n")
    lines.append("| Model | Accuracy |")
    lines.append("|---|---|")
    for name in models:
        acc = results[name].get("accuracy", "?")
        lines.append(f"| {name} | {acc}% |")
    lines.append("")

    # Per-source breakdown
    lines.append("## Per-Source Breakdown\n")
    all_sources = set()
    for r in results.values():
        all_sources.update(r.get("by_source", {}).keys())

    lines.append("| Source | " + " | ".join(models) + " |")
    lines.append("|---|" + "|".join(["---|"] * len(models)))
    for src in sorted(all_sources):
        row = [src]
        for name in models:
            rate = results[name].get("by_source", {}).get(src, "—")
            row.append(rate)
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Win analysis: which cases each model got right
    if len(models) == 2:
        lines.append("## Case-by-case wins\n")
        m1, m2 = models[0], models[1]
        cases_m1 = {c["id"]: c for c in results[m1].get("cases", [])}
        cases_m2 = {c["id"]: c for c in results[m2].get("cases", [])}

        both_right = sum(
            1 for cid in cases_m1
            if cases_m1[cid]["found"] and cases_m2.get(cid, {}).get("found")
        )
        only_m1 = sum(
            1 for cid in cases_m1
            if cases_m1[cid]["found"] and not cases_m2.get(cid, {}).get("found")
        )
        only_m2 = sum(
            1 for cid in cases_m2
            if cases_m2[cid]["found"] and not cases_m1.get(cid, {}).get("found")
        )
        both_wrong = sum(
            1 for cid in cases_m1
            if not cases_m1[cid]["found"] and not cases_m2.get(cid, {}).get("found")
        )

        lines.append(f"- Both correct: {both_right}")
        lines.append(f"- Only {m1}: {only_m1}")
        lines.append(f"- Only {m2}: {only_m2}")
        lines.append(f"- Both missed: {both_wrong}")
        lines.append("")

        if only_m1:
            lines.append(f"### Cases {m1} caught but {m2} missed\n")
            for cid, c in sorted(cases_m1.items()):
                if c["found"] and not cases_m2.get(cid, {}).get("found"):
                    lines.append(f"- {cid}: {c['diagnosis']}")
            lines.append("")

        if only_m2:
            lines.append(f"### Cases {m2} caught but {m1} missed\n")
            for cid, c in sorted(cases_m2.items()):
                if c["found"] and not cases_m1.get(cid, {}).get("found"):
                    lines.append(f"- {cid}: {c['diagnosis']}")
            lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"\n✓ Comparison written to {out.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser(description="A/B test multiple models on AegisMed.")
    ap.add_argument("--models", default="gemma3_tuned,gemma4_base",
                    help="comma-separated model keys to test (default: gemma3_tuned,gemma4_base)")
    ap.add_argument("--limit", type=int, default=None, help="limit cases (for quick test)")
    ap.add_argument("--delay", type=float, default=0.0, help="delay between cases (rate limit)")
    args = ap.parse_args()

    model_keys = [k.strip() for k in args.models.split(",")]
    unknown = [k for k in model_keys if k not in MODELS_TO_TEST]
    if unknown:
        sys.exit(f"Unknown models: {unknown}\nKnown: {', '.join(MODELS_TO_TEST.keys())}")

    results = {}
    for key in model_keys:
        try:
            path = run_eval_for_model(key, MODELS_TO_TEST[key], args.limit, args.delay)
            results[key] = parse_results_file(path)
        except Exception as err:
            print(f"✗ Failed to test {key}: {err}")
            sys.exit(1)

    write_comparison(results)
    print(f"\nOpen eval/comparison.md to see the full analysis.")


if __name__ == "__main__":
    main()

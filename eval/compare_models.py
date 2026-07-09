"""Compare AegisMed's board across several models on the same eval cases.

WHAT THIS DOES (plain language)
-------------------------------
`run_eval.py` scores one model at a time. This script runs the SAME cases
through the SAME board, once per model, swapping `aegismed.config.MODEL`
between passes, then writes one side-by-side report:

    accuracy of the fine-tuned model  vs.  the base Gemma model  vs.  Gemma 4

USAGE
-----
  python eval/compare_models.py \\
      --finetuned accounts/you/models/your-tuned-model \\
      --limit 10                     # quick run on the first 10 cases

  python eval/compare_models.py      # full 75-case run, default model IDs

The fine-tuned model ID can also be set via the FINETUNED_MODEL env var
instead of --finetuned.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aegismed import config  # noqa: E402
from eval import run_eval  # noqa: E402

RESULTS_JSON = Path(__file__).resolve().parent / "comparison_results.json"
RESULTS_MD = Path(__file__).resolve().parent / "model_comparison.md"

DEFAULT_BASE = "accounts/fireworks/models/gemma-3-27b-it"
DEFAULT_GEMMA4 = "accounts/fireworks/models/gemma-4-31b-it"


async def run_one_model(
    label: str, model_id: str, cases: list[dict], alias_table: dict,
    use_intake: bool, delay: float,
) -> dict:
    """Score every case with one model and return {label, model, rows, elapsed}."""
    config.MODEL = model_id
    print(f"\n=== {label}: {model_id} ===")
    rows = []
    for i, case in enumerate(cases, 1):
        start = time.monotonic()
        try:
            row = await run_eval.score_case(case, alias_table, use_intake=use_intake)
            row["latency_s"] = round(time.monotonic() - start, 2)
        except Exception as e:  # noqa: BLE001 — report and continue the run
            row = {
                "id": case["id"], "source": case["source"],
                "expected": case["expected_diagnosis"], "hit": False,
                "error": str(e)[:120], "latency_s": round(time.monotonic() - start, 2),
            }
        rows.append(row)
        mark = "✓" if row["hit"] else "·"
        note = f"  ! {row['error']}" if row.get("error") else ""
        print(f"  [{i}/{len(cases)}] {mark} {row['expected'][:46]}{note}")
        if delay:
            time.sleep(delay)
    return {"label": label, "model": model_id, "rows": rows}


def _summarize(rows: list[dict]) -> dict:
    total = len(rows)
    hits = sum(r["hit"] for r in rows)
    errors = sum(1 for r in rows if r.get("error"))
    latencies = [r["latency_s"] for r in rows if r.get("latency_s") is not None]
    return {
        "total": total,
        "hits": hits,
        "pct": (100 * hits / total) if total else 0.0,
        "errors": errors,
        "avg_latency_s": round(statistics.mean(latencies), 2) if latencies else None,
    }


def write_report(runs: list[dict], meta: dict) -> None:
    lines = ["# AegisMed model comparison", ""]
    lines.append(f"**Run date:** {meta['run_date']}  ")
    lines.append(f"**Cases:** {meta['n_cases']}  ")
    lines.append(f"**Intake step:** {'on — questions auto-answered from the case' if meta['use_intake'] else 'off'}  ")
    lines.append(
        "**Note:** each model is scored in a single pass at temperature 0.4 — "
        "results are one sample, not an average across repeats, so small "
        "differences (a few percentage points) may just be noise.  "
    )
    lines.append("")

    lines.append("## Headline")
    lines.append("")
    lines.append("| Model | Model ID | Correct | Hit rate | Errors | Avg latency/case |")
    lines.append("|---|---|---|---|---|---|")
    summaries = {}
    for run in runs:
        s = _summarize(run["rows"])
        summaries[run["label"]] = s
        lat = f"{s['avg_latency_s']}s" if s["avg_latency_s"] is not None else "n/a"
        lines.append(
            f"| {run['label']} | `{run['model']}` | {s['hits']}/{s['total']} "
            f"| {s['pct']:.0f}% | {s['errors']} | {lat} |"
        )
    lines.append("")

    # Per-source breakdown, one column per model.
    sources = sorted({r["source"] for run in runs for r in run["rows"]})
    lines.append("## Per-source hit rate")
    lines.append("")
    header = "| Source | " + " | ".join(run["label"] for run in runs) + " |"
    sep = "|---|" + "---|" * len(runs)
    lines.append(header)
    lines.append(sep)
    for src in sources:
        cells = []
        for run in runs:
            src_rows = [r for r in run["rows"] if r["source"] == src]
            h = sum(r["hit"] for r in src_rows)
            n = len(src_rows)
            cells.append(f"{h}/{n} ({100*h/n:.0f}%)" if n else "—")
        lines.append(f"| {src} | " + " | ".join(cells) + " |")
    lines.append("")

    # Per-case matrix.
    lines.append("## Per-case results")
    lines.append("")
    by_id = {}
    for run in runs:
        for r in run["rows"]:
            by_id.setdefault(r["id"], {"source": r["source"], "expected": r["expected"]})
            by_id[r["id"]][run["label"]] = r
    header = "| Case | Source | Correct diagnosis | " + " | ".join(run["label"] for run in runs) + " |"
    sep = "|---|---|---|" + "---|" * len(runs)
    lines.append(header)
    lines.append(sep)
    for case_id, info in by_id.items():
        exp = info["expected"].replace("|", "/")
        cells = []
        for run in runs:
            r = info.get(run["label"])
            if r is None:
                cells.append("—")
            elif r.get("error"):
                cells.append("⚠️")
            elif r["hit"]:
                cells.append("✅")
            else:
                cells.append("❌")
        lines.append(f"| {case_id} | {info['source']} | {exp} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append(
        "_“Correct” means the expected diagnosis (or a known synonym) appeared "
        "anywhere in that model's board output. Matching is text-based and "
        "approximate — skim ❌ rows by hand before trusting small differences "
        "between models. ⚠️ marks a case where the API call itself failed "
        "(see `eval/comparison_results.json` for the error message)._"
    )

    RESULTS_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nWrote {RESULTS_MD.relative_to(ROOT)}")

    print("\n── Summary ──")
    for run in runs:
        s = summaries[run["label"]]
        print(f"  {run['label']:12s} {run['model']:50s} {s['hits']}/{s['total']} = {s['pct']:.0f}%")


async def main_async(args) -> None:
    if config.demo_mode() and not args.allow_demo:
        sys.exit(
            "Refusing to run in demo mode (scores would be meaningless — every "
            "model would return the same canned answer). Set FIREWORKS_API_KEY "
            "in .env, or pass --allow-demo to smoke-test the plumbing anyway."
        )
    if config.demo_mode():
        print("⚠️  DEMO MODE: all three models will return identical canned "
              "answers — this only tests plumbing, not real model quality.\n")

    finetuned = args.finetuned or config.FINETUNED_MODEL_DEFAULT
    if not finetuned:
        sys.exit("No fine-tuned model ID given. Pass --finetuned <model-id> "
                  "or set FINETUNED_MODEL in .env.")

    cases = run_eval.load_cases(args.limit)
    alias_table = run_eval.load_alias_table()
    use_intake = not args.no_intake

    print(f"Comparing 3 models over {len(cases)} cases (intake: "
          f"{'on' if use_intake else 'off'})")

    model_specs = [
        ("Fine-tuned", finetuned),
        ("Base (Gemma 3)", args.base),
        ("Gemma 4", args.gemma4),
    ]

    runs = []
    for label, model_id in model_specs:
        run = await run_one_model(label, model_id, cases, alias_table, use_intake, args.delay)
        runs.append(run)
        # Persist after each model so a later failure doesn't lose earlier results.
        RESULTS_JSON.write_text(json.dumps(runs, indent=2), encoding="utf-8")

    meta = {
        "run_date": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "n_cases": len(cases),
        "use_intake": use_intake,
    }
    write_report(runs, meta)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Compare AegisMed's board across the fine-tuned model, "
                     "the base Gemma model, and Gemma 4."
    )
    ap.add_argument("--finetuned", default=None,
                     help="Fireworks model ID of the fine-tuned model "
                          "(or set FINETUNED_MODEL in .env)")
    ap.add_argument("--base", default=DEFAULT_BASE,
                     help=f"base model ID (default: {DEFAULT_BASE})")
    ap.add_argument("--gemma4", default=DEFAULT_GEMMA4,
                     help=f"Gemma 4 model ID (default: {DEFAULT_GEMMA4})")
    ap.add_argument("--limit", type=int, default=None, help="only score the first N cases")
    ap.add_argument("--delay", type=float, default=0.0, help="seconds to pause between cases")
    ap.add_argument("--no-intake", action="store_true",
                     help="skip the intake step (score the raw case only)")
    ap.add_argument("--allow-demo", action="store_true",
                     help="run even in demo mode (plumbing check only, scores meaningless)")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()

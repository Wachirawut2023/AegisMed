# Fine-tuning pipeline: what was built, real results, and why the eval showed no lift

This documents one end-to-end pass through AegisMed's fine-tuning pipeline: four
pipeline fixes, a real Fireworks fine-tuning job, a real A/B eval, and the
investigation into why that eval showed no measurable lift. Written so it stands
alone — no chat history required.

> **Provenance note:** the fine-tuning pipeline this report describes
> (`finetune/*.py`, `eval/comparison.md`, `eval/results_*.md`,
> `docs/FINETUNE.md`, the `SYNTHESIS_MODEL` config split) was built and run on
> a separate branch, `claude/finetune-pipeline-improvements-ljhc8l`, and isn't
> part of this branch's tree. This report is included here as supporting
> evidence for the "why we ship on base Gemma" note in
> [`PRODUCT_OVERVIEW.md`](PRODUCT_OVERVIEW.md) — the file paths it references
> live on that other branch, not this checkout.

## 1. What was built

Four fixes to the fine-tuning pipeline, all committed on
`claude/finetune-pipeline-improvements-ljhc8l`:

1. **Real specialist opinions in training input.** `finetune/build_finetune_data.py`
   used to pair the gold answer with a bare case description — the synthesis
   agent's "user" turn never matched what it actually reads at inference time
   (grounded case + retrieved evidence + every specialist's real opinion).
   `aegismed/orchestrator.py`'s `diagnose()` was split into a reusable
   `_convene_board()` (retrieval + the specialist fan-out, base model) that both
   `diagnose()` and the data builder now call, so training input is built the same
   way, from real model calls, every time.
2. **Per-agent model routing.** `aegismed/llm.py`'s `chat()` gained a `model`
   override, and `aegismed/config.py` gained `SYNTHESIS_MODEL` (falls back to
   `MODEL`). Only `orchestrator.py`'s synthesis call site uses it — intake,
   retrieval, and all 7 specialists always use the base `MODEL`. This matters
   because the fine-tuning data only trains the synthesis agent's task; pointing
   the single old `MODEL` var at a tuned adapter would have misrouted every other
   agent through it too.
3. **Disjoint train/eval split.** `aegismed/data_split.py` hashes each case's
   stable `id` to permanently reserve ~25% of `data/eval_cases.jsonl` as
   eval-only (21 of 75 cases). `build_finetune_data.py` only builds from the
   other ~75% (54 cases); `eval/run_eval.py` scores against the eval-only holdout
   by default. Previously ~90% of the eval set was also training data, so the
   headline accuracy mostly measured memorization.
4. **Teacher-distilled gold answers.** `build_finetune_data.py --teacher-model`
   shows a stronger model the case's real specialist opinions plus the verified
   diagnosis, and asks it to write case-specific reasoning instead of a fixed
   template. Verified on a live call: the distilled answer cites the actual
   specialist disagreements (e.g. "Medical Genetics favored Zellweger; Neurology
   and Endocrinology considered CDG...") instead of generic boilerplate.

### Bugs found and fixed along the way

- `aegismed/llm.py`: the Fireworks response's `message.content` field can be
  missing entirely when a "reasoning" model is cut off mid-thought — this crashed
  every caller with `KeyError`. Now degrades to `""`. Also added a `max_tokens`
  override (`chat()` was hardcoded to 1024, too small for a reasoning teacher
  model's visible chain-of-thought).
- `finetune/run_finetune.py`: the `httpx.Client`'s default
  `Content-Type: application/json` header silently overrode the multipart
  boundary header `httpx` computes for file uploads, so the dataset upload 400'd
  with `"Error parsing form"` on every real run. Fixed by not setting a default
  Content-Type at all (httpx sets the right one per request).
- `eval/compare_models.py`: `parse_results_file`'s per-case-row check used
  `"Case" not in line` to skip only the results table's header row, but
  `"CUPCase"` contains `"Case"` as a substring — every CUPCase-sourced row was
  silently dropped from every comparison this tool has ever produced. Fixed to
  check for the literal header prefix instead.

## 2. The real fine-tuning job

- **Dataset:** `aegismed-synthesis-v2`, 48 real training examples (54
  fine-tuning-eligible cases minus 6 that failed transiently and were skipped),
  each built from real retrieval + specialist calls (base model, standing in for
  `gemma-3-27b-it` — see caveat below) plus a teacher-distilled gold answer.
- **Base model:** `accounts/fireworks/models/gemma-3-27b-it`
- **Output model:** `accounts/wachirawut2002-fqt88/models/aegismed-gemma-tuned-v2`
- **Epochs:** 1 (Fireworks default LoRA rank — never raised or inspected)
- **Job:** `accounts/wachirawut2002-fqt88/supervisedFineTuningJobs/fe7git03`, completed

**Caveat:** `gemma-3-27b-it` is not available on this Fireworks account's
serverless tier (404s directly). Building the training data and running eval
therefore used `deepseek-v4-flash` as a stand-in base model for retrieval and the
7 specialists — only the actual fine-tuning job trained on real `gemma-3-27b-it`.

## 3. Real eval results

Two arms scored against the 21-case eval-only holdout (`eval/results_baseline.md`,
`eval/results_tuned.md`, `eval/comparison.md`):

| Arm | Specialists/retrieval/intake | Synthesis | Board-level score |
|---|---|---|---|
| baseline | `deepseek-v4-flash` | `deepseek-v4-flash` (no tuning) | 16/21 = 76% |
| tuned | `deepseek-v4-flash` | `aegismed-gemma-tuned-v2` (dedicated on-demand deployment) | 16/21 = 76% |

Identical headline, with exactly one case flipping in each direction (net zero):

- **Only baseline caught:** `rarebench-hms-0` — Vasculitis, autoinflammation,
  immunodeficiency, and hematologic defects syndrome
- **Only tuned caught:** `cupcase-1` — metastatic melanoma

The tuned model's dedicated deployment was torn down after scoring (on-demand GPU
deployments bill continuously while running); getting fresh numbers for that arm
means redeploying, which is a paid action requiring its own explicit go-ahead each
time — not something to auto-trigger.

## 4. Why no lift was observed

Investigating turned up a real, fixable measurement problem, not just "the
fine-tune didn't work" — plus several secondary factors that independently limit
how much lift was even detectable.

### The dominant reason: the metric barely measured what fine-tuning touched

`eval/run_eval.py`'s original scoring built
`board_text = result["synthesis"] + all 7 specialist opinions concatenated`
and counted a hit if the diagnosis name/alias appeared *anywhere* in that combined
text. Retrieval and all 7 specialists were **identical** in both arms (both ran on
`deepseek-v4-flash`, untouched by fine-tuning) — only the synthesis agent differed.
So if any specialist mentioned the right disease name in passing — even as a
dismissed, low-ranked possibility — the case counted as a "hit" regardless of what
the fine-tuned synthesis agent actually did with it. Since specialists already
surface the correct name in most cases (that's most of why baseline hit 16/21 with
*zero* fine-tuning), there was limited room for synthesis-only tuning to move that
particular number, even if it meaningfully changed the synthesis text's quality.

**Fix implemented this pass:** `eval/run_eval.py` now scores three signals,
loosest to strictest:
- `board` — the original whole-board signal (kept; still useful as "did the
  pipeline surface it at all")
- `synthesis` — alias match against `result["synthesis"]` alone, isolating the one
  agent that was actually fine-tuned
- `synthesis top-ranked` — alias match against just the `1.` entry of the
  `**Ranked differential diagnosis:**` list — the strictest, most
  decision-relevant signal (did the agent literally rank it first)

`eval/compare_models.py` now surfaces a synthesis-isolated win/loss breakdown
(not just the board-level one) whenever both compared results files have the new
columns, and falls back gracefully with an explicit note for older-format files.

**Not yet re-run for real:** getting fresh three-signal numbers needs live
Fireworks calls. The Fireworks account (`wachirawut2002-fqt88`) is currently
**suspended** ("possibly due to reaching the monthly spending limit or failure to
pay past invoices" — see fireworks.ai/account/billing), so this pass could not
execute a fresh eval run. `eval/results_baseline.md` and `eval/results_tuned.md`
on disk still reflect the *old* board-only metric.

### Secondary factors that independently limit detectable lift

1. **The baseline arm isn't a true untuned-gemma control.** `gemma-3-27b-it`
   isn't serverless-servable on this account, so the "baseline" arm used a
   different model family (`deepseek-v4-flash`) for synthesis entirely — not
   untuned `gemma-3-27b-it`. The result answers "is tuned-gemma-synthesis roughly
   as good as deepseek-flash-synthesis," not "did the LoRA change gemma's
   behavior." A real isolation needs *both* `gemma-3-27b-it` and
   `aegismed-gemma-tuned-v2` actually serving — ideally as a Multi-LoRA
   deployment (base + adapter, same host), which is what `finetune/deploy.py`
   was originally designed for.
2. **Fine-tuning can't fix upstream misses, and has weak leverage on upstream
   hits.** The synthesis agent only reorders/writes up candidates that retrieval
   + specialists already surfaced (identical in both arms). If the right
   diagnosis never came up upstream, no synthesis tuning saves it; if it came up
   clearly, most competent models rank it first regardless of tuning. That leaves
   only genuinely borderline cases as the band where synthesis-level tuning could
   matter — with 21 cases, plausibly just 1-3 cases, matching the exactly
   one-flip-each-way observed.
3. **Thin training signal.** 48 examples, 1 epoch, default (never raised or
   inspected) LoRA rank, on a capable 27B instruction-following model that
   already follows the `SYNTHESIS_PROMPT`'s detailed format closely. This is
   exactly the underfitting risk flagged before this pass started ("consider
   richer targets and higher LoRA rank if still underfit") — richer/teacher
   targets were done, higher rank/epochs were not, and there's no training-loss
   data to confirm or rule out underfitting.
4. **n=21 is too small for statistical power.** One flipped case is ~5
   percentage points. A genuine modest lift (say +5-8 points) would plausibly show
   up as "0% observed" by chance at this sample size.

## 5. What's still needed for a fully trustworthy comparison

- **Resolve the Fireworks billing suspension** (fireworks.ai/account/billing) —
  nothing further can run against Fireworks until this clears.
- **Re-run eval/run_eval.py for both arms** with the new three-signal metric once
  billing is resolved, to get real synthesis-isolated numbers.
- **A true same-base comparison**: redeploy `gemma-3-27b-it` and
  `aegismed-gemma-tuned-v2` together (Multi-LoRA, one deployment) so the "baseline"
  arm is actually untuned gemma, not a different model family. This is a paid,
  billed-until-torn-down action and needs its own explicit go-ahead each time, same
  as every dedicated-deployment step this session.
- **If still underfit after a fair comparison:** raise LoRA rank / epoch count,
  and inspect training loss (not currently surfaced by `finetune/run_finetune.py`).
- **Larger eval holdout** for statistical power — `data/build_dataset.py --sources
  rarearena` would pull in a bigger, uncommitted case pool;
  `aegismed/data_split.py`'s id-hash split means new cases flow into either pool
  without disturbing the existing 54/21 split.

## Appendix: raw result files

- `eval/results_baseline.md` — baseline arm, board-only metric (pre-dates this
  pass's stricter metrics)
- `eval/results_tuned.md` — tuned arm, board-only metric (same)
- `eval/comparison.md` — board-level A/B comparison (same)

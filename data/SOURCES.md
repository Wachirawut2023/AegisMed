# Data Sources & Licenses

AegisMed's evaluation and demo cases are built from **public, permissively-licensed**
medical datasets by `data/build_dataset.py`. This file documents where each case
comes from and how it may be used — important because the hackathon requires
submissions to be original and MIT-compliant.

## What we bundle in this repo

| Source | What it is | License | Used for |
|---|---|---|---|
| **RareBench** ([HF](https://huggingface.co/datasets/chenxz/RareBench), [GitHub](https://github.com/chenxz1111/RareBench)) | Rare-disease cases as coded symptom lists + confirmed diagnoses. Public sub-sets: **LIRICAL, RAMEDIS, HMS, MME**. | **Apache-2.0** | `eval_cases.jsonl` (coded cases), `aliases.json` |
| **CUPCase** ([HF](https://huggingface.co/datasets/ofir408/CupCase), [GitHub](https://github.com/nadavlab/CUPCase)) | 3,562 **real** case reports from BMC open-access journals, in plain clinical prose, each with the true diagnosis. | **Apache-2.0** | `eval_cases.jsonl` (narrative cases), `demo_cases.json` |

Both are Apache-2.0 licensed, which permits commercial use and redistribution
with attribution — compatible with this repo's MIT license. The generated files
(`eval_cases.jsonl`, `demo_cases.json`, `aliases.json`) are derivative works of
these datasets; please keep this attribution file alongside them.

### Upstream credit for RareBench sub-datasets
RareBench aggregates cases originally published by others. Please also credit:
LIRICAL (Robinson et al.), RAMEDIS, the Human Symptoms–Disease Network / HMS,
and the MME (MyGene2 / Matchmaker Exchange) cohort. See the RareBench paper
(*RareBench: Can LLMs Serve as Rare Diseases Specialists?*, KDD 2024,
[arXiv:2402.06341](https://arxiv.org/abs/2402.06341)) for full references.

## Optional sources (NOT bundled by default)

| Source | Why not bundled | How to use it |
|---|---|---|
| **RareArena** ([HF](https://huggingface.co/datasets/THUMedInfo/RareArena)) — ~50k PMC-derived rare-disease cases | **CC BY-NC-SA 4.0** — the *non-commercial* clause conflicts with an MIT / startup submission | Run `python data/build_dataset.py --sources rarearena`. Output goes to `data/eval_cases_noncommercial.jsonl`, which is **gitignored**. Use for a large private accuracy test only; never commit it. |
| **DDXPlus** ([HF](https://huggingface.co/datasets/aai530-group6/ddxplus)) — synthetic *common*-disease cases | CC-BY 4.0, but off-mission (not rare diseases) | A `load_ddxplus` adapter can be added as a "specificity control" (does AegisMed avoid over-calling rare diseases on ordinary symptoms?). |

## Extending answer-matching with official synonyms

`aliases.json` (alternate spellings per disease, so the scorer treats
"Fabry disease" and "alpha-galactosidase A deficiency" as the same answer) is
currently built from the disease names inside RareBench. You can enrich it with
official synonym sources, both **CC-BY 4.0**:

- **Orphadata / Orphanet** — rare disease ↔ HPO phenotype associations, with
  synonyms, frequencies, and epidemiology: <https://www.orphadata.com/>
- **HPO annotations (`phenotype.hpoa`)** — disease→phenotype for ~8,000 diseases:
  <https://hpo.jax.org/app/download/annotation> (note: OMIM-derived rows carry
  OMIM's own restrictions — prefer Orphanet-sourced rows for anything committed).

## Regenerating the data

```bash
python data/build_dataset.py                 # default: rarebench + cupcase
python data/build_dataset.py --per-source 25 # more cases per source
python data/build_dataset.py --seed 42       # a different reproducible sample
```

Raw downloads are cached in `data/.cache/` (gitignored) so re-runs are fast.

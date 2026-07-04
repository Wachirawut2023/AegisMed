# 🔬 Evidence & Citations — how AegisMed stays trustworthy

A short guide to how AegisMed grounds its answers in real evidence — and why it
is built to **never invent citations**.

## The problem with asking an AI to "cite sources"

If you ask a language model to cite textbooks or papers, it will happily produce
references that look perfect — real-sounding authors, journals, PMIDs, DOIs — but
are **often completely made up**. This is one of the best-documented failure
modes of LLMs, and in medicine a fabricated citation is worse than none: it
launders a guess into something that looks authoritative.

So AegisMed follows one rule: **the AI is never the source of a citation.**

## What AegisMed cites (all verifiable)

1. **The patient case.** Every specialist ties its reasoning to specific findings
   in the case ("supported by: burning pain since childhood, proteinuria"). You
   can check these against what you typed.

2. **Real reference pages, attached by the app — not the model.** For each
   diagnosis, AegisMed looks the disease up in a knowledge base and attaches:
   - the **Orphanet** rare-disease page (when the disease is known),
   - the **OMIM** genetic entry (when known),
   - a **PubMed** literature search link (always),
   - a **GARD** (NIH) rare-disease info link (always).

   Those official pages are curated from the primary literature and clinical
   guidelines, so they *are* the evidence trail — and the links are guaranteed
   real because they come from the knowledge base and deterministic search URLs,
   never from the model's memory.

## Evidence that informs the specialists (retrieval)

AegisMed doesn't only cite *after* diagnosing — it gathers evidence *before*, to
inform the specialists (this is "retrieval-augmented" reasoning):

```
case ─▶ retrieval agent ─▶ key phenotypes + candidate diseases
                              │
                              ▼   (looked up in the knowledge base)
                    verified reference links
                              │
                              ▼
        handed to all 7 specialists as "REFERENCE EVIDENCE (leads to verify)"
```

The retrieval agent only proposes **what to look up** — the reference links
themselves are real. Specialists are told to treat these as leads to weigh
against the case and cite by disease name, and are explicitly forbidden from
inventing citations. You can see what was retrieved in the app's
"🔎 Reference evidence considered by the board" panel.

## Where it lives in the code

| File | Job |
|---|---|
| `data/build_knowledge_base.py` | Builds `data/citations_index.json` — disease name → Orphanet/OMIM codes — from the RareBench disease mapping. Run once. |
| `data/citations_index.json` | The committed lookup table (~10,700 diseases). |
| `aegismed/knowledge.py` | Turns a diagnosis name into verified reference links; extracts diagnoses from the board's conclusion. |
| `aegismed/retrieval.py` | The retrieval agent + evidence dossier handed to the specialists. |

## Building / refreshing the knowledge base

```bash
python data/build_knowledge_base.py
```

This downloads the disease mapping (cached in `data/.cache/`) and writes
`data/citations_index.json`. Anything the index can't resolve still gets real
PubMed/GARD **search** links at runtime, so every diagnosis stays verifiable.

## Honest limitations

- Direct Orphanet/OMIM pages are attached only when the diagnosis name matches
  the knowledge base; otherwise you get search links (still real, just less
  precise). Adding Orphanet/HPO synonym files (see `data/SOURCES.md`) improves
  match rate.
- The reference pages are authoritative, but AegisMed does not (yet) quote a
  specific sentence or guideline recommendation from them — it points you to the
  right page to verify. That is a deliberate trade to avoid fabrication.

"""Verified citations — turns a diagnosis name into REAL reference links.

This is AegisMed's anti-hallucination layer. Language models happily invent
plausible-looking papers, PMIDs, and DOIs — which is dangerous in medicine. So
the AI is never asked to recall citations. Instead, this module attaches links
we can guarantee are real:

  - Orphanet and OMIM disease pages, when the diagnosis resolves to a known code
    (from data/citations_index.json, built by data/build_knowledge_base.py);
  - a PubMed and a GARD (NIH) search link for the diagnosis — always valid, so
    every diagnosis is verifiable even if we don't have its exact code.

Those official pages are themselves curated from the primary literature and
clinical guidelines, so they are the evidence trail — not a model's memory.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote_plus

_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "citations_index.json"

# Loaded once at import. Empty (with graceful fallback) if the file is missing.
try:
    _INDEX: dict[str, dict] = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
except (OSError, ValueError):
    _INDEX = {}


def kb_size() -> int:
    return len(_INDEX)


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def resolve(diagnosis: str) -> dict | None:
    """Find the knowledge-base entry for a diagnosis name (exact or trimmed match)."""
    key = _normalize(diagnosis)
    if not key:
        return None
    if key in _INDEX:
        return _INDEX[key]
    # light fallback: drop trailing qualifier words ("... type 2", "... syndrome")
    tokens = key.split()
    for cut in range(len(tokens) - 1, 1, -1):
        sub = " ".join(tokens[:cut])
        if sub in _INDEX:
            return _INDEX[sub]
    return None


def links_for(diagnosis: str) -> list[dict]:
    """Return a list of {label, url} references for a diagnosis.

    Always includes PubMed and GARD search links; adds the direct Orphanet and
    OMIM disease pages when the diagnosis resolves to a known code.
    """
    diagnosis = diagnosis.strip()
    links: list[dict] = []
    entry = resolve(diagnosis)
    if entry:
        if entry.get("orpha"):
            links.append({
                "label": "Orphanet (rare disease reference)",
                "url": f"https://www.orpha.net/en/disease/detail/{entry['orpha']}",
            })
        if entry.get("omim"):
            links.append({
                "label": "OMIM (genetic reference)",
                "url": f"https://omim.org/entry/{entry['omim']}",
            })
    q = quote_plus(diagnosis)
    links.append({
        "label": "PubMed — search the literature",
        "url": f"https://pubmed.ncbi.nlm.nih.gov/?term={q}",
    })
    links.append({
        "label": "GARD (NIH rare disease info)",
        "url": f"https://rarediseases.info.nih.gov/diseases/search?query={q}",
    })
    return links


def references_for(diagnoses: list[str]) -> list[dict]:
    """Build a de-duplicated reference list for several diagnoses."""
    seen, out = set(), []
    for dx in diagnoses:
        dx = dx.strip()
        key = _normalize(dx)
        if not dx or key in seen:
            continue
        seen.add(key)
        out.append({"diagnosis": dx, "links": links_for(dx)})
    return out


# The synthesis lists diagnoses like "1. Fabry disease [RARE] — reasoning...".
_DX_LINE = re.compile(r"^\s*\d+[.)]\s+(.+)$")


def extract_diagnoses(synthesis_text: str, limit: int = 6) -> list[str]:
    """Pull the diagnosis names out of the synthesis's ranked differential list."""
    names: list[str] = []
    in_list = False
    for line in synthesis_text.splitlines():
        low = line.lower()
        if "ranked differential" in low:
            in_list = True
            continue
        if in_list and line.strip().startswith("**") and "ranked differential" not in low:
            break  # reached the next section heading
        m = _DX_LINE.match(line)
        if m:
            # cut the name off before the tag/reasoning: [RARE], em dash, ' - ', '('
            name = re.split(r"\s*(?:\[|—|–| - |\()", m.group(1).strip(), maxsplit=1)[0]
            name = name.strip(" *:")
            if name:
                names.append(name)
        if len(names) >= limit:
            break
    return names

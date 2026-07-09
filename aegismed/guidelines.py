"""Clinical practice guideline search links — never invented, always live.

Same anti-hallucination philosophy as `aegismed/knowledge.py`: the AI is never
asked to recall a guideline or cite a specific document. Instead this module
deterministically builds *search* URLs on authoritative guideline sources from
the diagnosis name via `urllib.parse.quote_plus`, the same way `knowledge.py`
builds its always-valid PubMed and GARD links. Every search link here takes the
physician to a live search results page on a real guideline database — never to
an AI-selected "the guideline for X", since we cannot guarantee that page
exists or is current.

Two layers, both verified:
  1. An OPTIONAL curated exact-match index (`data/guidelines_index.json`, same
     idea as `knowledge.py`'s `citations_index.json`): if present, it maps a
     normalized diagnosis name to hand-verified {label, url} links to specific
     guideline documents. It ships empty by default — populating it is future
     work, and every entry must be manually browser-verified before it is added.
  2. Deterministic search links on sources confirmed to return real,
     query-filtered results (not just an HTTP 200 from a single-page app that
     ignores the query string).

Deferred (NOT shipped): WHO deep links (JS single-page app — a curl 200 doesn't
prove the query filters anything) and individual specialty-society deep links
(ACC/AHA, ACMG, etc. — mixed/unverifiable via an HTTP check). Those need manual
browser verification or a curated index entry before they can be trusted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote_plus

# Sources confirmed to accept a plus-encoded query and return real, filtered
# results. Order is intentional: broad literature/evidence first, then guideline
# aggregators.
_SOURCES = [
    ("PubMed — practice guidelines", "https://pubmed.ncbi.nlm.nih.gov/?term={q}+practice+guideline"),
    ("Cochrane Library (systematic reviews)", "https://www.cochranelibrary.com/search?q={q}"),
    ("NICE (UK national guidance)", "https://www.nice.org.uk/search?q={q}"),
    ("TRIP Database (evidence-based guidelines)", "https://www.tripdatabase.com/search?criteria={q}"),
    ("MedlinePlus (NIH)", "https://vsearch.nlm.nih.gov/vivisimo/cgi-bin/query-meta?v%3Aproject=medlineplus&query={q}"),
    ("NCBI Bookshelf / GeneReviews", "https://www.ncbi.nlm.nih.gov/books/?term={q}"),
    ("Guideline Central", "https://www.guidelinecentral.com/search/?q={q}"),
]

# Optional curated index: normalized diagnosis -> list of {label, url} links to
# specific, hand-verified guideline documents. Loaded once at import; empty (with
# graceful fallback to search links only) if the file is missing or invalid —
# exactly like knowledge.py's citations index.
_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "guidelines_index.json"
try:
    _INDEX: dict[str, list[dict]] = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
except (OSError, ValueError):
    _INDEX = {}


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def guideline_links_for(diagnosis: str) -> list[dict]:
    """Return guideline links ({label, url}) for a diagnosis name.

    Any curated exact-match guideline documents come first, followed by the
    always-valid deterministic search links.
    """
    diagnosis = diagnosis.strip()
    if not diagnosis:
        return []
    links: list[dict] = []
    curated = _INDEX.get(_normalize(diagnosis))
    if isinstance(curated, list):
        links.extend(entry for entry in curated if entry.get("label") and entry.get("url"))
    q = quote_plus(diagnosis)
    links.extend({"label": label, "url": template.format(q=q)} for label, template in _SOURCES)
    return links


def guidelines_for(diagnoses: list[str]) -> list[dict]:
    """De-duplicated [{diagnosis, links}] guideline list, one entry per diagnosis."""
    seen, out = set(), []
    for dx in diagnoses:
        dx = dx.strip()
        key = dx.lower()
        if not dx or key in seen:
            continue
        seen.add(key)
        out.append({"diagnosis": dx, "links": guideline_links_for(dx)})
    return out

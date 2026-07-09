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

Region support (`region`, one of "us"/"uk"/"eu", default "us"): the SAME set of
verified sources is reordered per region to foreground the source most relevant
to that practice context (e.g. NICE first for "uk"). This deliberately does NOT
add new, unverified region-specific sources (BMA, RCPCH, ESC, ESGO, EORTC,
etc.) — those remain deferred pending manual browser verification, exactly like
the WHO/specialty-society links below. A curated index entry may also be a
per-region dict (`{"us": [...], "uk": [...]}`) instead of a flat list; a flat
list is used for every region (backward compatible with existing entries).

Deferred (NOT shipped): WHO deep links (JS single-page app — a curl 200 doesn't
prove the query filters anything) and individual specialty-society deep links
(ACC/AHA, ACMG, BMA, RCPCH, ESC, ESGO, EORTC, etc. — mixed/unverifiable via an
HTTP check). Those need manual browser verification or a curated index entry
before they can be trusted.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import quote_plus

# Sources confirmed to accept a plus-encoded query and return real, filtered
# results. The pool is identical across regions — only the ORDER changes, to
# foreground the source most relevant to that practice context. Never add a
# region variant here without first curl/browser-verifying it (see module
# docstring).
_PUBMED = ("PubMed — practice guidelines", "https://pubmed.ncbi.nlm.nih.gov/?term={q}+practice+guideline")
_COCHRANE = ("Cochrane Library (systematic reviews)", "https://www.cochranelibrary.com/search?q={q}")
_NICE = ("NICE (UK national guidance)", "https://www.nice.org.uk/search?q={q}")
_TRIP = ("TRIP Database (evidence-based guidelines)", "https://www.tripdatabase.com/search?criteria={q}")
_MEDLINEPLUS = ("MedlinePlus (NIH)", "https://vsearch.nlm.nih.gov/vivisimo/cgi-bin/query-meta?v%3Aproject=medlineplus&query={q}")
_NCBI_BOOKSHELF = ("NCBI Bookshelf / GeneReviews", "https://www.ncbi.nlm.nih.gov/books/?term={q}")
_GUIDELINE_CENTRAL = ("Guideline Central", "https://www.guidelinecentral.com/search/?q={q}")

_REGION_SOURCES: dict[str, list[tuple[str, str]]] = {
    # US: broad literature/evidence first, then guideline aggregators.
    "us": [_PUBMED, _COCHRANE, _NICE, _TRIP, _MEDLINEPLUS, _NCBI_BOOKSHELF, _GUIDELINE_CENTRAL],
    # UK: NICE (the national guidance body) leads, then evidence-based sources.
    "uk": [_NICE, _TRIP, _COCHRANE, _PUBMED, _NCBI_BOOKSHELF, _MEDLINEPLUS, _GUIDELINE_CENTRAL],
    # EU: no single pan-European body is in the verified pool yet, so lead with
    # Cochrane (headquartered in the UK/EU, systematic-review gold standard).
    "eu": [_COCHRANE, _PUBMED, _TRIP, _NCBI_BOOKSHELF, _NICE, _MEDLINEPLUS, _GUIDELINE_CENTRAL],
}
_DEFAULT_REGION = "us"

# Backward-compatible alias: existing callers/tests that reference `_SOURCES`
# directly keep working, pinned to the default region's order.
_SOURCES = _REGION_SOURCES[_DEFAULT_REGION]

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


def _normalize_region(region: str) -> str:
    region = (region or "").strip().lower()
    return region if region in _REGION_SOURCES else _DEFAULT_REGION


def _curated_links_for(diagnosis: str, region: str) -> list[dict]:
    """Curated entry lookup, supporting both the flat-list and per-region shapes."""
    entry = _INDEX.get(_normalize(diagnosis))
    if isinstance(entry, dict):
        # Per-region curated entry: fall back to the default region if this
        # diagnosis has no curated link for the requested region.
        curated = entry.get(region) or entry.get(_DEFAULT_REGION) or []
    elif isinstance(entry, list):
        # Flat list: the same hand-verified links apply to every region.
        curated = entry
    else:
        curated = []
    return [e for e in curated if e.get("label") and e.get("url")]


def guideline_links_for(diagnosis: str, region: str = _DEFAULT_REGION) -> list[dict]:
    """Return guideline links ({label, url}) for a diagnosis name.

    Any curated exact-match guideline documents come first, followed by the
    always-valid deterministic search links, both ordered per `region`
    ("us"/"uk"/"eu", default "us" — unrecognized values fall back to "us").
    """
    diagnosis = diagnosis.strip()
    if not diagnosis:
        return []
    region = _normalize_region(region)
    links: list[dict] = list(_curated_links_for(diagnosis, region))
    q = quote_plus(diagnosis)
    links.extend({"label": label, "url": template.format(q=q)} for label, template in _REGION_SOURCES[region])
    return links


def guidelines_for(diagnoses: list[str], region: str = _DEFAULT_REGION) -> list[dict]:
    """De-duplicated [{diagnosis, links}] guideline list, one entry per diagnosis."""
    seen, out = set(), []
    for dx in diagnoses:
        dx = dx.strip()
        key = dx.lower()
        if not dx or key in seen:
            continue
        seen.add(key)
        out.append({"diagnosis": dx, "links": guideline_links_for(dx, region)})
    return out

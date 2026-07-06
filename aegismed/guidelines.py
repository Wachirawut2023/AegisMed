"""Clinical practice guideline search links — never invented, always live.

Same anti-hallucination philosophy as `aegismed/knowledge.py`: the AI is never
asked to recall a guideline or cite a specific document. Instead this module
deterministically builds *search* URLs on authoritative guideline sources from
the diagnosis name, the same way `knowledge.py` builds its always-valid PubMed
and GARD links. Every link here takes the physician to a live search results
page on a real guideline database or aggregator — never to an AI-selected
"the guideline for X", since we cannot guarantee that page exists or is current.

Sources are limited to ones confirmed to return real, query-filtered results
(not just an HTTP 200 from a single-page app that ignores the query string).
WHO and individual specialty-society deep links were considered but excluded
for now — verifying they filter correctly needs a browser check (or a curated
disease -> guideline-ID index, like `data/citations_index.json`), not just an
HTTP status check. Future work, not part of this module.
"""

from __future__ import annotations

from urllib.parse import quote_plus

_SOURCES = [
    ("PubMed — practice guidelines", "https://pubmed.ncbi.nlm.nih.gov/?term={q}+practice+guideline"),
    ("NICE (UK national guidance)", "https://www.nice.org.uk/search?q={q}"),
    ("TRIP Database (evidence-based guidelines)", "https://www.tripdatabase.com/search?criteria={q}"),
    ("MedlinePlus (NIH)", "https://vsearch.nlm.nih.gov/vivisimo/cgi-bin/query-meta?v%3Aproject=medlineplus&query={q}"),
    ("Guideline Central", "https://www.guidelinecentral.com/search/?q={q}"),
]


def guideline_links_for(diagnosis: str) -> list[dict]:
    """Return live guideline-search links ({label, url}) for a diagnosis name."""
    diagnosis = diagnosis.strip()
    if not diagnosis:
        return []
    q = quote_plus(diagnosis)
    return [{"label": label, "url": template.format(q=q)} for label, template in _SOURCES]


def guidelines_for(diagnoses: list[str]) -> list[dict]:
    """De-duplicated [{diagnosis, links}] guideline-search list, one entry per diagnosis."""
    seen, out = set(), []
    for dx in diagnoses:
        dx = dx.strip()
        key = dx.lower()
        if not dx or key in seen:
            continue
        seen.add(key)
        out.append({"diagnosis": dx, "links": guideline_links_for(dx)})
    return out

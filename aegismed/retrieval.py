"""Retrieval — gathers real reference evidence BEFORE the specialists decide.

This is the "additional data for sub-agent decision-making" layer. Given a case,
one quick model call extracts the salient phenotypes and a few candidate rare
diseases worth looking up. We then attach VERIFIED reference links to those
candidates from aegismed/knowledge.py (never invented). The resulting dossier is
handed to every specialist so their reasoning is grounded in real references,
and the same links are surfaced to the physician as citations.

The model only proposes *what to look up*; the citations themselves are real.
"""

from __future__ import annotations

import json
import re

from . import config, knowledge, llm
from .demo_data import DEMO_RETRIEVAL_CANDIDATES, DEMO_RETRIEVAL_PHENOTYPES
from .orchestrator import _format_case

RETRIEVAL_PROMPT = """
You are a clinical librarian preparing reference material for a rare-disease
board. Read the case and identify what the specialists should look up.

Respond with STRICT JSON and nothing else, in exactly this shape:
{
  "key_phenotypes": ["<salient clinical feature>", "..."],
  "candidate_diseases": ["<rare disease worth looking up>", "..."]
}

Rules:
- List 3-8 key phenotypes actually present in the case.
- List 3-8 candidate diseases (favor rare but plausible ones). Use standard
  disease names so they can be matched to a reference database.
- Do NOT diagnose or explain here; only list lookup terms. Do NOT invent
  citations — the system attaches verified references itself.
"""


def _parse_json(text: str) -> dict:
    try:
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return {"key_phenotypes": [], "candidate_diseases": []}
    return {
        "key_phenotypes": [str(x).strip() for x in data.get("key_phenotypes", []) if str(x).strip()][:8],
        "candidate_diseases": [str(x).strip() for x in data.get("candidate_diseases", []) if str(x).strip()][:8],
    }


def _build_dossier(phenotypes: list[str], candidates: list[dict]) -> str:
    """A compact, cited evidence block to prepend to each specialist's case."""
    if not candidates and not phenotypes:
        return ""
    lines = [
        "REFERENCE EVIDENCE (retrieved from a curated rare-disease knowledge "
        "base). Treat these as leads to weigh against the case, not confirmed "
        "facts. Cite by disease name when one informs your reasoning. Do not "
        "invent citations beyond these.",
    ]
    if phenotypes:
        lines.append("Key phenotypes flagged: " + "; ".join(phenotypes) + ".")
    for c in candidates:
        refs = " | ".join(l["url"] for l in c["links"])
        lines.append(f"- {c['name']} — {refs}")
    return "\n".join(lines)


async def retrieve(age: str, sex: str, symptoms: str, history: str, labs: str) -> dict:
    """Return {phenotypes, candidates:[{name, links}], dossier} for a case."""
    if config.demo_mode():
        phenotypes = DEMO_RETRIEVAL_PHENOTYPES
        names = DEMO_RETRIEVAL_CANDIDATES
    else:
        case_text = _format_case(age, sex, symptoms, history, labs)
        raw = await llm.chat(RETRIEVAL_PROMPT, case_text, agent_name="retrieval")
        parsed = _parse_json(raw)
        phenotypes = parsed["key_phenotypes"]
        names = parsed["candidate_diseases"]

    candidates = [{"name": n, "links": knowledge.links_for(n)} for n in names]
    return {
        "phenotypes": phenotypes,
        "candidates": candidates,
        "dossier": _build_dossier(phenotypes, candidates),
    }

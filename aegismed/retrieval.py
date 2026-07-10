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
from .demo_data import (
    DEMO_RETRIEVAL_CANDIDATES,
    DEMO_RETRIEVAL_PHENOTYPES,
    DEMO_RETRIEVAL_SPECIALTIES,
)
from .orchestrator import _format_case
from .specialists import SPECIALISTS

# Case-insensitive lookup from a returned name back to the canonical roster key.
_SPECIALTY_BY_LOWER = {name.lower(): name for name in SPECIALISTS}

RETRIEVAL_PROMPT = f"""
You are the triage clinician and librarian preparing a rare-disease board.
Read the case and decide (a) what to look up and (b) which specialists it needs.

The board's specialists are exactly:
{', '.join(SPECIALISTS)}.

Respond with STRICT JSON and nothing else, in exactly this shape:
{{
  "key_phenotypes": ["<salient clinical feature>", "..."],
  "candidate_diseases": ["<rare disease worth looking up>", "..."],
  "relevant_specialties": ["<specialty from the list above>", "..."]
}}

Rules:
- List 3-8 key phenotypes actually present in the case.
- List 3-8 candidate diseases (favor rare but plausible ones). Use standard
  disease names so they can be matched to a reference database.
- For relevant_specialties, choose ONLY names from the list above, copied
  verbatim. Include every specialty with even plausible relevance — err toward
  including one rather than leaving it out. Omit only clearly irrelevant ones.
- Do NOT diagnose or explain here; only list lookup terms. Do NOT invent
  citations — the system attaches verified references itself.
"""


def _validate_specialties(items) -> list[str]:
    out = []
    for x in items or []:
        canon = _SPECIALTY_BY_LOWER.get(str(x).strip().lower())
        if canon and canon not in out:
            out.append(canon)
    return out


def _parse_json(text: str) -> dict:
    try:
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return {"key_phenotypes": [], "candidate_diseases": [], "relevant_specialties": []}
    return {
        "key_phenotypes": [str(x).strip() for x in data.get("key_phenotypes", []) if str(x).strip()][:8],
        "candidate_diseases": [str(x).strip() for x in data.get("candidate_diseases", []) if str(x).strip()][:8],
        "relevant_specialties": _validate_specialties(data.get("relevant_specialties", [])),
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


async def retrieve(
    age: str, sex: str, symptoms: str, history: str, labs: str, api_key: str = "",
) -> dict:
    """Return {phenotypes, candidates, relevant_specialties, dossier} for a case.

    One model call does triage (which specialists are relevant) AND reference
    lookup (phenotypes + candidate diseases), so gating adds no extra call.

    If api_key is provided, use it instead of the server's default FIREWORKS_API_KEY.
    """
    if config.demo_mode(api_key):
        phenotypes = DEMO_RETRIEVAL_PHENOTYPES
        names = DEMO_RETRIEVAL_CANDIDATES
        relevant = _validate_specialties(DEMO_RETRIEVAL_SPECIALTIES)
    else:
        case_text = _format_case(age, sex, symptoms, history, labs)
        raw = await llm.chat(RETRIEVAL_PROMPT, case_text, agent_name="retrieval", api_key=api_key)
        parsed = _parse_json(raw)
        phenotypes = parsed["key_phenotypes"]
        names = parsed["candidate_diseases"]
        relevant = parsed["relevant_specialties"]

    candidates = [{"name": n, "links": knowledge.links_for(n)} for n in names]
    return {
        "phenotypes": phenotypes,
        "candidates": candidates,
        "relevant_specialties": relevant,
        "dossier": _build_dossier(phenotypes, candidates),
    }

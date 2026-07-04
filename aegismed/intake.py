"""The intake agent — asks for missing information BEFORE the board meets.

Just like Claude Code asks a few clarifying questions before it starts working,
AegisMed first sends the case to an "intake" agent. That agent reads the case
and decides whether any missing detail would meaningfully change the diagnosis.
If so, it returns a short list of targeted questions for the physician to answer.
Only then does the full specialist board convene — now with a richer case.

This mirrors how a good clinician takes a focused history before consulting.
"""

from __future__ import annotations

import json
import re

from . import config, llm
from .orchestrator import _format_case

INTAKE_PROMPT = """
You are the intake clinician for a rare-disease diagnostic board. Before five
specialists review this case, your job is to spot the MISSING information that
would most change the differential diagnosis, and ask the treating physician for it.

Rules:
- Ask ONLY high-value questions — the ones that would actually redirect the workup.
- Ask AT MOST 4 questions. Fewer is better. If the case is already detailed
  enough to proceed, ask none.
- Do not ask for information already provided. Do not give a diagnosis here.
- Prefer questions about: symptom timeline/triggers, family history, exposures/
  travel/medications, and key exams or tests not yet reported.

Respond with STRICT JSON and nothing else, in exactly this shape:
{
  "ready": <true if no questions are needed, otherwise false>,
  "questions": [
    {"question": "<the question to ask the physician>",
     "why": "<one short phrase: what this would help rule in or out>"}
  ]
}
"""


def _parse_intake_json(text: str) -> dict:
    """Pull the JSON object out of the model's reply, defensively.

    LLMs sometimes wrap JSON in ```json fences or add stray prose. We extract the
    first {...} block. If anything fails we 'fail open' (ready=true, no questions)
    so a parsing glitch never blocks the physician from getting a diagnosis.
    """
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        data = json.loads(text[start:end])
    except (ValueError, json.JSONDecodeError):
        return {"ready": True, "questions": []}

    questions = []
    for q in (data.get("questions") or [])[:4]:
        if isinstance(q, dict) and q.get("question"):
            questions.append({
                "question": str(q["question"]).strip(),
                "why": str(q.get("why", "")).strip(),
            })
        elif isinstance(q, str) and q.strip():
            questions.append({"question": q.strip(), "why": ""})

    ready = bool(data.get("ready", not questions))
    if not questions:
        ready = True
    return {"ready": ready, "questions": questions}


async def gather_questions(
    age: str, sex: str, symptoms: str, history: str, labs: str
) -> dict:
    """Ask the intake agent what else it needs. Returns {ready, questions, demo_mode}."""
    case_text = _format_case(age, sex, symptoms, history, labs)
    raw = await llm.chat(INTAKE_PROMPT, case_text, agent_name="intake")
    result = _parse_intake_json(raw)
    result["demo_mode"] = config.demo_mode()
    return result

"""The orchestrator — runs the whole diagnostic board for one patient case.

Flow:
  1. Turn the form fields into one readable case description.
  2. Ask all specialists AT THE SAME TIME (asyncio.as_completed), because none
     of them needs to see another's answer — just like independent consults.
  3. The board chair drafts a PRELIMINARY differential from those opinions.
  4. Every specialist reviews the draft (and each other's round-1 opinions)
     and can rebut or refine it — a real deliberation round, not just
     parallel independent opinions.
  5. The board chair issues the FINAL differential in light of that peer
     review.

`diagnose_stream()` is the one real implementation of this flow — it's an
async generator that yields a progress event as each stage completes, then a
final event carrying the complete result (used by the streaming
`/api/diagnose/stream` endpoint). `diagnose()` is a thin wrapper that drains
the generator and returns just the final result, for callers that don't
care about progress (the plain `/api/diagnose` endpoint, the eval harness,
teaching mode).
"""

import asyncio

from . import config, guidelines, knowledge, llm
from .demo_data import DEMO_BANNER
from .specialists import (
    SPECIALISTS,
    SYNTHESIS_PROMPT,
    peer_review_prompt,
    specialist_prompt,
    synthesis_prompt,
)

# Supported practice regions (Phase 3e geographic expansion). Unrecognized
# values fall back to "us" — see docs/ROADMAP.md Phase 3e for the full design.
_REGIONS = {"us", "uk", "eu"}
_DEFAULT_REGION = "us"

DISCLAIMER = (
    "AegisMed is a clinical decision-support prototype for licensed physicians. "
    "It does not provide medical advice, diagnosis, or treatment, and its output "
    "must always be verified by a qualified clinician."
)

# Smart-routing safeguards: always keep the rare-disease advocate on the board,
# and never convene fewer than this many specialists.
_ALWAYS_INCLUDE = {"Medical Genetics"}
_MIN_SPECIALISTS = 2


def _select_specialists(router_specialties: list[str]) -> list[str]:
    """Decide which specialists to convene, preserving roster order.

    - SPECIALIST_SELECTION=all -> the full board (the demo/max-recall toggle).
    - otherwise -> the router's picks plus the always-include core; but if that
      leaves too few (or the router returned nothing / failed), fall back to the
      full board so cost savings never cost us a diagnosis (fail-open).
    """
    everyone = list(SPECIALISTS)
    if config.specialist_selection() == "all":
        return everyone
    chosen = set(router_specialties) | _ALWAYS_INCLUDE
    chosen &= set(everyone)  # guard against anything off-roster
    if len(chosen) < _MIN_SPECIALISTS:
        return everyone
    return [name for name in everyone if name in chosen]


def _format_case(
    age: str, sex: str, symptoms: str, history: str, labs: str,
    clarifications: str = "",
) -> str:
    text = (
        f"PATIENT CASE\n"
        f"Age: {age or 'not stated'}\n"
        f"Sex: {sex or 'not stated'}\n"
        f"Presenting symptoms: {symptoms or 'not stated'}\n"
        f"Medical & family history: {history or 'not stated'}\n"
        f"Labs / investigations: {labs or 'not stated'}\n"
    )
    if clarifications.strip():
        text += f"Additional information (from intake questions):\n{clarifications.strip()}\n"
    return text


async def _run_specialist(name: str, region: str, grounded_case: str) -> tuple[str, str]:
    """Run one specialist and tag the result with its name (for as_completed)."""
    text = await llm.chat(
        specialist_prompt(name, region), grounded_case, agent_name=name,
        max_tokens=1536,
    )
    return name, text


async def _run_peer_review(name: str, region: str, peer_review_input: str) -> tuple[str, str]:
    """Run one specialist's round-2 rebuttal of the draft and tag it with its name."""
    text = await llm.chat(
        peer_review_prompt(name, region), peer_review_input,
        agent_name=f"peer_review:{name}", max_tokens=400,
    )
    return name, text


async def diagnose_stream(
    age: str, sex: str, symptoms: str, history: str, labs: str,
    clarifications: str = "", region: str = _DEFAULT_REGION,
):
    """Run the full board, yielding progress events as each stage completes.

    Yields dicts with an "event" key:
      - {"event": "specialist_done", "specialty", "completed", "total"} —
        once per specialist, round 1 (independent opinions), in completion
        order (not roster order).
      - {"event": "draft_synthesis_done"} — once the chair's preliminary
        differential is ready.
      - {"event": "peer_review_done", "specialty", "completed", "total"} —
        once per specialist, round 2 (reviewing the draft), in completion order.
      - {"event": "final_synthesis_done"} — once the chair's final
        differential (post-peer-review) is ready.
      - {"event": "final", "data": {...}} — the same dict diagnose() returns,
        always the last event yielded.
    """
    from . import retrieval  # local import avoids a circular dependency

    region = region if region in _REGIONS else _DEFAULT_REGION
    case_text = _format_case(age, sex, symptoms, history, labs, clarifications)

    # Step 0: retrieve real reference evidence to ground the specialists.
    evidence = await retrieval.retrieve(
        age=age, sex=sex, symptoms=symptoms,
        history=(history + ("\n" + clarifications if clarifications else "")),
        labs=labs,
    )
    grounded_case = case_text + ("\n\n" + evidence["dossier"] if evidence["dossier"] else "")

    # Step 1: convene only the relevant specialists (smart routing), in parallel,
    # yielding a progress event as each one finishes (order of completion, not roster order).
    names = _select_specialists(evidence.get("relevant_specialties", []))
    skipped = [n for n in SPECIALISTS if n not in names]
    tasks = [asyncio.create_task(_run_specialist(name, region, grounded_case)) for name in names]
    opinions_by_name: dict[str, str] = {}
    for finished in asyncio.as_completed(tasks):
        name, text = await finished
        opinions_by_name[name] = text
        yield {
            "event": "specialist_done",
            "specialty": name,
            "completed": len(opinions_by_name),
            "total": len(names),
        }
    # Rebuild in roster order for a stable, predictable UI regardless of which
    # specialist happened to finish first.
    specialist_opinions = [
        {"specialty": name, "opinion": opinions_by_name[name]} for name in names
    ]

    # Step 2: the board chair drafts a PRELIMINARY differential from the
    # independent round-1 opinions. The roster is passed in so the chair
    # adapts if specialties are added/removed.
    synthesis_input = (
        grounded_case
        + f"\nBOARD ROSTER: {', '.join(names)}\n"
        + "\nSPECIALIST OPINIONS\n\n"
        + "\n\n".join(
            f"--- {item['specialty']} ---\n{item['opinion']}"
            for item in specialist_opinions
        )
    )
    draft_synthesis = await llm.chat(
        synthesis_prompt(region), synthesis_input, agent_name="draft_synthesis",
        max_tokens=2048,
    )
    yield {"event": "draft_synthesis_done"}

    # Step 3: peer review — every specialist sees the draft (and every other
    # specialist's round-1 opinion) and can rebut or refine it, in parallel,
    # same fan-out pattern as round 1.
    peer_review_input = (
        synthesis_input
        + "\n\nCHAIR'S DRAFT DIFFERENTIAL (preliminary — critique or confirm it):\n"
        + draft_synthesis
    )
    pr_tasks = [
        asyncio.create_task(_run_peer_review(name, region, peer_review_input))
        for name in names
    ]
    peer_reviews_by_name: dict[str, str] = {}
    for finished in asyncio.as_completed(pr_tasks):
        name, text = await finished
        peer_reviews_by_name[name] = text
        yield {
            "event": "peer_review_done",
            "specialty": name,
            "completed": len(peer_reviews_by_name),
            "total": len(names),
        }
    peer_review = [
        {"specialty": name, "comment": peer_reviews_by_name[name]} for name in names
    ]

    # Step 4: the chair issues the FINAL differential, having read the
    # round-2 peer review. Same prompt/format as the draft pass — only the
    # input differs.
    final_synthesis_input = (
        synthesis_input
        + "\n\nYOUR OWN DRAFT DIFFERENTIAL FROM THE FIRST PASS:\n" + draft_synthesis
        + "\n\nROUND-2 PEER REVIEW FROM THE BOARD (revise your draft in light "
          "of this; produce your FINAL differential, not a repeat of the draft):\n\n"
        + "\n\n".join(f"--- {p['specialty']} ---\n{p['comment']}" for p in peer_review)
    )
    synthesis = await llm.chat(
        synthesis_prompt(region), final_synthesis_input, agent_name="final_synthesis",
        max_tokens=2048,
    )
    yield {"event": "final_synthesis_done"}

    # Step 5: attach VERIFIED citations for the diagnoses the board concluded.
    diagnoses = knowledge.extract_diagnoses(synthesis)
    references = knowledge.references_for(diagnoses)
    guideline_references = guidelines.guidelines_for(diagnoses, region=region)

    yield {
        "event": "final",
        "data": {
            "disclaimer": DISCLAIMER,
            "demo_mode": config.demo_mode(),
            "demo_banner": DEMO_BANNER if config.demo_mode() else "",
            "region": region,
            "evidence": {"phenotypes": evidence["phenotypes"], "candidates": evidence["candidates"]},
            "references": references,
            "guideline_references": guideline_references,
            "routing": {
                "selected_specialties": names,
                "skipped_specialties": skipped,
                "total_specialties": len(SPECIALISTS),
            },
            "specialist_opinions": specialist_opinions,
            "synthesis": synthesis,
            "deliberation": {
                "draft_synthesis": draft_synthesis,
                "peer_review": peer_review,
            },
        },
    }


async def diagnose(
    age: str, sex: str, symptoms: str, history: str, labs: str,
    clarifications: str = "", region: str = _DEFAULT_REGION,
) -> dict:
    """Run the full board and return everything the UI needs as one dict.

    A thin wrapper over diagnose_stream() for callers that just want the end
    result and don't need progress events (e.g. teaching mode, the eval harness).
    """
    async for event in diagnose_stream(
        age=age, sex=sex, symptoms=symptoms, history=history, labs=labs,
        clarifications=clarifications, region=region,
    ):
        if event["event"] == "final":
            return event["data"]
    raise RuntimeError("diagnose_stream ended without producing a final result")

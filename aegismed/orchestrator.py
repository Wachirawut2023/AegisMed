"""The orchestrator — runs the whole diagnostic board for one patient case.

Flow:
  1. Turn the form fields into one readable case description.
  2. Ask all specialists AT THE SAME TIME (asyncio.gather), because none
     of them needs to see another's answer — just like independent consults.
  3. Hand every opinion to the synthesis agent (the "board chair"), which
     produces the final ranked differential diagnosis for the physician.
"""

import asyncio

from . import config, knowledge, llm
from .demo_data import DEMO_BANNER
from .specialists import SPECIALISTS, SYNTHESIS_PROMPT

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


async def _convene_board(
    age: str, sex: str, symptoms: str, history: str, labs: str,
    clarifications: str = "",
) -> dict:
    """Run retrieval + the specialist fan-out (steps 0-1) and assemble the
    synthesis agent's input from their real opinions.

    Split out from diagnose() so batch tooling — the fine-tuning data builder
    (finetune/build_finetune_data.py) — can reuse the exact same real,
    per-case specialist opinions and grounded case text the app produces at
    inference time, without also calling the synthesis agent itself.
    """
    from . import retrieval  # local import avoids a circular dependency

    case_text = _format_case(age, sex, symptoms, history, labs, clarifications)

    # Step 0: retrieve real reference evidence to ground the specialists.
    evidence = await retrieval.retrieve(
        age=age, sex=sex, symptoms=symptoms,
        history=(history + ("\n" + clarifications if clarifications else "")),
        labs=labs,
    )
    grounded_case = case_text + ("\n\n" + evidence["dossier"] if evidence["dossier"] else "")

    # Step 1: convene only the relevant specialists (smart routing), in parallel.
    names = _select_specialists(evidence.get("relevant_specialties", []))
    skipped = [n for n in SPECIALISTS if n not in names]
    opinions = await asyncio.gather(
        *(
            llm.chat(SPECIALISTS[name], grounded_case, agent_name=name)
            for name in names
        )
    )
    specialist_opinions = [
        {"specialty": name, "opinion": text}
        for name, text in zip(names, opinions)
    ]

    # The roster is passed in so the chair adapts if specialties are added/removed.
    synthesis_input = (
        grounded_case
        + f"\nBOARD ROSTER: {', '.join(names)}\n"
        + "\nSPECIALIST OPINIONS\n\n"
        + "\n\n".join(
            f"--- {item['specialty']} ---\n{item['opinion']}"
            for item in specialist_opinions
        )
    )

    return {
        "evidence": evidence,
        "names": names,
        "skipped": skipped,
        "specialist_opinions": specialist_opinions,
        "synthesis_input": synthesis_input,
    }


async def diagnose(
    age: str, sex: str, symptoms: str, history: str, labs: str,
    clarifications: str = "",
) -> dict:
    """Run the full board and return everything the UI needs as one dict."""
    board = await _convene_board(age, sex, symptoms, history, labs, clarifications)

    # Step 2: the board chair merges the specialists' opinions into one briefing.
    synthesis = await llm.chat(
        SYNTHESIS_PROMPT, board["synthesis_input"], agent_name="synthesis",
        model=config.SYNTHESIS_MODEL,
    )

    # Step 3: attach VERIFIED citations for the diagnoses the board concluded.
    diagnoses = knowledge.extract_diagnoses(synthesis)
    references = knowledge.references_for(diagnoses)
    evidence = board["evidence"]

    return {
        "disclaimer": DISCLAIMER,
        "demo_mode": config.demo_mode(),
        "demo_banner": DEMO_BANNER if config.demo_mode() else "",
        "evidence": {"phenotypes": evidence["phenotypes"], "candidates": evidence["candidates"]},
        "references": references,
        "routing": {
            "selected_specialties": board["names"],
            "skipped_specialties": board["skipped"],
            "total_specialties": len(SPECIALISTS),
        },
        "specialist_opinions": board["specialist_opinions"],
        "synthesis": synthesis,
    }

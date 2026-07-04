"""The orchestrator — runs the whole diagnostic board for one patient case.

Flow:
  1. Turn the form fields into one readable case description.
  2. Ask all five specialists AT THE SAME TIME (asyncio.gather), because none
     of them needs to see another's answer — just like independent consults.
  3. Hand every opinion to the synthesis agent (the "board chair"), which
     produces the final ranked differential diagnosis for the physician.
"""

import asyncio

from . import config, llm
from .demo_data import DEMO_BANNER
from .specialists import SPECIALISTS, SYNTHESIS_PROMPT

DISCLAIMER = (
    "AegisMed is a clinical decision-support prototype for licensed physicians. "
    "It does not provide medical advice, diagnosis, or treatment, and its output "
    "must always be verified by a qualified clinician."
)


def _format_case(age: str, sex: str, symptoms: str, history: str, labs: str) -> str:
    return (
        f"PATIENT CASE\n"
        f"Age: {age or 'not stated'}\n"
        f"Sex: {sex or 'not stated'}\n"
        f"Presenting symptoms: {symptoms or 'not stated'}\n"
        f"Medical & family history: {history or 'not stated'}\n"
        f"Labs / investigations: {labs or 'not stated'}\n"
    )


async def diagnose(age: str, sex: str, symptoms: str, history: str, labs: str) -> dict:
    """Run the full board and return everything the UI needs as one dict."""
    case_text = _format_case(age, sex, symptoms, history, labs)

    # Step 1: all specialists review the case in parallel.
    names = list(SPECIALISTS)
    opinions = await asyncio.gather(
        *(
            llm.chat(SPECIALISTS[name], case_text, agent_name=name)
            for name in names
        )
    )
    specialist_opinions = [
        {"specialty": name, "opinion": text}
        for name, text in zip(names, opinions)
    ]

    # Step 2: the board chair merges the five opinions into one briefing.
    synthesis_input = case_text + "\n\nSPECIALIST OPINIONS\n\n" + "\n\n".join(
        f"--- {item['specialty']} ---\n{item['opinion']}"
        for item in specialist_opinions
    )
    synthesis = await llm.chat(SYNTHESIS_PROMPT, synthesis_input, agent_name="synthesis")

    return {
        "disclaimer": DISCLAIMER,
        "demo_mode": config.demo_mode(),
        "demo_banner": DEMO_BANNER if config.demo_mode() else "",
        "specialist_opinions": specialist_opinions,
        "synthesis": synthesis,
    }

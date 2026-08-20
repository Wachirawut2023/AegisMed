"""Unit tests for the orchestrator (aegismed/orchestrator.py).

_select_specialists and _format_case are pure/deterministic and tested
directly. diagnose() is exercised end-to-end in demo mode (no network) to
verify the smart-routing wiring surfaced in the "routing" field.
"""

import pytest

from aegismed import orchestrator
from aegismed.specialists import SPECIALISTS

pytestmark = pytest.mark.anyio


# --- _select_specialists --------------------------------------------------------


def test_select_specialists_all_overrides_router_picks(monkeypatch):
    monkeypatch.setenv("SPECIALIST_SELECTION", "all")
    assert orchestrator._select_specialists(["Cardiology"]) == list(SPECIALISTS)


def test_select_specialists_uses_router_picks_plus_always_include(monkeypatch):
    monkeypatch.setenv("SPECIALIST_SELECTION", "relevant")
    result = orchestrator._select_specialists(["Cardiology", "Neurology"])
    assert set(result) == {"Cardiology", "Neurology", "Medical Genetics"}
    # Roster order is preserved, not router order.
    assert result == [name for name in SPECIALISTS if name in result]


def test_select_specialists_falls_back_to_full_board_when_too_few(monkeypatch):
    monkeypatch.setenv("SPECIALIST_SELECTION", "relevant")
    # Router returns nothing -> only the always-include core (1 specialist)
    # survives, below _MIN_SPECIALISTS -> fails open to the full roster.
    assert orchestrator._select_specialists([]) == list(SPECIALISTS)


def test_select_specialists_ignores_off_roster_names(monkeypatch):
    monkeypatch.setenv("SPECIALIST_SELECTION", "relevant")
    result = orchestrator._select_specialists(["Not A Real Specialty", "Cardiology", "Neurology"])
    assert "Not A Real Specialty" not in result
    assert set(result) == {"Cardiology", "Neurology", "Medical Genetics"}


# --- _format_case ----------------------------------------------------------------


def test_format_case_uses_not_stated_placeholders_for_blank_fields():
    text = orchestrator._format_case("", "", "", "", "")
    assert text.count("not stated") == 5
    assert "Additional information" not in text


def test_format_case_includes_clarifications_when_present():
    text = orchestrator._format_case("24", "male", "pain", "history", "labs", "extra detail")
    assert "Additional information (from intake questions):" in text
    assert "extra detail" in text


def test_format_case_omits_clarifications_block_when_only_whitespace():
    text = orchestrator._format_case("24", "male", "pain", "history", "labs", "   \n  ")
    assert "Additional information" not in text


# --- diagnose() (demo mode, no network) -------------------------------------------


async def test_diagnose_demo_mode_routing_partitions_the_full_roster(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("SPECIALIST_SELECTION", "relevant")

    result = await orchestrator.diagnose(
        age="24", sex="male",
        symptoms="burning pain in hands and feet since childhood",
        history="", labs="",
    )

    routing = result["routing"]
    assert routing["total_specialties"] == len(SPECIALISTS)
    selected, skipped = set(routing["selected_specialties"]), set(routing["skipped_specialties"])
    assert selected | skipped == set(SPECIALISTS)
    assert not (selected & skipped)
    assert "Medical Genetics" in selected


async def test_diagnose_specialist_selection_all_convenes_everyone(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("SPECIALIST_SELECTION", "all")

    result = await orchestrator.diagnose(
        age="24", sex="male", symptoms="burning pain in hands and feet",
        history="", labs="",
    )

    assert result["routing"]["selected_specialties"] == list(SPECIALISTS)
    assert result["routing"]["skipped_specialties"] == []


async def test_diagnose_invalid_region_falls_back_to_us(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    result = await orchestrator.diagnose(
        age="24", sex="male", symptoms="burning pain in hands and feet",
        history="", labs="", region="not-a-region",
    )
    assert result["region"] == "us"

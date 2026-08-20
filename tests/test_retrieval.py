"""Unit tests for the retrieval layer (aegismed/retrieval.py).

_validate_specialties/_parse_json/_build_dossier are pure/deterministic and
tested directly. retrieve() is async: the demo-mode branch is network-free by
construction, and the real branch is tested with llm.chat mocked.
"""

import pytest

from aegismed import config, knowledge, retrieval
from aegismed.demo_data import DEMO_RETRIEVAL_CANDIDATES, DEMO_RETRIEVAL_PHENOTYPES

pytestmark = pytest.mark.anyio


# --- _validate_specialties ----------------------------------------------------


def test_validate_specialties_matches_case_insensitively():
    assert retrieval._validate_specialties(["cardiology", "NEUROLOGY"]) == ["Cardiology", "Neurology"]


def test_validate_specialties_drops_unknown_names():
    assert retrieval._validate_specialties(["Cardiology", "Not A Specialty"]) == ["Cardiology"]


def test_validate_specialties_dedupes_preserving_first_occurrence():
    assert retrieval._validate_specialties(["Cardiology", "cardiology", "Neurology"]) == [
        "Cardiology",
        "Neurology",
    ]


def test_validate_specialties_handles_empty_input():
    assert retrieval._validate_specialties([]) == []
    assert retrieval._validate_specialties(None) == []


# --- _parse_json ---------------------------------------------------------------


def test_parse_json_valid_response():
    text = (
        '{"key_phenotypes": ["fatigue"], '
        '"candidate_diseases": ["Fabry disease"], '
        '"relevant_specialties": ["Cardiology", "not-a-specialty"]}'
    )
    result = retrieval._parse_json(text)
    assert result == {
        "key_phenotypes": ["fatigue"],
        "candidate_diseases": ["Fabry disease"],
        "relevant_specialties": ["Cardiology"],
    }


def test_parse_json_malformed_text_fails_open():
    result = retrieval._parse_json("not json at all")
    assert result == {"key_phenotypes": [], "candidate_diseases": [], "relevant_specialties": []}


def test_parse_json_truncates_lists_to_eight():
    text = '{"key_phenotypes": [' + ", ".join(f'"p{i}"' for i in range(10)) + "]}"
    result = retrieval._parse_json(text)
    assert len(result["key_phenotypes"]) == 8


def test_parse_json_drops_blank_entries():
    text = '{"candidate_diseases": ["Fabry disease", "  ", ""]}'
    result = retrieval._parse_json(text)
    assert result["candidate_diseases"] == ["Fabry disease"]


# --- _build_dossier -------------------------------------------------------------


def test_build_dossier_empty_when_nothing_to_report():
    assert retrieval._build_dossier([], []) == ""


def test_build_dossier_includes_phenotypes_and_candidate_links():
    candidates = [{"name": "Fabry disease", "links": knowledge.links_for("Fabry disease")}]
    dossier = retrieval._build_dossier(["burning pain"], candidates)
    assert "burning pain" in dossier
    assert "Fabry disease" in dossier
    assert "|" in dossier  # links joined with " | "


# --- retrieve() ------------------------------------------------------------------


async def test_retrieve_demo_mode_uses_canned_data_and_builds_dossier(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    result = await retrieval.retrieve(age="24", sex="male", symptoms="pain", history="", labs="")

    assert result["phenotypes"] == DEMO_RETRIEVAL_PHENOTYPES
    assert [c["name"] for c in result["candidates"]] == DEMO_RETRIEVAL_CANDIDATES
    assert result["relevant_specialties"]  # non-empty, validated against roster
    assert result["dossier"]  # non-empty since phenotypes/candidates exist


async def test_retrieve_real_mode_parses_llm_reply(monkeypatch):
    monkeypatch.setattr(config, "demo_mode", lambda: False)

    async def fake_chat(system_prompt, user_prompt, agent_name=""):
        assert agent_name == "retrieval"
        return (
            '{"key_phenotypes": ["burning pain"], '
            '"candidate_diseases": ["Fabry disease"], '
            '"relevant_specialties": ["Cardiology", "Neurology"]}'
        )

    monkeypatch.setattr(retrieval.llm, "chat", fake_chat)

    result = await retrieval.retrieve(age="24", sex="male", symptoms="pain", history="", labs="")

    assert result["phenotypes"] == ["burning pain"]
    assert result["relevant_specialties"] == ["Cardiology", "Neurology"]
    [candidate] = result["candidates"]
    assert candidate["name"] == "Fabry disease"
    assert candidate["links"] == knowledge.links_for("Fabry disease")

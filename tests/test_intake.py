"""Unit tests for the intake agent (aegismed/intake.py).

_parse_intake_json is pure/deterministic and is the module's most important
defensive logic (it must "fail open" on a malformed LLM reply so a parsing
glitch never blocks a physician from reaching a diagnosis) — tested directly.
gather_questions/auto_answer are async and call llm.chat, which is mocked.
"""

import pytest

from aegismed import config, intake

pytestmark = pytest.mark.anyio


# --- _parse_intake_json ------------------------------------------------------


def test_parse_intake_json_valid_response():
    text = (
        '{"ready": false, "questions": ['
        '{"question": "Any family history?", "why": "genetic pattern"}]}'
    )
    result = intake._parse_intake_json(text)
    assert result == {
        "ready": False,
        "questions": [{"question": "Any family history?", "why": "genetic pattern"}],
    }


def test_parse_intake_json_strips_markdown_fence_and_prose():
    text = (
        "Sure, here are the questions:\n"
        "```json\n"
        '{"ready": false, "questions": [{"question": "Onset age?", "why": "timeline"}]}\n'
        "```\n"
        "Let me know if you need anything else."
    )
    result = intake._parse_intake_json(text)
    assert result["ready"] is False
    assert result["questions"] == [{"question": "Onset age?", "why": "timeline"}]


def test_parse_intake_json_invalid_text_fails_open():
    assert intake._parse_intake_json("not json at all") == {"ready": True, "questions": []}


def test_parse_intake_json_malformed_braces_fail_open():
    assert intake._parse_intake_json("{this is not valid json}") == {"ready": True, "questions": []}


def test_parse_intake_json_missing_questions_key_defaults_ready_true():
    result = intake._parse_intake_json('{"ready": false}')
    assert result == {"ready": True, "questions": []}


def test_parse_intake_json_accepts_bare_string_questions():
    result = intake._parse_intake_json('{"questions": ["Family history?", ""]}')
    assert result["questions"] == [{"question": "Family history?", "why": ""}]


def test_parse_intake_json_drops_dict_questions_without_question_key():
    result = intake._parse_intake_json('{"questions": [{"why": "no question field"}]}')
    assert result["questions"] == []
    assert result["ready"] is True


def test_parse_intake_json_truncates_to_first_four():
    text = '{"ready": false, "questions": [' + ", ".join(f'"Q{i}?"' for i in range(6)) + "]}"
    result = intake._parse_intake_json(text)
    assert len(result["questions"]) == 4
    assert [q["question"] for q in result["questions"]] == ["Q0?", "Q1?", "Q2?", "Q3?"]


def test_parse_intake_json_explicit_ready_true_with_questions_is_honored():
    text = '{"ready": true, "questions": [{"question": "Optional detail?"}]}'
    result = intake._parse_intake_json(text)
    assert result["ready"] is True
    assert len(result["questions"]) == 1


# --- gather_questions ---------------------------------------------------------


async def test_gather_questions_parses_llm_reply_and_adds_demo_mode(monkeypatch):
    async def fake_chat(system_prompt, user_prompt, agent_name=""):
        assert agent_name == "intake"
        return '{"ready": false, "questions": [{"question": "Travel history?", "why": "infection"}]}'

    monkeypatch.setattr(intake.llm, "chat", fake_chat)
    monkeypatch.setenv("DEMO_MODE", "true")

    result = await intake.gather_questions(age="30", sex="female", symptoms="fever", history="", labs="")

    assert result["ready"] is False
    assert result["questions"] == [{"question": "Travel history?", "why": "infection"}]
    assert result["demo_mode"] is True


# --- auto_answer ---------------------------------------------------------------


async def test_auto_answer_returns_empty_string_when_no_questions(monkeypatch):
    async def boom(*args, **kwargs):
        raise AssertionError("llm.chat should not be called with no questions")

    monkeypatch.setattr(intake.llm, "chat", boom)

    result = await intake.auto_answer([], age="30", sex="female", symptoms="fever", history="", labs="")
    assert result == ""


async def test_auto_answer_returns_empty_string_in_demo_mode(monkeypatch):
    async def boom(*args, **kwargs):
        raise AssertionError("llm.chat should not be called in demo mode")

    monkeypatch.setattr(intake.llm, "chat", boom)
    monkeypatch.setattr(config, "demo_mode", lambda: True)

    questions = [{"question": "Travel history?", "why": "infection"}]
    result = await intake.auto_answer(questions, age="30", sex="female", symptoms="fever", history="", labs="")
    assert result == ""


async def test_auto_answer_calls_llm_with_case_and_questions(monkeypatch):
    captured = {}

    async def fake_chat(system_prompt, user_prompt, agent_name=""):
        captured["system_prompt"] = system_prompt
        captured["user_prompt"] = user_prompt
        captured["agent_name"] = agent_name
        return "  Q: Travel history?\nA: Not documented.  "

    monkeypatch.setattr(intake.llm, "chat", fake_chat)
    monkeypatch.setattr(config, "demo_mode", lambda: False)

    questions = [{"question": "Travel history?", "why": "infection"}]
    result = await intake.auto_answer(
        questions, age="30", sex="female", symptoms="fever", history="", labs=""
    )

    assert result == "Q: Travel history?\nA: Not documented."
    assert captured["agent_name"] == "auto_answer"
    assert "Travel history?" in captured["user_prompt"]
    assert captured["system_prompt"] == intake.AUTO_ANSWER_PROMPT

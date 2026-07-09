"""Unit tests for the regional practice-context layer (Phase 3e).

Pure/deterministic string checks — no API key, no network.
"""

from aegismed import specialists


def test_specialist_prompt_includes_base_and_region_context():
    prompt = specialists.specialist_prompt("Cardiology", region="uk")
    assert specialists.SPECIALISTS["Cardiology"] in prompt
    assert "United Kingdom" in prompt


def test_specialist_prompt_defaults_to_us():
    default = specialists.specialist_prompt("Cardiology")
    us = specialists.specialist_prompt("Cardiology", region="us")
    assert default == us
    assert "United States" in default


def test_specialist_prompt_unrecognized_region_falls_back_to_us():
    fallback = specialists.specialist_prompt("Cardiology", region="not-a-region")
    us = specialists.specialist_prompt("Cardiology", region="us")
    assert fallback == us


def test_synthesis_prompt_includes_region_context():
    prompt = specialists.synthesis_prompt(region="eu")
    assert specialists.SYNTHESIS_PROMPT in prompt
    assert "European Union" in prompt


def test_all_three_regions_produce_distinct_context():
    contexts = {
        specialists.specialist_prompt("Cardiology", region=r)
        for r in ("us", "uk", "eu")
    }
    assert len(contexts) == 3

"""Unit tests for aegismed/config.py's demo_mode() and specialist_selection()."""

from aegismed import config


def test_demo_mode_explicit_true(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    assert config.demo_mode() is True


def test_demo_mode_explicit_false(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "false")
    assert config.demo_mode() is False


def test_demo_mode_auto_without_api_key_is_true(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "auto")
    monkeypatch.setattr(config, "FIREWORKS_API_KEY", "")
    assert config.demo_mode() is True


def test_demo_mode_auto_with_api_key_is_false(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "auto")
    monkeypatch.setattr(config, "FIREWORKS_API_KEY", "fw_some_key")
    assert config.demo_mode() is False


def test_demo_mode_defaults_to_auto_when_unset(monkeypatch):
    monkeypatch.delenv("DEMO_MODE", raising=False)
    monkeypatch.setattr(config, "FIREWORKS_API_KEY", "fw_some_key")
    assert config.demo_mode() is False


def test_specialist_selection_defaults_to_relevant(monkeypatch):
    monkeypatch.delenv("SPECIALIST_SELECTION", raising=False)
    assert config.specialist_selection() == "relevant"


def test_specialist_selection_all(monkeypatch):
    monkeypatch.setenv("SPECIALIST_SELECTION", "all")
    assert config.specialist_selection() == "all"


def test_specialist_selection_unknown_value_defaults_to_relevant(monkeypatch):
    monkeypatch.setenv("SPECIALIST_SELECTION", "everyone-please")
    assert config.specialist_selection() == "relevant"


def test_rate_limit_per_minute_defaults_to_20(monkeypatch):
    monkeypatch.delenv("RATE_LIMIT_PER_MINUTE", raising=False)
    assert config.rate_limit_per_minute() == 20


def test_rate_limit_per_minute_reads_env(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "5")
    assert config.rate_limit_per_minute() == 5


def test_rate_limit_per_minute_zero_disables(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")
    assert config.rate_limit_per_minute() == 0


def test_rate_limit_per_minute_invalid_value_falls_back_to_20(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "not-a-number")
    assert config.rate_limit_per_minute() == 20

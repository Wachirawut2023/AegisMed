"""Unit tests for the configurable model endpoint (AMD self-host path) and
the request-timeout knobs. Pure/deterministic — no network.
"""

import os

from aegismed import config


def test_default_endpoint_is_fireworks(monkeypatch):
    monkeypatch.setattr(config, "LLM_BASE_URL", "")
    assert config.chat_completions_url() == config.FIREWORKS_API_URL


def test_llm_base_url_overrides_endpoint(monkeypatch):
    monkeypatch.setattr(config, "LLM_BASE_URL", "http://amd-instance:8000/v1")
    assert config.chat_completions_url() == "http://amd-instance:8000/v1/chat/completions"


def test_llm_base_url_with_explicit_suffix_is_not_duplicated(monkeypatch):
    monkeypatch.setattr(config, "LLM_BASE_URL", "http://amd-instance:8000/v1/chat/completions")
    assert config.chat_completions_url() == "http://amd-instance:8000/v1/chat/completions"


def test_llm_base_url_trailing_slash_is_normalized(monkeypatch):
    monkeypatch.setattr(config, "LLM_BASE_URL", "http://amd-instance:8000/v1/")
    assert config.chat_completions_url() == "http://amd-instance:8000/v1/chat/completions"


def test_request_timeout_default():
    os.environ.pop("REQUEST_TIMEOUT_SECONDS", None)
    assert config.request_timeout() == 28


def test_request_timeout_reads_env(monkeypatch):
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "10")
    assert config.request_timeout() == 10


def test_request_timeout_invalid_env_falls_back(monkeypatch):
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "not-a-number")
    assert config.request_timeout() == 28


def test_llm_read_timeout_default():
    os.environ.pop("LLM_READ_TIMEOUT_SECONDS", None)
    assert config.llm_read_timeout() == 12

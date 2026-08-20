"""Endpoint-level tests for the FastAPI app.

Runs in demo mode (DEMO_MODE=true), so these exercise real routing/validation
logic but never call the network. Case storage is monkeypatched to a temp
file so tests never touch the real data/cases.jsonl.
"""

import json
import os

os.environ["DEMO_MODE"] = "true"

import pytest
from fastapi.testclient import TestClient

from aegismed import cases, llm, ratelimit
from aegismed.demo_data import EXAMPLE_CASE
from aegismed.main import app

client = TestClient(app)

VALID_CASE = {
    "symptoms": "burning pain in hands and feet since childhood, decreased sweating",
    "history": "maternal uncle died of renal failure",
    "labs": "proteinuria; LVH on ECG",
}


@pytest.fixture(autouse=True)
def _reset_rate_limit_buckets():
    # All requests in this module share one TestClient (one simulated client
    # IP), so without a reset the per-test request counts would accumulate
    # across the whole file and later tests could get spuriously 429'd.
    ratelimit.reset()
    yield
    ratelimit.reset()


def test_diagnose_defaults_to_us_region():
    resp = client.post("/api/diagnose", json=VALID_CASE)
    assert resp.status_code == 200
    assert resp.json()["region"] == "us"


def test_diagnose_accepts_uk_and_eu_region():
    for region in ("uk", "eu"):
        resp = client.post("/api/diagnose", json={**VALID_CASE, "region": region})
        assert resp.status_code == 200
        assert resp.json()["region"] == region


def test_diagnose_rejects_invalid_region():
    resp = client.post("/api/diagnose", json={**VALID_CASE, "region": "asia"})
    assert resp.status_code == 422


def test_diagnose_rejects_short_symptoms():
    resp = client.post("/api/diagnose", json={"symptoms": "short"})
    assert resp.status_code == 422


def test_teaching_case_returns_match_summary():
    resp = client.post(
        "/api/teaching/case",
        json={**VALID_CASE, "expected_diagnosis": "Fabry disease"},
    )
    assert resp.status_code == 200
    match = resp.json()["match_summary"]
    assert match["expected_diagnosis"] == "Fabry disease"
    assert "found_in_top_3" in match


def test_save_case_with_precomputed_board_output_skips_rerun(monkeypatch, tmp_path):
    monkeypatch.setattr(cases, "CASES_FILE", tmp_path / "cases.jsonl")

    async def _boom(*args, **kwargs):
        raise AssertionError("orchestrator.diagnose should not be called when board_output is provided")

    monkeypatch.setattr("aegismed.main.orchestrator.diagnose", _boom)

    # Only the required fields are given here — the rest of BoardOutput's
    # fields default to empty, proving a minimal-but-valid shape is accepted.
    precomputed = {"synthesis": "EXACT SYNTHESIS FROM SCREEN", "disclaimer": "d", "demo_mode": True, "region": "uk"}
    resp = client.post(
        "/api/cases/save",
        json={**VALID_CASE, "board_output": precomputed, "submitted_by": "Dr. Test", "specialty": "Cardiology"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["board_output"]["synthesis"] == "EXACT SYNTHESIS FROM SCREEN"
    assert data["board_output"]["region"] == "uk"


def test_save_case_accepts_real_diagnose_output_as_board_output(monkeypatch, tmp_path):
    """A genuine /api/diagnose result must always satisfy BoardOutput's shape."""
    monkeypatch.setattr(cases, "CASES_FILE", tmp_path / "cases.jsonl")

    diagnose_resp = client.post("/api/diagnose", json=VALID_CASE)
    board_output = diagnose_resp.json()

    save_resp = client.post(
        "/api/cases/save",
        json={**VALID_CASE, "board_output": board_output, "submitted_by": "Dr. Test"},
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["board_output"]["synthesis"] == board_output["synthesis"]


def test_save_case_accepts_teaching_case_output_with_match_summary(monkeypatch, tmp_path):
    monkeypatch.setattr(cases, "CASES_FILE", tmp_path / "cases.jsonl")

    teaching_resp = client.post(
        "/api/teaching/case",
        json={**VALID_CASE, "expected_diagnosis": "Fabry disease"},
    )
    board_output = teaching_resp.json()

    save_resp = client.post(
        "/api/cases/save",
        json={**VALID_CASE, "board_output": board_output, "submitted_by": "Dr. Test"},
    )
    assert save_resp.status_code == 200
    assert save_resp.json()["board_output"]["match_summary"]["expected_diagnosis"] == "Fabry disease"


def test_save_case_rejects_board_output_missing_required_field(monkeypatch, tmp_path):
    monkeypatch.setattr(cases, "CASES_FILE", tmp_path / "cases.jsonl")

    fabricated = {"demo_mode": True}  # no "synthesis", no "disclaimer"
    resp = client.post(
        "/api/cases/save",
        json={**VALID_CASE, "board_output": fabricated, "submitted_by": "Dr. Test"},
    )
    assert resp.status_code == 422


def test_save_case_rejects_board_output_with_wrong_field_types(monkeypatch, tmp_path):
    monkeypatch.setattr(cases, "CASES_FILE", tmp_path / "cases.jsonl")

    fabricated = {
        "synthesis": "1. Made up diagnosis",
        "disclaimer": "d",
        "demo_mode": True,
        # specialist_opinions must be a list of {specialty, opinion} objects.
        "specialist_opinions": ["not an opinion object"],
    }
    resp = client.post(
        "/api/cases/save",
        json={**VALID_CASE, "board_output": fabricated, "submitted_by": "Dr. Test"},
    )
    assert resp.status_code == 422


def test_save_case_rejects_oversized_board_output_field(monkeypatch, tmp_path):
    monkeypatch.setattr(cases, "CASES_FILE", tmp_path / "cases.jsonl")

    fabricated = {
        "synthesis": "x" * 20001,  # over BoardOutput's max_length
        "disclaimer": "d",
        "demo_mode": True,
    }
    resp = client.post(
        "/api/cases/save",
        json={**VALID_CASE, "board_output": fabricated, "submitted_by": "Dr. Test"},
    )
    assert resp.status_code == 422


def test_save_case_without_board_output_runs_the_board(monkeypatch, tmp_path):
    monkeypatch.setattr(cases, "CASES_FILE", tmp_path / "cases.jsonl")

    resp = client.post("/api/cases/save", json={**VALID_CASE, "submitted_by": "Dr. Test"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "saved"
    assert data["board_output"]["synthesis"]


def test_save_then_retrieve_case_roundtrips(monkeypatch, tmp_path):
    monkeypatch.setattr(cases, "CASES_FILE", tmp_path / "cases.jsonl")

    save_resp = client.post("/api/cases/save", json={**VALID_CASE, "submitted_by": "Dr. Roundtrip"})
    case_id = save_resp.json()["case_id"]

    get_resp = client.get(f"/api/cases/{case_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["submitted_by"] == "Dr. Roundtrip"

    missing_resp = client.get("/api/cases/does-not-exist")
    assert missing_resp.status_code == 404


def test_add_comment_to_missing_case_returns_404(monkeypatch, tmp_path):
    monkeypatch.setattr(cases, "CASES_FILE", tmp_path / "cases.jsonl")

    resp = client.post(
        "/api/cases/does-not-exist/comment",
        json={"author": "Dr. Test", "text": "hello"},
    )
    assert resp.status_code == 404


def test_health_reports_demo_mode():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["demo_mode"] is True


def test_home_serves_the_web_ui():
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_example_case_returns_the_builtin_case():
    resp = client.get("/api/example-case")
    assert resp.status_code == 200
    assert resp.json() == EXAMPLE_CASE


def test_demo_cases_falls_back_to_example_when_file_missing(monkeypatch, tmp_path):
    monkeypatch.setattr("aegismed.main.DEMO_CASES_FILE", tmp_path / "does-not-exist.json")

    resp = client.get("/api/demo-cases")
    assert resp.status_code == 200
    assert resp.json() == [{"label": "Example: Fabry disease", **EXAMPLE_CASE, "expected_diagnosis": "Fabry disease"}]


def test_demo_cases_reads_curated_file_when_present(monkeypatch, tmp_path):
    demo_file = tmp_path / "demo_cases.json"
    demo_file.write_text(
        json.dumps([
            {
                "source": "RareBench",
                "expected_diagnosis": "Pompe disease",
                "age": "5", "sex": "female",
                "symptoms": "muscle weakness", "history": "", "labs": "",
            }
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr("aegismed.main.DEMO_CASES_FILE", demo_file)

    resp = client.get("/api/demo-cases")
    assert resp.status_code == 200
    [case] = resp.json()
    assert case["label"] == "RareBench: Pompe disease"
    assert case["expected_diagnosis"] == "Pompe disease"
    assert case["age"] == "5"


def test_intake_endpoint_returns_questions_in_demo_mode():
    resp = client.post("/api/intake", json=VALID_CASE)
    assert resp.status_code == 200
    body = resp.json()
    assert body["demo_mode"] is True
    assert "questions" in body


def test_intake_endpoint_returns_502_on_llm_error(monkeypatch):
    async def _boom(*args, **kwargs):
        raise llm.LLMError("Fireworks is down")

    monkeypatch.setattr("aegismed.main.intake.gather_questions", _boom)
    resp = client.post("/api/intake", json=VALID_CASE)
    assert resp.status_code == 502


def test_diagnose_returns_502_on_llm_error(monkeypatch):
    async def _boom(*args, **kwargs):
        raise llm.LLMError("Fireworks is down")

    monkeypatch.setattr("aegismed.main.orchestrator.diagnose", _boom)
    resp = client.post("/api/diagnose", json=VALID_CASE)
    assert resp.status_code == 502


def test_teaching_case_returns_502_on_llm_error(monkeypatch):
    async def _boom(*args, **kwargs):
        raise llm.LLMError("Fireworks is down")

    monkeypatch.setattr("aegismed.main.orchestrator.diagnose", _boom)
    resp = client.post(
        "/api/teaching/case",
        json={**VALID_CASE, "expected_diagnosis": "Fabry disease"},
    )
    assert resp.status_code == 502


def test_save_case_returns_502_on_llm_error_when_no_board_output(monkeypatch, tmp_path):
    monkeypatch.setattr(cases, "CASES_FILE", tmp_path / "cases.jsonl")

    async def _boom(*args, **kwargs):
        raise llm.LLMError("Fireworks is down")

    monkeypatch.setattr("aegismed.main.orchestrator.diagnose", _boom)
    resp = client.post("/api/cases/save", json={**VALID_CASE, "submitted_by": "Dr. Test"})
    assert resp.status_code == 502


def test_list_cases_endpoint_returns_summaries(monkeypatch, tmp_path):
    monkeypatch.setattr(cases, "CASES_FILE", tmp_path / "cases.jsonl")

    client.post("/api/cases/save", json={**VALID_CASE, "submitted_by": "Dr. A", "specialty": "Cardiology"})
    client.post("/api/cases/save", json={**VALID_CASE, "submitted_by": "Dr. B", "specialty": "Neurology"})

    resp = client.get("/api/cases")
    assert resp.status_code == 200
    summaries = resp.json()
    assert len(summaries) == 2
    assert {s["specialty"] for s in summaries} == {"Cardiology", "Neurology"}

    filtered = client.get("/api/cases", params={"specialty": "Cardiology"})
    assert len(filtered.json()) == 1
    assert filtered.json()[0]["submitted_by"] == "Dr. A"


def test_add_comment_success(monkeypatch, tmp_path):
    monkeypatch.setattr(cases, "CASES_FILE", tmp_path / "cases.jsonl")

    save_resp = client.post("/api/cases/save", json={**VALID_CASE, "submitted_by": "Dr. Test"})
    case_id = save_resp.json()["case_id"]

    resp = client.post(
        f"/api/cases/{case_id}/comment",
        json={"author": "Dr. Reviewer", "text": "Agree with the differential."},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "comment added", "case_id": case_id}

    entry = cases.load_case(case_id)
    assert entry["team_comments"][0]["text"] == "Agree with the differential."


# --- rate limiting -----------------------------------------------------------------


def test_diagnose_returns_429_once_rate_limit_exceeded(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "2")

    for _ in range(2):
        assert client.post("/api/diagnose", json=VALID_CASE).status_code == 200

    resp = client.post("/api/diagnose", json=VALID_CASE)
    assert resp.status_code == 429
    assert "Retry-After" in resp.headers


def test_rate_limit_is_disabled_when_set_to_zero(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "0")

    for _ in range(5):
        assert client.post("/api/diagnose", json=VALID_CASE).status_code == 200


def test_read_only_endpoints_are_not_rate_limited(monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_PER_MINUTE", "1")

    # Use up /api/diagnose's budget...
    assert client.post("/api/diagnose", json=VALID_CASE).status_code == 200
    assert client.post("/api/diagnose", json=VALID_CASE).status_code == 429

    # ...but plain reads are a different (unlimited) code path entirely.
    for _ in range(5):
        assert client.get("/health").status_code == 200
        assert client.get("/api/example-case").status_code == 200

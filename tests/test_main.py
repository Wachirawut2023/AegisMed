"""Endpoint-level tests for the FastAPI app.

Runs in demo mode (DEMO_MODE=true), so these exercise real routing/validation
logic but never call the network. Case storage is monkeypatched to a temp
file so tests never touch the real data/cases.jsonl.
"""

import os

os.environ["DEMO_MODE"] = "true"

from fastapi.testclient import TestClient

from aegismed import cases
from aegismed.main import app

client = TestClient(app)

VALID_CASE = {
    "symptoms": "burning pain in hands and feet since childhood, decreased sweating",
    "history": "maternal uncle died of renal failure",
    "labs": "proteinuria; LVH on ECG",
}


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

    precomputed = {"synthesis": "EXACT SYNTHESIS FROM SCREEN", "disclaimer": "d", "demo_mode": True, "region": "uk"}
    resp = client.post(
        "/api/cases/save",
        json={**VALID_CASE, "board_output": precomputed, "submitted_by": "Dr. Test", "specialty": "Cardiology"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["board_output"] == precomputed
    assert data["board_output"]["synthesis"] == "EXACT SYNTHESIS FROM SCREEN"


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
    assert "endpoint" in body
    assert "request_timeout_seconds" in body


def test_diagnose_returns_504_when_board_exceeds_deadline(monkeypatch):
    import asyncio

    async def _hangs(*args, **kwargs):
        await asyncio.sleep(10)

    monkeypatch.setattr("aegismed.main.config.request_timeout", lambda: 0.05)
    monkeypatch.setattr("aegismed.main.orchestrator.diagnose", _hangs)

    resp = client.post("/api/diagnose", json=VALID_CASE)
    assert resp.status_code == 504

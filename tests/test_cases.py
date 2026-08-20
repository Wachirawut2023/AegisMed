"""Unit tests for the case-history storage layer (aegismed/cases.py).

Every test monkeypatches CASES_FILE to a tmp_path file so the real
data/cases.jsonl is never read or written.
"""

import json
from concurrent.futures import ThreadPoolExecutor

from aegismed import cases


def _use_tmp_file(monkeypatch, tmp_path):
    path = tmp_path / "cases.jsonl"
    monkeypatch.setattr(cases, "CASES_FILE", path)
    return path


def test_generate_case_id_is_short_and_unique():
    ids = {cases.generate_case_id() for _ in range(20)}
    assert len(ids) == 20
    assert all(len(i) == 8 for i in ids)


def test_save_case_writes_metadata_and_empty_comments(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    case_id = cases.save_case(
        board_output={"synthesis": "1. Fabry disease [RARE] — high."},
        submitted_by="Dr. Test",
        specialty="Cardiology",
    )
    entry = cases.load_case(case_id)
    assert entry["case_id"] == case_id
    assert entry["submitted_by"] == "Dr. Test"
    assert entry["specialty"] == "Cardiology"
    assert entry["team_comments"] == []
    assert entry["timestamp"]


def test_load_case_returns_none_when_file_missing(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    assert cases.load_case("does-not-exist") is None


def test_load_case_returns_none_when_id_not_found(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    cases.save_case(board_output={"synthesis": ""})
    assert cases.load_case("does-not-exist") is None


def test_list_cases_empty_when_file_missing(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    assert cases.list_cases() == []


def test_list_cases_filters_by_specialty(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    cases.save_case(board_output={"synthesis": "1. A"}, specialty="Cardiology")
    cases.save_case(board_output={"synthesis": "1. B"}, specialty="Neurology")

    cardiology_only = cases.list_cases(specialty="Cardiology")
    assert len(cardiology_only) == 1
    assert cardiology_only[0]["specialty"] == "Cardiology"


def test_list_cases_respects_limit_and_most_recent_first(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    import time

    ids = []
    for i in range(3):
        ids.append(cases.save_case(board_output={"synthesis": f"1. Disease {i}"}))
        time.sleep(0.001)  # ensure distinct ISO timestamps

    result = cases.list_cases(limit=2)
    assert len(result) == 2
    # Most recently saved case comes first.
    assert result[0]["case_id"] == ids[-1]


def test_list_cases_includes_top_diagnosis_and_comment_count(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    case_id = cases.save_case(board_output={"synthesis": "1. Fabry disease [RARE] — high."})
    cases.append_comment(case_id, author="Dr. A", text="agreed")

    [summary] = cases.list_cases()
    assert summary["top_diagnosis"] == "Fabry disease"
    assert summary["num_comments"] == 1


def test_append_comment_to_missing_case_returns_false(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    cases.save_case(board_output={"synthesis": "1. A"})  # some other case exists
    assert cases.append_comment("does-not-exist", author="Dr. A", text="hi") is False


def test_append_comment_when_file_missing_returns_false(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    assert cases.append_comment("anything", author="Dr. A", text="hi") is False


def test_append_comment_appends_timestamped_entry(monkeypatch, tmp_path):
    _use_tmp_file(monkeypatch, tmp_path)
    case_id = cases.save_case(board_output={"synthesis": "1. A"})

    assert cases.append_comment(case_id, author="Dr. A", text="first") is True
    assert cases.append_comment(case_id, author="Dr. B", text="second") is True

    entry = cases.load_case(case_id)
    assert [c["text"] for c in entry["team_comments"]] == ["first", "second"]
    assert entry["team_comments"][0]["author"] == "Dr. A"
    assert all(c["timestamp"] for c in entry["team_comments"])


# --- concurrency safety -------------------------------------------------------------
#
# append_comment does a read-modify-write of the whole file; save_case appends a
# line that can exceed PIPE_BUF. Real OS threads (unlike asyncio tasks) can be
# preempted mid-syscall, so these exercise the file lock with genuine concurrent
# writers rather than just asserting it was called.


def test_append_comment_survives_concurrent_writers(monkeypatch, tmp_path):
    path = _use_tmp_file(monkeypatch, tmp_path)
    case_id = cases.save_case(board_output={"synthesis": "1. Test disease"})

    n = 25
    with ThreadPoolExecutor(max_workers=n) as pool:
        results = list(pool.map(
            lambda i: cases.append_comment(case_id, author=f"Dr. {i}", text=f"comment {i}"),
            range(n),
        ))

    assert all(results), "every concurrent comment should have been recorded"

    entry = cases.load_case(case_id)
    assert len(entry["team_comments"]) == n
    assert {c["text"] for c in entry["team_comments"]} == {f"comment {i}" for i in range(n)}

    # The file must still be exactly one valid JSON object per case, not a
    # truncated or interleaved mess from unlocked concurrent rewrites.
    lines = [l for l in path.read_text(encoding="utf-8").split("\n") if l.strip()]
    assert len(lines) == 1
    json.loads(lines[0])


def test_save_case_survives_concurrent_writers(monkeypatch, tmp_path):
    path = _use_tmp_file(monkeypatch, tmp_path)

    n = 25
    with ThreadPoolExecutor(max_workers=n) as pool:
        case_ids = list(pool.map(
            lambda i: cases.save_case(board_output={"synthesis": f"1. Disease {i}" * 200}),
            range(n),
        ))

    assert len(set(case_ids)) == n  # every ID unique, none silently overwritten

    lines = [l for l in path.read_text(encoding="utf-8").split("\n") if l.strip()]
    assert len(lines) == n
    for line in lines:
        json.loads(line)  # every line intact, not interleaved with another writer's


def test_extract_top_diagnosis_strips_rare_tag():
    board_output = {"synthesis": "1. Fabry disease [RARE] — high; reasoning here.\n2. Pompe disease"}
    assert cases._extract_top_diagnosis(board_output) == "Fabry disease"


def test_extract_top_diagnosis_handles_hyphen_and_em_dash_markers():
    assert cases._extract_top_diagnosis({"synthesis": "1. Marfan syndrome - high."}) == "Marfan syndrome"
    assert cases._extract_top_diagnosis({"synthesis": "1. Marfan syndrome — high."}) == "Marfan syndrome"


def test_extract_top_diagnosis_returns_unknown_when_no_ranked_line():
    assert cases._extract_top_diagnosis({"synthesis": "no numbered list here"}) == "Unknown"


def test_extract_top_diagnosis_returns_unknown_for_empty_synthesis():
    assert cases._extract_top_diagnosis({}) == "Unknown"
    assert cases._extract_top_diagnosis({"synthesis": ""}) == "Unknown"

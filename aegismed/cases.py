"""Case history storage — a light persistence layer for B2B hospital workflows.

Cases are stored as JSON lines (one complete board result per line) in a simple
file-based log. No auth, no patient identity, no PHI — just case lookup by ID
and team comment append. Each case is self-contained and can be retrieved later
for case-conference follow-up, second-opinion review, or team discussion.
"""

import fcntl
import json
import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import IO, Optional

CASES_FILE = Path(__file__).resolve().parent.parent / "data" / "cases.jsonl"


@contextmanager
def _locked_file(mode: str, lock_type: int) -> "IO[str]":
    """Open CASES_FILE under an flock so readers and writers never interleave.

    append_comment does a read-modify-write of the *entire* file, and a
    board_output line can easily exceed PIPE_BUF, so unlocked concurrent
    writers can both interleave partial lines and silently drop each other's
    updates. LOCK_EX (writers) blocks everyone else out; LOCK_SH (readers)
    just blocks until any in-progress write finishes, so a read never lands
    mid-rewrite.
    """
    f = open(CASES_FILE, mode, encoding="utf-8")
    try:
        fcntl.flock(f.fileno(), lock_type)
        yield f
    finally:
        # A write sitting in Python's buffer isn't visible to the next
        # opener yet — flush (and fsync, so it survives a crash) BEFORE
        # unlocking, or releasing the lock races the data actually landing.
        f.flush()
        os.fsync(f.fileno())
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        f.close()


def generate_case_id() -> str:
    """Generate a unique case ID (short UUID)."""
    return str(uuid.uuid4())[:8]


def save_case(
    board_output: dict,
    submitted_by: str = "",
    specialty: str = "",
) -> str:
    """Save a completed board result with optional metadata.

    Args:
        board_output: The full dict from orchestrator.diagnose() or api/teaching/case
        submitted_by: Free text, e.g. "Dr. Smith, Cardiology"
        specialty: Primary specialty relevant to the case (e.g. "Cardiology")

    Returns:
        case_id: A short unique ID for this case.
    """
    case_id = generate_case_id()
    timestamp = datetime.utcnow().isoformat()

    case_entry = {
        "case_id": case_id,
        "timestamp": timestamp,
        "submitted_by": submitted_by,
        "specialty": specialty or "",
        "board_output": board_output,
        "team_comments": [],
    }

    # Append to the cases log (create file if it doesn't exist).
    CASES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with _locked_file("a", fcntl.LOCK_EX) as f:
        f.write(json.dumps(case_entry) + "\n")

    return case_id


def load_case(case_id: str) -> Optional[dict]:
    """Load a saved case by ID.

    Returns:
        The full case entry (board_output + metadata), or None if not found.
    """
    if not CASES_FILE.exists():
        return None

    with _locked_file("r", fcntl.LOCK_SH) as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("case_id") == case_id:
                return entry

    return None


def list_cases(specialty: str = "", limit: int = 50) -> list[dict]:
    """List cases, optionally filtered by specialty.

    Returns:
        A list of case summaries (board_output reduced to diagnosis + timestamp),
        most recent first, up to `limit` results.
    """
    if not CASES_FILE.exists():
        return []

    cases = []
    with _locked_file("r", fcntl.LOCK_SH) as f:
        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            if specialty and entry.get("specialty") != specialty:
                continue
            cases.append(entry)

    # Most recent first
    cases.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    # Return summaries with just diagnosis + metadata (not full board output)
    return [
        {
            "case_id": c["case_id"],
            "timestamp": c["timestamp"],
            "submitted_by": c["submitted_by"],
            "specialty": c["specialty"],
            "top_diagnosis": _extract_top_diagnosis(c.get("board_output", {})),
            "num_comments": len(c.get("team_comments", [])),
        }
        for c in cases[:limit]
    ]


def append_comment(case_id: str, author: str, text: str) -> bool:
    """Append a team comment to a case.

    Returns:
        True if successful, False if case not found.
    """
    if not CASES_FILE.exists():
        return False

    # Read and rewrite under ONE held lock (not open-read-close-open-write) so
    # no other process's write or read can land between the two halves.
    with _locked_file("r+", fcntl.LOCK_EX) as f:
        lines = []
        found = False

        for line in f:
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry.get("case_id") == case_id:
                found = True
                comment = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "author": author,
                    "text": text,
                }
                entry.setdefault("team_comments", []).append(comment)
            lines.append(json.dumps(entry))

        if not found:
            return False

        f.seek(0)
        f.truncate()
        f.write("\n".join(lines) + "\n")

    return True


def _extract_top_diagnosis(board_output: dict) -> str:
    """Extract the top diagnosis from a board output dict.

    Parses the synthesis to find the first diagnosis in the ranked list.
    """
    synthesis = board_output.get("synthesis", "")
    if not synthesis:
        return "Unknown"

    # Look for "1. DiagnosisName" pattern
    for line in synthesis.split("\n"):
        line = line.strip()
        if line.startswith("1."):
            # Extract the diagnosis name (before [RARE] or — or other markers)
            diagnosis = line[2:].strip()
            for marker in ["[RARE]", " —", " \\[", " -"]:
                if marker in diagnosis:
                    diagnosis = diagnosis.split(marker)[0].strip()
                    break
            return diagnosis or "Unknown"

    return "Unknown"

"""Build the citation knowledge base used for evidence-grounded diagnosis.

WHAT THIS DOES (plain language)
-------------------------------
It builds a lookup table that maps a disease NAME to real, authoritative
reference pages: its Orphanet and OMIM disease entries. AegisMed uses this to
attach VERIFIED citations to diagnoses (and to give the specialists real
reference leads), instead of letting the AI invent papers — which language
models do frequently and dangerously in medicine.

Source: the RareBench disease mapping (Apache-2.0), which pairs disease names
with their official ORPHA and OMIM codes. We invert it into name -> codes.

Output: data/citations_index.json  (committed; small)

USAGE
-----
  python data/build_knowledge_base.py

Anything the index cannot resolve still gets real PubMed / GARD *search* links
at runtime (see aegismed/knowledge.py), so every diagnosis is verifiable.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx

DATA_DIR = Path(__file__).resolve().parent
CACHE_DIR = DATA_DIR / ".cache"
DISEASE_MAP_URL = (
    "https://huggingface.co/datasets/chenxz/RareBench/resolve/main/"
    "mapping/disease_mapping.json"
)
OUT = DATA_DIR / "citations_index.json"


def _normalize(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", text.lower()).split())


def _english_parts(raw: str) -> list[str]:
    """Split 'NameA/NameB;NameC' into readable English variants."""
    parts = []
    for chunk in re.split(r"[/;]", raw):
        chunk = chunk.strip()
        if chunk and sum(c.isascii() for c in chunk) / max(len(chunk), 1) > 0.7:
            parts.append(chunk)
    return parts


def _load_disease_map() -> dict:
    dest = CACHE_DIR / "disease_mapping.json"
    if not dest.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        print("Downloading RareBench disease mapping ...")
        with httpx.Client(follow_redirects=True, timeout=120) as c:
            r = c.get(DISEASE_MAP_URL)
            r.raise_for_status()
            dest.write_bytes(r.content)
    return json.loads(dest.read_text(encoding="utf-8"))


def main() -> None:
    disease_map = _load_disease_map()

    # normalized name -> {"orpha": code, "omim": code, "display": readable name}
    index: dict[str, dict] = {}
    for code, raw in disease_map.items():
        code = code.strip()
        prefix, _, num = code.partition(":")
        if prefix not in ("ORPHA", "OMIM"):
            continue
        for part in _english_parts(raw):
            key = _normalize(part)
            if not key:
                continue
            entry = index.setdefault(key, {"orpha": "", "omim": "", "display": part})
            field = "orpha" if prefix == "ORPHA" else "omim"
            # keep the first (lowest) code we see for stability
            if not entry[field]:
                entry[field] = num

    OUT.write_text(json.dumps(index, ensure_ascii=False, indent=0))
    resolved_orpha = sum(1 for e in index.values() if e["orpha"])
    resolved_omim = sum(1 for e in index.values() if e["omim"])
    print("── Knowledge base built ─────────────────")
    print(f"disease name keys : {len(index)}")
    print(f"with Orphanet page: {resolved_orpha}")
    print(f"with OMIM entry   : {resolved_omim}")
    print(f"written           : {OUT.name} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()

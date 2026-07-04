"""Build AegisMed's evaluation and demo datasets from public medical datasets.

WHAT THIS SCRIPT DOES (in plain language)
-----------------------------------------
It downloads real, publicly-licensed rare-disease datasets, converts every
case into ONE simple format that AegisMed understands, and saves the result to:

  data/eval_cases.jsonl   <- the test set (case + the known-correct diagnosis)
  data/demo_cases.json    <- a few readable cases for the UI / demo video
  data/aliases.json       <- alternative names per disease (fairer scoring)

You run it once. You do NOT need an API key or a GPU for this step — it only
prepares data. Scoring the data with the AI happens later in eval/run_eval.py.

USAGE
-----
  python data/build_dataset.py                      # default: rarebench + cupcase
  python data/build_dataset.py --sources rarebench  # just one source
  python data/build_dataset.py --per-source 20      # more cases per source
  python data/build_dataset.py --sources rarearena  # big extra set (NOT committed)

SOURCES & LICENSES: see data/SOURCES.md
"""

from __future__ import annotations

import argparse
import io
import json
import random
import re
import sys
import zipfile
from pathlib import Path

import httpx

# Where things live -----------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent
CACHE_DIR = DATA_DIR / ".cache"          # downloaded raw files (gitignored)
HF = "https://huggingface.co"            # HuggingFace base URL

# RareBench (Apache-2.0): coded rare-disease cases + code->name mapping files
RAREBENCH = f"{HF}/datasets/chenxz/RareBench/resolve/main"
RAREBENCH_SUBSETS = ["LIRICAL", "RAMEDIS", "HMS", "MME"]

# CUPCase (Apache-2.0): real natural-language case reports, read via the
# datasets-server rows API so we don't need to parse Parquet files.
CUPCASE_ROWS = (
    "https://datasets-server.huggingface.co/rows"
    "?dataset=ofir408%2FCupCase&config=default&split=test"
)

# RareArena (CC BY-NC-SA — NON-COMMERCIAL): only downloaded on explicit request,
# never committed to this repo. Output goes to a gitignored file.
RAREARENA_ROWS = (
    "https://datasets-server.huggingface.co/rows"
    "?dataset=THUMedInfo%2FRareArena&config=default&split=train"
)


def _client() -> httpx.Client:
    # follow_redirects=True is essential: HuggingFace 'resolve' URLs redirect to a CDN.
    return httpx.Client(follow_redirects=True, timeout=120)


def _download(url: str, dest: Path) -> Path:
    """Download url to dest, caching so re-runs are fast."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    print(f"  downloading {url.split('/')[-1]} ...")
    with _client() as c:
        r = c.get(url)
        r.raise_for_status()
        dest.write_bytes(r.content)
    return dest


# --- helpers to clean up disease names --------------------------------------

def _english_names(raw: str) -> list[str]:
    """RareBench disease names look like 'NameA/NameB' or contain ';' or Chinese.
    Return the readable English variants, most canonical first."""
    parts: list[str] = []
    for chunk in re.split(r"[/;]", raw):
        chunk = chunk.strip()
        # keep chunks that are mostly ASCII letters (drop Chinese synonyms)
        if chunk and sum(c.isascii() for c in chunk) / len(chunk) > 0.7:
            parts.append(chunk)
    # de-duplicate while preserving order
    seen, out = set(), []
    for p in parts:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out or [raw.strip()]


def _normalize(text: str) -> str:
    """Lowercase and strip punctuation — used to compare disease names."""
    return re.sub(r"[^a-z0-9 ]", " ", text.lower()).strip()


# --- source adapters: each yields the SAME unified case dict -----------------

def load_rarebench(per_source: int, rng: random.Random) -> list[dict]:
    """Coded phenotype cases from RareBench's four public sub-datasets."""
    print("RareBench:")
    _download(f"{RAREBENCH}/data.zip", CACHE_DIR / "rarebench_data.zip")
    phe = json.loads(_download(
        f"{RAREBENCH}/mapping/phenotype_mapping.json",
        CACHE_DIR / "phenotype_mapping.json").read_text())
    dis = json.loads(_download(
        f"{RAREBENCH}/mapping/disease_mapping.json",
        CACHE_DIR / "disease_mapping.json").read_text())

    cases: list[dict] = []
    with zipfile.ZipFile(CACHE_DIR / "rarebench_data.zip") as zf:
        for subset in RAREBENCH_SUBSETS:
            rows = []
            with zf.open(f"data/{subset}.jsonl") as f:
                for line in io.TextIOWrapper(f, encoding="utf-8"):
                    line = line.strip()
                    if line:
                        rows.append(json.loads(line))
            rng.shuffle(rows)
            picked = 0
            for i, row in enumerate(rows):
                # symptoms: turn HPO codes into readable phenotype names
                names = [phe[c] for c in row["Phenotype"] if c in phe]
                if len(names) < 3:
                    continue  # too little signal to be a fair test
                # ground-truth diagnosis: prefer an English name
                dcodes = row.get("RareDisease", [])
                dnames = []
                for c in dcodes:
                    if c in dis:
                        dnames.extend(_english_names(dis[c]))
                if not dnames:
                    continue
                canonical = dnames[0]
                cases.append({
                    "id": f"rarebench-{subset.lower()}-{i}",
                    "source": f"RareBench/{subset}",
                    "case_style": "coded",
                    "age": "", "sex": "",
                    "symptoms": "; ".join(names) + ".",
                    "history": "", "labs": "",
                    "expected_diagnosis": canonical,
                    "expected_diagnosis_codes": dcodes,
                    "expected_aliases": sorted({_normalize(n) for n in dnames}),
                })
                picked += 1
                if picked >= per_source:
                    break
            print(f"  {subset}: {picked} cases")
    return cases


def _parse_age_sex(text: str) -> tuple[str, str]:
    # Case reports state demographics in the opening sentence ("A 42-year-old
    # woman..."), so read sex from just the start to avoid stray later pronouns.
    head = text[:160]
    age = ""
    m = re.search(r"(\d{1,3})[\s-]*year[\s-]*old", text, re.I)
    if m:
        age = m.group(1)
    male = bool(re.search(r"\b(man|male|boy|gentleman)\b", head, re.I))
    female = bool(re.search(r"\b(woman|female|girl|lady)\b", head, re.I))
    sex = "male" if male and not female else "female" if female and not male else ""
    return age, sex


def _fetch_rows(base_url: str, want: int, rng: random.Random) -> list[dict]:
    """Page through a HuggingFace datasets-server split and sample `want` rows."""
    collected: list[dict] = []
    offset = 0
    page = 100
    with _client() as c:
        while len(collected) < max(want * 6, want + 50) and offset < 3000:
            r = c.get(f"{base_url}&offset={offset}&length={page}")
            if r.status_code != 200:
                break
            rows = r.json().get("rows", [])
            if not rows:
                break
            collected.extend(x["row"] for x in rows)
            offset += page
    rng.shuffle(collected)
    return collected


def load_cupcase(per_source: int, rng: random.Random) -> list[dict]:
    """Real natural-language case reports from CUPCase (BMC open-access)."""
    print("CUPCase:")
    rows = _fetch_rows(CUPCASE_ROWS, per_source, rng)
    cases: list[dict] = []
    for i, row in enumerate(rows):
        text = (row.get("clean_case_presentation") or "").strip()
        dx = (row.get("correct_diagnosis") or "").strip().rstrip(".")
        if len(text) < 80 or not dx:
            continue
        age, sex = _parse_age_sex(text)
        cases.append({
            "id": f"cupcase-{i}",
            "source": "CUPCase",
            "case_style": "narrative",
            "age": age, "sex": sex,
            "symptoms": text,
            "history": "", "labs": "",
            "expected_diagnosis": dx,
            "expected_diagnosis_codes": [],
            "expected_aliases": sorted({_normalize(dx)}),
            # distractors are WRONG answers — kept so the scorer can be strict
            "distractors": [row.get(f"distractor{n}", "") for n in (1, 2, 3)],
        })
        if len(cases) >= per_source:
            break
    print(f"  {len(cases)} cases")
    return cases


def load_rarearena(per_source: int, rng: random.Random) -> list[dict]:
    """RareArena — NON-COMMERCIAL (CC BY-NC-SA). Never committed; local eval only."""
    print("RareArena (NON-COMMERCIAL — output will be gitignored):")
    rows = _fetch_rows(RAREARENA_ROWS, per_source, rng)
    cases = []
    for i, row in enumerate(rows):
        # RareArena rows vary; try the common fields defensively
        text = str(row.get("case") or row.get("text") or row.get("RDC") or "").strip()
        dx = str(row.get("diagnosis") or row.get("disease") or row.get("answer") or "").strip()
        if len(text) < 80 or not dx:
            continue
        age, sex = _parse_age_sex(text)
        cases.append({
            "id": f"rarearena-{i}", "source": "RareArena", "case_style": "narrative",
            "age": age, "sex": sex, "symptoms": text, "history": "", "labs": "",
            "expected_diagnosis": dx, "expected_diagnosis_codes": [],
            "expected_aliases": sorted({_normalize(dx)}),
        })
        if len(cases) >= per_source:
            break
    print(f"  {len(cases)} cases")
    return cases


ADAPTERS = {
    "rarebench": load_rarebench,
    "cupcase": load_cupcase,
    "rarearena": load_rarearena,   # non-commercial: opt-in only
}

# Well-known rare diseases we prefer to surface in the demo (readable & teachable).
# These are recognizable names a general audience / judges will know, and they
# occur in the CUPCase "clinically uncommon" case reports.
DEMO_KEYWORDS = [
    "fabry", "wilson", "pompe", "porphyria", "gaucher", "marfan", "ehlers",
    "amyloid", "sarcoid", "behcet", "whipple", "kawasaki", "hemochromatosis",
    "addison", "cushing", "myasthenia", "guillain", "takotsubo", "lupus",
    "pheochromocytoma", "granulomatosis", "wegener", "churg", "goodpasture",
    "histiocytosis", "castleman", "still disease", "vasculitis", "sweet",
    "acromegaly", "carcinoid", "mastocytosis", "poems", "erdheim", "moyamoya",
    "dermatomyositis", "giant cell arteritis", "sjogren", "scleroderma",
    "hemophagocytic", "antiphospholipid", "polyarteritis",
]


def build_aliases(cases: list[dict]) -> dict[str, list[str]]:
    """Map canonical diagnosis -> list of alias spellings, from the cases we built.
    (Extensible with Orphanet/HPO synonym files — see data/SOURCES.md.)"""
    table: dict[str, set] = {}
    for c in cases:
        table.setdefault(c["expected_diagnosis"], set()).update(c["expected_aliases"])
    return {k: sorted(v) for k, v in table.items()}


def _trim(case: dict, limit: int = 1200) -> dict:
    d = dict(case)
    if len(d["symptoms"]) > limit:
        d["symptoms"] = d["symptoms"][:limit].rsplit(" ", 1)[0] + " ..."
    return d


def curate_demo_cases(rng: random.Random, n: int = 8, fallback: list[dict] | None = None) -> list[dict]:
    """Scan a LARGE pool of CUPCase reports for recognizable rare diseases.

    The eval set is only a small random sample, so it rarely contains famous
    diseases. For the demo we search a much bigger pool specifically for
    diagnoses a general audience will recognize (see DEMO_KEYWORDS)."""
    print("Curating recognizable demo cases from a larger CUPCase pool...")
    rows = _fetch_rows(CUPCASE_ROWS, want=250, rng=rng)  # fetches up to ~1.5k rows
    picked: dict[str, dict] = {}   # keyed by diagnosis so we get variety
    for i, row in enumerate(rows):
        dx = (row.get("correct_diagnosis") or "").strip().rstrip(".")
        text = (row.get("clean_case_presentation") or "").strip()
        if not dx or len(text) < 120:
            continue
        if not any(k in dx.lower() for k in DEMO_KEYWORDS):
            continue
        if dx.lower() in picked:
            continue
        age, sex = _parse_age_sex(text)
        picked[dx.lower()] = _trim({
            "id": f"demo-cupcase-{i}", "source": "CUPCase", "case_style": "narrative",
            "age": age, "sex": sex, "symptoms": text, "history": "", "labs": "",
            "expected_diagnosis": dx, "expected_diagnosis_codes": [],
            "expected_aliases": sorted({_normalize(dx)}),
        })
        if len(picked) >= n:
            break
    demo = list(picked.values())
    # top up from the eval set if we somehow found too few recognizable ones
    if len(demo) < n and fallback:
        for c in fallback:
            if len(demo) >= n:
                break
            if c["case_style"] == "narrative" and c["expected_diagnosis"].lower() not in picked:
                demo.append(_trim(c))
    print(f"  {len(demo)} demo cases: " + ", ".join(c["expected_diagnosis"] for c in demo))
    return demo


def main() -> None:
    ap = argparse.ArgumentParser(description="Build AegisMed eval/demo datasets.")
    ap.add_argument("--sources", default="rarebench,cupcase",
                    help="comma-separated: rarebench,cupcase,rarearena")
    ap.add_argument("--per-source", type=int, default=15,
                    help="cases per source (per sub-dataset for RareBench)")
    ap.add_argument("--seed", type=int, default=7, help="random seed (reproducible)")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    sources = [s.strip().lower() for s in args.sources.split(",") if s.strip()]
    non_commercial = "rarearena" in sources

    all_cases: list[dict] = []
    for s in sources:
        if s not in ADAPTERS:
            print(f"!! unknown source '{s}' (known: {', '.join(ADAPTERS)})")
            continue
        all_cases.extend(ADAPTERS[s](args.per_source, rng))

    if not all_cases:
        print("No cases produced — check your network connection.")
        sys.exit(1)

    rng.shuffle(all_cases)

    # Non-commercial data must never land in the committed eval file.
    out_name = "eval_cases_noncommercial.jsonl" if non_commercial else "eval_cases.jsonl"
    out_path = DATA_DIR / out_name
    with out_path.open("w", encoding="utf-8") as f:
        for c in all_cases:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    if not non_commercial:
        (DATA_DIR / "aliases.json").write_text(
            json.dumps(build_aliases(all_cases), ensure_ascii=False, indent=2))
        demo = curate_demo_cases(rng, n=8, fallback=all_cases)
        (DATA_DIR / "demo_cases.json").write_text(
            json.dumps(demo, ensure_ascii=False, indent=2))

    # Summary
    diseases = {c["expected_diagnosis"] for c in all_cases}
    by_source: dict[str, int] = {}
    for c in all_cases:
        by_source[c["source"]] = by_source.get(c["source"], 0) + 1
    print("\n── Summary ─────────────────────────────")
    print(f"total cases : {len(all_cases)}")
    print(f"distinct dx : {len(diseases)}")
    for src, n in sorted(by_source.items()):
        print(f"  {src}: {n}")
    print(f"written     : {out_path.name}")
    if non_commercial:
        print("NOTE: non-commercial data — this file is gitignored, do NOT commit it.")


if __name__ == "__main__":
    main()

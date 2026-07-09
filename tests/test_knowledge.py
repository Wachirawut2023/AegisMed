"""Unit tests for the verified-citation layer.

Pure/deterministic — no API key, no network. Uses "Fabry disease" as a stable
real entry in the committed knowledge base (data/citations_index.json).
"""

from aegismed import knowledge


def test_normalize_strips_punctuation_and_case():
    assert knowledge._normalize("Fabry Disease, type 2!") == "fabry disease type 2"
    assert knowledge._normalize("   ") == ""


def test_resolve_exact_match():
    entry = knowledge.resolve("Fabry disease")
    assert entry is not None
    assert entry.get("orpha")  # Fabry disease has an Orphanet code in the KB


def test_resolve_trimmed_qualifier_fallback():
    # A trailing qualifier the KB doesn't index should fall back to the base name.
    assert knowledge.resolve("Fabry disease type 9") is not None


def test_resolve_unknown_returns_none():
    assert knowledge.resolve("Definitely Not A Real Disease XYZ") is None


def test_links_always_include_pubmed_and_gard():
    labels = [l["label"] for l in knowledge.links_for("Anything At All")]
    assert any("PubMed" in x for x in labels)
    assert any("GARD" in x for x in labels)


def test_links_add_orphanet_when_resolved():
    labels = [l["label"] for l in knowledge.links_for("Fabry disease")]
    assert any("Orphanet" in x for x in labels)


def test_references_for_dedupes():
    refs = knowledge.references_for(["Fabry disease", "fabry disease", "Pompe disease"])
    assert [r["diagnosis"] for r in refs] == ["Fabry disease", "Pompe disease"]


def test_extract_diagnoses_parses_ranked_list_and_trims_tags():
    synthesis = (
        "**Ranked differential diagnosis:**\n"
        "1. Fabry disease [RARE] — high; burning pain since childhood.\n"
        "2. Pompe disease (glycogen storage) — moderate.\n"
        "3. Hypertrophic cardiomyopathy - low; LVH noted.\n"
        "**Where the specialists agree:** ...\n"
    )
    names = knowledge.extract_diagnoses(synthesis)
    assert names == ["Fabry disease", "Pompe disease", "Hypertrophic cardiomyopathy"]


def test_extract_diagnoses_respects_limit():
    lines = "\n".join(f"{i}. Disease {i}" for i in range(1, 10))
    synthesis = "**Ranked differential diagnosis:**\n" + lines
    assert len(knowledge.extract_diagnoses(synthesis, limit=3)) == 3

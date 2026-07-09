"""Unit tests for the clinical guideline search-link layer.

Pure/deterministic — no API key, no network. These functions only build URL
strings, so we assert on shape, encoding, ordering, and de-duplication.
"""

from urllib.parse import quote_plus

from aegismed import guidelines


def test_links_one_per_source_with_labels():
    links = guidelines.guideline_links_for("Fabry disease")
    # One link per configured search source (curated index is empty by default).
    assert len(links) == len(guidelines._SOURCES)
    assert all(l["label"] and l["url"] for l in links)


def test_query_is_url_encoded_not_raw():
    links = guidelines.guideline_links_for("Fabry disease")
    encoded = quote_plus("Fabry disease")  # "Fabry+disease"
    assert encoded in links[0]["url"]
    # A raw space must never leak into a URL.
    assert all(" " not in l["url"] for l in links)


def test_special_characters_are_escaped():
    # Ampersands / slashes in a diagnosis must be percent-encoded, not injected
    # raw into the URL (which could alter query parameters).
    links = guidelines.guideline_links_for("Sotos & Marfan / overlap")
    for l in links:
        assert " " not in l["url"]
        assert "%26" in l["url"]  # the "&" from the diagnosis is encoded
        assert "%2F" in l["url"]  # the "/" from the diagnosis is encoded


def test_empty_or_whitespace_returns_nothing():
    assert guidelines.guideline_links_for("") == []
    assert guidelines.guideline_links_for("   ") == []


def test_guidelines_for_dedupes_case_insensitively_and_preserves_order():
    out = guidelines.guidelines_for(["Fabry disease", "fabry disease", "Pompe disease"])
    assert [e["diagnosis"] for e in out] == ["Fabry disease", "Pompe disease"]
    assert all(e["links"] for e in out)


def test_guidelines_for_skips_blanks():
    out = guidelines.guidelines_for(["", "  ", "Fabry disease"])
    assert [e["diagnosis"] for e in out] == ["Fabry disease"]


def test_curated_index_links_come_first(monkeypatch):
    # Simulate a populated curated index; curated links should precede search links.
    curated = {"fabry disease": [{"label": "NICE NG-example", "url": "https://example.org/ng"}]}
    monkeypatch.setattr(guidelines, "_INDEX", curated)
    links = guidelines.guideline_links_for("Fabry disease")
    assert links[0]["label"] == "NICE NG-example"
    assert len(links) == len(guidelines._SOURCES) + 1


def test_curated_index_ignores_malformed_entries(monkeypatch):
    monkeypatch.setattr(guidelines, "_INDEX", {"fabry disease": [{"label": "no url"}]})
    links = guidelines.guideline_links_for("Fabry disease")
    # Malformed curated entry dropped; only the search links remain.
    assert len(links) == len(guidelines._SOURCES)

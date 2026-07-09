"""Unit tests for the clinical guideline search-link layer.

Pure/deterministic — no API key, no network. These functions only build URL
strings, so we assert on shape, encoding, ordering, and de-duplication.
"""

from urllib.parse import quote_plus

from aegismed import guidelines


def test_links_one_per_source_with_labels():
    # Pompe disease has no curated index entry, so this is search-links only.
    links = guidelines.guideline_links_for("Pompe disease")
    assert len(links) == len(guidelines._SOURCES)
    assert all(l["label"] and l["url"] for l in links)


def test_query_is_url_encoded_not_raw():
    links = guidelines.guideline_links_for("Pompe disease")
    encoded = quote_plus("Pompe disease")  # "Pompe+disease"
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


# --- Region support (Phase 3e) -------------------------------------------


def test_region_defaults_to_us_order():
    default = guidelines.guideline_links_for("Pompe disease")
    us = guidelines.guideline_links_for("Pompe disease", region="us")
    assert [l["url"] for l in default] == [l["url"] for l in us]


def test_unrecognized_region_falls_back_to_us():
    fallback = guidelines.guideline_links_for("Pompe disease", region="not-a-region")
    us = guidelines.guideline_links_for("Pompe disease", region="us")
    assert [l["url"] for l in fallback] == [l["url"] for l in us]


def test_uk_region_leads_with_nice():
    links = guidelines.guideline_links_for("Pompe disease", region="uk")
    assert links[0]["label"].startswith("NICE")


def test_every_region_uses_the_same_verified_source_pool():
    # Only order differs — the set of sources must be identical across regions.
    pools = {
        region: {label for label, _ in sources}
        for region, sources in guidelines._REGION_SOURCES.items()
    }
    assert len(set(map(frozenset, pools.values()))) == 1


def test_curated_index_per_region_dict_falls_back_to_us(monkeypatch):
    curated = {"fabry disease": {"us": [{"label": "US doc", "url": "https://example.org/us"}]}}
    monkeypatch.setattr(guidelines, "_INDEX", curated)
    # "eu" has no entry -> falls back to "us".
    links = guidelines.guideline_links_for("Fabry disease", region="eu")
    assert links[0]["label"] == "US doc"


def test_curated_index_per_region_dict_picks_matching_region(monkeypatch):
    curated = {
        "fabry disease": {
            "us": [{"label": "US doc", "url": "https://example.org/us"}],
            "uk": [{"label": "UK doc", "url": "https://example.org/uk"}],
        }
    }
    monkeypatch.setattr(guidelines, "_INDEX", curated)
    links = guidelines.guideline_links_for("Fabry disease", region="uk")
    assert links[0]["label"] == "UK doc"


def test_guidelines_for_passes_region_through():
    uk = guidelines.guidelines_for(["Pompe disease"], region="uk")
    us = guidelines.guidelines_for(["Pompe disease"], region="us")
    assert uk[0]["links"][0]["label"].startswith("NICE")
    assert not us[0]["links"][0]["label"].startswith("NICE")

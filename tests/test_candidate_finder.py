from unittest.mock import MagicMock
from wikidata_coverage.suggest.candidate_finder import ExternalCandidateFinder


def test_candidate_finder_basic():
    finder = ExternalCandidateFinder()
    candidates = finder.find_candidates(category="female_researchers", max_candidates=5)

    assert len(candidates) > 0
    c = candidates[0]
    assert c.name != ""
    assert bool(c.demographic_category)
    assert len(c.sources) > 0


def test_candidate_finder_granular_filtering():
    finder = ExternalCandidateFinder()
    # Filter by female gender QID
    candidates = finder.find_candidates(gender_qid="Q6581072", max_candidates=3)
    for c in candidates:
        assert c.gender_qid == "Q6581072"


def test_verify_source_url_heuristics():
    from wikidata_coverage.suggest.candidate_finder import verify_source_url_heuristics

    # Test 1: Valid DOI
    ok, msg = verify_source_url_heuristics("https://doi.org/10.1038/s41586-021-00001-x", "Dr. Jade Tan-Holmes")
    assert ok is True

    # Test 2: Invalid scheme
    ok, msg = verify_source_url_heuristics("invalid-url-path", "Dr. Gladys West")
    assert ok is False
    assert "Invalid URL scheme" in msg


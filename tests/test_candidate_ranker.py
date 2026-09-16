from wikidata_coverage.scoring.candidate_ranker import CandidateRanker, SourceReliabilityScorer
from wikidata_coverage.scoring.mbfc_cache import MBFCCache
from wikidata_coverage.suggest.candidate_finder import ExternalCandidateFinder, CandidateSource


def test_mbfc_cache(tmp_path):
    cache_file = tmp_path / "test_mbfc_cache.json"
    cache = MBFCCache(cache_file=cache_file)

    # Check default assessment outcome lookup
    outcome = cache.get_assessment_outcome("Encyclopaedia Britannica")
    assert outcome in ["source known to be reliable", "source of mixed reliability", "source known to be unreliable"]

    # Set new determination and check save/reload
    cache.set_factual_reporting("Custom Local Press", "HIGH", notes="Test note")
    assert cache_file.exists()

    cache_reloaded = MBFCCache(cache_file=cache_file)
    assert cache_reloaded.get_assessment_outcome("Custom Local Press") == "source known to be reliable"


def test_source_reliability_scorer():
    scorer = SourceReliabilityScorer()

    peer_reviewed_source = CandidateSource(
        title="Sample Peer-Reviewed Paper",
        url="https://doi.org/10.1000/182",
        publisher="Oxford University Press",
        venue="Journal of Physics",
        publication_year=2021,
        doi="10.1000/182",
        citation_count=50,
        is_peer_reviewed=True,
        is_academic=True,
        source_type="journal_article",
        assessment_outcome="source known to be reliable",
    )

    unreliable_source = CandidateSource(
        title="Unverified Blog Post",
        url="https://example-blog.com/post",
        is_peer_reviewed=False,
        is_academic=False,
        source_type="news_article",
        assessment_outcome="source known to be unreliable",
    )

    high_score = scorer.score_source(peer_reviewed_source)
    low_score = scorer.score_source(unreliable_source)

    assert high_score > low_score
    assert 0.0 <= high_score <= 1.0
    assert 0.0 <= low_score <= 1.0


def test_candidate_ranker_multi_factor():
    finder = ExternalCandidateFinder()
    ranker = CandidateRanker()

    candidates = finder.find_candidates(max_candidates=5)
    ranked = ranker.rank_candidates(candidates)

    assert len(ranked) > 0
    # Ensure ranked in descending order by composite_rank_score
    for i in range(len(ranked) - 1):
        assert ranked[i].composite_rank_score >= ranked[i + 1].composite_rank_score

    # Check score_breakdown structure
    for c in ranked:
        assert "disparity" in c.score_breakdown
        assert "influence" in c.score_breakdown
        assert "reliability" in c.score_breakdown
        assert "composite" in c.score_breakdown
        assert len(c.score_breakdown["disparity"]["steps"]) > 0
        assert len(c.score_breakdown["influence"]["steps"]) > 0
        assert len(c.score_breakdown["reliability"]["steps"]) > 0

    # Check literature references
    refs = ranker.get_literature_references()
    assert len(refs) >= 4
    disclaimer = ranker.get_western_bias_disclaimer()
    assert "WESTERN DATABASE BIAS" in disclaimer


"""Unit tests for QuickStatements & Local LLM RAG Wikitext generator."""

from wikidata_coverage.suggest.candidate_finder import ExternalCandidateFinder
from wikidata_coverage.suggest.rag_generator import (
    FlexibleLLMRAGGenerator,
    generate_quickstatements_for_candidate,
    save_candidate_outputs,
)


def test_quickstatements_generation():
    finder = ExternalCandidateFinder()
    candidates = finder.find_candidates(max_candidates=5)

    for c in candidates:
        qs_text = generate_quickstatements_for_candidate(c)
        assert len(qs_text) > 0
        if c.existing_qid:
            assert c.existing_qid in qs_text
        else:
            assert "CREATE" in qs_text
            assert "LAST\tP31\tQ5" in qs_text


def test_rag_wikitext_generator():
    finder = ExternalCandidateFinder()
    candidates = finder.find_candidates(max_candidates=2)

    rag_gen = FlexibleLLMRAGGenerator()
    intro_wikitext, warning_msg = rag_gen.generate_wikitext_intro(candidates[0], provider="local")

    assert len(intro_wikitext) > 0
    assert "<ref" in intro_wikitext and "</ref>" in intro_wikitext
    assert "== References ==" in intro_wikitext
    assert "{{reflist}}" in intro_wikitext


def test_validate_wikitext_format():
    from wikidata_coverage.suggest.rag_generator import validate_wikitext_format

    valid_sample = (
        "'''Dr. Amina Abubakar''' is a [[Kenya|Kenyan]] [[researcher]] <ref name=\"src_1\">{{cite web | author=Amina | title=Profile | url=https://example.org}}</ref>.\n\n"
        "== References ==\n{{reflist}}"
    )
    is_valid, errors = validate_wikitext_format(valid_sample)
    assert is_valid is True
    assert len(errors) == 0

    invalid_sample = "{{cite web | title=Broken }} no ref tag"
    is_valid, errors = validate_wikitext_format(invalid_sample)
    assert is_valid is False
    assert len(errors) > 0


def test_save_candidate_outputs(tmp_path):
    finder = ExternalCandidateFinder()
    candidates = finder.find_candidates(max_candidates=3)

    paths = save_candidate_outputs(candidates, out_dir=tmp_path)
    assert "quickstatements" in paths
    assert "wikitext" in paths
    assert "json" in paths

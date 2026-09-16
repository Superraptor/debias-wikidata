"""Unit tests for QLever Quality & Constraint Audit engine."""

from __future__ import annotations

import pytest
from wikidata_coverage.core.entity import Claim, Entity
from wikidata_coverage.detectors.quality_audit import (
    QualityAuditResult,
    run_qlever_quality_audit,
)


class DummyActionApiClient:
    """Mock ActionApiClient for testing full entity fetching and label resolution."""

    def __init__(self, entities_dict: dict[str, dict] | None = None) -> None:
        self.entities_dict = entities_dict or {}

    def get_entities(self, ids: list[str], *, languages: list[str] | None = None) -> dict[str, dict]:
        out = {}
        for qid in ids:
            if qid in self.entities_dict:
                out[qid] = self.entities_dict[qid]
            else:
                out[qid] = {
                    "labels": {"en": {"value": f"Full Label for {qid}"}},
                    "claims": {
                        "P31": [
                            {
                                "mainsnak": {
                                    "datatype": "wikibase-item",
                                    "datavalue": {"value": {"id": "Q5"}},
                                }
                            }
                        ],
                        "P21": [
                            {
                                "mainsnak": {
                                    "datatype": "wikibase-item",
                                    "datavalue": {"value": {"id": "Q6581097"}},
                                }
                            }
                        ],
                    },
                }
        return out

    def get_labels(self, qids: list[str], *, lang: str = "en") -> dict[str, str]:
        return {qid: f"Label_{qid}" for qid in qids}

    def get_property_constraints_raw(self, property_id: str) -> dict:
        return {}


def _create_tsv_entity(qid: str, prop_pids: list[str]) -> Entity:
    claims = {
        "P31": [Claim(property_id="P31", value={"id": "Q5"}, value_type="wikibase-item")]
    }
    for p in prop_pids:
        claims[p] = [Claim(property_id=p, value="test_val", value_type="string")]
    return Entity(
        id=qid,
        labels={"en": f"TSV Entity {qid}"},
        claims=claims,
    )


def test_quality_audit_candidate_selection_and_enrichment():
    # Build population of 10 Q5 entities with varying statement counts
    # e1..e5 have 1 property; e6..e10 have 4 properties
    entities = []
    for i in range(1, 6):
        entities.append(_create_tsv_entity(f"Q{i}", ["P21"]))
    for i in range(6, 11):
        entities.append(_create_tsv_entity(f"Q{i}", ["P21", "P27", "P106", "P19"]))

    api = DummyActionApiClient()
    res = run_qlever_quality_audit(
        entities=entities,
        class_qid="Q5",
        top_n=3,
        frequency_threshold=0.5,
        api_client=api,
    )

    assert isinstance(res, QualityAuditResult)
    assert res.total_population_size == 10
    assert res.audited_count == 3
    # Top 3 lowest-quality (fewest statements) in TSV are Q1, Q2, Q3
    assert set(res.audited_qids) == {"Q1", "Q2", "Q3"}
    # Next candidate QIDs should be present for front-end batch loading
    assert len(res.next_candidate_qids) > 0
    assert "Q4" in res.next_candidate_qids
    assert "Q5" in res.next_candidate_qids


def test_quality_audit_empty_population():
    res = run_qlever_quality_audit(entities=[], class_qid="Q5", top_n=50)
    assert res.total_population_size == 0
    assert res.audited_count == 0
    assert len(res.coverage_report.findings) == 0


def test_quality_audit_scoring_and_report():
    entities = [
        _create_tsv_entity("Q101", ["P21"]),
        _create_tsv_entity("Q102", ["P21", "P27", "P106"]),
        _create_tsv_entity("Q103", ["P21", "P27", "P106"]),
        _create_tsv_entity("Q104", ["P21", "P27", "P106"]),
    ]

    mock_json = {
        "Q101": {
            "labels": {"en": {"value": "Lowest Quality Q101"}},
            "claims": {
                # Missing P27, P106
                "P31": [{"mainsnak": {"datavalue": {"value": {"id": "Q5"}}}}],
            },
        }
    }

    api = DummyActionApiClient(mock_json)
    res = run_qlever_quality_audit(
        entities=entities,
        class_qid="Q5",
        top_n=1,
        frequency_threshold=0.75,
        api_client=api,
    )

    assert res.audited_count == 1
    assert res.audited_qids == ["Q101"]
    report = res.coverage_report
    assert len(report.findings) > 0
    by_ent = report.by_entity()
    assert "Q101" in by_ent
    score_obj = by_ent["Q101"]
    assert score_obj.score > 0

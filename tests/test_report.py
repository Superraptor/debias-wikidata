from wikidata_coverage.core.finding import Finding, FindingKind, Severity
from wikidata_coverage.core.report import CoverageReport


def make_finding(
    entity_id, severity, kind=FindingKind.MISSING_STATEMENT, detector="d1", entity_label=None
):
    return Finding(
        entity_id=entity_id,
        entity_label=entity_label,
        kind=kind,
        detector=detector,
        message="test",
        severity=severity,
    )


def test_by_entity_groups_and_scores():
    report = CoverageReport()
    report.add(
        [
            make_finding("Q1", Severity.HIGH.value, entity_label="Entity One"),
            make_finding("Q1", Severity.LOW.value),
            make_finding("Q2", Severity.MEDIUM.value, entity_label="Entity Two"),
        ]
    )
    grouped = report.by_entity()
    assert set(grouped.keys()) == {"Q1", "Q2"}
    assert grouped["Q1"].score == round(Severity.HIGH.value + Severity.LOW.value, 3)
    assert grouped["Q1"].label == "Entity One"
    assert grouped["Q2"].score == Severity.MEDIUM.value
    assert grouped["Q2"].label == "Entity Two"


def test_summary_worst_entities_sorted_desc():
    report = CoverageReport()
    report.add(
        [
            make_finding("Q1", 0.1, entity_label="Item 1"),
            make_finding("Q2", 0.9, entity_label="Item 2"),
            make_finding("Q3", 0.5),
        ]
    )
    summary = report.summary()
    assert "scoring_criteria" in summary
    worst = summary["worst_entities"]
    ids_in_order = [row["entity_id"] for row in worst]
    assert ids_in_order == ["Q2", "Q3", "Q1"]
    assert worst[0]["entity_label"] == "Item 2"
    assert worst[1]["entity_label"] == "Q3"  # fallback to entity_id when label is missing


def test_worst_entities_method():
    report = CoverageReport()
    report.add(
        [
            make_finding("Q10", 0.8, entity_label="Alpha"),
            make_finding("Q20", 0.4, entity_label="Beta"),
        ]
    )
    worst = report.worst_entities(n=1)
    assert len(worst) == 1
    assert worst[0]["entity_id"] == "Q10"
    assert worst[0]["entity_label"] == "Alpha"


def test_to_json_roundtrip_contains_findings():
    report = CoverageReport()
    report.add([make_finding("Q1", 0.5)])
    text = report.to_json()
    assert "Q1" in text
    assert "missing_statement" in text
    assert "scoring_criteria" in text


def test_to_csv_has_header_and_row():
    report = CoverageReport()
    report.add([make_finding("Q1", 0.5)])
    csv_text = report.to_csv()
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("entity_id,kind,detector")
    assert "Q1" in lines[1]

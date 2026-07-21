from wikidata_coverage.core.finding import Finding, FindingKind, Severity
from wikidata_coverage.core.report import CoverageReport


def make_finding(entity_id, severity, kind=FindingKind.MISSING_STATEMENT, detector="d1"):
    return Finding(
        entity_id=entity_id,
        kind=kind,
        detector=detector,
        message="test",
        severity=severity,
    )


def test_by_entity_groups_and_scores():
    report = CoverageReport()
    report.add(
        [
            make_finding("Q1", Severity.HIGH.value),
            make_finding("Q1", Severity.LOW.value),
            make_finding("Q2", Severity.MEDIUM.value),
        ]
    )
    grouped = report.by_entity()
    assert set(grouped.keys()) == {"Q1", "Q2"}
    assert grouped["Q1"].score == round(Severity.HIGH.value + Severity.LOW.value, 3)
    assert grouped["Q2"].score == Severity.MEDIUM.value


def test_summary_worst_entities_sorted_desc():
    report = CoverageReport()
    report.add(
        [
            make_finding("Q1", 0.1),
            make_finding("Q2", 0.9),
            make_finding("Q3", 0.5),
        ]
    )
    summary = report.summary()
    ids_in_order = [row["entity_id"] for row in summary["worst_entities"]]
    assert ids_in_order == ["Q2", "Q3", "Q1"]


def test_to_json_roundtrip_contains_findings():
    report = CoverageReport()
    report.add([make_finding("Q1", 0.5)])
    text = report.to_json()
    assert "Q1" in text
    assert "missing_statement" in text


def test_to_csv_has_header_and_row():
    report = CoverageReport()
    report.add([make_finding("Q1", 0.5)])
    csv_text = report.to_csv()
    lines = csv_text.strip().splitlines()
    assert lines[0].startswith("entity_id,kind,detector")
    assert "Q1" in lines[1]

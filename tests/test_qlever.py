"""Unit tests for QLever ingestion and SPARQL result parsing."""

from pathlib import Path
import tempfile
import pytest

from wikidata_coverage.access.qlever import (
    parse_qlever_tsv,
    parse_qlever_csv,
    build_entities_from_qlever_rows,
    load_entities_from_qlever_file,
)
from wikidata_coverage.bias.sexual_orientation import SexualOrientationDetector
from wikidata_coverage.core.entity import Entity


def test_parse_qlever_tsv():
    tsv = """?item\t?itemLabel\t?gender\t?sexual_orientation
http://www.wikidata.org/entity/Q42\tDouglas Adams\thttp://www.wikidata.org/entity/Q6581097\t
http://www.wikidata.org/entity/Q62\tAlan Turing\thttp://www.wikidata.org/entity/Q6581097\thttp://www.wikidata.org/entity/Q6636
"""
    rows = parse_qlever_tsv(tsv)
    assert len(rows) == 2
    assert rows[0]["item"] == "http://www.wikidata.org/entity/Q42"
    assert rows[0]["itemLabel"] == "Douglas Adams"
    assert rows[1]["sexual_orientation"] == "http://www.wikidata.org/entity/Q6636"


def test_build_entities_from_qlever_rows():
    rows = [
        {
            "item": "http://www.wikidata.org/entity/Q42",
            "itemLabel": "Douglas Adams",
            "gender": "http://www.wikidata.org/entity/Q6581097",
            "citizenship": "http://www.wikidata.org/entity/Q145",
        },
        {
            "item": "http://www.wikidata.org/entity/Q62",
            "itemLabel": "Alan Turing",
            "gender": "http://www.wikidata.org/entity/Q6581097",
            "sexual_orientation": "http://www.wikidata.org/entity/Q6636",
        },
    ]
    entities = build_entities_from_qlever_rows(rows)
    assert len(entities) == 2

    ent_q42 = next(e for e in entities if e.id == "Q42")
    assert ent_q42.has_property("P21")
    assert ent_q42.has_property("P27")
    assert not ent_q42.has_property("P91")

    ent_q62 = next(e for e in entities if e.id == "Q62")
    assert ent_q62.has_property("P21")
    assert ent_q62.has_property("P91")


def test_load_entities_from_qlever_file():
    tsv_data = """?item\t?itemLabel\t?gender\t?sexual_orientation
http://www.wikidata.org/entity/Q100\tTest Person 1\thttp://www.wikidata.org/entity/Q6581072\t
http://www.wikidata.org/entity/Q200\tTest Person 2\thttp://www.wikidata.org/entity/Q6581097\thttp://www.wikidata.org/entity/Q1035954
"""
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False, encoding="utf-8") as f:
        f.write(tsv_data)
        temp_path = f.name

    try:
        entities = load_entities_from_qlever_file(temp_path)
        assert len(entities) == 2
        assert entities[0].id == "Q100"
        assert entities[1].id == "Q200"
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_sexual_orientation_assumed_heterosexual():
    rows = [
        {"item": "Q1", "gender": "Q6581097"},  # No P91
        {"item": "Q2", "gender": "Q6581072"},  # No P91
        {"item": "Q3", "gender": "Q6581097", "sexual_orientation": "Q6636"},  # Homosexual
    ]
    entities = build_entities_from_qlever_rows(rows)

    # Primary analysis: explicit P91 only
    det_explicit = SexualOrientationDetector(assume_heterosexual_if_missing=False)
    metrics_explicit = det_explicit.run(entities)
    # Only Q3 has P91, so population size = 1
    assert any(m.group_key == "homosexual" and m.group_size == 1 for m in metrics_explicit)

    # Secondary analysis: assume heterosexual for missing P91
    det_assumed = SexualOrientationDetector(assume_heterosexual_if_missing=True)
    metrics_assumed = det_assumed.run(entities)
    # Total population = 3 (Q1 heterosexual, Q2 heterosexual, Q3 homosexual)
    het_metric = next(m for m in metrics_assumed if m.group_key == "heterosexual")
    homo_metric = next(m for m in metrics_assumed if m.group_key == "homosexual")
    assert het_metric.group_size == 2
    assert homo_metric.group_size == 1
    assert het_metric.population_size == 3

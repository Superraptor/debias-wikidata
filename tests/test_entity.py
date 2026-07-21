from wikidata_coverage.core.entity import Entity


SAMPLE_ENTITY_JSON = {
    "labels": {"en": {"value": "Douglas Adams"}},
    "descriptions": {"en": {"value": "English author"}},
    "claims": {
        "P31": [
            {
                "mainsnak": {
                    "datatype": "wikibase-item",
                    "datavalue": {"value": {"id": "Q5"}},
                },
                "rank": "normal",
                "qualifiers": {},
                "references": [],
            }
        ],
        "P569": [
            {
                "mainsnak": {
                    "datatype": "time",
                    "datavalue": {"value": {"time": "+1952-03-11T00:00:00Z"}},
                },
                "rank": "normal",
                "qualifiers": {},
                "references": [{}],
            }
        ],
        "P21": [
            {
                "mainsnak": {
                    "datatype": "wikibase-item",
                    "datavalue": {"value": {"id": "Q6581097"}},
                },
                "rank": "deprecated",
                "qualifiers": {},
                "references": [],
            }
        ],
    },
}


def test_from_wbgetentities_json_parses_labels_and_claims():
    entity = Entity.from_wbgetentities_json("Q42", SAMPLE_ENTITY_JSON)
    assert entity.id == "Q42"
    assert entity.label() == "Douglas Adams"
    assert entity.has_property("P31")
    assert entity.has_property("P569")


def test_deprecated_claims_excluded_by_default():
    entity = Entity.from_wbgetentities_json("Q42", SAMPLE_ENTITY_JSON)
    assert not entity.has_property("P21")  # only a deprecated statement exists
    assert entity.has_property("P21", include_deprecated=True)


def test_instance_of_extracts_qids():
    entity = Entity.from_wbgetentities_json("Q42", SAMPLE_ENTITY_JSON)
    assert entity.instance_of() == ["Q5"]


def test_missing_property_returns_false():
    entity = Entity.from_wbgetentities_json("Q42", SAMPLE_ENTITY_JSON)
    assert not entity.has_property("P106")

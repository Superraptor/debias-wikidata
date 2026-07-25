from wikidata_coverage.core.entity import Entity
from wikidata_coverage.core.finding import FindingKind
from wikidata_coverage.detectors.constraints import (
    CONSTRAINT_TYPE_MANDATORY,
    ConstraintDetector,
)


class FakeApiClient:
    """Stands in for ActionApiClient; returns canned constraint JSON so
    tests never touch the network."""

    def __init__(self, constraint_json_by_property):
        self._data = constraint_json_by_property

    def get_property_constraints_raw(self, property_id):
        return self._data.get(property_id, {})


def _mandatory_constraint_json():
    return {
        "claims": {
            "P2302": [
                {
                    "mainsnak": {
                        "datavalue": {"value": {"id": CONSTRAINT_TYPE_MANDATORY}}
                    },
                    "qualifiers": {},
                }
            ]
        }
    }


def _entity_missing_property(qid="Q1"):
    return Entity.from_wbgetentities_json(
        qid,
        {
            "labels": {"en": {"value": "Test Item"}},
            "descriptions": {},
            "claims": {},
        },
    )


def _entity_with_property(qid="Q1", prop="P569"):
    return Entity.from_wbgetentities_json(
        qid,
        {
            "labels": {"en": {"value": "Test Item"}},
            "descriptions": {},
            "claims": {
                prop: [
                    {
                        "mainsnak": {
                            "datatype": "time",
                            "datavalue": {"value": {"time": "+2000-01-01T00:00:00Z"}},
                        },
                        "rank": "normal",
                        "qualifiers": {},
                        "references": [],
                    }
                ]
            },
        },
    )


def test_mandatory_constraint_flags_missing_property():
    fake_api = FakeApiClient({"P569": _mandatory_constraint_json()})
    detector = ConstraintDetector(properties_to_check=["P569"], api_client=fake_api)

    entity = _entity_missing_property()
    findings = detector.run([entity])

    assert len(findings) == 1
    assert findings[0].kind == FindingKind.MISSING_STATEMENT
    assert findings[0].property_id == "P569"
    assert findings[0].entity_id == "Q1"


def test_mandatory_constraint_satisfied_produces_no_finding():
    fake_api = FakeApiClient({"P569": _mandatory_constraint_json()})
    detector = ConstraintDetector(properties_to_check=["P569"], api_client=fake_api)

    entity = _entity_with_property()
    findings = detector.run([entity])

    assert findings == []


def test_no_constraints_defined_produces_no_findings():
    fake_api = FakeApiClient({})  # property has no constraints at all
    detector = ConstraintDetector(properties_to_check=["P999"], api_client=fake_api)

    entity = _entity_missing_property()
    findings = detector.run([entity])

    assert findings == []


def test_unspecified_properties_checks_all_entity_properties():
    fake_api = FakeApiClient({"P569": _mandatory_constraint_json()})
    detector = ConstraintDetector(properties_to_check=None, api_client=fake_api)

    entity = _entity_with_property(qid="Q1", prop="P569")
    findings = detector.run([entity])

    assert findings == []


def _fictional_entity_missing_property(qid="Q99"):
    return Entity.from_wbgetentities_json(
        qid,
        {
            "labels": {"en": {"value": "Snow White"}},
            "descriptions": {},
            "claims": {
                "P31": [
                    {
                        "mainsnak": {
                            "datatype": "wikibase-item",
                            "datavalue": {"value": {"id": "Q148837"}},
                        },
                        "rank": "normal",
                        "qualifiers": {},
                        "references": [],
                    }
                ]
            },
        },
    )


def test_fictional_entity_excluded_by_default():
    fake_api = FakeApiClient({"P569": _mandatory_constraint_json()})
    detector = ConstraintDetector(properties_to_check=["P569"], exclude_fictional=True, api_client=fake_api)

    fictional_entity = _fictional_entity_missing_property()
    findings = detector.run([fictional_entity])

    assert findings == []


def test_fictional_entity_included_when_requested():
    fake_api = FakeApiClient({"P569": _mandatory_constraint_json()})
    detector = ConstraintDetector(properties_to_check=["P569"], exclude_fictional=False, api_client=fake_api)

    fictional_entity = _fictional_entity_missing_property()
    findings = detector.run([fictional_entity])

    assert len(findings) == 1
    assert findings[0].kind == FindingKind.MISSING_STATEMENT
    assert findings[0].entity_id == "Q99"

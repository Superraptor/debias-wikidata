from unittest.mock import MagicMock

from wikidata_coverage.access.sparql import SparqlClient
from wikidata_coverage.bias.ethnicity import EthnicityBalanceDetector
from wikidata_coverage.bias.gender import GenderBalanceDetector
from wikidata_coverage.bias.geographic import GeographicDisparityDetector
from wikidata_coverage.bias.intersectionality import (
    IntersectionalityDetector,
    nationality_and_gender_detector,
)
from wikidata_coverage.bias.linguistic import LinguisticCoverageDetector
from wikidata_coverage.bias.metrics import DisparityMetric
from wikidata_coverage.bias.report import BiasReport
from wikidata_coverage.bias.rural_urban import RuralUrbanDetector
from wikidata_coverage.bias.sexual_orientation import SexualOrientationDetector
from wikidata_coverage.core.entity import Claim, Entity


def make_test_entity(
    qid: str,
    gender_qid: str | None = None,
    country_qid: str | None = None,
    p91_qid: str | None = None,
    p19_qid: str | None = None,
    ethnicity_qid: str | None = None,
    labels: dict | None = None,
    descriptions: dict | None = None,
    aliases: dict | None = None,
) -> Entity:
    claims = {}
    if gender_qid:
        claims["P21"] = [Claim(property_id="P21", value={"id": gender_qid})]
    if country_qid:
        claims["P27"] = [Claim(property_id="P27", value={"id": country_qid})]
    if p91_qid:
        claims["P91"] = [Claim(property_id="P91", value={"id": p91_qid})]
    if p19_qid:
        claims["P19"] = [Claim(property_id="P19", value={"id": p19_qid})]
    if ethnicity_qid:
        claims["P172"] = [Claim(property_id="P172", value={"id": ethnicity_qid})]

    return Entity(
        id=qid,
        labels=labels or {"en": "Test Entity"},
        descriptions=descriptions or {},
        aliases=aliases or {},
        claims=claims,
    )


def test_gender_balance_detector():
    entities = [
        make_test_entity("Q1", gender_qid="Q6581097"),  # male
        make_test_entity("Q2", gender_qid="Q6581097"),  # male
        make_test_entity("Q3", gender_qid="Q6581072"),  # female
    ]
    detector = GenderBalanceDetector()
    metrics = detector.run(entities)
    assert len(metrics) == 2
    report = BiasReport()
    report.add(metrics)
    assert report.summary()["total_metrics"] == 2


def test_sexual_orientation_detector():
    entities = [
        make_test_entity("Q1", p91_qid="Q1072"),  # heterosexual
        make_test_entity("Q2", p91_qid="Q6636"),  # homosexual
    ]
    detector = SexualOrientationDetector()
    metrics = detector.run(entities)
    assert len(metrics) == 2
    assert any(m.group_key == "Q6636" for m in metrics)


def test_linguistic_coverage_detector_with_mock_sparql():
    mock_sparql = MagicMock()
    mock_sparql.query.return_value = [
        {"langCode": "en", "maxSpeakers": 1000000000},
        {"langCode": "fr", "maxSpeakers": 300000000},
    ]

    entities = [
        make_test_entity("Q1", labels={"en": "Entity 1", "fr": "Entité 1"}),
        make_test_entity("Q2", labels={"en": "Entity 2"}),
    ]

    detector = LinguisticCoverageDetector(
        sparql=mock_sparql, top_n_languages=2, coverage_types=("label",)
    )
    metrics = detector.run(entities)
    assert len(metrics) >= 2
    en_metric = next(m for m in metrics if m.group_key == "en")
    assert en_metric.observed_value == 1.0
    fr_metric = next(m for m in metrics if m.group_key == "fr")
    assert fr_metric.observed_value == 0.5


def test_rural_urban_detector_with_mock_sparql():
    mock_sparql = MagicMock()
    # Mock return for urban_rural_world_shares and classify_places_by_type
    mock_sparql.query.side_effect = [
        # urban_rural_world_shares return
        [{"pop": 1000, "urbanPct": 60}],
        # classify_places_by_type return
        [
            {"place": "http://www.wikidata.org/entity/Q100", "placeType": "http://www.wikidata.org/entity/Q515"},  # city (urban)
            {"place": "http://www.wikidata.org/entity/Q200", "placeType": "http://www.wikidata.org/entity/Q532"},  # village (rural)
        ],
    ]

    entities = [
        make_test_entity("Q1", p19_qid="Q100"),
        make_test_entity("Q2", p19_qid="Q200"),
    ]

    detector = RuralUrbanDetector(sparql=mock_sparql)
    metrics = detector.run(entities)

    assert len(metrics) == 3  # urban, rural, unclassified
    urban_m = next(m for m in metrics if m.group_key == "urban")
    rural_m = next(m for m in metrics if m.group_key == "rural")
    assert urban_m.group_size == 1
    assert rural_m.group_size == 1


def test_ethnicity_balance_detector():
    entities = [
        make_test_entity("Q1", ethnicity_qid="Q539050"),
        make_test_entity("Q2", ethnicity_qid="Q40232"),
    ]
    detector = EthnicityBalanceDetector()
    metrics = detector.run(entities)
    assert len(metrics) == 2
    assert any(m.group_key == "Q539050" for m in metrics)


def test_intersectionality_detector():
    entities = [
        make_test_entity("Q1", country_qid="Q142", gender_qid="Q6581072"),  # France x Female
        make_test_entity("Q2", country_qid="Q142", gender_qid="Q6581097"),  # France x Male
    ]
    detector = nationality_and_gender_detector()
    metrics = detector.run(entities)
    assert len(metrics) == 2
    assert any(m.group_key == "Q142 x Q6581072" for m in metrics)
    assert any(m.group_key == "Q142 x Q6581097" for m in metrics)


def test_bias_report_resolve_labels():
    mock_api = MagicMock()
    mock_api.get_labels.return_value = {"Q110161171": "householder"}

    metric = DisparityMetric(
        axis="occupation_and_gender",
        detector="occupation_and_gender_detector",
        group_key="Q110161171 x Q6581097",
        group_label="Q110161171 × male",
        population_size=10,
        group_size=5,
        observed_value=0.5,
        expected_value=None,
        disparity_ratio=None,
        severity=0.1,
        message="test",
    )
    report = BiasReport()
    report.add([metric])
    report.resolve_labels(api_client=mock_api)

    assert report.metrics[0].group_label == "householder × male"


def test_sparql_client_property_filters():
    mock_query = MagicMock(return_value=[{"item": "http://www.wikidata.org/entity/Q10"}])

    client = SparqlClient()
    client.query = mock_query

    qids = client.qids_of_class("Q5", property_filters={"P27": "Q142", "P106": "Q169470"}, limit=10)
    assert qids == ["Q10"]
    query_str = mock_query.call_args[0][0]
    assert "?item wdt:P27 wd:Q142 ." in query_str
    assert "?item wdt:P106 wd:Q169470 ." in query_str

"""
wikidata_coverage.bias
======================

Bias-detection layer: group-level disparity metrics across gender, geographic,
demographic, linguistic, sexual orientation, rural/urban, ethnicity, and intersectional axes.

Unlike the entity-level ``Finding`` that coverage detectors emit, bias detectors
produce ``DisparityMetric`` objects -- one row per group -- which are aggregated
into a ``BiasReport``.

Public surface
--------------
* ``BiasReport``                -- aggregator, exporter (JSON / CSV / chart-ready)
* ``DisparityMetric``           -- single group-level metric (one per detector run)
* ``BiasDetector``              -- abstract base; subclass + implement ``run()``
* ``GroupShareDetector``        -- groups by a categorical property, compares shares
* ``GroupMeanDetector``         -- groups by a categorical property, compares means
* ``GenderBalanceDetector``     -- pre-wired to P21 (sex or gender)
* ``GeographicDisparityDetector`` -- pre-wired to P27 (country of citizenship)
* ``DemographicBalanceDetector``-- generic: point at any categorical PID
* ``LinguisticCoverageDetector``-- measures label/description/alias coverage vs. speaker share
* ``SexualOrientationDetector`` -- distribution of P91 (sexual orientation) values
* ``RuralUrbanDetector``        -- measures urban vs. rural birthplace representation
* ``EthnicityBalanceDetector``   -- representation of P172 (ethnic group) values
* ``IntersectionalityDetector`` -- joint representation across paired axes (e.g. nationality x gender)
* ``baselines``                 -- module providing Wikidata SPARQL-backed population baselines
"""

from wikidata_coverage.bias import baselines
from wikidata_coverage.bias.base import BiasDetector, GroupMeanDetector, GroupShareDetector
from wikidata_coverage.bias.demographic import DemographicBalanceDetector
from wikidata_coverage.bias.ethnicity import EthnicityBalanceDetector
from wikidata_coverage.bias.gender import GenderBalanceDetector
from wikidata_coverage.bias.geographic import GeographicDisparityDetector
from wikidata_coverage.bias.intersectionality import (
    IntersectionalityDetector,
    ethnicity_and_gender_detector,
    language_and_gender_detector,
    nationality_and_gender_detector,
    occupation_and_gender_detector,
)
from wikidata_coverage.bias.linguistic import LinguisticCoverageDetector
from wikidata_coverage.bias.metrics import DisparityMetric
from wikidata_coverage.bias.report import BiasReport
from wikidata_coverage.bias.rural_urban import RuralUrbanDetector
from wikidata_coverage.bias.sexual_orientation import SexualOrientationDetector

__all__ = [
    "BiasReport",
    "DisparityMetric",
    "BiasDetector",
    "GroupShareDetector",
    "GroupMeanDetector",
    "GenderBalanceDetector",
    "GeographicDisparityDetector",
    "DemographicBalanceDetector",
    "LinguisticCoverageDetector",
    "SexualOrientationDetector",
    "RuralUrbanDetector",
    "EthnicityBalanceDetector",
    "IntersectionalityDetector",
    "nationality_and_gender_detector",
    "language_and_gender_detector",
    "occupation_and_gender_detector",
    "ethnicity_and_gender_detector",
    "baselines",
]

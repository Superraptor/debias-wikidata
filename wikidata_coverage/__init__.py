"""
wikidata_coverage
==================

A general-purpose toolkit for detecting, assessing, and suggesting fixes
for data modeling and coverage gaps in Wikidata, including group-level
bias detection across gender, geographic, demographic, and linguistic axes.

Public API surface is intentionally small; most extension happens by
subclassing `Detector` in `wikidata_coverage.detectors.base` (entity-level)
or `BiasDetector` in `wikidata_coverage.bias.base` (group-level).
"""

from wikidata_coverage.bias.metrics import DisparityMetric
from wikidata_coverage.bias.report import BiasReport
from wikidata_coverage.core.entity import Entity
from wikidata_coverage.core.finding import Finding, FindingKind, Severity
from wikidata_coverage.core.report import CoverageReport

__all__ = [
    # Coverage (entity-level)
    "Entity",
    "Finding",
    "FindingKind",
    "Severity",
    "CoverageReport",
    # Bias (group-level)
    "BiasReport",
    "DisparityMetric",
]

__version__ = "0.1.0"

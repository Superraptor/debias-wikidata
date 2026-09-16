"""Detector modules for Wikidata coverage and quality auditing."""

from wikidata_coverage.detectors.base import Detector
from wikidata_coverage.detectors.class_profile import ClassProfileDetector
from wikidata_coverage.detectors.constraints import ConstraintDetector
from wikidata_coverage.detectors.quality_audit import QualityAuditResult, run_qlever_quality_audit

__all__ = [
    "Detector",
    "ClassProfileDetector",
    "ConstraintDetector",
    "QualityAuditResult",
    "run_qlever_quality_audit",
]

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
from wikidata_coverage.scoring.candidate_ranker import CandidateRanker, SourceReliabilityScorer
from wikidata_coverage.scoring.mbfc_cache import MBFCCache
from wikidata_coverage.suggest.candidate_finder import CandidateIndividual, CandidateSource, ExternalCandidateFinder
from wikidata_coverage.suggest.rag_generator import FlexibleLLMRAGGenerator, generate_quickstatements_for_candidate

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
    # Candidate Discovery & Source Ranking
    "CandidateIndividual",
    "CandidateSource",
    "ExternalCandidateFinder",
    "CandidateRanker",
    "SourceReliabilityScorer",
    "MBFCCache",
    "FlexibleLLMRAGGenerator",
    "generate_quickstatements_for_candidate",
]

__version__ = "0.1.0"


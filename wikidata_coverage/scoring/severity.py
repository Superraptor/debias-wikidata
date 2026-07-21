"""Scoring customization point.

Default scoring (sum of finding severities per entity) lives directly on
`EntityScore.score` in core/report.py since it's simple enough not to need
its own module. This file is where that gets replaced once real usage
shows the default isn't good enough -- e.g. normalizing by expected
property count, weighting by detector confidence, or exponential
penalties for entities with many findings vs. many entities with one each.

Left as a stub with a working default `ScoringStrategy` protocol so the
extension point exists without over-building it before it's needed.
"""

from __future__ import annotations

from typing import Callable, Protocol

from wikidata_coverage.core.finding import Finding


class ScoringStrategy(Protocol):
    def __call__(self, findings: list[Finding]) -> float: ...


def sum_of_severities(findings: list[Finding]) -> float:
    """Default strategy, matches EntityScore.score in core/report.py."""
    return round(sum(f.severity for f in findings), 3)


def mean_of_severities(findings: list[Finding]) -> float:
    """Alternative: doesn't penalize entities just for having many findings,
    only for how bad those findings are on average."""
    if not findings:
        return 0.0
    return round(sum(f.severity for f in findings) / len(findings), 3)


def max_severity(findings: list[Finding]) -> float:
    """Alternative: score driven entirely by the single worst finding."""
    return max((f.severity for f in findings), default=0.0)


DEFAULT_STRATEGY: ScoringStrategy = sum_of_severities

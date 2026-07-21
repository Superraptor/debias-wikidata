"""Aggregate group-level output for bias detectors.

Entity-level `Finding` ("this item is missing X") doesn't fit bias
detection well -- the interesting signal here is disparity *between
groups* (women vs. men, Global South vs. Global North, well- vs.
poorly-linked language editions), not a defect on any single item.
`DisparityMetric` is that unit: one row per group, describing its
observed share/mean of some measure against an expected baseline.

Both Finding-based and DisparityMetric-based detectors can coexist in the
same pipeline; they just report through different aggregators
(`CoverageReport` vs. `BiasReport`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DisparityMetric:
    axis: str                      # e.g. "gender", "country", "language_coverage"
    detector: str
    group_key: str                 # e.g. "Q6581072", "Q142" (France), "global_south"
    group_label: str               # human-readable, e.g. "female", "France"
    population_size: int           # size of the population this metric was computed over
    group_size: int                # number of entities in this group
    observed_value: float          # share (0-1) for GroupShareDetector, or mean for GroupMeanDetector
    expected_value: float | None   # baseline to compare against, if one was supplied
    disparity_ratio: float | None  # observed / expected, None if no baseline
    severity: float
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "axis": self.axis,
            "detector": self.detector,
            "group_key": self.group_key,
            "group_label": self.group_label,
            "population_size": self.population_size,
            "group_size": self.group_size,
            "observed_value": self.observed_value,
            "expected_value": self.expected_value,
            "disparity_ratio": self.disparity_ratio,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
        }

"""Two statistical patterns cover all four requested bias axes (gender,
demographic, geographic, linguistic):

1. GroupShareDetector -- "what fraction of the population falls into each
   group, and how does that compare to an expected baseline?"
   Fits gender balance, geographic distribution, and any other categorical
   demographic axis (ethnicity, occupation category, etc.).

2. GroupMeanDetector -- "does some continuous measure differ across
   groups?"
   Fits linguistic coverage: "do biographies of women have, on average,
   fewer language editions than biographies of men?"

Rather than reimplement grouping/comparison logic per axis, the four
concrete detectors (gender.py, demographic.py, geographic.py,
linguistic.py) are thin configurations of these two.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from typing import Callable, Iterable

from wikidata_coverage.bias.metrics import DisparityMetric
from wikidata_coverage.core.entity import Entity


class BiasDetector(ABC):
    """Bias-detector analog of Detector, but emits DisparityMetric (group-
    level) rather than Finding (entity-level)."""

    name: str = "base_bias_detector"
    axis: str = "unspecified"

    @abstractmethod
    def run(self, entities: Iterable[Entity]) -> list[DisparityMetric]:
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<BiasDetector name={self.name!r} axis={self.axis!r}>"


def disparity_severity(ratio: float | None) -> float:
    """Standard severity mapping for a disparity ratio (observed / expected).

    Symmetric: both severe under- and over-representation count.
    Returns a float in [0.0, 1.0].
    """
    if ratio is None:
        return 0.1
    deviation = abs(1 - ratio)
    if deviation >= 0.7:
        return 1.0
    if deviation >= 0.4:
        return 0.7
    if deviation >= 0.2:
        return 0.4
    return 0.15


class GroupShareDetector(BiasDetector):
    """Groups entities by `group_fn`, computes each group's share of the
    total population, and compares against an expected baseline (if one
    is supplied for that group).

    Entities for which `group_fn` returns None are excluded from the
    population entirely (e.g. items with no P21 statement don't count
    toward gender-balance denominators -- they're a coverage gap, not a
    zero for one gender).
    """

    def __init__(
        self,
        axis: str,
        name: str,
        group_fn: Callable[[Entity], str | None],
        group_label_fn: Callable[[str], str] | None = None,
        expected_shares: dict[str, float] | None = None,
        min_group_size: int = 1,
    ) -> None:
        """
        Args:
            axis: metric axis label, e.g. "gender", "geographic_citizenship".
            name: detector name for reporting.
            group_fn: entity -> group key, or None to exclude the entity.
            group_label_fn: group key -> human-readable label. Defaults to
                identity (the raw key).
            expected_shares: group key -> expected fraction of the
                population (0-1). Groups without an entry get
                expected_value=None (reported, but no disparity_ratio).
            min_group_size: groups smaller than this are still reported
                but flagged in evidence as low-confidence.
        """
        self.axis = axis
        self.name = name
        self.group_fn = group_fn
        self.group_label_fn = group_label_fn or (lambda k: k)
        self.expected_shares = expected_shares or {}
        self.min_group_size = min_group_size

    def run(self, entities: Iterable[Entity]) -> list[DisparityMetric]:
        groups: dict[str, list[Entity]] = defaultdict(list)
        for e in entities:
            key = self.group_fn(e)
            if key is not None:
                groups[key].append(e)

        population_size = sum(len(v) for v in groups.values())
        if population_size == 0:
            return []

        metrics: list[DisparityMetric] = []
        for key, members in groups.items():
            observed_share = len(members) / population_size
            expected = self.expected_shares.get(key)
            ratio = (observed_share / expected) if expected else None

            metrics.append(
                DisparityMetric(
                    axis=self.axis,
                    detector=self.name,
                    group_key=key,
                    group_label=self.group_label_fn(key),
                    population_size=population_size,
                    group_size=len(members),
                    observed_value=round(observed_share, 4),
                    expected_value=expected,
                    disparity_ratio=round(ratio, 4) if ratio is not None else None,
                    severity=self._severity_for_ratio(ratio),
                    message=self._message(key, observed_share, expected, len(members)),
                    evidence={"low_confidence": len(members) < self.min_group_size},
                )
            )

        return metrics

    def _message(self, key: str, observed: float, expected: float | None, n: int) -> str:
        label = self.group_label_fn(key)
        if expected is None:
            return f"{label}: {observed:.1%} of population ({n} entities), no baseline set."
        direction = "under" if observed < expected else "over"
        return (
            f"{label}: {observed:.1%} of population ({n} entities) vs. "
            f"{expected:.1%} expected -- {direction}represented."
        )

    @staticmethod
    def _severity_for_ratio(ratio: float | None) -> float:
        """Delegates to module-level disparity_severity() for external use."""
        return disparity_severity(ratio)


class GroupMeanDetector(BiasDetector):
    """Groups entities by `group_fn`, computes the mean of `measure_fn`
    within each group, and compares each group's mean against the overall
    population mean (not an external baseline -- the comparison point here
    is "how do groups compare to each other," which is the right frame for
    something like language-edition counts where there's no independent
    ground truth to check against).
    """

    def __init__(
        self,
        axis: str,
        name: str,
        group_fn: Callable[[Entity], str | None],
        measure_fn: Callable[[Entity], float],
        group_label_fn: Callable[[str], str] | None = None,
        min_group_size: int = 5,
    ) -> None:
        self.axis = axis
        self.name = name
        self.group_fn = group_fn
        self.measure_fn = measure_fn
        self.group_label_fn = group_label_fn or (lambda k: k)
        self.min_group_size = min_group_size

    def run(self, entities: Iterable[Entity]) -> list[DisparityMetric]:
        groups: dict[str, list[Entity]] = defaultdict(list)
        all_entities: list[Entity] = []
        for e in entities:
            all_entities.append(e)
            key = self.group_fn(e)
            if key is not None:
                groups[key].append(e)

        if not all_entities:
            return []

        overall_mean = sum(self.measure_fn(e) for e in all_entities) / len(all_entities)
        population_size = len(all_entities)

        metrics: list[DisparityMetric] = []
        for key, members in groups.items():
            group_mean = sum(self.measure_fn(e) for e in members) / len(members)
            ratio = (group_mean / overall_mean) if overall_mean else None

            metrics.append(
                DisparityMetric(
                    axis=self.axis,
                    detector=self.name,
                    group_key=key,
                    group_label=self.group_label_fn(key),
                    population_size=population_size,
                    group_size=len(members),
                    observed_value=round(group_mean, 4),
                    expected_value=round(overall_mean, 4),
                    disparity_ratio=round(ratio, 4) if ratio is not None else None,
                    severity=GroupShareDetector._severity_for_ratio(ratio),
                    message=(
                        f"{self.group_label_fn(key)}: mean {group_mean:.2f} vs. "
                        f"population mean {overall_mean:.2f} ({len(members)} entities)."
                    ),
                    evidence={"low_confidence": len(members) < self.min_group_size},
                )
            )

        return metrics

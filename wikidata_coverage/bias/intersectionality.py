"""Intersectional bias detection: evaluates representation disparities across paired axes.

Examples:
- Nationality (P27) x Gender (P21): e.g., "France (Q142) x female (Q6581072)"
- Language Spoken (P1412) x Gender (P21): e.g., "English (Q1860) x female (Q6581072)"
- Occupation (P106) x Gender (P21): e.g., "physicist (Q169470) x female (Q6581072)"
- Ethnicity (P172) x Gender (P21): e.g., "Han Chinese (Q40232) x female (Q6581072)"

Baseline Calculation
--------------------
When marginal baselines are available for Axis A (e.g. Country population shares)
and Axis B (e.g. Gender ratio 50/50), the expected joint baseline can be estimated
assuming independence:

    P(A and B) = P(A) * P(B)

Explicit joint baselines can also be passed, or the detector can operate in exploratory mode.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Iterable

from wikidata_coverage.bias import baselines as _baselines
from wikidata_coverage.bias.base import BiasDetector, disparity_severity
from wikidata_coverage.bias.gender import GENDER_LABELS, gender_of
from wikidata_coverage.bias.geographic import COUNTRY_LABELS
from wikidata_coverage.bias.metrics import DisparityMetric
from wikidata_coverage.core.entity import Entity

if TYPE_CHECKING:
    from wikidata_coverage.access.sparql import SparqlClient

logger = logging.getLogger(__name__)


def _extract_single_qid(entity: Entity, property_id: str) -> str | None:
    values = entity.values_for(property_id)
    if not values:
        return None
    v = values[0]
    return v.get("id") if isinstance(v, dict) else None


class IntersectionalityDetector(BiasDetector):
    """Measures representation across joint categories (Axis A x Axis B)."""

    def __init__(
        self,
        axis: str,
        name: str,
        extract_a: Callable[[Entity], str | None],
        extract_b: Callable[[Entity], str | None],
        label_a: Callable[[str], str] | None = None,
        label_b: Callable[[str], str] | None = None,
        expected_shares_a: dict[str, float] | None = None,
        expected_shares_b: dict[str, float] | None = None,
        expected_joint_shares: dict[str, float] | None = None,
        min_group_size: int = 1,
    ) -> None:
        """
        Args:
            axis: axis identifier, e.g. "nationality_and_gender".
            name: detector name for reporting.
            extract_a: entity -> group key A (or None).
            extract_b: entity -> group key B (or None).
            label_a: key A -> human-readable label.
            label_b: key B -> human-readable label.
            expected_shares_a: marginal population share for axis A.
            expected_shares_b: marginal population share for axis B.
            expected_joint_shares: explicit joint expected share override dict
                keyed by "keyA x keyB". If provided, overrides multiplicative estimation.
            min_group_size: groups smaller than this are flagged low-confidence.
        """
        self.axis = axis
        self.name = name
        self.extract_a = extract_a
        self.extract_b = extract_b
        self.label_a = label_a or (lambda k: k)
        self.label_b = label_b or (lambda k: k)
        self.min_group_size = min_group_size

        if expected_joint_shares is not None:
            self.expected_joint_shares = expected_joint_shares
        elif expected_shares_a and expected_shares_b:
            # Estimate via independence: P(A and B) = P(A) * P(B)
            joint: dict[str, float] = {}
            for ka, pa in expected_shares_a.items():
                for kb, pb in expected_shares_b.items():
                    joint[f"{ka} x {kb}"] = round(pa * pb, 6)
            self.expected_joint_shares = joint
        else:
            self.expected_joint_shares = {}

    def run(self, entities: Iterable[Entity]) -> list[DisparityMetric]:
        entity_list = list(entities)
        if not entity_list:
            return []

        groups: dict[str, list[Entity]] = {}
        for e in entity_list:
            ka = self.extract_a(e)
            kb = self.extract_b(e)
            if ka is not None and kb is not None:
                joint_key = f"{ka} x {kb}"
                groups.setdefault(joint_key, []).append(e)

        population_size = sum(len(v) for v in groups.values())
        if population_size == 0:
            return []

        metrics: list[DisparityMetric] = []
        for joint_key, members in groups.items():
            ka, kb = joint_key.split(" x ", 1)
            label = f"{self.label_a(ka)} × {self.label_b(kb)}"
            observed_share = len(members) / population_size
            expected = self.expected_joint_shares.get(joint_key)
            ratio = (observed_share / expected) if expected else None

            metrics.append(
                DisparityMetric(
                    axis=self.axis,
                    detector=self.name,
                    group_key=joint_key,
                    group_label=label,
                    population_size=population_size,
                    group_size=len(members),
                    observed_value=round(observed_share, 4),
                    expected_value=expected,
                    disparity_ratio=round(ratio, 4) if ratio is not None else None,
                    severity=disparity_severity(ratio),
                    message=self._message(label, observed_share, expected, len(members)),
                    evidence={"low_confidence": len(members) < self.min_group_size},
                )
            )

        return metrics

    @staticmethod
    def _message(label: str, observed: float, expected: float | None, n: int) -> str:
        if expected is None:
            return f"{label}: {observed:.1%} of sub-population ({n} entities), no joint baseline set."
        direction = "under" if observed < expected else "over"
        return (
            f"{label}: {observed:.1%} of sub-population ({n} entities) vs. "
            f"{expected:.1%} expected — {direction}represented."
        )


# ---------------------------------------------------------------------------
# Pre-configured intersectional detectors
# ---------------------------------------------------------------------------

def nationality_and_gender_detector(
    sparql: "SparqlClient | None" = None,
    min_group_size: int = 1,
) -> IntersectionalityDetector:
    """Preconfigured detector for Citizenship (P27) x Gender (P21)."""
    if sparql is not None:
        country_shares = _baselines.country_population_shares(sparql)
        gender_shares = _baselines.gender_population_shares(sparql)
    else:
        country_shares = None
        gender_shares = {"Q6581072": 0.5, "Q6581097": 0.5}

    return IntersectionalityDetector(
        axis="nationality_and_gender",
        name="nationality_and_gender_detector",
        extract_a=lambda e: _extract_single_qid(e, "P27"),
        extract_b=gender_of,
        label_a=lambda qid: COUNTRY_LABELS.get(qid, qid),
        label_b=lambda qid: GENDER_LABELS.get(qid, qid),
        expected_shares_a=country_shares,
        expected_shares_b=gender_shares,
        min_group_size=min_group_size,
    )


def language_and_gender_detector(
    sparql: "SparqlClient | None" = None,
    min_group_size: int = 1,
) -> IntersectionalityDetector:
    """Preconfigured detector for Spoken Language (P1412) x Gender (P21)."""
    if sparql is not None:
        lang_shares = _baselines.language_speaker_shares(sparql)
        gender_shares = _baselines.gender_population_shares(sparql)
    else:
        lang_shares = None
        gender_shares = {"Q6581072": 0.5, "Q6581097": 0.5}

    return IntersectionalityDetector(
        axis="language_and_gender",
        name="language_and_gender_detector",
        extract_a=lambda e: _extract_single_qid(e, "P1412"),
        extract_b=gender_of,
        label_a=lambda qid: qid,
        label_b=lambda qid: GENDER_LABELS.get(qid, qid),
        expected_shares_a=lang_shares,
        expected_shares_b=gender_shares,
        min_group_size=min_group_size,
    )


def occupation_and_gender_detector(
    min_group_size: int = 1,
) -> IntersectionalityDetector:
    """Preconfigured detector for Occupation (P106) x Gender (P21). Exploratory baseline."""
    return IntersectionalityDetector(
        axis="occupation_and_gender",
        name="occupation_and_gender_detector",
        extract_a=lambda e: _extract_single_qid(e, "P106"),
        extract_b=gender_of,
        label_a=lambda qid: qid,
        label_b=lambda qid: GENDER_LABELS.get(qid, qid),
        min_group_size=min_group_size,
    )


def ethnicity_and_gender_detector(
    min_group_size: int = 1,
) -> IntersectionalityDetector:
    """Preconfigured detector for Ethnic Group (P172) x Gender (P21). Exploratory baseline."""
    from wikidata_coverage.bias.ethnicity import ETHNICITY_LABELS
    return IntersectionalityDetector(
        axis="ethnicity_and_gender",
        name="ethnicity_and_gender_detector",
        extract_a=lambda e: _extract_single_qid(e, "P172"),
        extract_b=gender_of,
        label_a=lambda qid: ETHNICITY_LABELS.get(qid, qid),
        label_b=lambda qid: GENDER_LABELS.get(qid, qid),
        min_group_size=min_group_size,
    )

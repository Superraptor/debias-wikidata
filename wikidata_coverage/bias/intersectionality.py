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

from collections import defaultdict
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
        self.expected_shares_a = expected_shares_a
        self.expected_shares_b = expected_shares_b
        self.min_group_size = min_group_size

        if expected_joint_shares is not None:
            self.expected_joint_shares = expected_joint_shares
        elif expected_shares_a and expected_shares_b:
            shares_a = expected_shares_a[0] if isinstance(expected_shares_a, tuple) else expected_shares_a
            shares_b = expected_shares_b[0] if isinstance(expected_shares_b, tuple) else expected_shares_b
            # Estimate via independence: P(A and B) = P(A) * P(B)
            joint: dict[str, float] = {}
            for ka, pa in shares_a.items():
                for kb, pb in shares_b.items():
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

        dynamic_expected: dict[str, float] = dict(self.expected_joint_shares)
        calculation_explanations: dict[str, str] = {}

        # 1. Handle nationality_and_sexual_orientation dynamically with country-specific Ipsos survey statistics
        if getattr(self, "_is_nationality_sexual_orientation", False):
            shares_a = self.expected_shares_a[0] if isinstance(self.expected_shares_a, tuple) else (self.expected_shares_a or {})
            count_a: dict[str, int] = defaultdict(int)
            for joint_key, members in groups.items():
                c_qid, _ = joint_key.split(" x ", 1)
                count_a[c_qid] += len(members)

            for joint_key in groups:
                c_qid, cat = joint_key.split(" x ", 1)
                pa = shares_a.get(c_qid, count_a[c_qid] / population_size)
                ipsos_map = _baselines.ipsos_sexual_orientation_shares(country_qid=c_qid, by_qid=False)
                pb = ipsos_map.get(cat)
                if pb:
                    dynamic_expected[joint_key] = round(pa * pb, 6)
                    is_cs = c_qid in _baselines.IPSOS_COUNTRY_SEXUAL_ORIENTATION_SHARES
                    country_name = COUNTRY_LABELS.get(c_qid, c_qid)
                    if is_cs:
                        calculation_explanations[joint_key] = (
                            f"Calculated via P(Country) × P(Sexual Orientation | Country) using country-specific Ipsos survey statistics for {country_name} ({c_qid})."
                        )
                    else:
                        calculation_explanations[joint_key] = (
                            f"Calculated via P(Country) × P(Sexual Orientation) using Ipsos 30-country global LGBT+ survey baseline."
                        )

        # 2. Handle generic expected_shares_b (e.g. gender or sexual_orientation)
        elif self.expected_shares_b or self.expected_shares_a:
            shares_a = self.expected_shares_a[0] if isinstance(self.expected_shares_a, tuple) else (self.expected_shares_a or {})
            shares_b = self.expected_shares_b[0] if isinstance(self.expected_shares_b, tuple) else (self.expected_shares_b or {})
            count_a: dict[str, int] = defaultdict(int)
            for joint_key, members in groups.items():
                ka, _ = joint_key.split(" x ", 1)
                count_a[ka] += len(members)

            for joint_key in groups:
                ka, kb = joint_key.split(" x ", 1)
                if joint_key not in dynamic_expected and shares_b:
                    pb = shares_b.get(kb)
                    if pb:
                        if ka in shares_a:
                            pa = shares_a[ka]
                            dynamic_expected[joint_key] = round(pa * pb, 6)
                            calculation_explanations[joint_key] = f"Calculated via P({self.axis.split('_and_')[0]}) × P({self.axis.split('_and_')[1]}) population baselines."
                        else:
                            pa = count_a[ka] / population_size
                            dynamic_expected[joint_key] = round(pa * pb, 6)
                            calculation_explanations[joint_key] = (
                                f"Calculated via P(Sample Frequency of {self.axis.split('_and_')[0]}) × P({self.axis.split('_and_')[1]}) baseline "
                                f"(no external baseline table for {self.label_a(ka)})."
                            )
                elif joint_key in dynamic_expected and joint_key not in calculation_explanations:
                    calculation_explanations[joint_key] = f"Calculated via P({self.axis.split('_and_')[0]}) × P({self.axis.split('_and_')[1]}) population baselines."

        metrics: list[DisparityMetric] = []
        for joint_key, members in groups.items():
            ka, kb = joint_key.split(" x ", 1)
            label = f"{self.label_a(ka)} × {self.label_b(kb)}"
            observed_share = len(members) / population_size
            expected = dynamic_expected.get(joint_key)
            ratio = (observed_share / expected) if expected else None

            ev: dict[str, Any] = {"low_confidence": len(members) < self.min_group_size}
            expl = calculation_explanations.get(joint_key)
            if expl:
                ev["calculation_explanation"] = expl
                ev["baseline_note"] = expl

            msg = self._message(label, observed_share, expected, len(members))
            if expl and expected is not None:
                msg += f" [{expl}]"

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
                    message=msg,
                    evidence=ev,
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
        lang_shares, lang_names = _baselines.language_speaker_shares_by_qid(sparql)
        gender_shares = _baselines.gender_population_shares(sparql)
    else:
        lang_shares = None
        lang_names = {}
        gender_shares = {"Q6581072": 0.5, "Q6581097": 0.5}

    return IntersectionalityDetector(
        axis="language_and_gender",
        name="language_and_gender_detector",
        extract_a=lambda e: _extract_single_qid(e, "P1412"),
        extract_b=gender_of,
        label_a=lambda qid: lang_names.get(qid, qid),
        label_b=lambda qid: GENDER_LABELS.get(qid, qid),
        expected_shares_a=lang_shares,
        expected_shares_b=gender_shares,
        min_group_size=min_group_size,
    )


def occupation_and_gender_detector(
    sparql: "SparqlClient | None" = None,
    min_group_size: int = 1,
) -> IntersectionalityDetector:
    """Preconfigured detector for Occupation (P106) x Gender (P21).

    Uses sample occupation frequency combined with population gender baselines
    (P1539/P1540 or 50/50 split) for expected values, as no global population baseline exists for occupations.
    """
    if sparql is not None:
        gender_shares = _baselines.gender_population_shares(sparql)
    else:
        gender_shares = {"Q6581072": 0.5, "Q6581097": 0.5}

    return IntersectionalityDetector(
        axis="occupation_and_gender",
        name="occupation_and_gender_detector",
        extract_a=lambda e: _extract_single_qid(e, "P106"),
        extract_b=gender_of,
        label_a=lambda qid: qid,
        label_b=lambda qid: GENDER_LABELS.get(qid, qid),
        expected_shares_b=gender_shares,
        min_group_size=min_group_size,
    )


def ethnicity_and_gender_detector(
    sparql: "SparqlClient | None" = None,
    min_group_size: int = 1,
) -> IntersectionalityDetector:
    """Preconfigured detector for Ethnic Group (P172) x Gender (P21)."""
    from wikidata_coverage.bias.ethnicity import ETHNICITY_LABELS, format_ethnicity_label

    if sparql is not None:
        ethnicity_shares = _baselines.ethnicity_expected_shares_timeline(sparql)
        gender_shares = _baselines.gender_population_shares(sparql)
    else:
        ethnicity_shares = None
        gender_shares = {"Q6581072": 0.5, "Q6581097": 0.5}

    return IntersectionalityDetector(
        axis="ethnicity_and_gender",
        name="ethnicity_and_gender_detector",
        extract_a=lambda e: _extract_single_qid(e, "P172"),
        extract_b=gender_of,
        label_a=lambda qid: format_ethnicity_label(qid, ETHNICITY_LABELS),
        label_b=lambda qid: GENDER_LABELS.get(qid, qid),
        expected_shares_a=ethnicity_shares,
        expected_shares_b=gender_shares,
        min_group_size=min_group_size,
    )


def nationality_and_sexual_orientation_detector(
    sparql: "SparqlClient | None" = None,
    min_group_size: int = 1,
    assume_heterosexual_if_missing: bool = False,
) -> IntersectionalityDetector:
    """Preconfigured detector for Country of Citizenship (P27) x Sexual Orientation (P91)
    using Ipsos country-specific survey statistics for surveyed countries, and global Ipsos stats for others."""
    from wikidata_coverage.bias.sexual_orientation import _orientation_category_of

    if sparql is not None:
        country_shares = _baselines.country_population_shares(sparql)
    else:
        country_shares = None

    detector = IntersectionalityDetector(
        axis="nationality_and_sexual_orientation",
        name="nationality_and_sexual_orientation_detector",
        extract_a=lambda e: _extract_single_qid(e, "P27"),
        extract_b=lambda e: _orientation_category_of(e, assume_heterosexual_if_missing=assume_heterosexual_if_missing),
        label_a=lambda qid: COUNTRY_LABELS.get(qid, qid),
        label_b=lambda k: k,
        expected_shares_a=country_shares,
        min_group_size=min_group_size,
    )
    detector._is_nationality_sexual_orientation = True
    return detector


def sexual_orientation_and_gender_detector(
    sparql: "SparqlClient | None" = None,
    min_group_size: int = 1,
    assume_heterosexual_if_missing: bool = False,
) -> IntersectionalityDetector:
    """Preconfigured detector for Sexual Orientation (P91) x Gender (P21)."""
    from wikidata_coverage.bias.sexual_orientation import _orientation_category_of

    global_orientation = _baselines.ipsos_sexual_orientation_shares(by_qid=False)
    if sparql is not None:
        gender_shares = _baselines.gender_population_shares(sparql)
    else:
        gender_shares = {"Q6581072": 0.5, "Q6581097": 0.5}

    return IntersectionalityDetector(
        axis="sexual_orientation_and_gender",
        name="sexual_orientation_and_gender_detector",
        extract_a=lambda e: _orientation_category_of(e, assume_heterosexual_if_missing=assume_heterosexual_if_missing),
        extract_b=gender_of,
        label_a=lambda k: k,
        label_b=lambda qid: GENDER_LABELS.get(qid, qid),
        expected_shares_a=global_orientation,
        expected_shares_b=gender_shares,
        min_group_size=min_group_size,
    )


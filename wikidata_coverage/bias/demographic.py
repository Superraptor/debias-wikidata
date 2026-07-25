"""Generic demographic-axis detector: same statistical machinery as
GenderBalanceDetector, but parametrized over an arbitrary categorical
property rather than hardcoded to P21.

Use this for demographic axes beyond gender -- e.g. P27 (country of
citizenship) as a nationality-balance check independent of the geographic
detector's population-weighted framing, P106 (occupation) balance within
a specific class, age-bracket balance derived from P569, etc.

A note on scope: some demographic axes (e.g. P172 "ethnic group") are
sensitive both because Wikidata's coverage of them is inconsistent/
contested and because the category itself may reflect self-identification
that doesn't map cleanly onto population statistics. This detector will
run against any property you point it at, but the "expected baseline" for
sensitive axes deserves real thought (ideally sourced from the relevant
domain literature) rather than a default -- there's deliberately no
built-in baseline table for these axes the way there is for gender/
geography, and expected_shares is required rather than optional here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from wikidata_coverage.bias import baselines as _baselines
from wikidata_coverage.bias.base import GroupShareDetector
from wikidata_coverage.core.entity import Entity

if TYPE_CHECKING:
    from wikidata_coverage.access.sparql import SparqlClient


PROPERTY_AXIS_NAMES: dict[str, str] = {
    "P27": "nationality (P27)",
    "P172": "ethnicity (P172)",
    "P106": "occupation (P106)",
    "P19": "place_of_birth (P19)",
    "P20": "place_of_death (P20)",
    "P140": "religion (P140)",
    "P91": "sexual_orientation (P91)",
    "P569": "birth_year (P569)",
}


class DemographicBalanceDetector(GroupShareDetector):
    """Balance check for any single-value categorical property."""

    def __init__(
        self,
        property_id: str,
        expected_shares: dict[str, float] | None = None,
        sparql: "SparqlClient" | None = None,
        axis: str | None = None,
        group_label_fn: Callable[[str], str] | None = None,
        min_group_size: int = 1,
        take_first_value: bool = True,
    ) -> None:
        """
        Args:
            property_id: the PID to group by, e.g. "P106" (occupation), "P27" (nationality), "P172" (ethnicity).
            expected_shares: group key -> expected population fraction. Defaults to time-aware Earth-benchmarked baselines for P27 and P172.
            sparql: optional SPARQL client to fetch live time-aware baselines and sovereign state filters.
            axis: metric axis label; defaults to descriptive label (e.g. nationality (P27)) or property id.
            take_first_value: if an entity has multiple values for
                property_id, use only the first (avoids double-counting
                entities across groups, which would break share math).
        """
        sovereign_set: set[str] | None = None
        if property_id == "P27" and sparql is not None:
            sovereign_set = _baselines.sovereign_country_qids(sparql)

        if not expected_shares and sparql is not None:
            if property_id == "P27":
                expected_shares = _baselines.country_expected_shares_timeline(sparql)
            elif property_id == "P172":
                expected_shares = _baselines.ethnicity_expected_shares_timeline(sparql)

        def group_fn(entity: Entity) -> str | None:
            values = entity.values_for(property_id)
            if not values:
                return None
            v = values[0] if take_first_value else values
            qid = None
            if isinstance(v, dict) and "id" in v:
                qid = v["id"]
            elif isinstance(v, str) and v.startswith("Q"):
                qid = v

            if qid and property_id == "P27" and sovereign_set is not None:
                if qid not in sovereign_set:
                    return None
            return qid

        default_axis = PROPERTY_AXIS_NAMES.get(property_id, property_id)
        if group_label_fn is None and property_id == "P172":
            from wikidata_coverage.bias.ethnicity import ETHNICITY_LABELS, format_ethnicity_label
            group_label_fn = lambda qid: format_ethnicity_label(qid, ETHNICITY_LABELS)

        super().__init__(
            axis=axis or default_axis,
            name=f"demographic_balance_detector[{property_id}]",
            group_fn=group_fn,
            group_label_fn=group_label_fn,
            expected_shares=expected_shares or {},
            min_group_size=min_group_size,
        )

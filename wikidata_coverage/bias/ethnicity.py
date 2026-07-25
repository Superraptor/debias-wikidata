"""Ethnic group balance: representation across recorded P172 (ethnic group) values.

IMPORTANT — what this detector measures and what it doesn't
-----------------------------------------------------------
It measures the **distribution of recorded ethnic group values** among Wikidata entities
that *have* P172 stated. It does **not**:

* Flag any entity for *missing* P172. Ethnicity is a sensitive attribute;
  Wikidata coverage of P172 is sparse and unevenly populated across sub-populations.
* Provide a single hardcoded default baseline. Population-level ethnic demographics
  vary heavily depending on regional/national context and scope.

What it *does* do
-----------------
Surfaces the distribution of recorded P172 values within a sample so that:
* Over- or under-representation of specific ethnic groups among entities that
  *do* have P172 recorded can be examined.
* Researchers can pass explicit ``expected_shares`` tailored to their specific domain or cohort.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from wikidata_coverage.bias import baselines as _baselines
from wikidata_coverage.bias.base import GroupShareDetector
from wikidata_coverage.bias.metrics import DisparityMetric
from wikidata_coverage.core.entity import Entity

if TYPE_CHECKING:
    from wikidata_coverage.access.sparql import SparqlClient

# Common P172 (ethnic group) values and human-readable labels.
# Unrecognized QIDs fall back to showing the raw QID.
ETHNICITY_LABELS: dict[str, str] = {
    "Q539050": "African Americans",
    "Q49085": "African Americans",
    "Q40232": "Han Chinese",
    "Q49078": "Afro-Germans",
    "Q134552": "Bengalis",
    "Q614911": "African descent",
    "Q79800": "Tamils",
    "Q42406": "English people",
    "Q35323": "Arabs",
    "Q7325": "Jewish people",
    "Q34069": "Ashkenazi Jews",
    "Q177520": "Ashkenazi Jews",
    "Q1025585": "Sephardi Jews",
    "Q49077": "Black people",
    "Q200615": "White people",
    "Q600465": "Romani people",
    "Q539051": "Greeks",
    "Q42884": "Germans",
    "Q49542": "Russians",
    "Q1026": "Poles",
    "Q50001": "Italians",
    "Q200569": "Dutch",
    "Q79797": "Armenians",
}


def _ethnicity_of(entity: Entity) -> str | None:
    values = entity.values_for("P172")
    if not values:
        return None
    v = values[0]
    return v.get("id") if isinstance(v, dict) else None


def format_ethnicity_label(qid: str, custom_labels: dict[str, str] | None = None) -> str:
    labels = {**ETHNICITY_LABELS, **(custom_labels or {})}
    label = labels.get(qid)
    if label and label != qid:
        return f"{label} ({qid})"
    return qid


class EthnicityBalanceDetector(GroupShareDetector):
    """Preconfigured GroupShareDetector for P172 (ethnic group).

    Fetches population (P1082) and point in time (P585) values from Wikidata when sparql is supplied,
    benchmarking each ethnic group's population against Earth's / world population timeline.
    """

    def __init__(
        self,
        expected_shares: dict[str, float] | None = None,
        sparql: "SparqlClient | None" = None,
        label_overrides: dict[str, str] | None = None,
        min_group_size: int = 1,
    ) -> None:
        """
        Args:
            expected_shares: optional population share dict, keyed by P172 QID.
            sparql: optional SPARQL client to fetch live time-aware P1082 population baselines.
            label_overrides: custom ``{qid: label}`` mapping.
            min_group_size: groups smaller than this are flagged as low-confidence.
        """
        self.sparql = sparql
        labels = {**ETHNICITY_LABELS, **(label_overrides or {})}
        super().__init__(
            axis="ethnicity",
            name="ethnicity_balance_detector",
            group_fn=_ethnicity_of,
            group_label_fn=lambda qid: format_ethnicity_label(qid, labels),
            expected_shares=expected_shares or {},
            min_group_size=min_group_size,
        )

    def run(self, entities: Iterable[Entity]) -> list[DisparityMetric]:
        entity_list = list(entities)
        if self.sparql is not None:
            # Collect unique ethnicity QIDs from entities
            ethnicity_qids = set()
            for e in entity_list:
                qid = _ethnicity_of(e)
                if qid:
                    ethnicity_qids.add(qid)
            if ethnicity_qids:
                live_shares = _baselines.ethnicity_expected_shares_timeline(
                    self.sparql, ethnicity_qids=list(ethnicity_qids)
                )
                self.expected_shares.update(live_shares)

        metrics = super().run(entity_list)
        source = "Wikidata SPARQL P1082/P585 (Ethnic Group Population & Point in Time)" if self.sparql else "Exploratory / Custom Baseline"
        b_type = "time-aware Earth population benchmark" if self.sparql else "user-supplied"
        for m in metrics:
            m.evidence["source"] = source
            m.evidence["baseline_type"] = b_type
        return metrics

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

from wikidata_coverage.bias.base import GroupShareDetector
from wikidata_coverage.core.entity import Entity

# Common P172 (ethnic group) values and human-readable labels.
# Unrecognized QIDs fall back to showing the raw QID.
ETHNICITY_LABELS: dict[str, str] = {
    "Q539050": "African Americans",
    "Q40232": "Han Chinese",
    "Q49078": "Afro-Germans",
    "Q134552": "Bengalis",
    "Q614911": "African descent",
    "Q79800": "Tamils",
    "Q42406": "Kurds",
    "Q35323": "Arabs",
    "Q7325": "Jews",
    "Q177520": "Ashkenazi Jews",
    "Q1025585": "Sephardi Jews",
    "Q49077": "Black people",
    "Q200615": "White people",
    "Q600465": "Romani people",
}


def _ethnicity_of(entity: Entity) -> str | None:
    values = entity.values_for("P172")
    if not values:
        return None
    v = values[0]
    return v.get("id") if isinstance(v, dict) else None


class EthnicityBalanceDetector(GroupShareDetector):
    """Preconfigured GroupShareDetector for P172 (ethnic group).

    No default baseline is provided (exploratory mode by default). Pass
    ``expected_shares`` explicitly if you wish to compare against a specific
    demographic baseline for your target cohort.
    """

    def __init__(
        self,
        expected_shares: dict[str, float] | None = None,
        label_overrides: dict[str, str] | None = None,
        min_group_size: int = 1,
    ) -> None:
        """
        Args:
            expected_shares: optional population share dict, keyed by P172 QID.
            label_overrides: custom ``{qid: label}`` mapping.
            min_group_size: groups smaller than this are flagged as low-confidence.
        """
        labels = {**ETHNICITY_LABELS, **(label_overrides or {})}
        super().__init__(
            axis="ethnicity",
            name="ethnicity_balance_detector",
            group_fn=_ethnicity_of,
            group_label_fn=lambda qid: labels.get(qid, qid),
            expected_shares=expected_shares or {},
            min_group_size=min_group_size,
        )

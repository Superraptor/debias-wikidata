"""Geographic disparity: what fraction of a population's biographies (or
other entities) come from each country, compared to that country's share
of world population.

The point isn't "every country should have proportional Wikidata
coverage regardless of context" -- it's giving the community a concrete,
inspectable number for "this region gets far less coverage than its
population share would predict," which is the kind of signal the
challenge statement asks for re: "disparities in coverage across regions
of the world."

Baseline sources
----------------
* **Default (static)**: ``APPROX_WORLD_POPULATION_SHARE`` — a rough
  illustrative table, adequate for quick runs and tests.
* **Live (recommended)**: pass a ``SparqlClient`` to the constructor.
  ``baselines.country_population_shares(sparql)`` is called once and
  cached process-wide, so repeated instantiations within the same run
  don't incur extra network traffic.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

from wikidata_coverage.bias import baselines as _baselines
from wikidata_coverage.bias.base import GroupShareDetector
from wikidata_coverage.core.entity import Entity

if TYPE_CHECKING:
    from wikidata_coverage.access.sparql import SparqlClient

# Approximate world population shares by country, keyed by Wikidata QID.
# THIS IS A ROUGH, ILLUSTRATIVE DEFAULT -- replace with a live source (UN
# World Population Prospects, World Bank API) before relying on this for
# real analysis. Shares are approximate and will drift; the point of
# having a default here is so the detector is runnable out of the box,
# not that these numbers should be trusted as current.
APPROX_WORLD_POPULATION_SHARE = {
    "Q668": 0.178,   # India
    "Q148": 0.177,   # China
    "Q30": 0.042,    # United States
    "Q252": 0.035,   # Indonesia
    "Q843": 0.030,   # Pakistan
    "Q1033": 0.029,  # Nigeria
    "Q155": 0.027,   # Brazil
    "Q902": 0.021,   # Bangladesh
    "Q159": 0.018,   # Russia
    "Q96": 0.016,    # Mexico
    "Q115": 0.016,   # Ethiopia
    "Q17": 0.015,    # Japan
    "Q928": 0.014,   # Philippines
    "Q79": 0.014,    # Egypt
    "Q881": 0.012,   # Vietnam
    "Q974": 0.012,   # DR Congo
    "Q43": 0.011,    # Turkey
    "Q794": 0.011,   # Iran
    "Q183": 0.010,   # Germany
    "Q258": 0.007,   # South Africa
    "Q884": 0.006,   # South Korea
    "Q145": 0.0085,  # United Kingdom
    "Q142": 0.008,   # France
    "Q29": 0.006,    # Spain
    "Q114": 0.006,   # Kenya
}

COUNTRY_LABELS = {
    "Q668": "India", "Q148": "China", "Q30": "United States", "Q252": "Indonesia",
    "Q843": "Pakistan", "Q1033": "Nigeria", "Q155": "Brazil", "Q902": "Bangladesh",
    "Q159": "Russia", "Q96": "Mexico", "Q115": "Ethiopia", "Q17": "Japan",
    "Q928": "Philippines", "Q79": "Egypt", "Q881": "Vietnam", "Q974": "DR Congo",
    "Q43": "Turkey", "Q794": "Iran", "Q183": "Germany", "Q258": "South Africa",
    "Q884": "South Korea", "Q145": "United Kingdom", "Q142": "France",
    "Q29": "Spain", "Q114": "Kenya",
}


def _country_of(entity: Entity, property_id: str) -> str | None:
    values = entity.values_for(property_id)
    if not values:
        return None
    v = values[0]
    return v.get("id") if isinstance(v, dict) else None


class GeographicDisparityDetector(GroupShareDetector):
    """Groups entities by country (citizenship P27 by default; pass
    property_id="P17" for "country" or "P19" for "place of birth"'s
    containing country isn't directly derivable -- P19 gives a place, not
    a country, so P27/P17 are the practical choices) and compares each
    country's share of the population against its world-population share.

    Pass a ``SparqlClient`` to use live P1082-derived population shares
    from Wikidata; otherwise falls back to ``APPROX_WORLD_POPULATION_SHARE``.
    """

    def __init__(
        self,
        property_id: str = "P27",
        population_baseline: dict[str, float] | None = None,
        label_fn: Callable[[str], str] | None = None,
        min_group_size: int = 1,
        sparql: "SparqlClient | None" = None,
        force_refresh: bool = False,
    ) -> None:
        """
        Args:
            property_id: country property to group by.
                P27 (country of citizenship) is the default.
                P17 (country) is an alternative for non-biographical entities.
            population_baseline: explicit share dict override. Mutually
                exclusive with ``sparql``; if both are provided, this wins.
            label_fn: QID -> human-readable country name. Defaults to
                ``COUNTRY_LABELS`` lookup with raw QID fallback.
            min_group_size: groups smaller than this are flagged as
                low-confidence in their evidence.
            sparql: if provided, fetch live country population shares from
                Wikidata P1082 (cached process-wide). Ignored when
                ``population_baseline`` is explicitly supplied.
            force_refresh: bypass the module-level baseline cache.
        """
        if population_baseline is not None:
            baseline = population_baseline
        elif sparql is not None:
            baseline = _baselines.country_population_shares(sparql, force_refresh=force_refresh)
            if not baseline:
                baseline = APPROX_WORLD_POPULATION_SHARE
        else:
            baseline = APPROX_WORLD_POPULATION_SHARE

        super().__init__(
            axis="geographic",
            name=f"geographic_disparity_detector[{property_id}]",
            group_fn=lambda e: _country_of(e, property_id),
            group_label_fn=label_fn or (lambda qid: COUNTRY_LABELS.get(qid, qid)),
            expected_shares=baseline,
            min_group_size=min_group_size,
        )

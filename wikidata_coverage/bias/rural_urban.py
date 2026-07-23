"""Rural/urban coverage disparity.

Groups biographical entities by the urban/rural character of their place of
origin (P19 — place of birth by default) and compares each group's share
against the world's urban/rural population split from Wikidata.

Classification pipeline
-----------------------
1. Collect all unique P19 place QIDs from the entity batch (no extra API call
   — the QID is already present in the entity's P19 claim value).
2. Query WDQS for the P31 (instance of) types of those place QIDs.
3. Classify each place as "urban", "rural", or "unclassified" by matching P31
   values against the ``URBAN_TYPES`` / ``RURAL_TYPES`` frozensets in
   ``bias/baselines.py``.
4. Entities without P19, or whose place can't be classified, go into
   "unclassified" — they are reported informatively but excluded from the
   disparity ratio calculation.

Typical finding
---------------
Wikidata biographical coverage is heavily urban-skewed: people born in major
cities (especially capital cities) are far more likely to have a Wikidata item
than equally notable people from rural areas. This detector quantifies that gap
relative to the world's ~57 % urban / 43 % rural split (or the live Wikidata
estimate if SPARQL data is sufficient).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterable

from wikidata_coverage.bias import baselines as _baselines
from wikidata_coverage.bias.base import BiasDetector, disparity_severity
from wikidata_coverage.bias.gadm import gadm_lookup_point
from wikidata_coverage.bias.ghs import ghs_country_urban_shares
from wikidata_coverage.bias.metrics import DisparityMetric
from wikidata_coverage.core.entity import Entity

if TYPE_CHECKING:
    from wikidata_coverage.access.sparql import SparqlClient

logger = logging.getLogger(__name__)


class RuralUrbanDetector(BiasDetector):
    """Measures whether Wikidata biographical coverage skews toward urban
    birthplaces relative to country-level urban/rural population splits.

    Uses Wikidata coordinate locations (P625), GADM administrative boundaries
    (data/gadm_410-levels.gpkg), and country-level urbanization statistics from
    the GHS dataset (data/GHS_COUNTRY_STATS_MT_GLOBE_R2024A.zip).
    """

    name = "rural_urban_detector"
    axis = "rural_urban"

    def __init__(
        self,
        sparql: "SparqlClient",
        property_id: str = "P19",
        force_refresh: bool = False,
    ) -> None:
        """
        Args:
            sparql: SPARQL client used for:
              (a) fetching place coordinates (P625) and country data, and
              (b) classifying place QIDs by P31 type during ``run()``.
            property_id: which place property to classify entities by.
                * ``P19`` — place of birth (default, most widely populated)
                * ``P20`` — place of death
                * ``P551`` — residence
                * ``P937`` — work location
            force_refresh: bypass the cached urban/rural baseline data.
        """
        self.sparql = sparql
        self.property_id = property_id
        self.force_refresh = force_refresh
        self._ghs_shares = ghs_country_urban_shares(sparql, force_refresh=force_refresh)
        self._world_baseline = _baselines.urban_rural_world_shares(
            sparql, force_refresh=force_refresh
        )

    def run(self, entities: Iterable[Entity]) -> list[DisparityMetric]:
        entity_list = list(entities)
        if not entity_list:
            return []

        # 1. Collect unique place QIDs from the configured property.
        place_to_entities: dict[str, list[Entity]] = {}
        no_place: list[Entity] = []
        for e in entity_list:
            values = e.values_for(self.property_id)
            qid: str | None = None
            if values:
                v = values[0]
                qid = v.get("id") if isinstance(v, dict) else (v if isinstance(v, str) and v.startswith("Q") else None)
            if qid:
                place_to_entities.setdefault(qid, []).append(e)
            else:
                no_place.append(e)

        place_qids = list(place_to_entities.keys())

        # 2. Fetch coordinates (P625) and P31 types for place QIDs.
        coords_map = self.sparql.place_coordinates(place_qids, force_refresh=self.force_refresh)
        type_classification = _baselines.classify_places_by_type(
            self.sparql, place_qids
        )

        # 3. Classify places and determine country ISO3/QID per place.
        place_classification: dict[str, str] = {}
        place_country: dict[str, str | None] = {}

        for qid in place_qids:
            cat = type_classification.get(qid, "unclassified")
            c_info = coords_map.get(qid, {})
            lat, lon = c_info.get("lat"), c_info.get("lon")
            c_qid = c_info.get("country_qid")

            country_code = c_qid
            if lat is not None and lon is not None:
                gadm = gadm_lookup_point(lat, lon, force_refresh=self.force_refresh)
                if gadm.get("iso3"):
                    country_code = gadm["iso3"]
                if gadm.get("classification"):
                    cat = gadm["classification"]

            place_country[qid] = country_code
            place_classification[qid] = cat

        # 4. Group entities and compute country-level expected urban shares.
        groups: dict[str, list[Entity]] = {"urban": [], "rural": [], "unclassified": list(no_place)}
        entity_expected_urban: list[float] = []

        for qid, ents in place_to_entities.items():
            category = place_classification.get(qid, "unclassified")
            groups[category].extend(ents)

            if category in ("urban", "rural"):
                c_code = place_country.get(qid)
                # Look up country urban share from GHS or fallback
                u_share = (
                    self._ghs_shares.get(c_code)
                    if c_code and c_code in self._ghs_shares
                    else self._world_baseline.get("urban", 0.57)
                )
                for _ in ents:
                    entity_expected_urban.append(u_share)

        # 5. Build country-level weighted baseline for the classified cohort.
        if entity_expected_urban:
            cohort_expected_urban = round(sum(entity_expected_urban) / len(entity_expected_urban), 4)
        else:
            cohort_expected_urban = self._world_baseline.get("urban", 0.57)

        cohort_expected = {
            "urban": cohort_expected_urban,
            "rural": round(1.0 - cohort_expected_urban, 4),
        }

        # 6. Build metrics.
        population_size = len(entity_list)
        classified_size = len(groups["urban"]) + len(groups["rural"])

        metrics: list[DisparityMetric] = []
        for category in ("urban", "rural", "unclassified"):
            members = groups[category]
            count = len(members)
            share_of_total = round(count / population_size, 4)

            if category == "unclassified":
                metrics.append(
                    DisparityMetric(
                        axis=self.axis,
                        detector=self.name,
                        group_key=category,
                        group_label=category,
                        population_size=population_size,
                        group_size=count,
                        observed_value=share_of_total,
                        expected_value=None,
                        disparity_ratio=None,
                        severity=0.0,
                        message=(
                            f"unclassified: {count}/{population_size} entities "
                            f"({share_of_total:.1%}) — no coordinates/P31 match for their "
                            f"{self.property_id} place, or no {self.property_id} recorded."
                        ),
                        evidence={
                            "property_id": self.property_id,
                            "no_place_count": len(no_place),
                            "unclassified_place_count": count - len(no_place),
                        },
                    )
                )
                continue

            expected = cohort_expected.get(category)
            if classified_size:
                observed = round(count / classified_size, 4)
            else:
                observed = 0.0
            ratio = round(observed / expected, 4) if (expected and classified_size) else None

            metrics.append(
                DisparityMetric(
                    axis=self.axis,
                    detector=self.name,
                    group_key=category,
                    group_label=category,
                    population_size=classified_size or population_size,
                    group_size=count,
                    observed_value=observed,
                    expected_value=expected,
                    disparity_ratio=ratio,
                    severity=disparity_severity(ratio),
                    message=self._message(
                        category, observed, expected, count, classified_size, share_of_total
                    ),
                    evidence={
                        "property_id": self.property_id,
                        "classified_population": classified_size,
                        "total_population": population_size,
                        "share_of_total": share_of_total,
                        "country_weighted_baseline": True,
                    },
                )
            )

        return metrics

    @staticmethod
    def _message(
        category: str,
        observed: float,
        expected: float | None,
        count: int,
        classified: int,
        share_of_total: float,
    ) -> str:
        base = (
            f"{category}: {count}/{classified} classified entities "
            f"({observed:.1%} of classified; {share_of_total:.1%} of all)"
        )
        if expected is None:
            return f"{base}."
        direction = "over" if observed > expected else "under"
        return f"{base} vs. {expected:.1%} country-weighted expected population — {direction}represented."

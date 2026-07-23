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
from wikidata_coverage.bias.metrics import DisparityMetric
from wikidata_coverage.core.entity import Entity

if TYPE_CHECKING:
    from wikidata_coverage.access.sparql import SparqlClient

logger = logging.getLogger(__name__)


class RuralUrbanDetector(BiasDetector):
    """Measures whether Wikidata biographical coverage skews toward urban
    birthplaces relative to the world's urban/rural population split.

    The expected baseline is fetched from Wikidata at initialization (P6343
    urban population, weighted by P1082 across countries) and falls back to
    the UN World Urbanization Prospects estimate (~57 % urban) if SPARQL data
    is insufficient.
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
              (a) fetching world urban/rural baseline at init, and
              (b) classifying place QIDs by P31 type during ``run()``.
            property_id: which place property to classify entities by.
                * ``P19`` — place of birth (default, most widely populated)
                * ``P20`` — place of death
                * ``P551`` — residence
                * ``P937`` — work location
            force_refresh: bypass the module-level urban/rural baseline cache.
        """
        self.sparql = sparql
        self.property_id = property_id
        self._baseline = _baselines.urban_rural_world_shares(
            sparql, force_refresh=force_refresh
        )
        logger.info(
            "RuralUrbanDetector initialized (property=%s). "
            "World baseline: urban=%.1f%% rural=%.1f%%",
            property_id,
            self._baseline.get("urban", 0) * 100,
            self._baseline.get("rural", 0) * 100,
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
                qid = v.get("id") if isinstance(v, dict) else None
            if qid:
                place_to_entities.setdefault(qid, []).append(e)
            else:
                no_place.append(e)

        # 2. Classify places via SPARQL.
        classification = _baselines.classify_places_by_type(
            self.sparql, list(place_to_entities.keys())
        )

        # 3. Group entities into urban / rural / unclassified.
        groups: dict[str, list[Entity]] = {"urban": [], "rural": [], "unclassified": list(no_place)}
        for qid, ents in place_to_entities.items():
            category = classification.get(qid, "unclassified")
            groups[category].extend(ents)

        # 4. Build metrics.
        population_size = len(entity_list)
        classified_size = len(groups["urban"]) + len(groups["rural"])

        metrics: list[DisparityMetric] = []
        for category in ("urban", "rural", "unclassified"):
            members = groups[category]
            count = len(members)
            share_of_total = round(count / population_size, 4)

            if category == "unclassified":
                # Informational only — no baseline, no disparity ratio.
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
                            f"({share_of_total:.1%}) — no P31 match for their "
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

            # For urban/rural, compute share within classified-only population
            # (excludes unclassified from denominator, making the ratio meaningful).
            expected = self._baseline.get(category)
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
        return f"{base} vs. {expected:.1%} world population — {direction}represented."

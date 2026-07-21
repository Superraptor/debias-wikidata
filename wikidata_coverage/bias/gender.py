"""Gender balance: what fraction of a population (typically biographies,
`instance of` Q5 human) is recorded as each P21 (sex or gender) value,
compared to a real-world population baseline.

Known Wikidata/Wikipedia gender-gap context worth keeping in mind: only a
minority of biographical articles are about women (independent tracking
efforts have put it in roughly the 19-20% range in recent years), so
expect this detector to reliably surface a real, well-documented
disparity -- the value here is the tooling to quantify and track it over
a specific slice (a WikiProject, a country, a time period), not the
discovery that the gap exists.

Baseline sources
----------------
* **Default (static)**: ``DEFAULT_GENDER_BASELINE`` -- near-parity 50/50.
* **Live country-specific**: pass ``sparql`` and ``country_qid`` to fetch
  P1539 (female population) and P1540 (male population) from that country's
  Wikidata item. Useful when the scope of your entities is a specific
  country where the actual sex ratio differs from world average.
* **Live world aggregate**: pass ``sparql`` only (no ``country_qid``) to
  aggregate P1539/P1540 across all countries in Wikidata.

All live baselines are cached process-wide by ``bias.baselines``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wikidata_coverage.bias import baselines as _baselines
from wikidata_coverage.bias.base import GroupShareDetector
from wikidata_coverage.core.entity import Entity

if TYPE_CHECKING:
    from wikidata_coverage.access.sparql import SparqlClient

# Common P21 (sex or gender) values and their labels. Not exhaustive --
# unrecognized QIDs fall back to showing the raw QID as the label.
GENDER_LABELS = {
    "Q6581097": "male",
    "Q6581072": "female",
    "Q1097630": "intersex",
    "Q48270": "non-binary",
    "Q1052281": "transgender female",
    "Q2449503": "transgender male",
    "Q189125": "transgender person",
}

# Default baseline: rough real-world population parity between the two
# most-recorded categories. This is a coarse default, not a normative
# claim about how many gender categories exist -- override with
# expected_shares tailored to your scope (e.g. a profession where the
# real-world baseline isn't 50/50) rather than relying on this blindly.
DEFAULT_GENDER_BASELINE = {
    "Q6581097": 0.5,   # male
    "Q6581072": 0.5,   # female
}


def gender_of(entity: Entity) -> str | None:
    values = entity.values_for("P21")
    if not values:
        return None
    v = values[0]
    return v.get("id") if isinstance(v, dict) else None


class GenderBalanceDetector(GroupShareDetector):
    """Preconfigured GroupShareDetector for P21. Scope the ``entities`` you
    pass to ``run()`` to the population you care about first (e.g. via
    ``SparqlClient.qids_of_class("Q5", ...)`` for humans generally, or a more
    specific class/occupation/nationality query) -- this detector doesn't
    do that scoping itself.

    Pass ``sparql`` to fetch a live baseline from Wikidata's P1539/P1540
    population figures. Pass ``country_qid`` additionally to get a
    country-specific sex ratio rather than the world aggregate.
    """

    def __init__(
        self,
        expected_shares: dict[str, float] | None = None,
        min_group_size: int = 1,
        sparql: "SparqlClient | None" = None,
        country_qid: str | None = None,
        force_refresh: bool = False,
    ) -> None:
        """
        Args:
            expected_shares: explicit share override. If provided, ``sparql``
                is ignored. Keyed by P21 value QID.
            min_group_size: groups below this size are flagged low-confidence.
            sparql: if provided (and ``expected_shares`` is None), fetches
                P1539/P1540 population data from Wikidata as the baseline.
            country_qid: when using ``sparql``, restrict to a specific country
                item (e.g. ``"Q30"`` for the United States) rather than
                aggregating world totals.
            force_refresh: bypass the module-level baseline cache.
        """
        if expected_shares is not None:
            baseline = expected_shares
        elif sparql is not None:
            live = _baselines.gender_population_shares(
                sparql, country_qid=country_qid, force_refresh=force_refresh
            )
            baseline = live if live else DEFAULT_GENDER_BASELINE
        else:
            baseline = DEFAULT_GENDER_BASELINE

        super().__init__(
            axis="gender",
            name="gender_balance_detector",
            group_fn=gender_of,
            group_label_fn=lambda qid: GENDER_LABELS.get(qid, qid),
            expected_shares=baseline,
            min_group_size=min_group_size,
        )

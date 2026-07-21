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

from typing import Callable

from wikidata_coverage.bias.base import GroupShareDetector
from wikidata_coverage.core.entity import Entity


class DemographicBalanceDetector(GroupShareDetector):
    """Balance check for any single-value categorical property."""

    def __init__(
        self,
        property_id: str,
        expected_shares: dict[str, float],
        axis: str | None = None,
        group_label_fn: Callable[[str], str] | None = None,
        min_group_size: int = 1,
        take_first_value: bool = True,
    ) -> None:
        """
        Args:
            property_id: the PID to group by, e.g. "P106" (occupation).
            expected_shares: REQUIRED (no silent default) -- group key ->
                expected population fraction. Forces the caller to make an
                explicit, reviewable choice about the baseline for
                whatever axis this is.
            axis: metric axis label; defaults to the property id.
            take_first_value: if an entity has multiple values for
                property_id, use only the first (avoids double-counting
                entities across groups, which would break share math).
                Set False only if you've designed expected_shares to
                account for multi-membership.
        """
        def group_fn(entity: Entity) -> str | None:
            values = entity.values_for(property_id)
            if not values:
                return None
            v = values[0] if take_first_value else values
            return v.get("id") if isinstance(v, dict) else None

        super().__init__(
            axis=axis or property_id,
            name=f"demographic_balance_detector[{property_id}]",
            group_fn=group_fn,
            group_label_fn=group_label_fn,
            expected_shares=expected_shares,
            min_group_size=min_group_size,
        )

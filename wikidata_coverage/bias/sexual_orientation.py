"""Sexual orientation coverage: distribution of P91 (sexual orientation) values.

Population Baselines & Sources
-------------------------------
Baseline expectations are derived from the official Ipsos LGBT+ Pride Global Surveys:
* Ipsos LGBT+ Pride 2023 Global Survey (30-Country Report):
  https://www.ipsos.com/en/ipsos-lgbt-pride-2023-global-survey
* Ipsos LGBT+ Pride 2024 Global Survey:
  https://www.ipsos.com/en/lgbt-pride-2024

Both global averages and country-specific statistics (for surveyed countries such as Brazil,
Spain, USA, UK, France, Germany, Japan, Australia, Canada, etc.) are available.

IMPORTANT — what this detector measures and what it doesn't
-----------------------------------------------------------
It measures the **distribution of recorded values** among Wikidata entities
that *already have* P91 stated. It does **not**:

* Flag any entity for *missing* P91. Sexual orientation is a deeply personal
  attribute; Wikidata policy is that it should only be recorded where it is
  publicly stated by the person themselves. Absence of P91 is not a coverage
  gap to be reported.

Note on P91 and Wikidata coverage quality
-----------------------------------------
Because P91 is recorded only for entities where it is publicly known, any
sample will inherently over-represent sexual minorities who have been openly
public about their orientation (activists, artists, politicians). This
selection bias should be considered when interpreting the output.
"""

from __future__ import annotations

from wikidata_coverage.bias import baselines
from wikidata_coverage.bias.base import GroupShareDetector
from wikidata_coverage.core.entity import Entity

# Known P91 value QIDs and their human-readable labels.
ORIENTATION_LABELS: dict[str, str] = {
    "Q1035954": "heterosexual",
    "Q1072": "heterosexual",
    "Q6636": "homosexual",
    "Q43200": "gay",
    "Q1097630": "gay",
    "Q44748": "lesbian",
    "Q747010": "lesbian",
    "Q6649": "bisexual",
    "Q18116794": "asexual",
    "Q724351": "asexual",
    "Q271534": "pansexual",
    "Q272530": "pansexual",
    "Q1415741": "queer",
    "Q18057751": "queer",
    "Q212623": "non-heterosexuality",
    "Q26705162": "demisexual",
    "Q1097401": "polysexual",
}


def _orientation_qid_of(entity: Entity, assume_heterosexual_if_missing: bool = False) -> str | None:
    values = entity.values_for("P91")
    if not values:
        return "Q1035954" if assume_heterosexual_if_missing else None
    v = values[0]
    return (v.get("id") if isinstance(v, dict) else None) or ("Q1035954" if assume_heterosexual_if_missing else None)


def _orientation_category_of(entity: Entity, assume_heterosexual_if_missing: bool = False) -> str | None:
    qid = _orientation_qid_of(entity, assume_heterosexual_if_missing=assume_heterosexual_if_missing)
    if not qid:
        return None
    return baselines.SEXUAL_ORIENTATION_CANONICAL_MAP.get(qid, ORIENTATION_LABELS.get(qid, qid))


class SexualOrientationDetector(GroupShareDetector):
    """Distribution of P91 (sexual orientation) values among entities that
    have this property explicitly recorded, or under secondary analysis where missing
    P91 values are assumed heterosexual.

    By default, uses population statistics from the Ipsos LGBT+ Pride Global Surveys:
    - 2023 Survey: https://www.ipsos.com/en/ipsos-lgbt-pride-2023-global-survey
    - 2024 Survey: https://www.ipsos.com/en/lgbt-pride-2024

    Supports both global 30-country averages and country-specific baselines
    (e.g., country_qid="Q155" for Brazil, country_qid="Q30" for USA).
    Categories can be grouped canonically (e.g. gay/lesbian/homosexual → "homosexual")
    or evaluated by raw QID.
    """

    def __init__(
        self,
        country_qid: str | None = None,
        use_ipsos_baselines: bool = True,
        group_by_category: bool = True,
        expected_shares: dict[str, float] | None = None,
        label_overrides: dict[str, str] | None = None,
        min_group_size: int = 1,
        assume_heterosexual_if_missing: bool = False,
    ) -> None:
        """
        Args:
            country_qid: optional country QID (e.g. Q30 for USA, Q155 for Brazil) to load
                country-specific Ipsos survey statistics.
            use_ipsos_baselines: if True (default), populates expected_shares using Ipsos statistics.
            group_by_category: if True (default), groups related QIDs into canonical orientation categories.
            expected_shares: explicit prevalence dict override.
            label_overrides: additional ``{qid: label}`` entries to merge with ORIENTATION_LABELS.
            min_group_size: groups smaller than this are flagged as low-confidence.
            assume_heterosexual_if_missing: if True, entities lacking P91 are assigned heterosexual.
        """
        labels = {**ORIENTATION_LABELS, **(label_overrides or {})}
        self.country_qid = country_qid
        self.assume_heterosexual_if_missing = assume_heterosexual_if_missing
        self.baseline_info = baselines.ipsos_sexual_orientation_info(country_qid)

        if expected_shares is None and use_ipsos_baselines:
            expected_shares = baselines.ipsos_sexual_orientation_shares(
                country_qid=country_qid,
                by_qid=not group_by_category,
            )

        if group_by_category:
            group_fn = lambda e: _orientation_category_of(e, assume_heterosexual_if_missing=assume_heterosexual_if_missing)
        else:
            group_fn = lambda e: _orientation_qid_of(e, assume_heterosexual_if_missing=assume_heterosexual_if_missing)

        group_label_fn = (lambda k: k) if group_by_category else (lambda qid: labels.get(qid, qid))

        super().__init__(
            axis="sexual_orientation",
            name="sexual_orientation_detector",
            group_fn=group_fn,
            group_label_fn=group_label_fn,
            expected_shares=expected_shares or {},
            min_group_size=min_group_size,
        )

    def run(self, entities: Iterable[Entity]) -> list[DisparityMetric]:
        metrics = super().run(entities)
        mode = "assumed_heterosexual_if_missing" if self.assume_heterosexual_if_missing else "explicit_only"
        for m in metrics:
            m.evidence.update(self.baseline_info)
            m.evidence["analysis_mode"] = mode
            m.evidence["assume_heterosexual_if_missing"] = self.assume_heterosexual_if_missing
        return metrics

    def _message(self, key: str, observed: float, expected: float | None, n: int) -> str:
        base_msg = super()._message(key, observed, expected, n)
        mode_str = " (Assumed Heterosexual for Missing P91)" if self.assume_heterosexual_if_missing else ""
        if expected is not None:
            source = self.baseline_info["source"]
            year = self.baseline_info["source_year"]
            b_type = self.baseline_info["baseline_type"]
            return f"{base_msg}{mode_str} [Source: {source} ({year}), {b_type}]"
        return f"{base_msg}{mode_str}"


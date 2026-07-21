"""Sexual orientation coverage: distribution of P91 (sexual orientation) values.

IMPORTANT — what this detector measures and what it doesn't
-----------------------------------------------------------
It measures the **distribution of recorded values** among Wikidata entities
that *already have* P91 stated. It does **not**:

* Flag any entity for *missing* P91. Sexual orientation is a deeply personal
  attribute; Wikidata policy is that it should only be recorded where it is
  publicly stated by the person themselves. Absence of P91 is not a coverage
  gap to be reported.
* Provide a built-in population-level baseline. Published prevalence estimates
  vary widely by country, study methodology, year, and definition (LGB only?
  LGBTQ+? self-identified vs. behaviour-based?). A single hardcoded default
  would misrepresent this complexity.

What it *does* do
-----------------
Surfaces the distribution of *recorded* P91 values within a sample so that:

* Over- or under-representation of specific orientations among entities that
  *do* have P91 recorded can be examined.
* The rate at which P91 is recorded at all (vs. absent) is visible in context
  with the broader entity population.

A researcher can pass an explicit ``expected_shares`` override if they wish
to compare against a specific study's estimates — see the docstring example.

Note on P91 and Wikidata coverage quality
-----------------------------------------
Because P91 is recorded only for entities where it is publicly known, any
sample will inherently over-represent sexual minorities who have been openly
public about their orientation (activists, artists, politicians). This
selection bias should be considered when interpreting the output.
"""

from __future__ import annotations

from wikidata_coverage.bias.base import GroupShareDetector
from wikidata_coverage.core.entity import Entity

# Known P91 value QIDs and their human-readable labels.
# This is not exhaustive — unlisted QIDs fall back to displaying the raw QID.
ORIENTATION_LABELS: dict[str, str] = {
    "Q1072": "heterosexual",
    "Q6636": "homosexual",
    "Q43200": "gay",
    "Q44748": "lesbian",
    "Q1035954": "bisexual",
    "Q18116794": "asexual",
    "Q271534": "pansexual",
    "Q1415741": "queer",
    "Q26705162": "demisexual",
    "Q1097401": "polysexual",
}


def _orientation_of(entity: Entity) -> str | None:
    values = entity.values_for("P91")
    if not values:
        return None
    v = values[0]
    return v.get("id") if isinstance(v, dict) else None


class SexualOrientationDetector(GroupShareDetector):
    """Distribution of P91 (sexual orientation) values among entities that
    have this property explicitly recorded.

    No default baseline is provided. Pass ``expected_shares`` explicitly if
    you wish to compare against a specific study's population estimates::

        detector = SexualOrientationDetector(
            expected_shares={
                "Q1072": 0.95,    # heterosexual
                "Q6636": 0.025,   # homosexual  } adjust to the specific study
                "Q1035954": 0.02, # bisexual    } and its definitions
                "Q18116794": 0.005, # asexual
            }
        )

    Without ``expected_shares``, every group's ``disparity_ratio`` will be
    ``None`` (exploratory mode only — observed distribution is reported but
    not compared against any baseline).
    """

    def __init__(
        self,
        expected_shares: dict[str, float] | None = None,
        label_overrides: dict[str, str] | None = None,
        min_group_size: int = 1,
    ) -> None:
        """
        Args:
            expected_shares: optional population-level prevalence dict,
                keyed by P91 value QID. No built-in default; see module
                docstring for the rationale.
            label_overrides: additional ``{qid: label}`` entries to merge
                with (or override) the built-in ``ORIENTATION_LABELS`` table.
            min_group_size: groups smaller than this are flagged as
                low-confidence in their evidence dict.
        """
        labels = {**ORIENTATION_LABELS, **(label_overrides or {})}
        super().__init__(
            axis="sexual_orientation",
            name="sexual_orientation_detector",
            group_fn=_orientation_of,
            group_label_fn=lambda qid: labels.get(qid, qid),
            expected_shares=expected_shares or {},
            min_group_size=min_group_size,
        )

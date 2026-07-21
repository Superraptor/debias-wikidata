"""Linguistic coverage: how well is Wikidata's multilingual metadata populated?

Three distinct coverage axes, each producing one ``DisparityMetric`` per language:

* ``linguistic_label``       — fraction of entities that have a label in this language
* ``linguistic_description`` — fraction with a description
* ``linguistic_alias``       — fraction with at least one alias

Expected baseline for each language: its share of global speaker population,
fetched once via P1098 from WDQS at detector initialization and cached for
the process lifetime.

Interpretation
--------------
A disparity_ratio > 1 means a language has *more* coverage than its speaker
share predicts (typically English, German, French — languages of heavy
Wikidata contributor communities). A ratio < 1 means speakers of that language
are underserved by Wikidata's multilingual metadata relative to their numbers.

The detector reports all languages that appear in either the speaker baseline
*or* the entity data, so you will always see languages present in your sample
even if they're not in the top-N baseline list (their expected_value will be
None, and disparity_ratio will be None — exploratory only for those).
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

# Maps coverage_type key → axis name used in DisparityMetric
COVERAGE_AXES: dict[str, str] = {
    "label": "linguistic_label",
    "description": "linguistic_description",
    "alias": "linguistic_alias",
}


class LinguisticCoverageDetector(BiasDetector):
    """Measures multilingual metadata coverage weighted by speaker population.

    For each language in the configured set, computes what fraction of the
    given entities have a label / description / alias in that language, then
    compares that fraction against the language's global speaker-population
    share from Wikidata (P1098).

    Example::

        from wikidata_coverage.access.sparql import SparqlClient
        from wikidata_coverage.bias.linguistic import LinguisticCoverageDetector
        from wikidata_coverage.bias.report import BiasReport

        sparql = SparqlClient()
        detector = LinguisticCoverageDetector(sparql, top_n_languages=20)
        report = BiasReport()
        report.add(detector.run(entities))
        print(report.to_csv())
    """

    name = "linguistic_coverage_detector"
    axis = "linguistic"

    def __init__(
        self,
        sparql: "SparqlClient",
        top_n_languages: int = 30,
        min_speakers: int = 1_000_000,
        coverage_types: tuple[str, ...] = ("label", "description", "alias"),
        force_refresh: bool = False,
    ) -> None:
        """
        Args:
            sparql: SPARQL client used to fetch the speaker-population baseline.
            top_n_languages: number of languages (ranked by speaker count) to
                include in the baseline. Languages outside the top-N are still
                reported if present in entity data, but with no expected_value.
            min_speakers: languages below this speaker threshold are excluded
                from the baseline. Default (1 M) keeps the set tractable.
            coverage_types: which metadata axes to measure. Any subset of
                ``("label", "description", "alias")``.
            force_refresh: bypass the module-level speaker-share cache.
        """
        self.coverage_types = [ct for ct in coverage_types if ct in COVERAGE_AXES]
        self._speaker_shares: dict[str, float] = _baselines.language_speaker_shares(
            sparql,
            top_n=top_n_languages,
            min_speakers=min_speakers,
            force_refresh=force_refresh,
        )
        if not self._speaker_shares:
            logger.warning(
                "LinguisticCoverageDetector: no speaker shares loaded from Wikidata. "
                "Metrics will be reported without an expected_value (exploratory only)."
            )

    def run(self, entities: Iterable[Entity]) -> list[DisparityMetric]:
        entity_list = list(entities)
        if not entity_list:
            return []

        n = len(entity_list)

        # Collect all languages that appear in the entity data or the baseline.
        candidate_langs: set[str] = set(self._speaker_shares.keys())
        for e in entity_list:
            candidate_langs.update(e.labels.keys())
            candidate_langs.update(e.descriptions.keys())
            candidate_langs.update(e.aliases.keys())

        metrics: list[DisparityMetric] = []
        for lang in sorted(candidate_langs):
            expected = self._speaker_shares.get(lang)

            for ctype in self.coverage_types:
                covered = self._count_covered(entity_list, lang, ctype)
                observed = round(covered / n, 4)
                ratio = round(observed / expected, 4) if expected else None

                metrics.append(
                    DisparityMetric(
                        axis=COVERAGE_AXES[ctype],
                        detector=self.name,
                        group_key=lang,
                        group_label=lang,
                        population_size=n,
                        group_size=covered,
                        observed_value=observed,
                        expected_value=expected,
                        disparity_ratio=ratio,
                        severity=disparity_severity(ratio),
                        message=self._message(lang, ctype, observed, expected, covered, n),
                        evidence={
                            "coverage_type": ctype,
                            "in_baseline": expected is not None,
                            "low_confidence": n < 20,
                        },
                    )
                )

        return metrics

    @staticmethod
    def _count_covered(entities: list[Entity], lang: str, ctype: str) -> int:
        if ctype == "label":
            return sum(1 for e in entities if lang in e.labels)
        if ctype == "description":
            return sum(1 for e in entities if lang in e.descriptions)
        # alias
        return sum(1 for e in entities if e.aliases.get(lang))

    @staticmethod
    def _message(
        lang: str,
        ctype: str,
        observed: float,
        expected: float | None,
        covered: int,
        total: int,
    ) -> str:
        base = (
            f"{lang} {ctype} coverage: {covered}/{total} entities ({observed:.1%})"
        )
        if expected is None:
            return f"{base} — no speaker-population baseline available."
        direction = "over" if observed > expected else "under"
        return (
            f"{base} vs. {expected:.1%} speaker-population share "
            f"— {direction}served (ratio {observed/expected:.2f})."
        )

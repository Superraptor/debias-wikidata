"""Class-profile ("shape") detection.

For a set of entities sharing a class (instance-of/subclass-of), learn
which properties are common among peers and flag items missing properties
that most of their peers have. This complements constraint-based detection:
constraints tell you what's *technically* required; this tells you what's
*conventionally* expected for a given type even without a formal rule.

A more rigorous version of this idea exists natively in Wikidata as
EntitySchemas (ShEx, the E-namespace) -- worth a dedicated detector later
that validates against a specific schema rather than an empirically
learned profile. This detector is deliberately schema-free: give it a
batch of same-class entities and it infers the expected profile from the
population itself.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from wikidata_coverage.core.entity import Entity
from wikidata_coverage.core.finding import Finding, FindingKind, Severity, SuggestedFix
from wikidata_coverage.detectors.base import Detector


@dataclass
class ClassProfile:
    class_id: str
    population_size: int
    property_frequency: dict[str, float]  # property_id -> fraction of population having it


class ClassProfileDetector(Detector):
    """Statistically infers an expected-property profile per class from the
    entities it's given, then flags population members missing properties
    that exceed `frequency_threshold` prevalence among their peers.

    Note: this detector needs a reasonably sized, class-homogeneous batch to
    produce a meaningful profile -- it's not meant to run over a single
    mixed-class list. Typical usage: fetch all Qxxx `instance of` Qyyy via
    SparqlClient.qids_of_class, then run this detector on that batch alone.
    """

    name = "class_profile_detector"

    def __init__(
        self,
        frequency_threshold: float = 0.8,
        min_population_size: int = 20,
    ) -> None:
        """
        Args:
            frequency_threshold: if >= this fraction of peers have a
                property, absence is flagged for the rest. 0.8 = "80% of
                similar items have this, so items lacking it stand out."
            min_population_size: below this, don't trust the inferred
                profile enough to raise findings (too few peers to judge).
        """
        self.frequency_threshold = frequency_threshold
        self.min_population_size = min_population_size

    def build_profile(self, entities: list[Entity], class_id: str) -> ClassProfile:
        members = [e for e in entities if class_id in e.classes()]
        counts: Counter[str] = Counter()
        for e in members:
            for prop_id in e.property_ids():
                if e.has_property(prop_id):
                    counts[prop_id] += 1

        n = len(members)
        frequency = {prop: (count / n if n else 0.0) for prop, count in counts.items()}
        return ClassProfile(class_id=class_id, population_size=n, property_frequency=frequency)

    def run(self, entities: Iterable[Entity]) -> list[Finding]:
        entities = list(entities)
        findings: list[Finding] = []

        # Group entities by every class they belong to, then build + apply
        # a profile per class. An entity in multiple classes is judged
        # against each independently.
        class_members: dict[str, list[Entity]] = {}
        for e in entities:
            for c in e.classes():
                class_members.setdefault(c, []).append(e)

        for class_id, members in class_members.items():
            if len(members) < self.min_population_size:
                continue

            profile = self.build_profile(entities, class_id)
            expected_props = {
                prop
                for prop, freq in profile.property_frequency.items()
                if freq >= self.frequency_threshold
            }

            for entity in members:
                missing = {p for p in expected_props if not entity.has_property(p)}
                for prop_id in missing:
                    freq = profile.property_frequency[prop_id]
                    findings.append(
                        Finding(
                            entity_id=entity.id,
                            kind=FindingKind.MISSING_STATEMENT,
                            detector=self.name,
                            property_id=prop_id,
                            message=(
                                f"{entity.label()} ({entity.id}) is missing {prop_id}, "
                                f"present in {freq:.0%} of {profile.population_size} "
                                f"peers classified as {class_id}."
                            ),
                            severity=self._severity_for_frequency(freq),
                            evidence={
                                "class_id": class_id,
                                "peer_frequency": freq,
                                "population_size": profile.population_size,
                            },
                            suggested_fix=SuggestedFix(
                                description=(
                                    f"Consider adding {prop_id} to {entity.id}, common "
                                    f"among peers of class {class_id}."
                                ),
                                quickstatements=f"{entity.id}|{prop_id}|<VALUE>",
                            ),
                        )
                    )

        return findings

    @staticmethod
    def _severity_for_frequency(freq: float) -> float:
        # Higher peer prevalence -> more conspicuous absence -> higher severity.
        if freq >= 0.95:
            return Severity.HIGH.value
        if freq >= 0.85:
            return Severity.MEDIUM.value
        return Severity.LOW.value

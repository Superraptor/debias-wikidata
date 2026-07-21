"""Existence ("missing entity") detection.

This is the hardest coverage question -- "what items should exist in
Wikidata but don't?" -- because it requires an external ground-truth
reference set: there's no way to derive "all ISO 3166 country codes" or
"all IUPAC-named chemical elements" from Wikidata alone. So this module is
a plugin interface, not a fixed algorithm: general-purpose here means
"pluggable," not "domain-free."

To use it: implement a ReferenceSource for your domain (fetch a canonical
list of identifiers + labels from wherever they live), and hand it to
ExistenceDetector along with a way to check whether a given reference
entry already has a matching Wikidata item (typically via a SPARQL query
on an external-id property, e.g. "has any item with wdt:P297 = 'FR'?").
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable

from wikidata_coverage.access.sparql import SparqlClient
from wikidata_coverage.core.entity import Entity
from wikidata_coverage.core.finding import Finding, FindingKind, Severity
from wikidata_coverage.detectors.base import Detector


@dataclass
class ReferenceItem:
    """One entry from an external ground-truth source that we expect to
    have a corresponding Wikidata item."""

    external_id: str
    label: str
    metadata: dict | None = None


class ReferenceSource(ABC):
    """Implement this per domain: ISO codes, periodic table elements,
    a Wikipedia category's members, a museum's collection API, etc."""

    name: str = "reference_source"
    #: The Wikidata property used to link back to this external id system,
    #: e.g. "P297" for ISO 3166-1 alpha-2 country code. Used to check for
    #: an existing match via SPARQL.
    matching_property: str | None = None

    @abstractmethod
    def fetch_all(self) -> list[ReferenceItem]:
        """Return the full canonical list of items expected to exist."""
        raise NotImplementedError


class ExistenceDetector(Detector):
    """Compares a ReferenceSource's canonical list against Wikidata (via
    the matching_property) and flags reference entries with no
    corresponding item."""

    name = "existence_detector"

    def __init__(self, source: ReferenceSource, sparql_client: SparqlClient | None = None) -> None:
        if not source.matching_property:
            raise ValueError(
                f"ReferenceSource {source.name!r} must define matching_property "
                "so we know how to check for an existing Wikidata match."
            )
        self.source = source
        self.sparql = sparql_client or SparqlClient()

    def run(self, entities: Iterable[Entity] = ()) -> list[Finding]:
        """Note: unlike other detectors, this one doesn't take an entity
        batch as its primary input -- it drives from the reference source
        and queries Wikidata itself. `entities` is accepted for interface
        consistency but unused."""
        findings: list[Finding] = []
        reference_items = self.source.fetch_all()
        existing_ids = self._existing_external_ids()

        for item in reference_items:
            if item.external_id in existing_ids:
                continue
            findings.append(
                Finding(
                    entity_id=f"<missing:{self.source.name}:{item.external_id}>",
                    kind=FindingKind.MISSING_ENTITY,
                    detector=self.name,
                    property_id=self.source.matching_property,
                    message=(
                        f"No Wikidata item found with {self.source.matching_property} "
                        f"= {item.external_id!r} ({item.label}), expected per "
                        f"reference source {self.source.name!r}."
                    ),
                    severity=Severity.MEDIUM.value,
                    evidence={
                        "external_id": item.external_id,
                        "label": item.label,
                        "source": self.source.name,
                        "metadata": item.metadata,
                    },
                )
            )
        return findings

    def _existing_external_ids(self) -> set[str]:
        query = f"""
        SELECT ?value WHERE {{
          ?item wdt:{self.source.matching_property} ?value .
        }}
        """
        rows = self.sparql.query(query)
        return {row["value"] for row in rows}

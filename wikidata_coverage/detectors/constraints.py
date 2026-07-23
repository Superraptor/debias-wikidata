"""Constraint-based detection.

Wikidata already encodes expectations about a property's values as
constraint statements (P2302) on the property's own item -- format
(regex), value-type, allowed values ("one of"), mandatory qualifiers, etc.
This is the lowest-effort, highest-signal detector because we don't need
to invent an expected schema: we read Wikidata's own.

NOTE: the constraint-type QIDs below (Q21502404 etc.) are the well-known
ones as of this writing but Wikidata occasionally reshuffles constraint
modeling. Treat CONSTRAINT_TYPE_* as configuration, not gospel -- verify
against https://www.wikidata.org/wiki/Help:Property_constraints_portal
before relying on this in production, and consider fetching the mapping
dynamically (e.g. via the constraint-type item's own P31) for a v2.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from wikidata_coverage.access.api import ActionApiClient
from wikidata_coverage.core.entity import Entity
from wikidata_coverage.core.finding import Finding, FindingKind, Severity, SuggestedFix
from wikidata_coverage.detectors.base import Detector

# Well-known constraint-type item QIDs (see module docstring caveat).
CONSTRAINT_TYPE_MANDATORY = "Q21502408"
CONSTRAINT_TYPE_FORMAT = "Q21502404"
CONSTRAINT_TYPE_ONE_OF = "Q21510859"
CONSTRAINT_TYPE_VALUE_TYPE = "Q21510865"
CONSTRAINT_TYPE_SINGLE_VALUE = "Q19474404"

# Qualifier properties used *on* constraint statements to parametrize them.
QUALIFIER_REGEX_PATTERN = "P1793"       # format as a regular expression
QUALIFIER_ALLOWED_ITEM = "P2305"        # item of property constraint (allowed value)


class ConstraintDetector(Detector):
    """Evaluates each entity's claims for a fixed set of properties against
    those properties' own P2302 constraint declarations."""

    name = "constraint_detector"

    def __init__(self, properties_to_check: list[str], api_client: ActionApiClient | None = None) -> None:
        """
        Args:
            properties_to_check: PIDs whose constraints should be enforced,
                e.g. ["P569", "P21", "P106"]. Kept explicit rather than
                "all properties on the entity" so runs stay bounded and
                predictable for a general-purpose v1.
            api_client: injected for testability; defaults to a live client.
        """
        self.properties_to_check = properties_to_check
        self.api = api_client or ActionApiClient()
        self._constraint_cache: dict[str, list[dict[str, Any]]] = {}

    def _constraints_for_property(self, property_id: str) -> list[dict[str, Any]]:
        if property_id in self._constraint_cache:
            return self._constraint_cache[property_id]

        entity_json = self.api.get_property_constraints_raw(property_id)
        raw_constraints = entity_json.get("claims", {}).get("P2302", [])

        parsed: list[dict[str, Any]] = []
        for stmt in raw_constraints:
            constraint_type = (
                stmt.get("mainsnak", {})
                .get("datavalue", {})
                .get("value", {})
                .get("id")
            )
            qualifiers = stmt.get("qualifiers", {})
            parsed.append({"type": constraint_type, "qualifiers": qualifiers})

        self._constraint_cache[property_id] = parsed
        return parsed

    def run(self, entities: Iterable[Entity]) -> list[Finding]:
        findings: list[Finding] = []

        for entity in entities:
            for prop_id in self.properties_to_check:
                try:
                    findings.extend(self._check_property(entity, prop_id))
                except Exception as exc:  # noqa: BLE001 - one bad prop shouldn't kill the run
                    findings.append(
                        Finding(
                            entity_id=entity.id,
                            entity_label=entity.label(),
                            kind=FindingKind.CONSTRAINT_VIOLATION,
                            detector=self.name,
                            property_id=prop_id,
                            message=f"Constraint check errored: {exc}",
                            severity=Severity.INFO.value,
                            evidence={"error": str(exc)},
                        )
                    )

        return findings

    def _check_property(self, entity: Entity, property_id: str) -> list[Finding]:
        findings: list[Finding] = []
        constraints = self._constraints_for_property(property_id)
        has_value = entity.has_property(property_id)

        for constraint in constraints:
            ctype = constraint["type"]
            qualifiers = constraint["qualifiers"]

            if ctype == CONSTRAINT_TYPE_MANDATORY and not has_value:
                findings.append(
                    Finding(
                        entity_id=entity.id,
                        entity_label=entity.label(),
                        kind=FindingKind.MISSING_STATEMENT,
                        detector=self.name,
                        property_id=property_id,
                        message=(
                            f"{entity.label()} ({entity.id}) is missing "
                            f"mandatory property {property_id}."
                        ),
                        severity=Severity.HIGH.value,
                        evidence={"constraint_type": ctype},
                        suggested_fix=SuggestedFix(
                            description=f"Add a value for {property_id} on {entity.id}.",
                            quickstatements=f"{entity.id}|{property_id}|<VALUE>",
                        ),
                    )
                )
                continue

            if not has_value:
                continue  # remaining constraint types only make sense if a value exists

            if ctype == CONSTRAINT_TYPE_FORMAT:
                findings.extend(self._check_format(entity, property_id, qualifiers))
            elif ctype == CONSTRAINT_TYPE_SINGLE_VALUE:
                findings.extend(self._check_single_value(entity, property_id))
            elif ctype == CONSTRAINT_TYPE_ONE_OF:
                findings.extend(self._check_one_of(entity, property_id, qualifiers))

        return findings

    def _check_format(
        self, entity: Entity, property_id: str, qualifiers: dict[str, Any]
    ) -> list[Finding]:
        pattern_snaks = qualifiers.get(QUALIFIER_REGEX_PATTERN)
        if not pattern_snaks:
            return []

        pattern = pattern_snaks[0].get("datavalue", {}).get("value")
        if not pattern:
            return []

        findings = []
        for value in entity.values_for(property_id):
            text = value if isinstance(value, str) else str(value)
            if not re.fullmatch(pattern, text):
                findings.append(
                    Finding(
                        entity_id=entity.id,
                        entity_label=entity.label(),
                        kind=FindingKind.CONSTRAINT_VIOLATION,
                        detector=self.name,
                        property_id=property_id,
                        message=(
                            f"Value {text!r} for {property_id} on {entity.id} "
                            f"does not match expected format {pattern!r}."
                        ),
                        severity=Severity.MEDIUM.value,
                        evidence={"value": text, "pattern": pattern},
                    )
                )
        return findings

    def _check_single_value(self, entity: Entity, property_id: str) -> list[Finding]:
        values = entity.values_for(property_id)
        if len(values) <= 1:
            return []
        return [
            Finding(
                entity_id=entity.id,
                entity_label=entity.label(),
                kind=FindingKind.CONSTRAINT_VIOLATION,
                detector=self.name,
                property_id=property_id,
                message=(
                    f"{property_id} on {entity.id} has {len(values)} values "
                    f"but is constrained to a single value."
                ),
                severity=Severity.LOW.value,
                evidence={"values": values},
            )
        ]

    def _check_one_of(
        self, entity: Entity, property_id: str, qualifiers: dict[str, Any]
    ) -> list[Finding]:
        allowed_snaks = qualifiers.get(QUALIFIER_ALLOWED_ITEM, [])
        allowed_ids = {
            s.get("datavalue", {}).get("value", {}).get("id")
            for s in allowed_snaks
            if s.get("datavalue")
        }
        allowed_ids.discard(None)
        if not allowed_ids:
            return []

        findings = []
        for value in entity.values_for(property_id):
            value_id = value.get("id") if isinstance(value, dict) else None
            if value_id and value_id not in allowed_ids:
                findings.append(
                    Finding(
                        entity_id=entity.id,
                        entity_label=entity.label(),
                        kind=FindingKind.CONSTRAINT_VIOLATION,
                        detector=self.name,
                        property_id=property_id,
                        message=(
                            f"Value {value_id} for {property_id} on {entity.id} "
                            f"is not in the allowed set {sorted(allowed_ids)}."
                        ),
                        severity=Severity.MEDIUM.value,
                        evidence={"value": value_id, "allowed": sorted(allowed_ids)},
                    )
                )
        return findings

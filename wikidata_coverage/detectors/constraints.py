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
CONSTRAINT_TYPE_SUBJECT_TYPE = "Q21503250"
CONSTRAINT_TYPE_REQUIRES_STATEMENT = "Q21502838"
CONSTRAINT_TYPE_REQUIRES_STATEMENT_ALT = "Q21503247"
CONSTRAINT_TYPE_QUALIFIER = "Q21510851"

# Qualifier properties used *on* constraint statements to parametrize them.
QUALIFIER_REGEX_PATTERN = "P1793"       # format as a regular expression
QUALIFIER_ALLOWED_ITEM = "P2305"        # item of property constraint (allowed/required value)
QUALIFIER_REQUIRED_PROPERTY = "P2306"   # required or conflicting property
QUALIFIER_CLASS = "P2309"               # class QID
QUALIFIER_RELATION = "P2308"            # relation QID
QUALIFIER_CONSTRAINT_STATUS = "P2303"   # constraint status qualifier (mandatory vs suggestion)

# QIDs representing suggestion-level constraint status
STATUS_SUGGESTION_QIDS = {"Q52712268", "Q64605023", "Q623138", "Q99393050"}

FICTIONAL_CLASSES = {
    "Q148837",     # fictional character / entity
    "Q15711870",    # fictional human
    "Q15632617",    # fictional female human
    "Q15773347",    # fictional male human
    "Q21070568",    # fictional organization
    "Q223166",      # fictional element
    "Q15773317",    # fictional character
    "Q61928601",    # fictional character
}


def is_fictional_entity(entity: Entity) -> bool:
    """Returns True if entity belongs to a known fictional character/entity class or carries fictional markers."""
    if set(entity.classes()) & FICTIONAL_CLASSES:
        return True
    if entity.has_property("P1080"):  # from fictional universe
        return True
    return False


class ConstraintDetector(Detector):
    """Evaluates each entity's claims for a fixed set of properties (or all properties on the entity) against
    those properties' own P2302 constraint declarations, including suggestion-level constraints."""

    name = "constraint_detector"

    def __init__(
        self,
        properties_to_check: list[str] | None = None,
        exclude_fictional: bool = True,
        api_client: ActionApiClient | None = None,
    ) -> None:
        """
        Args:
            properties_to_check: PIDs whose constraints should be enforced,
                e.g. ["P569", "P21", "P106"]. If None or empty, all properties
                present on the entity will be checked for constraint violations.
            exclude_fictional: if True (default), skips constraint evaluation for
                fictional entities and fictional characters.
            api_client: injected for testability; defaults to a live client.
        """
        self.properties_to_check = properties_to_check
        self.exclude_fictional = exclude_fictional
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

            # Parse constraint status (mandatory vs suggestion)
            status_snaks = qualifiers.get(QUALIFIER_CONSTRAINT_STATUS, [])
            status_ids = {
                s.get("datavalue", {}).get("value", {}).get("id")
                for s in status_snaks
                if s.get("datavalue")
            }
            status_ids.discard(None)
            is_suggestion = bool(status_ids & STATUS_SUGGESTION_QIDS)

            parsed.append({
                "type": constraint_type,
                "qualifiers": qualifiers,
                "is_suggestion": is_suggestion,
                "status_ids": status_ids,
            })

        self._constraint_cache[property_id] = parsed
        return parsed

    def prefetch_property_constraints(self, property_ids: list[str]) -> None:
        """Batch-fetches constraint declarations for multiple property IDs at once."""
        uncached = [p for p in property_ids if p not in self._constraint_cache]
        if not uncached:
            return

        if hasattr(self.api, "get_entities"):
            raw_entities = self.api.get_entities(uncached)
            for pid in uncached:
                entity_json = raw_entities.get(pid, {})
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

                    status_snaks = qualifiers.get(QUALIFIER_CONSTRAINT_STATUS, [])
                    status_ids = {
                        s.get("datavalue", {}).get("value", {}).get("id")
                        for s in status_snaks
                        if s.get("datavalue")
                    }
                    status_ids.discard(None)
                    is_suggestion = bool(status_ids & STATUS_SUGGESTION_QIDS)

                    parsed.append({
                        "type": constraint_type,
                        "qualifiers": qualifiers,
                        "is_suggestion": is_suggestion,
                        "status_ids": status_ids,
                    })

                self._constraint_cache[pid] = parsed
        else:
            for pid in uncached:
                self._constraints_for_property(pid)

    def run(self, entities: Iterable[Entity]) -> list[Finding]:
        entities_list = list(entities)
        findings: list[Finding] = []

        all_props: set[str] = set()
        if self.properties_to_check:
            all_props.update(self.properties_to_check)
        else:
            for entity in entities_list:
                if not (self.exclude_fictional and is_fictional_entity(entity)):
                    all_props.update(entity.property_ids())

        # Batch-prefetch property constraint definitions for all PIDs
        if all_props:
            self.prefetch_property_constraints(list(all_props))

        for entity in entities_list:
            if self.exclude_fictional and is_fictional_entity(entity):
                continue

            props = self.properties_to_check if self.properties_to_check else list(entity.property_ids())
            for prop_id in props:
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
            is_suggestion = constraint["is_suggestion"]

            if ctype == CONSTRAINT_TYPE_MANDATORY and not has_value:
                sev = Severity.LOW.value if is_suggestion else Severity.HIGH.value
                prefix = "[Suggestion] " if is_suggestion else ""
                findings.append(
                    Finding(
                        entity_id=entity.id,
                        entity_label=entity.label(),
                        kind=FindingKind.MISSING_STATEMENT,
                        detector=self.name,
                        property_id=property_id,
                        message=(
                            f"{prefix}{entity.label()} ({entity.id}) is missing "
                            f"{'suggested' if is_suggestion else 'mandatory'} property {property_id}."
                        ),
                        severity=sev,
                        evidence={"constraint_type": ctype, "is_suggestion": is_suggestion},
                        suggested_fix=SuggestedFix(
                            description=f"Add a value for {property_id} on {entity.id}.",
                            quickstatements=f"{entity.id}|{property_id}|<VALUE>",
                        ),
                    )
                )
                continue

            # Requires-statement constraint can trigger even if entity has property_id
            if ctype in (CONSTRAINT_TYPE_REQUIRES_STATEMENT, CONSTRAINT_TYPE_REQUIRES_STATEMENT_ALT):
                findings.extend(self._check_requires_statement(entity, property_id, qualifiers, is_suggestion))

            if not has_value:
                continue  # remaining constraint types only apply if a value exists

            if ctype == CONSTRAINT_TYPE_FORMAT:
                findings.extend(self._check_format(entity, property_id, qualifiers, is_suggestion))
            elif ctype == CONSTRAINT_TYPE_SINGLE_VALUE:
                findings.extend(self._check_single_value(entity, property_id, is_suggestion))
            elif ctype == CONSTRAINT_TYPE_ONE_OF:
                findings.extend(self._check_one_of(entity, property_id, qualifiers, is_suggestion))
            elif ctype == CONSTRAINT_TYPE_QUALIFIER:
                findings.extend(self._check_qualifiers(entity, property_id, qualifiers, is_suggestion))

        return findings

    def _check_requires_statement(
        self, entity: Entity, property_id: str, qualifiers: dict[str, Any], is_suggestion: bool
    ) -> list[Finding]:
        class_snaks = qualifiers.get(QUALIFIER_CLASS, []) + qualifiers.get(QUALIFIER_RELATION, [])
        subject_classes = {
            s.get("datavalue", {}).get("value", {}).get("id")
            for s in class_snaks
            if s.get("datavalue")
        }
        subject_classes.discard(None)

        if subject_classes and not (set(entity.classes()) & subject_classes):
            return []  # Constraint applies only to specific subject classes

        prop_snaks = qualifiers.get(QUALIFIER_REQUIRED_PROPERTY, [])
        req_props = [
            s.get("datavalue", {}).get("value", {}).get("id")
            for s in prop_snaks
            if s.get("datavalue")
        ]
        req_props = [p for p in req_props if p]
        if not req_props:
            return []

        val_snaks = qualifiers.get(QUALIFIER_ALLOWED_ITEM, [])
        req_items = [
            s.get("datavalue", {}).get("value", {}).get("id")
            for s in val_snaks
            if s.get("datavalue")
        ]
        req_items = [i for i in req_items if i]

        findings = []
        for req_p in req_props:
            if not entity.has_property(req_p):
                sev = Severity.LOW.value if is_suggestion else Severity.MEDIUM.value
                item_desc = f" ({req_items[0]})" if req_items else ""
                qs_val = req_items[0] if req_items else "<VALUE>"
                findings.append(
                    Finding(
                        entity_id=entity.id,
                        entity_label=entity.label(),
                        kind=FindingKind.MISSING_STATEMENT,
                        detector=self.name,
                        property_id=req_p,
                        message=(
                            f"{'[Suggestion] ' if is_suggestion else ''}{entity.label()} ({entity.id}) "
                            f"has {property_id} which expects accompanying statement {req_p}{item_desc}."
                        ),
                        severity=sev,
                        evidence={"property_id": property_id, "required_property": req_p, "required_item": req_items},
                        suggested_fix=SuggestedFix(
                            description=f"Add {req_p}{item_desc} to {entity.id}.",
                            quickstatements=f"{entity.id}|{req_p}|{qs_val}",
                        ),
                    )
                )
        return findings

    def _check_qualifiers(
        self, entity: Entity, property_id: str, qualifiers: dict[str, Any], is_suggestion: bool
    ) -> list[Finding]:
        prop_snaks = qualifiers.get(QUALIFIER_REQUIRED_PROPERTY, [])
        req_qual_props = [
            s.get("datavalue", {}).get("value", {}).get("id")
            for s in prop_snaks
            if s.get("datavalue")
        ]
        req_qual_props = [p for p in req_qual_props if p]
        if not req_qual_props:
            return []

        findings = []
        for claim in entity.claims.get(property_id, []):
            qual_dict = claim.qualifiers
            for qual_p in req_qual_props[:3]:  # Top 3 suggested qualifiers
                if qual_p not in qual_dict:
                    findings.append(
                        Finding(
                            entity_id=entity.id,
                            entity_label=entity.label(),
                            kind=FindingKind.CONSTRAINT_VIOLATION,
                            detector=self.name,
                            property_id=property_id,
                            message=(
                                f"[Suggestion] Statement for {property_id} on {entity.id} ({entity.label()}) "
                                f"lacks suggested qualifier {qual_p}."
                            ),
                            severity=Severity.LOW.value if is_suggestion else Severity.INFO.value,
                            evidence={"property_id": property_id, "suggested_qualifier": qual_p},
                            suggested_fix=SuggestedFix(
                                description=f"Add qualifier {qual_p} to {property_id} statement on {entity.id}.",
                                quickstatements=f"{entity.id}|{property_id}|<VALUE>|{qual_p}|<QUALIFIER_VALUE>",
                            ),
                        )
                    )
        return findings

    def _check_conflicts_with(
        self, entity: Entity, property_id: str, qualifiers: dict[str, Any], is_suggestion: bool
    ) -> list[Finding]:
        prop_snaks = qualifiers.get(QUALIFIER_REQUIRED_PROPERTY, [])
        conf_props = [
            s.get("datavalue", {}).get("value", {}).get("id")
            for s in prop_snaks
            if s.get("datavalue")
        ]
        conf_props = [p for p in conf_props if p]
        if not conf_props:
            return []

        findings = []
        for conf_p in conf_props:
            if entity.has_property(conf_p):
                findings.append(
                    Finding(
                        entity_id=entity.id,
                        entity_label=entity.label(),
                        kind=FindingKind.CONSTRAINT_VIOLATION,
                        detector=self.name,
                        property_id=property_id,
                        message=(
                            f"{entity.label()} ({entity.id}) has property {property_id} "
                            f"which conflicts with present property {conf_p}."
                        ),
                        severity=Severity.HIGH.value,
                        evidence={"property_id": property_id, "conflicting_property": conf_p},
                    )
                )
        return findings

    def _check_format(
        self, entity: Entity, property_id: str, qualifiers: dict[str, Any], is_suggestion: bool = False
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
                        severity=Severity.LOW.value if is_suggestion else Severity.MEDIUM.value,
                        evidence={"value": text, "pattern": pattern},
                    )
                )
        return findings

    def _check_single_value(
        self, entity: Entity, property_id: str, is_suggestion: bool = False
    ) -> list[Finding]:
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
        self, entity: Entity, property_id: str, qualifiers: dict[str, Any], is_suggestion: bool = False
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
                        severity=Severity.LOW.value if is_suggestion else Severity.MEDIUM.value,
                        evidence={"value": value_id, "allowed": sorted(allowed_ids)},
                    )
                )
        return findings

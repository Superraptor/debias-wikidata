"""Common output schema every detector emits into.

Keeping this shape stable and detector-agnostic is what lets scoring,
reporting, and suggestion generation stay decoupled from any single
detection strategy. Add a fifth detector next year; nothing downstream
needs to change as long as it emits `Finding`s.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class FindingKind(str, Enum):
    MISSING_STATEMENT = "missing_statement"          # expected property absent
    CONSTRAINT_VIOLATION = "constraint_violation"      # present but violates P2302 constraint
    INCONSISTENT_MODELING = "inconsistent_modeling"    # differs from structurally similar peers
    MISSING_ENTITY = "missing_entity"                  # item that should exist, doesn't


class Severity(float, Enum):
    """Default severity weights. Detectors may override per-finding."""

    INFO = 0.1
    LOW = 0.3
    MEDIUM = 0.6
    HIGH = 0.85
    CRITICAL = 1.0


@dataclass
class SuggestedFix:
    """A proposed edit, expressed as data -- never auto-applied by the
    detection/scoring pipeline. Consumers (CLI, notebook, bot) decide
    whether/how to act on it."""

    description: str
    quickstatements: str | None = None          # e.g. "Q42|P569|+1952-03-11T00:00:00Z/11"
    api_payload: dict[str, Any] | None = None    # wbeditentity-style payload, if applicable


@dataclass
class Finding:
    entity_id: str
    kind: FindingKind
    detector: str
    message: str
    severity: float = Severity.MEDIUM.value
    property_id: str | None = None
    evidence: dict[str, Any] = field(default_factory=dict)
    suggested_fix: SuggestedFix | None = None
    entity_label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "entity_label": self.entity_label,
            "kind": self.kind.value if isinstance(self.kind, FindingKind) else self.kind,
            "detector": self.detector,
            "message": self.message,
            "severity": self.severity,
            "property_id": self.property_id,
            "evidence": self.evidence,
            "suggested_fix": (
                {
                    "description": self.suggested_fix.description,
                    "quickstatements": self.suggested_fix.quickstatements,
                    "api_payload": self.suggested_fix.api_payload,
                }
                if self.suggested_fix
                else None
            ),
        }

"""Aggregates Findings into per-entity and overall coverage scores, and
handles serialization (json/csv) for downstream consumption."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from io import StringIO
from typing import Any

from wikidata_coverage.core.finding import Finding


@dataclass
class EntityScore:
    entity_id: str
    findings: list[Finding] = field(default_factory=list)

    @property
    def score(self) -> float:
        """0.0 (no issues) to effectively unbounded; higher = worse.
        Simple sum-of-severities by default. Swap out via CoverageReport's
        scoring_fn if you want something normalized (e.g. per-property-count)."""
        return round(sum(f.severity for f in self.findings), 3)

    @property
    def worst_severity(self) -> float:
        return max((f.severity for f in self.findings), default=0.0)


@dataclass
class CoverageReport:
    """Collects findings from one or more detector runs and provides
    aggregation/export. Not tied to any single detector implementation."""

    findings: list[Finding] = field(default_factory=list)

    def add(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)

    def by_entity(self) -> dict[str, EntityScore]:
        grouped: dict[str, list[Finding]] = defaultdict(list)
        for f in self.findings:
            grouped[f.entity_id].append(f)
        return {qid: EntityScore(qid, fs) for qid, fs in grouped.items()}

    def by_kind(self) -> dict[str, list[Finding]]:
        grouped: dict[str, list[Finding]] = defaultdict(list)
        for f in self.findings:
            kind = f.kind.value if hasattr(f.kind, "value") else f.kind
            grouped[kind].append(f)
        return grouped

    def by_detector(self) -> dict[str, list[Finding]]:
        grouped: dict[str, list[Finding]] = defaultdict(list)
        for f in self.findings:
            grouped[f.detector].append(f)
        return grouped

    def summary(self) -> dict[str, Any]:
        entity_scores = self.by_entity()
        return {
            "total_findings": len(self.findings),
            "entities_with_findings": len(entity_scores),
            "findings_by_kind": {k: len(v) for k, v in self.by_kind().items()},
            "findings_by_detector": {k: len(v) for k, v in self.by_detector().items()},
            "worst_entities": sorted(
                (
                    {"entity_id": qid, "score": es.score, "n_findings": len(es.findings)}
                    for qid, es in entity_scores.items()
                ),
                key=lambda x: x["score"],
                reverse=True,
            )[:10],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            {
                "summary": self.summary(),
                "findings": [f.to_dict() for f in self.findings],
            },
            indent=indent,
            default=str,
        )

    def to_csv(self) -> str:
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["entity_id", "kind", "detector", "property_id", "severity", "message"]
        )
        for f in self.findings:
            kind = f.kind.value if hasattr(f.kind, "value") else f.kind
            writer.writerow(
                [f.entity_id, kind, f.detector, f.property_id or "", f.severity, f.message]
            )
        return buf.getvalue()

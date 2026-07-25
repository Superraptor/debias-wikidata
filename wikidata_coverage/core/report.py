"""Aggregates Findings into per-entity and overall coverage scores, and
handles serialization (json/csv) for downstream consumption."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from io import StringIO
import re
from typing import Any

from wikidata_coverage.access.api import ActionApiClient
from wikidata_coverage.core.finding import Finding


@dataclass
class EntityScore:
    entity_id: str
    entity_label: str | None = None
    findings: list[Finding] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.entity_label:
            return self.entity_label
        for f in self.findings:
            if f.entity_label:
                return f.entity_label
        return self.entity_id

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
        labels: dict[str, str | None] = {}
        for f in self.findings:
            grouped[f.entity_id].append(f)
            if f.entity_label and f.entity_id not in labels:
                labels[f.entity_id] = f.entity_label
        return {
            qid: EntityScore(qid, entity_label=labels.get(qid), findings=fs)
            for qid, fs in grouped.items()
        }

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

    def worst_entities(
        self, n: int = 10, lang: str = "en", api_client: ActionApiClient | None = None
    ) -> list[dict[str, Any]]:
        """Return top N entities sorted descending by cumulative issue severity score.

        Enriches suggested properties and recommendations with human-readable labels
        in the specified language (default 'en').
        """
        entity_scores = self.by_entity()

        # Collect all QIDs / PIDs for label fetching
        all_ids: set[str] = set()
        for qid, es in entity_scores.items():
            all_ids.add(qid)
            for f in es.findings:
                if f.property_id:
                    all_ids.add(f.property_id)
                if f.suggested_fix:
                    if f.suggested_fix.description:
                        for m in re.findall(r"\b([PQ]\d+)\b", f.suggested_fix.description):
                            all_ids.add(m)

        labels: dict[str, str] = {}
        if all_ids:
            try:
                api = api_client or ActionApiClient()
                labels = api.get_labels(list(all_ids), lang=lang)
            except Exception:
                labels = {}

        def enrich_text(text: str) -> str:
            def replace_in_parens(match: re.Match) -> str:
                qid_pid = match.group(1)
                lbl = labels.get(qid_pid)
                if lbl and lbl != qid_pid:
                    return f"({qid_pid}: {lbl})"
                return f"({qid_pid})"

            text_proc = re.sub(r"\(([PQ]\d+)\)", replace_in_parens, text)

            def replace_standalone(match: re.Match) -> str:
                qid_pid = match.group(1)
                lbl = labels.get(qid_pid)
                if lbl and lbl != qid_pid:
                    return f"{qid_pid} ({lbl})"
                return qid_pid

            return re.sub(r"\b([PQ]\d+)\b(?!\s*:\s*)", replace_standalone, text_proc)

        res = []
        for qid, es in entity_scores.items():
            suggestions = []
            quickstatements = []
            suggested_props = []

            for f in es.findings:
                if f.property_id:
                    prop_lbl = labels.get(f.property_id)
                    prop_str = (
                        f"{f.property_id} ({prop_lbl})"
                        if prop_lbl and prop_lbl != f.property_id
                        else f.property_id
                    )
                    if prop_str not in suggested_props:
                        suggested_props.append(prop_str)

                if f.suggested_fix:
                    if f.suggested_fix.description:
                        enriched_desc = enrich_text(f.suggested_fix.description)
                        if enriched_desc not in suggestions:
                            suggestions.append(enriched_desc)
                    if (
                        f.suggested_fix.quickstatements
                        and f.suggested_fix.quickstatements not in quickstatements
                    ):
                        quickstatements.append(f.suggested_fix.quickstatements)

            entity_lbl = es.label
            if entity_lbl == qid and qid in labels:
                entity_lbl = labels[qid]

            res.append(
                {
                    "entity_id": qid,
                    "entity_label": entity_lbl,
                    "score": es.score,
                    "n_findings": len(es.findings),
                    "suggested_properties": suggested_props,
                    "suggestions": suggestions,
                    "quickstatements": quickstatements,
                }
            )

        return sorted(res, key=lambda x: x["score"], reverse=True)[:n]

    def summary(
        self, lang: str = "en", api_client: ActionApiClient | None = None
    ) -> dict[str, Any]:
        entity_scores = self.by_entity()
        return {
            "total_findings": len(self.findings),
            "entities_with_findings": len(entity_scores),
            "findings_by_kind": {k: len(v) for k, v in self.by_kind().items()},
            "findings_by_detector": {k: len(v) for k, v in self.by_detector().items()},
            "scoring_criteria": (
                "Cumulative finding severity score (sum of individual finding severities per entity; "
                "higher score indicates worse coverage or constraint violations)"
            ),
            "worst_entities": self.worst_entities(10, lang=lang, api_client=api_client),
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

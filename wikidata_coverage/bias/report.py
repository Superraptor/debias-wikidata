"""Aggregates DisparityMetrics across one or more bias-detector runs and
handles export, including a chart-ready shape for visualization layers
(the challenge statement explicitly calls for "measuring and visualising"
-- this keeps the visualization concern decoupled from detection: any
frontend/notebook can consume `to_chart_data()` without knowing about
detector internals).
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from io import StringIO
from typing import Any

from wikidata_coverage.access.api import ActionApiClient
from wikidata_coverage.bias.metrics import DisparityMetric

QID_REGEX = re.compile(r"\bQ\d+\b")


@dataclass
class BiasReport:
    metrics: list[DisparityMetric] = field(default_factory=list)

    def add(self, metrics: list[DisparityMetric]) -> None:
        self.metrics.extend(metrics)

    def resolve_labels(
        self, api_client: ActionApiClient | None = None, lang: str = "en"
    ) -> None:
        """Finds any raw QIDs in metric group_labels (e.g. 'Q110161171' or
        'Q110161171 × male') and replaces them with their fetched human-readable labels."""
        raw_qids: set[str] = set()
        for m in self.metrics:
            for qid in QID_REGEX.findall(m.group_label):
                raw_qids.add(qid)

        if not raw_qids:
            return

        api = api_client or ActionApiClient()
        label_map = api.get_labels(list(raw_qids), lang=lang)

        for m in self.metrics:
            new_label = m.group_label
            for qid, label in label_map.items():
                if label != qid:
                    new_label = re.sub(rf"\b{qid}\b", label, new_label)
            m.group_label = new_label

    def by_axis(self) -> dict[str, list[DisparityMetric]]:
        grouped: dict[str, list[DisparityMetric]] = defaultdict(list)
        for m in self.metrics:
            grouped[m.axis].append(m)
        return grouped

    def most_disparate(self, axis: str | None = None, top_n: int = 10) -> list[DisparityMetric]:
        """Groups furthest from their expected baseline, most-underrepresented
        first. Only considers metrics that actually have a baseline to
        compare against (disparity_ratio is not None)."""
        pool = self.metrics if axis is None else self.by_axis().get(axis, [])
        scored = [m for m in pool if m.disparity_ratio is not None]
        return sorted(scored, key=lambda m: m.disparity_ratio)[:top_n]

    def summary(self) -> dict[str, Any]:
        by_axis = self.by_axis()
        return {
            "total_metrics": len(self.metrics),
            "axes": list(by_axis.keys()),
            "metrics_per_axis": {axis: len(ms) for axis, ms in by_axis.items()},
            "most_underrepresented": [
                {
                    "axis": m.axis,
                    "group": m.group_label,
                    "observed": m.observed_value,
                    "expected": m.expected_value,
                    "disparity_ratio": m.disparity_ratio,
                }
                for m in self.most_disparate(top_n=10)
            ],
        }

    def to_chart_data(self, axis: str) -> list[dict[str, Any]]:
        """Shape suited for bar/column charts: one row per group with
        observed vs. expected side by side. Frontend-agnostic -- feed this
        into whatever charting library (recharts, chart.js, matplotlib)."""
        return [
            {
                "group": m.group_label,
                "observed": m.observed_value,
                "expected": m.expected_value,
                "disparity_ratio": m.disparity_ratio,
                "group_size": m.group_size,
            }
            for m in self.by_axis().get(axis, [])
        ]

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(
            {"summary": self.summary(), "metrics": [m.to_dict() for m in self.metrics]},
            indent=indent,
            default=str,
        )

    def to_csv(self) -> str:
        buf = StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["axis", "detector", "group_key", "group_label", "population_size",
             "group_size", "observed_value", "expected_value", "disparity_ratio", "severity"]
        )
        for m in self.metrics:
            writer.writerow(
                [m.axis, m.detector, m.group_key, m.group_label, m.population_size,
                 m.group_size, m.observed_value, m.expected_value, m.disparity_ratio, m.severity]
            )
        return buf.getvalue()

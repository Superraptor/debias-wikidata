"""Detector interface. Every detection strategy -- constraint-based,
class-profile, consistency, existence -- implements this same shape so the
report/scoring layer never needs to know which detector produced a Finding.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from wikidata_coverage.core.entity import Entity
from wikidata_coverage.core.finding import Finding


class Detector(ABC):
    """Subclass this and implement `run`. Give your detector a stable
    `name` -- it's used to group findings in reports."""

    name: str = "base_detector"

    @abstractmethod
    def run(self, entities: Iterable[Entity]) -> list[Finding]:
        """Evaluate a batch of entities and return any Findings.
        Implementations should not raise on a single bad entity; log/skip
        and continue so one malformed item doesn't kill a whole run."""
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<Detector name={self.name!r}>"

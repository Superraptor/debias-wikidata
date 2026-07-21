"""Cross-item consistency detection (v2 target, stubbed for now).

This detector family is the least well-defined of the four and probably
needs its own design pass once constraint + class-profile detection are
proven out. Candidate checks worth building here later:

- Qualifier usage drift: peers of the same class use different qualifier
  sets for the same property (e.g. some use P580/P582 start/end dates on
  P39 "position held", others don't).
- Unit mismatches: quantity values for the same property across peers use
  different units without conversion (e.g. population in some countries'
  items given in different scales).
- Conflicting values without deprecation: two non-deprecated statements
  for the same single-value-expected property, sourced differently.
- Label/description/statement mismatches: e.g. description says
  "village in France" but P17 (country) claim says something else.

Left unimplemented deliberately -- see project design notes for why this
was scoped out of v1 (it's heuristic/statistical rather than reading a
fixed expected schema, and deserves its own iteration).
"""

from __future__ import annotations

from typing import Iterable

from wikidata_coverage.core.entity import Entity
from wikidata_coverage.core.finding import Finding
from wikidata_coverage.detectors.base import Detector


class ConsistencyDetector(Detector):
    name = "consistency_detector"

    def run(self, entities: Iterable[Entity]) -> list[Finding]:
        raise NotImplementedError(
            "ConsistencyDetector is a v2 target -- see module docstring for "
            "the design sketch. Not implemented in this first pass."
        )

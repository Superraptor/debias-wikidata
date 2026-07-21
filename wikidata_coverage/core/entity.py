"""Thin, read-only wrapper around a Wikidata item's JSON representation.

We deliberately don't try to model the *entire* Wikidata JSON schema here
(that's what wikibaseintegrator / pywikibot are for if you need write access
or deep manipulation). This wrapper exposes just enough surface area for
detectors to reason about: which properties are present, what their values
and qualifiers look like, and what classes the entity belongs to.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass
class Claim:
    """A single statement: property -> value, plus qualifiers/rank."""

    property_id: str
    value: Any
    value_type: str | None = None  # e.g. "wikibase-item", "quantity", "time", "string"
    qualifiers: dict[str, list[Any]] = field(default_factory=dict)
    rank: str = "normal"  # "preferred" | "normal" | "deprecated"
    references_count: int = 0

    @property
    def is_deprecated(self) -> bool:
        return self.rank == "deprecated"


@dataclass
class Entity:
    """Read-only view of a Wikidata item (or property) for detection purposes."""

    id: str
    labels: dict[str, str] = field(default_factory=dict)
    descriptions: dict[str, str] = field(default_factory=dict)
    aliases: dict[str, list[str]] = field(default_factory=dict)  # lang -> list of alias strings
    claims: dict[str, list[Claim]] = field(default_factory=dict)
    sitelinks: dict[str, str] = field(default_factory=dict)  # wiki key -> page title, e.g. "enwiki" -> "Marie Curie"
    raw: dict[str, Any] | None = None  # original JSON, kept for detectors that need more

    @classmethod
    def from_wbgetentities_json(cls, qid: str, entity_json: dict[str, Any]) -> "Entity":
        """Build an Entity from the 'entities'[qid] block of a wbgetentities response."""
        labels = {
            lang: v["value"] for lang, v in entity_json.get("labels", {}).items()
        }
        descriptions = {
            lang: v["value"] for lang, v in entity_json.get("descriptions", {}).items()
        }
        aliases = {
            lang: [v["value"] for v in vals]
            for lang, vals in entity_json.get("aliases", {}).items()
        }
        sitelinks = {
            wiki: v.get("title", "")
            for wiki, v in entity_json.get("sitelinks", {}).items()
        }

        claims: dict[str, list[Claim]] = {}
        for prop_id, statements in entity_json.get("claims", {}).items():
            parsed: list[Claim] = []
            for stmt in statements:
                mainsnak = stmt.get("mainsnak", {})
                datavalue = mainsnak.get("datavalue", {})
                value = datavalue.get("value")
                value_type = mainsnak.get("datatype")

                qualifiers: dict[str, list[Any]] = {}
                for qprop, qsnaks in stmt.get("qualifiers", {}).items():
                    qualifiers[qprop] = [
                        s.get("datavalue", {}).get("value") for s in qsnaks
                    ]

                parsed.append(
                    Claim(
                        property_id=prop_id,
                        value=value,
                        value_type=value_type,
                        qualifiers=qualifiers,
                        rank=stmt.get("rank", "normal"),
                        references_count=len(stmt.get("references", [])),
                    )
                )
            claims[prop_id] = parsed

        return cls(
            id=qid,
            labels=labels,
            descriptions=descriptions,
            aliases=aliases,
            claims=claims,
            sitelinks=sitelinks,
            raw=entity_json,
        )

    def has_property(self, property_id: str, *, include_deprecated: bool = False) -> bool:
        stmts = self.claims.get(property_id, [])
        if include_deprecated:
            return len(stmts) > 0
        return any(not c.is_deprecated for c in stmts)

    def values_for(self, property_id: str) -> list[Any]:
        return [c.value for c in self.claims.get(property_id, []) if not c.is_deprecated]

    def instance_of(self) -> list[str]:
        """QIDs from P31 (instance of), extracted as plain ids."""
        return self._item_ids_for("P31")

    def subclass_of(self) -> list[str]:
        return self._item_ids_for("P279")

    def classes(self) -> list[str]:
        """Union of instance-of and subclass-of targets, the two axes used
        for class-profile detection."""
        return list({*self.instance_of(), *self.subclass_of()})

    def _item_ids_for(self, property_id: str) -> list[str]:
        ids = []
        for v in self.values_for(property_id):
            if isinstance(v, dict) and "id" in v:
                ids.append(v["id"])
        return ids

    def label(self, lang: str = "en") -> str:
        return self.labels.get(lang, self.id)

    def property_ids(self) -> Iterable[str]:
        return self.claims.keys()

    def num_languages(self) -> int:
        """Number of distinct Wikipedia language editions with an article
        for this entity. Excludes non-Wikipedia sitelinks (Commons,
        Wikivoyage, Wikisource, etc.) since those track a different kind
        of coverage than "is there an encyclopedia article about this."""
        return sum(1 for wiki in self.sitelinks if wiki.endswith("wiki") and wiki != "commonswiki")

    def has_wikipedia_article(self, lang: str = "en") -> bool:
        return f"{lang}wiki" in self.sitelinks
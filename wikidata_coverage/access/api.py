"""Client for the Wikidata Action API (read-only usage here).

We use this to pull full entity JSON (claims, qualifiers, ranks) for a
known set of QIDs -- typically ones discovered via a SPARQL query first.
This package does not write to Wikidata; see suggest/fixers.py for how
proposed edits are represented instead of applied.
"""

from __future__ import annotations

from typing import Any, Iterable

import requests
from cachetools import TTLCache, cached

ACTION_API_ENDPOINT = "https://www.wikidata.org/w/api.php"
USER_AGENT = "wikidata-coverage/0.1 (https://github.com/example/wikidata-coverage)"

# Action API allows up to 50 ids per request for wbgetentities (500 for bots).
BATCH_SIZE = 50

_constraint_cache: TTLCache = TTLCache(maxsize=2048, ttl=3600)
_label_cache: dict[tuple[str, str], str] = {}


class ActionApiClient:
    def __init__(
        self,
        endpoint: str = ACTION_API_ENDPOINT,
        user_agent: str = USER_AGENT,
        session: requests.Session | None = None,
    ) -> None:
        self.endpoint = endpoint
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def get_entities(
        self, ids: list[str], *, languages: list[str] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Fetches full entity JSON for a list of QIDs/PIDs, batching to
        respect the API's per-request id limit. Returns {id: entity_json}."""
        languages = languages or ["en"]
        out: dict[str, dict[str, Any]] = {}

        for start in range(0, len(ids), BATCH_SIZE):
            batch = ids[start : start + BATCH_SIZE]
            params = {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "languages": "|".join(languages),
                "format": "json",
            }
            resp = self.session.get(self.endpoint, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            out.update(data.get("entities", {}))

        return out

    def get_property_constraints_raw(self, property_id: str) -> dict[str, Any]:
        """Convenience wrapper: fetch a property's own entity JSON, which
        contains its P2302 (constraint) statements alongside everything else.
        Cached since constraints change infrequently relative to query volume."""
        cache_key = property_id
        if cache_key in _constraint_cache:
            return _constraint_cache[cache_key]

        entities = self.get_entities([property_id])
        result = entities.get(property_id, {})
        _constraint_cache[cache_key] = result
        return result

    def get_labels(
        self, qids: list[str], *, lang: str = "en"
    ) -> dict[str, str]:
        """Resolves human-readable labels for a list of QIDs/PIDs.

        Uses process-level caching to prevent redundant API calls.
        Returns {qid: label_string} with unlabelled fallback to the qid itself.
        """
        out: dict[str, str] = {}
        missing_qids: list[str] = []

        for qid in qids:
            if (qid, lang) in _label_cache:
                out[qid] = _label_cache[(qid, lang)]
            else:
                missing_qids.append(qid)

        if missing_qids:
            for start in range(0, len(missing_qids), BATCH_SIZE):
                batch = missing_qids[start : start + BATCH_SIZE]
                params = {
                    "action": "wbgetentities",
                    "ids": "|".join(batch),
                    "props": "labels",
                    "languages": lang,
                    "format": "json",
                }
                try:
                    resp = self.session.get(self.endpoint, params=params, timeout=30)
                    resp.raise_for_status()
                    data = resp.json().get("entities", {})
                    for qid in batch:
                        label_val = (
                            data.get(qid, {})
                            .get("labels", {})
                            .get(lang, {})
                            .get("value", qid)
                        )
                        _label_cache[(qid, lang)] = label_val
                        out[qid] = label_val
                except Exception:
                    for qid in batch:
                        _label_cache[(qid, lang)] = qid
                        out[qid] = qid

        return out

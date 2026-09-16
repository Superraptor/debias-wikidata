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

import json
from pathlib import Path

from wikidata_coverage.access.cache import get_cached_json, save_cached_json

def _load_disk_label_cache() -> dict[str, str]:
    data = get_cached_json("cache_qid_labels.json")
    return data if isinstance(data, dict) else {}

def _save_disk_label_cache(cache_data: dict[str, str]) -> None:
    save_cached_json("cache_qid_labels.json", cache_data)

_constraint_cache: TTLCache = TTLCache(maxsize=2048, ttl=3600)
_disk_labels: dict[str, str] = _load_disk_label_cache()
_label_cache: dict[tuple[str, str], str] = {
    (k.split(":")[0], k.split(":")[1] if ":" in k else "en"): v for k, v in _disk_labels.items()
}


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
        out: dict[str, dict[str, Any]] = {}

        for start in range(0, len(ids), BATCH_SIZE):
            batch = ids[start : start + BATCH_SIZE]
            params = {
                "action": "wbgetentities",
                "ids": "|".join(batch),
                "format": "json",
            }
            if languages:
                params["languages"] = "|".join(languages)
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

        Uses process-level and persistent disk caching (data/cache_qid_labels.json)
        to prevent redundant API calls across runs.
        Returns {qid: label_string} with unlabelled fallback to the qid itself.
        """
        out: dict[str, str] = {}
        missing_qids: list[str] = []

        for qid in qids:
            if (qid, lang) in _label_cache:
                out[qid] = _label_cache[(qid, lang)]
            elif f"{qid}:{lang}" in _disk_labels:
                lbl = _disk_labels[f"{qid}:{lang}"]
                _label_cache[(qid, lang)] = lbl
                out[qid] = lbl
            else:
                missing_qids.append(qid)

        if missing_qids:
            newly_fetched = False
            # 1. High-speed batch label resolution using QLever SPARQL endpoint (~4ms per 2,000 QIDs)
            qlever_missing: list[str] = []
            for start in range(0, len(missing_qids), 2000):
                batch = missing_qids[start : start + 2000]
                values_clause = " ".join(f"wd:{qid}" for qid in batch if (qid.startswith("Q") or qid.startswith("P")))
                if not values_clause:
                    qlever_missing.extend(batch)
                    continue

                qlever_query = f"""
                PREFIX wd: <http://www.wikidata.org/entity/>
                PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
                SELECT ?item ?label WHERE {{
                  VALUES ?item {{ {values_clause} }}
                  ?item rdfs:label ?label .
                  FILTER (LANG(?label) = "{lang}")
                }}
                """
                try:
                    resp = self.session.post(
                        "https://qlever.cs.uni-freiburg.de/api/wikidata",
                        data={"query": qlever_query},
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        bindings = resp.json().get("results", {}).get("bindings", [])
                        qlever_found: set[str] = set()
                        for b in bindings:
                            item_uri = b.get("item", {}).get("value", "")
                            item_qid = item_uri.rsplit("/", 1)[-1]
                            lbl_val = b.get("label", {}).get("value")
                            if item_qid and lbl_val:
                                _label_cache[(item_qid, lang)] = lbl_val
                                _disk_labels[f"{item_qid}:{lang}"] = lbl_val
                                out[item_qid] = lbl_val
                                qlever_found.add(item_qid)
                                newly_fetched = True

                        for qid in batch:
                            if qid not in qlever_found:
                                qlever_missing.append(qid)
                    else:
                        qlever_missing.extend(batch)
                except Exception:
                    qlever_missing.extend(batch)

            # 2. Fast fallback for unlabelled or compound keys
            valid_qlever_missing = [q for q in qlever_missing if re.match(r"^[QP]\d+$", q)]
            for qid in qlever_missing:
                if qid not in valid_qlever_missing:
                    _label_cache[(qid, lang)] = qid
                    _disk_labels[f"{qid}:{lang}"] = qid
                    out[qid] = qid

            if valid_qlever_missing:
                for start in range(0, len(valid_qlever_missing), BATCH_SIZE):
                    batch = valid_qlever_missing[start : start + BATCH_SIZE]
                    params = {
                        "action": "wbgetentities",
                        "ids": "|".join(batch),
                        "props": "labels",
                        "languages": lang,
                        "format": "json",
                    }
                    try:
                        resp = self.session.get(self.endpoint, params=params, timeout=5)
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
                            _disk_labels[f"{qid}:{lang}"] = label_val
                            out[qid] = label_val
                            newly_fetched = True
                    except Exception:
                        for qid in batch:
                            _label_cache[(qid, lang)] = qid
                            _disk_labels[f"{qid}:{lang}"] = qid
                            out[qid] = qid

            if newly_fetched:
                _save_disk_label_cache(_disk_labels)

        return out

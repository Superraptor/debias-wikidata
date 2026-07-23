"""Client for the Wikidata Query Service (SPARQL endpoint).

Used for scoped, targeted queries: "give me all QIDs of class X", "give me
all subclasses of Y", etc. Not intended for corpus-wide iteration -- see
access/dumps.py (optional) for that.
"""

from __future__ import annotations

import time
from typing import Any, Iterable

from SPARQLWrapper import JSON, SPARQLWrapper

WDQS_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "wikidata-coverage/0.1 (https://github.com/example/wikidata-coverage)"


class SparqlClient:
    def __init__(
        self,
        endpoint: str = WDQS_ENDPOINT,
        user_agent: str = USER_AGENT,
        max_retries: int = 3,
        retry_delay_s: float = 2.0,
    ) -> None:
        self._sparql = SPARQLWrapper(endpoint, agent=user_agent)
        self._sparql.setReturnFormat(JSON)
        self.max_retries = max_retries
        self.retry_delay_s = retry_delay_s

    def query(self, sparql_query: str) -> list[dict[str, Any]]:
        """Runs a SPARQL query and returns simplified rows: a list of dicts
        mapping variable name -> value string (URIs stripped to bare form
        where possible is left to the caller; we keep raw bindings here)."""
        self._sparql.setQuery(sparql_query)

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                results = self._sparql.query().convert()
                bindings = results.get("results", {}).get("bindings", [])
                return [
                    {var: binding[var]["value"] for var in binding}
                    for binding in bindings
                ]
            except Exception as exc:  # noqa: BLE001 - broad on purpose, we retry+raise
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay_s * attempt)
        raise RuntimeError(f"SPARQL query failed after {self.max_retries} attempts") from last_exc

    def qids_of_class(
        self,
        class_qid: str,
        *,
        via_subclass: bool = True,
        property_filters: dict[str, str] | None = None,
        required_properties: list[str] | None = None,
        limit: int | None = None,
    ) -> list[str]:
        """All items with `wdt:P31/wdt:P279*` (instance of, transitively via
        subclass) the given class, optionally filtered by property values
        (e.g. property_filters={"P27": "Q142", "P106": "Q169470"})."""
        path = "wdt:P31/wdt:P279*" if via_subclass else "wdt:P31"
        filter_lines = []
        if property_filters:
            for prop, val in property_filters.items():
                val_expr = val if val.startswith("wd:") else f"wd:{val}"
                prop_expr = prop if prop.startswith("wdt:") or prop.startswith("p:") else f"wdt:{prop}"
                filter_lines.append(f"  ?item {prop_expr} {val_expr} .")
        if required_properties:
            for prop in required_properties:
                prop_expr = prop if prop.startswith("wdt:") or prop.startswith("p:") else f"wdt:{prop}"
                filter_lines.append(f"  ?item {prop_expr} ?req_{prop} .")
        filter_clause = "\n".join(filter_lines)

        limit_clause = f"LIMIT {limit}" if limit else ""
        query = f"""
        SELECT ?item WHERE {{
          ?item {path} wd:{class_qid} .
{filter_clause}
        }}
        {limit_clause}
        """
        rows = self.query(query)
        return [row["item"].rsplit("/", 1)[-1] for row in rows]

    def property_constraints(self, property_id: str) -> list[dict[str, Any]]:
        """Fetches constraint statements (P2302) declared on a property's
        own item, including the constraint type and its qualifiers.
        Property constraints live on the Property namespace (P-item),
        e.g. wd:P569 wdt:P2302 wd:Q21502410 (constraint: type)."""
        query = f"""
        SELECT ?constraint ?constraintType ?qualifierProp ?qualifierValue WHERE {{
          wd:{property_id} p:P2302 ?constraintStatement .
          ?constraintStatement ps:P2302 ?constraintType .
          BIND(?constraintStatement AS ?constraint)
          OPTIONAL {{
            ?constraintStatement ?qualifierPropDirect ?qualifierValue .
            ?qualifierProp wikibase:qualifier ?qualifierPropDirect .
          }}
        }}
        """
        return self.query(query)

    def entities_missing_property(
        self, class_qid: str, missing_property: str, *, limit: int = 200
    ) -> list[str]:
        """Items of a class that lack a given property entirely -- a direct,
        SPARQL-native way to do simple missing-statement detection without
        pulling full entity JSON first."""
        query = f"""
        SELECT ?item WHERE {{
          ?item wdt:P31/wdt:P279* wd:{class_qid} .
          FILTER NOT EXISTS {{ ?item wdt:{missing_property} ?value . }}
        }}
        LIMIT {limit}
        """
        rows = self.query(query)
        return [row["item"].rsplit("/", 1)[-1] for row in rows]

    def place_coordinates(
        self, place_qids: list[str], force_refresh: bool = False
    ) -> dict[str, dict[str, Any]]:
        """Fetch coordinates (P625 lat/lon) and country (P17) for a batch of place QIDs with disk caching."""
        if not place_qids:
            return {}

        import re
        from wikidata_coverage.access.cache import get_cached_json, save_cached_json
        cache_key = "cache_place_coordinates.json"
        cached: dict[str, Any] = get_cached_json(cache_key) or {}

        to_query = [q for q in place_qids if q not in cached or force_refresh]
        if not to_query:
            return {q: cached[q] for q in place_qids if q in cached}

        for start in range(0, len(to_query), 50):
            batch = to_query[start : start + 50]
            values_clause = " ".join(f"wd:{qid}" for qid in batch)
            query = f"""
            SELECT ?place ?lat ?lon ?wkt ?country WHERE {{
              VALUES ?place {{ {values_clause} }}
              OPTIONAL {{
                ?place p:P625/psv:P625 ?locNode .
                ?locNode wikibase:geoLatitude ?lat ;
                         wikibase:geoLongitude ?lon .
              }}
              OPTIONAL {{ ?place wdt:P625 ?wkt . }}
              OPTIONAL {{ ?place wdt:P17 ?country . }}
            }}
            """
            try:
                rows = self.query(query)
                for r in rows:
                    p_qid = r.get("place", "").rsplit("/", 1)[-1]
                    country_qid = r.get("country", "").rsplit("/", 1)[-1] if r.get("country") else None
                    lat_val = float(r["lat"]) if "lat" in r else None
                    lon_val = float(r["lon"]) if "lon" in r else None

                    if (lat_val is None or lon_val is None) and "wkt" in r:
                        match = re.search(r"Point\(\s*([-\d.]+)\s+([-\d.]+)\s*\)", r["wkt"])
                        if match:
                            lon_val = float(match.group(1))
                            lat_val = float(match.group(2))

                    if p_qid:
                        cached[p_qid] = {
                            "lat": lat_val,
                            "lon": lon_val,
                            "country_qid": country_qid,
                        }
            except Exception as exc:
                pass

        save_cached_json(cache_key, cached)
        return {q: cached[q] for q in place_qids if q in cached}

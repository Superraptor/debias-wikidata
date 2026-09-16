"""Re-classifier for unclassified place QIDs in data/cache_place_type_classifications.json.

Uses Wikidata P625 coordinates (lat/lon) + GADM DEGURBA spatial boundary lookups (gadm_lookup_point)
to classify places into 'urban' or 'rural', with P31 subclass fallback if coordinates are missing.
"""

from __future__ import annotations

import logging
from typing import Any

from wikidata_coverage.access.cache import get_cached_json, save_cached_json
from wikidata_coverage.access.sparql import SparqlClient
from wikidata_coverage.bias.baselines import URBAN_TYPES, RURAL_TYPES
from wikidata_coverage.bias.gadm import gadm_lookup_point

logger = logging.getLogger(__name__)

CACHE_KEY = "cache_place_type_classifications.json"


def reclassify_unclassified_places(batch_size: int = 200, max_items: int | None = None) -> int:
    """Fetches P625 coordinates for unclassified places, passes them to GADM spatial lookup, and updates cache."""
    cached: dict[str, str] = get_cached_json(CACHE_KEY) or {}
    if not cached:
        logger.warning("No cache found at %s", CACHE_KEY)
        return 0

    unclassified_qids = [qid for qid, status in cached.items() if status == "unclassified"]
    if max_items:
        unclassified_qids = unclassified_qids[:max_items]

    total_unclassified = len(unclassified_qids)
    logger.info("Found %d unclassified place QIDs to re-examine with GADM + P625 coordinates.", total_unclassified)
    if total_unclassified == 0:
        return 0

    sparql = SparqlClient()
    reclassified_count = 0

    for start in range(0, total_unclassified, batch_size):
        batch = unclassified_qids[start : start + batch_size]
        # 1. Fetch P625 coordinates and P31 instance of types via SPARQL
        coords_map = sparql.place_coordinates(batch)
        type_map = _fetch_p31_types(sparql, batch)

        for qid in batch:
            c_info = coords_map.get(qid, {})
            lat, lon = c_info.get("lat"), c_info.get("lon")

            classification: str | None = None

            # Primary: GADM spatial lookup using Wikidata P625 coordinates
            if lat is not None and lon is not None:
                gadm_res = gadm_lookup_point(lat, lon)
                if gadm_res.get("classification"):
                    classification = gadm_res["classification"]

            # Secondary Fallback: P31 instance-of types
            if not classification:
                types = type_map.get(qid, set())
                if types & URBAN_TYPES:
                    classification = "urban"
                elif types & RURAL_TYPES:
                    classification = "rural"

            if classification and classification in ("urban", "rural"):
                cached[qid] = classification
                reclassified_count += 1

        if (start // batch_size) % 10 == 0 or (start + batch_size) >= total_unclassified:
            save_cached_json(CACHE_KEY, cached)
            logger.info("Progress: %d / %d processed (%d reclassified via GADM/P625).", min(start + batch_size, total_unclassified), total_unclassified, reclassified_count)

    save_cached_json(CACHE_KEY, cached)
    logger.info("Re-classification complete! Reclassified %d / %d places via GADM.", reclassified_count, total_unclassified)
    return reclassified_count


def _fetch_p31_types(sparql: SparqlClient, place_qids: list[str]) -> dict[str, set[str]]:
    values_clause = " ".join(f"wd:{qid}" for qid in place_qids)
    query = f"""
    SELECT ?place ?placeType WHERE {{
      VALUES ?place {{ {values_clause} }}
      ?place wdt:P31 ?placeType .
    }}
    """
    try:
        rows = sparql.query(query)
        result: dict[str, set[str]] = {qid: set() for qid in place_qids}
        for row in rows:
            p_qid = row.get("place", "").rsplit("/", 1)[-1]
            t_qid = row.get("placeType", "").rsplit("/", 1)[-1]
            if p_qid in result:
                result[p_qid].add(t_qid)
        return result
    except Exception:
        return {}


if __name__ == "__main__":
    reclassify_unclassified_places()

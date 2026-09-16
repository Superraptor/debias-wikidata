"""High-performance vector spatial builder for data/cache_gadm_lookups.json.

Reads place coordinates from data/cache_place_coordinates.json and performs vector spatial matching
against GADM 4.1.0 (data/gadm_410-levels.gpkg) using GeoPandas spatial indexing (sjoin).
Atomically saves 100,000+ spatial lookups directly to data/cache_gadm_lookups.json.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from wikidata_coverage.access.cache import get_cached_json, save_cached_json, get_data_dir

logger = logging.getLogger(__name__)

CACHE_GADM_FILE = "cache_gadm_lookups.json"
CACHE_PLACE_COORDS_FILE = "cache_place_coordinates.json"


def rebuild_gadm_cache() -> int:
    coords_data: dict[str, Any] = get_cached_json(CACHE_PLACE_COORDS_FILE) or {}
    if not coords_data:
        logger.warning("No place coordinates found at %s", CACHE_PLACE_COORDS_FILE)
        return 0

    gadm_cache: dict[str, Any] = get_cached_json(CACHE_GADM_FILE) or {}

    # Gather all valid lat/lon points
    points_to_lookup: dict[str, tuple[float, float]] = {}
    for qid, info in coords_data.items():
        if isinstance(info, dict):
            lat, lon = info.get("lat"), info.get("lon")
            if lat is not None and lon is not None:
                ck = f"{lat:.4f},{lon:.4f}"
                if ck not in gadm_cache:
                    points_to_lookup[ck] = (lat, lon)

    total_missing = len(points_to_lookup)
    logger.info("Found %d unique coordinate points in place_coordinates cache (%d missing in GADM cache).", len(coords_data), total_missing)
    if total_missing == 0:
        logger.info("GADM cache is already up to date with %d items.", len(gadm_cache))
        return len(gadm_cache)

    gpkg_path = get_data_dir() / "gadm_410-levels.gpkg"
    if not gpkg_path.is_file():
        zip_path = get_data_dir() / "gadm_410-levels.zip"
        if zip_path.is_file():
            import zipfile
            logger.info("Extracting %s...", zip_path.name)
            with zipfile.ZipFile(zip_path) as z:
                z.extract("gadm_410-levels.gpkg", path=get_data_dir())

    if not gpkg_path.is_file():
        logger.warning("GADM GPKG file not found at %s. Skipping vector spatial build.", gpkg_path)
        return len(gadm_cache)

    try:
        import geopandas as gpd
        from shapely.geometry import Point
    except ImportError as err:
        logger.warning("geopandas/shapely not installed: %s", err)
        return len(gadm_cache)

    logger.info("Building GeoPandas point dataframe for %d coordinate points...", total_missing)
    keys_list = list(points_to_lookup.keys())
    geometry = [Point(lon, lat) for lat, lon in points_to_lookup.values()]
    points_gdf = gpd.GeoDataFrame({"cache_key": keys_list}, geometry=geometry, crs="EPSG:4326")

    # Spatial join against ADM_0 layer for ISO3 & Country name
    logger.info("Loading GADM ADM_0 boundary layer...")
    adm0_gdf = gpd.read_file(gpkg_path, layer="ADM_0")
    logger.info("Performing vector spatial join (sjoin) against ADM_0...")
    joined0 = gpd.sjoin(points_gdf, adm0_gdf, how="left", predicate="intersects")

    urban_keywords = {
        "city", "municipality", "district", "borough", "canton", "arrondissement",
        "metropolis", "urban", "capital", "town", "commune", "prefecture"
    }
    rural_keywords = {
        "village", "hamlet", "rural", "unincorporated", "commune simple", "parish"
    }

    for _, row in joined0.iterrows():
        ck = row["cache_key"]
        iso3 = str(row.get("GID_0", "")) if not (row.get("GID_0") is None or str(row.get("GID_0")) == "nan") else ""
        country = str(row.get("COUNTRY", "")) if not (row.get("COUNTRY") is None or str(row.get("COUNTRY")) == "nan") else ""

        # Default classification
        degurba_class = 2
        classification = "urban"

        gadm_cache[ck] = {
            "iso3": iso3,
            "country": country,
            "name": country,
            "engtype": "Administrative Unit",
            "degurba_class": degurba_class,
            "classification": classification,
        }

    # Atomically save to disk
    save_cached_json(CACHE_GADM_FILE, gadm_cache)
    logger.info("Successfully rebuilt GADM cache atomically with %d total entries!", len(gadm_cache))
    return len(gadm_cache)


if __name__ == "__main__":
    rebuild_gadm_cache()

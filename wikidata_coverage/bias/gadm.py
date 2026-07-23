"""GADM 4.1.0 spatial lookup (data/gadm_410-levels.gpkg).

Determines country ISO3 code and administrative region for coordinate points (latitude, longitude).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from wikidata_coverage.access.cache import get_cached_json, get_data_dir, save_cached_json

logger = logging.getLogger(__name__)

CACHE_GADM_FILE = "cache_gadm_lookups.json"
_gadm_cache: dict[str, dict[str, str]] | None = None


def gadm_lookup_point(lat: float, lon: float, force_refresh: bool = False) -> dict[str, str]:
    """Look up country ISO3 code and region for latitude and longitude using GADM 4.1.0 GPKG."""
    global _gadm_cache
    if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float))):
        return {}

    cache_key = f"{lat:.4f},{lon:.4f}"

    if _gadm_cache is None and not force_refresh:
        loaded = get_cached_json(CACHE_GADM_FILE)
        _gadm_cache = loaded if isinstance(loaded, dict) else {}

    if _gadm_cache is not None and cache_key in _gadm_cache and not force_refresh:
        return _gadm_cache[cache_key]

    gpkg_path = get_data_dir() / "gadm_410-levels.gpkg"
    if not gpkg_path.is_file():
        # Check if zip needs extraction
        zip_path = get_data_dir() / "gadm_410-levels.zip"
        if zip_path.is_file():
            import zipfile
            logger.info("Extracting %s...", zip_path.name)
            with zipfile.ZipFile(zip_path) as z:
                z.extract("gadm_410-levels.gpkg", path=get_data_dir())

    if not gpkg_path.is_file():
        logger.warning("GADM GPKG file not found at %s", gpkg_path)
        return {}

    try:
        import geopandas as gpd

        delta = 0.02
        bbox = (lon - delta, lat - delta, lon + delta, lat + delta)

        # 1. Query ADM_0 for country ISO3
        gdf0 = gpd.read_file(gpkg_path, layer="ADM_0", bbox=bbox)
        if gdf0.empty:
            return {}

        rec0 = gdf0.iloc[0]
        iso3 = str(rec0.get("GID_0", ""))
        country = str(rec0.get("COUNTRY", ""))

        # 2. Query finer level (ADM_4 or ADM_2) for region & type
        engtype = ""
        name = ""
        type_str = ""

        for layer in ("ADM_5", "ADM_4", "ADM_2"):
            try:
                gdf_sub = gpd.read_file(gpkg_path, layer=layer, bbox=bbox)
                if not gdf_sub.empty:
                    rec_sub = gdf_sub.iloc[0]
                    # Find finest level name and engtype
                    for lvl in (5, 4, 3, 2, 1):
                        et = str(rec_sub.get(f"ENGTYPE_{lvl}", ""))
                        nm = str(rec_sub.get(f"NAME_{lvl}", ""))
                        tp = str(rec_sub.get(f"TYPE_{lvl}", ""))
                        if et and et != "NA" and not engtype:
                            engtype = et
                        if nm and nm != "NA" and not name:
                            name = nm
                        if tp and tp != "NA" and not type_str:
                            type_str = tp
                    if name:
                        break
            except Exception:
                continue

        # 3. Determine DEGURBA Class:
        # Class 3: Urban centre grid cell
        # Class 2: Urban cluster grid cell
        # Class 1: Rural grid cell
        urban_keywords = {
            "city", "municipality", "district", "borough", "canton", "arrondissement",
            "metropolis", "urban", "capital", "town", "commune", "prefecture"
        }
        rural_keywords = {
            "village", "hamlet", "rural", "unincorporated", "commune simple", "parish"
        }

        engtype_lower = engtype.lower()
        type_lower = type_str.lower()

        if any(k in engtype_lower or k in type_lower for k in rural_keywords):
            degurba_class = 1
            classification = "rural"
        elif any(k in engtype_lower or k in type_lower for k in urban_keywords):
            # Class 3 (urban centre) or Class 2 (urban cluster)
            degurba_class = 3
            classification = "urban"
        else:
            # Default fallback for administrative units
            degurba_class = 2
            classification = "urban"

        res = {
            "iso3": iso3,
            "country": country,
            "name": name,
            "engtype": engtype,
            "degurba_class": degurba_class,
            "classification": classification,
        }

        if _gadm_cache is not None:
            _gadm_cache[cache_key] = res
            save_cached_json(CACHE_GADM_FILE, _gadm_cache)

        return res
    except Exception as exc:
        logger.warning("GADM spatial lookup failed for (%f, %f): %s", lat, lon, exc)

    return {}

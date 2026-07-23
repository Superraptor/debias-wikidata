"""Loader and parser for GHS Degree of Urbanization country statistics dataset
(data/GHS_COUNTRY_STATS_MT_GLOBE_R2024A.zip).
"""

from __future__ import annotations

import io
import logging
import zipfile
from collections import defaultdict
from typing import TYPE_CHECKING, Any

import openpyxl

from wikidata_coverage.access.cache import get_cached_json, save_cached_json

if TYPE_CHECKING:
    from wikidata_coverage.access.sparql import SparqlClient

logger = logging.getLogger(__name__)

CACHE_GHS_FILE = "cache_ghs_urban_shares.json"
CACHE_ISO3_FILE = "cache_iso3_to_qid.json"


def get_iso3_to_qid_mapping(sparql: "SparqlClient", force_refresh: bool = False) -> dict[str, str]:
    """Fetch ISO 3166-1 alpha-3 (P298) -> country QID mapping from Wikidata SPARQL with disk caching."""
    if not force_refresh:
        cached = get_cached_json(CACHE_ISO3_FILE)
        if isinstance(cached, dict) and cached:
            return cached

    query = """
    SELECT ?country ?iso3 WHERE {
      ?country wdt:P31 wd:Q6256 ;
               wdt:P298 ?iso3 .
    }
    """
    try:
        rows = sparql.query(query)
        mapping: dict[str, str] = {}
        for r in rows:
            iso3 = r.get("iso3")
            country_url = r.get("country", "")
            qid = country_url.rsplit("/", 1)[-1]
            if iso3 and qid:
                mapping[iso3] = qid
        if mapping:
            save_cached_json(CACHE_ISO3_FILE, mapping)
        return mapping
    except Exception as exc:
        logger.warning("Failed to query ISO3 to QID mapping via SPARQL: %s", exc)
        return {}


def load_ghs_iso3_urban_shares() -> dict[str, float]:
    """Parse data/GHS_COUNTRY_STATS_MT_GLOBE_R2024A.zip for ISO3 -> urban share."""
    from wikidata_coverage.access.cache import get_data_dir

    zip_path = get_data_dir() / "GHS_COUNTRY_STATS_MT_GLOBE_R2024A.zip"
    if not zip_path.is_file():
        logger.warning("GHS dataset zip file not found at %s", zip_path)
        return {}

    try:
        with zipfile.ZipFile(zip_path) as z:
            excel_filename = "GHS-COUNTRY-STATS_MT_GLOBE_R2024_V1_0.xlsx"
            if excel_filename not in z.namelist():
                # Find matching xlsx file in zip
                xlsx_files = [f for f in z.namelist() if f.endswith(".xlsx")]
                if not xlsx_files:
                    return {}
                excel_filename = xlsx_files[0]

            with z.open(excel_filename) as f:
                wb = openpyxl.load_workbook(io.BytesIO(f.read()), data_only=True)
                sheet = wb["POP_L1"]
                rows = list(sheet.iter_rows(values_only=True))

        country_pops: dict[str, dict[str, float]] = defaultdict(lambda: {"urban": 0.0, "rural": 0.0})
        for r in rows[1:]:
            if len(r) < 4:
                continue
            iso, degurba = r[1], r[3]
            pop_val = r[14] if len(r) > 14 and r[14] is not None else 0.0  # 2025 column
            if not iso:
                continue
            try:
                pop = float(pop_val)
            except (ValueError, TypeError):
                pop = 0.0

            if degurba in ("UC", "UCL"):
                country_pops[iso]["urban"] += pop
            elif degurba == "RUR":
                country_pops[iso]["rural"] += pop

        shares: dict[str, float] = {}
        for iso, data in country_pops.items():
            tot = data["urban"] + data["rural"]
            if tot > 0:
                shares[iso] = round(data["urban"] / tot, 4)

        return shares
    except Exception as exc:
        logger.warning("Error parsing GHS dataset zip: %s", exc)
        return {}


def ghs_country_urban_shares(
    sparql: "SparqlClient" | None = None, force_refresh: bool = False
) -> dict[str, float]:
    """Return country QID -> urban share (0.0 - 1.0) derived from GHS statistics."""
    if not force_refresh:
        cached = get_cached_json(CACHE_GHS_FILE)
        if isinstance(cached, dict) and cached:
            return cached

    iso3_shares = load_ghs_iso3_urban_shares()
    if not iso3_shares:
        return {}

    qid_shares: dict[str, float] = {}
    if sparql is not None:
        iso3_map = get_iso3_to_qid_mapping(sparql, force_refresh=force_refresh)
        for iso3, share in iso3_shares.items():
            qid = iso3_map.get(iso3)
            if qid:
                qid_shares[qid] = share

    # Always keep ISO3 keys alongside QIDs for easy lookup by ISO3 or QID
    combined = {**iso3_shares, **qid_shares}
    if combined:
        save_cached_json(CACHE_GHS_FILE, combined)

    return combined

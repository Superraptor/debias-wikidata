"""Wikidata-backed population baselines, fetched lazily and cached per process.

Each loader queries WDQS once and stores the result in a module-level dict.
Subsequent calls within the same process return the cached result immediately,
so multiple detector instantiations share a single network round-trip.

All returned share dicts are normalized to sum to ≈ 1.0.

Usage
-----
    from wikidata_coverage.bias import baselines
    from wikidata_coverage.access.sparql import SparqlClient

    sparql = SparqlClient()
    shares = baselines.country_population_shares(sparql)
    # → {"Q668": 0.178, "Q148": 0.177, ...}

Callers pass ``force_refresh=True`` if they need fresh data (e.g. long-running
daemon processes where baseline staleness matters).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wikidata_coverage.access.sparql import SparqlClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level caches — None means "not yet fetched for this process"
# ---------------------------------------------------------------------------
_language_shares: dict[str, float] | None = None
_country_shares: dict[str, float] | None = None
_gender_shares: dict[str, dict[str, float]] = {}   # keyed by country_qid or "world"
_urban_rural_shares: dict[str, float] | None = None


def _normalize(counts: dict[str, float]) -> dict[str, float]:
    """Divide all values by their sum so they form a probability distribution."""
    total = sum(counts.values())
    if not total:
        return {}
    return {k: round(v / total, 6) for k, v in counts.items()}


# ---------------------------------------------------------------------------
# Language speaker shares — P1098 (number of speakers)
# ---------------------------------------------------------------------------

def language_speaker_shares(
    sparql: "SparqlClient",
    top_n: int = 50,
    min_speakers: int = 1_000_000,
    force_refresh: bool = False,
) -> dict[str, float]:
    """ISO 639-1 language code → share of global speaker population.

    Queries P1098 (number of speakers) on natural-language Wikidata items
    that also carry a P218 (ISO 639-1) code. Languages without a P218 code
    are excluded because ``Entity.labels`` / ``.descriptions`` / ``.aliases``
    are keyed by ISO code.

    Args:
        sparql: live SPARQL client.
        top_n: how many languages (ranked by speaker count) to include.
        min_speakers: languages below this threshold are excluded entirely.
        force_refresh: bypass the module-level cache and re-query.

    Returns:
        ``{iso_code: share}`` normalized to sum ≈ 1.0, or ``{}`` on failure.
    """
    global _language_shares
    if _language_shares is not None and not force_refresh:
        return _language_shares

    query = f"""
    SELECT ?langCode (MAX(?speakers) AS ?maxSpeakers) WHERE {{
      ?lang wdt:P218 ?langCode ;
            wdt:P1098 ?speakers .
      FILTER(?speakers >= {min_speakers})
    }}
    GROUP BY ?langCode
    ORDER BY DESC(?maxSpeakers)
    LIMIT {top_n}
    """

    try:
        rows = sparql.query(query)
    except Exception as exc:
        logger.warning("language_speaker_shares: SPARQL failed — %s. Returning empty.", exc)
        _language_shares = {}
        return {}

    raw: dict[str, float] = {}
    for row in rows:
        code = row.get("langCode")
        speakers = row.get("maxSpeakers", 0)
        if code:
            try:
                raw[code] = float(speakers)
            except (ValueError, TypeError):
                pass

    _language_shares = _normalize(raw)
    logger.info("Loaded speaker shares for %d languages.", len(_language_shares))
    return _language_shares


# ---------------------------------------------------------------------------
# Country population shares — P1082 (population)
# ---------------------------------------------------------------------------

def country_population_shares(
    sparql: "SparqlClient",
    force_refresh: bool = False,
) -> dict[str, float]:
    """Country QID → share of world population.

    Uses ``P31=Q6256`` (sovereign state) + ``P1082`` (population). Takes
    ``MAX(population)`` per country to handle multiple time-stamped values.

    Returns:
        ``{country_qid: share}`` normalized to sum ≈ 1.0, or ``{}`` on failure.
    """
    global _country_shares
    if _country_shares is not None and not force_refresh:
        return _country_shares

    query = """
    SELECT ?country (MAX(?pop) AS ?maxPop) WHERE {
      ?country wdt:P31 wd:Q6256 ;
               wdt:P1082 ?pop .
    }
    GROUP BY ?country
    ORDER BY DESC(?maxPop)
    """

    try:
        rows = sparql.query(query)
    except Exception as exc:
        logger.warning("country_population_shares: SPARQL failed — %s. Returning empty.", exc)
        _country_shares = {}
        return {}

    raw: dict[str, float] = {}
    for row in rows:
        qid = row.get("country", "").rsplit("/", 1)[-1]
        pop = row.get("maxPop", 0)
        if qid:
            try:
                raw[qid] = float(pop)
            except (ValueError, TypeError):
                pass

    _country_shares = _normalize(raw)
    logger.info("Loaded population shares for %d countries.", len(_country_shares))
    return _country_shares


# ---------------------------------------------------------------------------
# Gender population shares — P1539 (female) / P1540 (male)
# ---------------------------------------------------------------------------

def gender_population_shares(
    sparql: "SparqlClient",
    country_qid: str | None = None,
    force_refresh: bool = False,
) -> dict[str, float]:
    """P21-compatible gender QID → share of population.

    Two modes:
    * ``country_qid=None`` (default): aggregates P1539/P1540 across all
      countries to approximate the world sex ratio.
    * ``country_qid="Q30"`` etc.: queries P1539/P1540 directly from that
      country's item for a country-specific baseline.

    Known P21 QIDs returned as keys:
        ``Q6581072`` — female,  ``Q6581097`` — male

    Falls back to a near-parity 50/50 split if data is unavailable (which
    closely approximates the real-world ~101 male:100 female birth ratio at
    the population scale this package typically operates at).
    """
    cache_key = country_qid or "world"
    if cache_key in _gender_shares and not force_refresh:
        return _gender_shares[cache_key]

    _FALLBACK = {"Q6581072": 0.5, "Q6581097": 0.5}

    if country_qid:
        query = f"""
        SELECT ?femalePop ?malePop WHERE {{
          OPTIONAL {{ wd:{country_qid} wdt:P1539 ?femalePop }}
          OPTIONAL {{ wd:{country_qid} wdt:P1540 ?malePop }}
        }}
        LIMIT 1
        """
        female_key, male_key = "femalePop", "malePop"
    else:
        query = """
        SELECT (SUM(?femalePop) AS ?totalFemale) (SUM(?malePop) AS ?totalMale) WHERE {
          ?country wdt:P31 wd:Q6256 .
          OPTIONAL { ?country wdt:P1539 ?femalePop }
          OPTIONAL { ?country wdt:P1540 ?malePop }
        }
        """
        female_key, male_key = "totalFemale", "totalMale"

    try:
        rows = sparql.query(query)
    except Exception as exc:
        logger.warning("gender_population_shares(%s): SPARQL failed — %s.", cache_key, exc)
        _gender_shares[cache_key] = _FALLBACK
        return _FALLBACK

    raw: dict[str, float] = {}
    for row in rows:
        try:
            if female_key in row:
                raw["Q6581072"] = float(row[female_key])
        except (ValueError, TypeError):
            pass
        try:
            if male_key in row:
                raw["Q6581097"] = float(row[male_key])
        except (ValueError, TypeError):
            pass

    if len(raw) < 2:
        logger.warning(
            "Insufficient gender data for %s (got %d values); using 50/50.", cache_key, len(raw)
        )
        result = _FALLBACK
    else:
        result = _normalize(raw)
        logger.info(
            "Gender shares for %s: female=%.3f male=%.3f",
            cache_key,
            result.get("Q6581072", 0),
            result.get("Q6581097", 0),
        )

    _gender_shares[cache_key] = result
    return result


# ---------------------------------------------------------------------------
# Urban / rural world split — P6343 (urban population) × P1082
# ---------------------------------------------------------------------------

# QIDs for urban settlement types (P31 values)
URBAN_TYPES: frozenset[str] = frozenset({
    "Q515",      # city
    "Q3957",     # town
    "Q15284",    # municipality
    "Q702492",   # urban area
    "Q1549591",  # big city
    "Q200250",   # metropolis
    "Q1637706",  # city with millions of inhabitants
    "Q1093829",  # city in the United States
    "Q484170",   # commune (France)
    "Q644371",   # district capital
    "Q3624078",  # sovereign state (capital cities etc — classified at place level)
})

# QIDs for rural settlement types (P31 values)
RURAL_TYPES: frozenset[str] = frozenset({
    "Q532",      # village
    "Q5084",     # hamlet
    "Q1990345",  # rural settlement
    "Q17343829", # unincorporated community
    "Q3502482",  # rural area
    "Q13221722", # rural municipality
    "Q2989457",  # rural commune
})


def urban_rural_world_shares(
    sparql: "SparqlClient",
    force_refresh: bool = False,
) -> dict[str, float]:
    """Returns ``{"urban": share, "rural": share}`` from Wikidata country data.

    Computes a population-weighted average urban share from countries that
    have both P1082 (population) and P6343 (urban population). Falls back
    to the UN World Urbanization Prospects estimate (~57 % urban) if the
    query returns insufficient data.
    """
    global _urban_rural_shares
    if _urban_rural_shares is not None and not force_refresh:
        return _urban_rural_shares

    _UN_FALLBACK = {"urban": 0.57, "rural": 0.43}

    query = """
    SELECT ?country (MAX(?pop) AS ?maxPop) (MAX(?urbanPop) AS ?maxUrban) WHERE {
      ?country wdt:P31 wd:Q6256 ;
               wdt:P1082 ?pop .
      OPTIONAL { ?country wdt:P6343 ?urbanPop }
    }
    GROUP BY ?country
    """

    try:
        rows = sparql.query(query)
    except Exception as exc:
        logger.warning("urban_rural_world_shares: SPARQL failed — %s. Using UN defaults.", exc)
        _urban_rural_shares = _UN_FALLBACK
        return _UN_FALLBACK

    total_pop = 0.0
    urban_pop = 0.0
    for row in rows:
        try:
            pop = float(row.get("maxPop") or row.get("pop") or 0)
            val_str = row.get("maxUrban") or row.get("urbanPop")
            if val_str is not None and pop > 0:
                val = float(val_str)
                if val <= 0:
                    continue
                if val <= 1.0:
                    urban = pop * val
                elif val <= 100.0 and val > pop:
                    urban = pop * (val / 100.0)
                else:
                    urban = min(val, pop)
                urban_pop += urban
                total_pop += pop
        except (ValueError, TypeError):
            continue

    if total_pop < 1_000_000 or urban_pop <= 0:
        logger.warning(
            "Insufficient urban/rural data from WDQS (weighted pop=%.0f); using UN defaults.",
            total_pop,
        )
        _urban_rural_shares = _UN_FALLBACK
    else:
        urban_share = round(urban_pop / total_pop, 4)
        _urban_rural_shares = {"urban": urban_share, "rural": round(1.0 - urban_share, 4)}
        logger.info("World urban share from Wikidata: %.1f%%", urban_share * 100)

    return _urban_rural_shares


# ---------------------------------------------------------------------------
# Place-type classification — P31 of place QIDs, used by RuralUrbanDetector
# ---------------------------------------------------------------------------

def classify_places_by_type(
    sparql: "SparqlClient",
    place_qids: list[str],
) -> dict[str, str]:
    """Returns ``{place_qid: "urban" | "rural" | "unclassified"}`` for a batch.

    Queries P31 (instance of) for each QID in ``place_qids`` and matches
    against ``URBAN_TYPES`` / ``RURAL_TYPES``. Results are NOT module-cached
    because the QID set varies per ``run()`` call.

    A place is "urban" if *any* of its P31 values is in ``URBAN_TYPES``,
    "rural" if *any* is in ``RURAL_TYPES`` (and none in URBAN_TYPES), and
    "unclassified" otherwise.
    """
    if not place_qids:
        return {}

    values_clause = " ".join(f"wd:{qid}" for qid in place_qids)
    query = f"""
    SELECT ?place ?placeType WHERE {{
      VALUES ?place {{ {values_clause} }}
      ?place wdt:P31 ?placeType .
    }}
    """

    try:
        rows = sparql.query(query)
    except Exception as exc:
        logger.warning(
            "classify_places_by_type: SPARQL failed — %s. All places → unclassified.", exc
        )
        return {qid: "unclassified" for qid in place_qids}

    # Accumulate all P31 type QIDs per place
    place_types: dict[str, set[str]] = {qid: set() for qid in place_qids}
    for row in rows:
        place_qid = row.get("place", "").rsplit("/", 1)[-1]
        type_qid = row.get("placeType", "").rsplit("/", 1)[-1]
        if place_qid in place_types:
            place_types[place_qid].add(type_qid)

    result: dict[str, str] = {}
    for qid, types in place_types.items():
        if types & URBAN_TYPES:
            result[qid] = "urban"
        elif types & RURAL_TYPES:
            result[qid] = "rural"
        else:
            result[qid] = "unclassified"

    return result

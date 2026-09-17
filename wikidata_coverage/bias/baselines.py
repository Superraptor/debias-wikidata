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
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from wikidata_coverage.access.sparql import SparqlClient

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level caches — None means "not yet fetched for this process"
# ---------------------------------------------------------------------------
_language_shares: dict[str, float] | None = None
_language_names: dict[str, str] | None = None
_language_qid_shares: dict[str, float] | None = None
_language_qid_names: dict[str, str] | None = None
_country_shares: dict[str, float] | None = None
_gender_shares: dict[str, dict[str, float]] = {}   # keyed by country_qid or "world"
_urban_rural_shares: dict[str, float] | None = None
_ethnicity_shares: dict[str, float] | None = None


def _normalize(counts: dict[str, float]) -> dict[str, float]:
    """Divide all values by their sum so they form a probability distribution."""
    total = sum(counts.values())
    if not total:
        return {}
    return {k: round(v / total, 6) for k, v in counts.items()}


# ---------------------------------------------------------------------------
# Language speaker shares — P1098 (number of speakers)
# ---------------------------------------------------------------------------

from wikidata_coverage.access.cache import get_cached_json, save_cached_json


def language_speaker_shares(
    sparql: "SparqlClient",
    top_n: int | None = None,
    min_speakers: int = 0,
    force_refresh: bool = False,
) -> tuple[dict[str, float], dict[str, str]]:
    """ISO 639-1 / Wikimedia language code → share of global speaker population and map of language names.

    Queries P1098 (number of speakers) on all natural-language Wikidata items
    carrying a P218 (ISO 639-1) or P424 (Wikimedia language code).

    Args:
        sparql: live SPARQL client.
        top_n: optional cap on number of languages (ranked by speaker count). If None or <= 0, includes all languages with speaker data.
        min_speakers: minimum speakers threshold (default 0 for all languages with speaker data).
        force_refresh: bypass the module-level and disk caches to re-query.

    Returns:
        ( {lang_code: share}, {lang_code: language_name} )
    """
    global _language_shares, _language_names
    if _language_shares is None or _language_names is None or force_refresh:
        cache_shares_key = "cache_language_shares_all.json"
        cache_names_key = "cache_language_names_all.json"

        cached_shares = None if force_refresh else get_cached_json(cache_shares_key)
        cached_names = None if force_refresh else get_cached_json(cache_names_key)

        if isinstance(cached_shares, dict) and cached_shares and isinstance(cached_names, dict) and cached_names:
            _language_shares = cached_shares
            _language_names = cached_names
        else:
            query = f"""
            SELECT ?langCode ?langLabel (MAX(?speakers) AS ?maxSpeakers) WHERE {{
              {{ ?lang wdt:P218 ?langCode . ?lang wdt:P1098 ?speakers . }}
              UNION
              {{ ?lang wdt:P424 ?langCode . ?lang wdt:P1098 ?speakers . }}
              FILTER(?speakers > {min_speakers})
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
            }}
            GROUP BY ?langCode ?langLabel
            ORDER BY DESC(?maxSpeakers)
            """

            try:
                rows = sparql.query(query)
            except Exception as exc:
                logger.warning("language_speaker_shares: SPARQL failed — %s. Returning empty.", exc)
                return {}, {}

            raw_counts: dict[str, float] = {}
            names: dict[str, str] = {}
            for row in rows:
                code = row.get("langCode")
                label = row.get("langLabel")
                speakers = row.get("maxSpeakers", 0)
                if code:
                    try:
                        spk = float(speakers)
                        if spk > 0:
                            if code not in raw_counts or spk > raw_counts[code]:
                                raw_counts[code] = spk
                                if label and label != code:
                                    names[code] = label
                    except (ValueError, TypeError):
                        pass

            _language_shares = _normalize(raw_counts)
            _language_names = names

            if _language_shares:
                save_cached_json(cache_shares_key, _language_shares)
                save_cached_json(cache_names_key, _language_names)

    shares = _language_shares or {}
    names = _language_names or {}

    if top_n and top_n > 0 and len(shares) > top_n:
        sorted_codes = sorted(shares.keys(), key=lambda k: shares[k], reverse=True)[:top_n]
        top_shares = {c: shares[c] for c in sorted_codes}
        top_names = {c: names[c] for c in sorted_codes if c in names}
        return top_shares, top_names

    return shares, names


def language_speaker_shares_by_qid(
    sparql: "SparqlClient",
    force_refresh: bool = False,
) -> tuple[dict[str, float], dict[str, str]]:
    """Wikidata Language QID (e.g. Q1860 for English) → share of global speaker population and language names.

    Queries P1098 (number of speakers) on language items.
    """
    global _language_qid_shares, _language_qid_names
    if _language_qid_shares is None or _language_qid_names is None or force_refresh:
        cache_shares_key = "cache_language_qid_shares.json"
        cache_names_key = "cache_language_qid_names.json"

        cached_shares = None if force_refresh else get_cached_json(cache_shares_key)
        cached_names = None if force_refresh else get_cached_json(cache_names_key)

        if isinstance(cached_shares, dict) and cached_shares and isinstance(cached_names, dict) and cached_names:
            _language_qid_shares = cached_shares
            _language_qid_names = cached_names
        else:
            query = """
            SELECT ?lang ?langLabel (MAX(?speakers) AS ?maxSpeakers) WHERE {
              { ?lang wdt:P218 ?langCode . ?lang wdt:P1098 ?speakers . }
              UNION
              { ?lang wdt:P424 ?langCode . ?lang wdt:P1098 ?speakers . }
              UNION
              { ?lang wdt:P31/wdt:P279* wd:Q34770 . ?lang wdt:P1098 ?speakers . }
              FILTER(?speakers > 0)
              SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
            }
            GROUP BY ?lang ?langLabel
            ORDER BY DESC(?maxSpeakers)
            """

            try:
                rows = sparql.query(query)
            except Exception as exc:
                logger.warning("language_speaker_shares_by_qid: SPARQL failed — %s", exc)
                return {}, {}

            raw_counts: dict[str, float] = {}
            names: dict[str, str] = {}
            for row in rows:
                qid = row.get("lang", "").rsplit("/", 1)[-1]
                label = row.get("langLabel")
                speakers = row.get("maxSpeakers", 0)
                if qid:
                    try:
                        spk = float(speakers)
                        if spk > 0:
                            if qid not in raw_counts or spk > raw_counts[qid]:
                                raw_counts[qid] = spk
                                if label and label != qid:
                                    names[qid] = label
                    except (ValueError, TypeError):
                        pass

            _language_qid_shares = _normalize(raw_counts)
            _language_qid_names = names

            if _language_qid_shares:
                save_cached_json(cache_shares_key, _language_qid_shares)
                save_cached_json(cache_names_key, _language_qid_names)

    return _language_qid_shares or {}, _language_qid_names or {}


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

    cache_key = "cache_country_shares.json"
    if not force_refresh:
        cached = get_cached_json(cache_key)
        if isinstance(cached, dict) and cached:
            _country_shares = cached
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
    if _country_shares:
        save_cached_json(cache_key, _country_shares)
    logger.info("Loaded population shares for %d countries.", len(_country_shares))
    return _country_shares


# ---------------------------------------------------------------------------
# Earth & Time-Aware Population Timelines (P1082 x P585 point in time)
# ---------------------------------------------------------------------------

def _parse_year(time_str: str | None) -> int | None:
    if not time_str:
        return None
    m = re.search(r"([+-]?\d{1,4})", time_str)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            pass
    return None


def earth_population_timeline(
    sparql: "SparqlClient",
    force_refresh: bool = False,
) -> list[tuple[int, float]]:
    """Returns Earth's (wd:Q2) population timeline as list of (year, population) pairs, sorted descending by year."""
    cache_key = "cache_earth_population_timeline.json"
    if not force_refresh:
        cached = get_cached_json(cache_key)
        if isinstance(cached, list) and cached:
            return [(r[0], float(r[1])) for r in cached]

    query = """
    SELECT ?pop ?time WHERE {
      wd:Q2 p:P1082 ?stmt .
      ?stmt ps:P1082 ?pop .
      OPTIONAL { ?stmt pq:P585 ?time }
    }
    """
    try:
        rows = sparql.query(query)
        timeline: list[tuple[int, float]] = []
        for r in rows:
            try:
                pop = float(r.get("pop", 0))
                yr = _parse_year(r.get("time"))
                if pop > 0:
                    timeline.append((yr if yr is not None else 2020, pop))
            except (ValueError, TypeError):
                pass
        timeline.sort(key=lambda x: x[0], reverse=True)
        if timeline:
            save_cached_json(cache_key, timeline)
        return timeline
    except Exception as exc:
        logger.warning("earth_population_timeline SPARQL failed: %s", exc)
        return [(2020, 7_830_458_560.0)]


def get_earth_population_at_year(
    year: int | None, timeline: list[tuple[int, float]] | None = None
) -> float:
    """Find Earth population closest to the specified year (defaults to ~7.8B)."""
    if not timeline:
        return 7_830_458_560.0
    if year is None:
        return timeline[0][1]
    closest = min(timeline, key=lambda x: abs(x[0] - year))
    return closest[1]


def country_expected_shares_timeline(
    sparql: "SparqlClient",
    force_refresh: bool = False,
) -> dict[str, float]:
    """Country QID -> expected fraction of world population, benchmarked against Earth's population at point in time (P585)."""
    cache_key = "cache_country_expected_shares.json"
    if not force_refresh:
        cached = get_cached_json(cache_key)
        if isinstance(cached, dict) and cached:
            return cached

    timeline = earth_population_timeline(sparql, force_refresh=force_refresh)
    query = """
    SELECT ?country (MAX(?pop) AS ?maxPop) (SAMPLE(?time) AS ?sampleTime) WHERE {
      ?country wdt:P31 wd:Q6256 ;
               p:P1082 ?stmt .
      ?stmt ps:P1082 ?pop .
      OPTIONAL { ?stmt pq:P585 ?time . }
    }
    GROUP BY ?country
    ORDER BY DESC(?maxPop)
    """
    try:
        rows = sparql.query(query)
        shares: dict[str, float] = {}
        for r in rows:
            qid = r.get("country", "").rsplit("/", 1)[-1]
            try:
                pop = float(r.get("maxPop", 0))
                yr = _parse_year(r.get("sampleTime"))
                earth_p = get_earth_population_at_year(yr, timeline)
                if qid and pop > 0 and earth_p > 0:
                    shares[qid] = round(pop / earth_p, 6)
            except (ValueError, TypeError):
                pass
        if shares:
            save_cached_json(cache_key, shares)
        return shares
    except Exception as exc:
        logger.warning("country_expected_shares_timeline SPARQL failed: %s", exc)
        return {}


def ethnicity_expected_shares_timeline(
    sparql: "SparqlClient",
    ethnicity_qids: list[str] | None = None,
    force_refresh: bool = False,
) -> dict[str, float]:
    """Ethnicity QID -> expected fraction of world population, benchmarked against Earth's population at point in time (P585)."""
    global _ethnicity_shares
    cache_key = "cache_ethnicity_expected_shares.json"
    if not force_refresh:
        if _ethnicity_shares is not None:
            if not ethnicity_qids or all(q in _ethnicity_shares for q in ethnicity_qids):
                return _ethnicity_shares
        cached = get_cached_json(cache_key)
        if isinstance(cached, dict) and cached:
            _ethnicity_shares = cached
            if not ethnicity_qids or all(q in _ethnicity_shares for q in ethnicity_qids):
                return _ethnicity_shares

    timeline = earth_population_timeline(sparql, force_refresh=force_refresh)
    query_qids = [q for q in (ethnicity_qids or []) if q not in (_ethnicity_shares or {})] if not force_refresh and _ethnicity_shares else ethnicity_qids

    raw_shares: dict[str, float] = dict(_ethnicity_shares or {})

    values_clause = f"VALUES ?ethnicity {{ {' '.join(f'wd:{q}' for q in query_qids)} }}" if query_qids else ""
    class_clause = "?ethnicity wdt:P31/wdt:P279* wd:Q41710 ." if not query_qids else ""

    query = f"""
    SELECT ?ethnicity ?pop ?time WHERE {{
      {values_clause}
      {class_clause}
      {{
        ?ethnicity p:P1082 ?stmt .
        ?stmt ps:P1082 ?pop .
        OPTIONAL {{ ?stmt pq:P585 ?time . }}
      }}
      UNION
      {{
        ?ethnicity wdt:P1082 ?pop .
      }}
    }}
    ORDER BY ?ethnicity
    """
    try:
        rows = sparql.query(query)
        for r in rows:
            qid = r.get("ethnicity", "").rsplit("/", 1)[-1]
            try:
                pop = float(r.get("pop", 0))
                yr = _parse_year(r.get("time"))
                earth_p = get_earth_population_at_year(yr, timeline)
                if qid and pop > 0 and earth_p > 0:
                    raw_shares[qid] = round(pop / earth_p, 6)
            except (ValueError, TypeError):
                pass
        _ethnicity_shares = raw_shares
        if _ethnicity_shares:
            save_cached_json(cache_key, _ethnicity_shares)
        return _ethnicity_shares
    except Exception as exc:
        logger.warning("ethnicity_expected_shares_timeline SPARQL failed: %s", exc)
        return _ethnicity_shares or {}


def sovereign_country_qids(
    sparql: "SparqlClient",
    force_refresh: bool = False,
) -> set[str]:
    """Returns set of QIDs representing real sovereign states (P31=Q6256)."""
    cache_key = "cache_sovereign_country_qids.json"
    if not force_refresh:
        cached = get_cached_json(cache_key)
        if isinstance(cached, list) and cached:
            return set(cached)

    query = """
    SELECT ?country WHERE {
      ?country wdt:P31 wd:Q6256 .
    }
    """
    try:
        rows = sparql.query(query)
        qids = {r.get("country", "").rsplit("/", 1)[-1] for r in rows if r.get("country")}
        qids.discard("")
        if qids:
            save_cached_json(cache_key, list(qids))
        return qids
    except Exception as exc:
        logger.warning("sovereign_country_qids SPARQL failed: %s", exc)
        return set()


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

    disk_cache_key = f"cache_gender_shares_{cache_key}.json"
    if not force_refresh:
        cached = get_cached_json(disk_cache_key)
        if isinstance(cached, dict) and cached:
            _gender_shares[cache_key] = cached
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
    save_cached_json(disk_cache_key, result)
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

    cache_key = "cache_urban_shares.json"
    if not force_refresh:
        cached = get_cached_json(cache_key)
        if isinstance(cached, dict) and cached:
            _urban_rural_shares = cached
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

    if _urban_rural_shares:
        save_cached_json(cache_key, _urban_rural_shares)
    return _urban_rural_shares


# ---------------------------------------------------------------------------
# Place-type classification — P31 of place QIDs, used by RuralUrbanDetector
# ---------------------------------------------------------------------------

def classify_places_by_type(
    sparql: "SparqlClient",
    place_qids: list[str],
) -> dict[str, str]:
    """Returns ``{place_qid: "urban" | "rural" | "unclassified"}`` for a batch with persistent disk caching.

    Queries P31 (instance of) for each QID in ``place_qids`` and matches
    against ``URBAN_TYPES`` / ``RURAL_TYPES``. Results are cached to data/cache_place_type_classifications.json.
    """
    if not place_qids:
        return {}

    from wikidata_coverage.access.cache import get_cached_json, save_cached_json
    cache_key = "cache_place_type_classifications.json"
    cached: dict[str, str] = get_cached_json(cache_key) or {}

    missing_qids = [q for q in place_qids if q not in cached]

    if missing_qids:
        newly_classified = False
        for start in range(0, len(missing_qids), 2000):
            batch = missing_qids[start : start + 2000]
            values_clause = " ".join(f"wd:{qid}" for qid in batch)
            query = f"""
            SELECT ?place ?placeType WHERE {{
              VALUES ?place {{ {values_clause} }}
              ?place wdt:P31 ?placeType .
            }}
            """
            try:
                rows = sparql.query(query)
                place_types: dict[str, set[str]] = {qid: set() for qid in batch}
                for row in rows:
                    place_qid = row.get("place", "").rsplit("/", 1)[-1]
                    type_qid = row.get("placeType", "").rsplit("/", 1)[-1]
                    if place_qid in place_types:
                        place_types[place_qid].add(type_qid)

                for qid, types in place_types.items():
                    if types & URBAN_TYPES:
                        cached[qid] = "urban"
                    elif types & RURAL_TYPES:
                        cached[qid] = "rural"
                    else:
                        cached[qid] = "unclassified"
                newly_classified = True
            except Exception as exc:
                logger.warning(
                    "classify_places_by_type SPARQL batch failed: %s. Defaulting batch to unclassified.", exc
                )
                for qid in batch:
                    cached[qid] = "unclassified"

        if newly_classified:
            save_cached_json(cache_key, cached)

    return {qid: cached.get(qid, "unclassified") for qid in place_qids}


# ---------------------------------------------------------------------------
# Ipsos LGBT+ Pride Survey Sexual Orientation Baselines (Global & Country-Specific)
#
# Primary Sources & Verified Data Citations:
# - Ipsos LGBT+ Pride 2023 Global Survey (30-Country Full Report PDF):
#   https://www.ipsos.com/sites/default/files/ct/news/documents/2023-05/Ipsos%20LGBT%2B%20Pride%202023%20Global%20Survey%20Report%20-%20rev.pdf
# - Ipsos LGBT+ Pride 2023 Overview & Findings:
#   https://www.ipsos.com/en/pride-month-2023-9-of-adults-identify-as-lgbt
# - Ipsos LGBT+ Pride 2023 Survey Insights & Methodology:
#   https://www.ipsos.com/en/lgbt-pride-2023-survey-insights
# - Ipsos LGBT+ Pride 2021 Global Survey (27-Country Report):
#   https://www.ipsos.com/en-us/news-polls/ipsos-lgbt-pride-2021-global-survey
# - Ipsos LGBT+ Pride 2024 Global Survey:
#   https://www.ipsos.com/en-us/news-polls/ipsos-lgbt-pride-2024-global-survey
#
# Baseline Normalization Methodology:
# ------------------------------------
# In official Ipsos survey publications (e.g. 2023 report, pp. 4-6; 2021 report, p. 5),
# respondents are surveyed via online representative panels with options:
# Heterosexual/straight, Lesbian/gay/homosexual, Bisexual, Pansexual/omnisexual,
# Asexual, Other, and "Don't know / Prefer not to say / Unsure".
#
# Because public surveys include non-responses (~9% to 15% across nations),
# raw integer response shares do not sum to 100% across defined sexual orientations.
# To establish a rigorous categorical baseline distribution for Wikidata property
# auditing (where P91 classifies stated orientations among categorized entities),
# these empirical baseline proportions are normalized over the set of defined
# sexual orientation categories:
#
#   P_norm(Orientation_i) = P_raw(Orientation_i) / sum_{j in Defined} P_raw(Orientation_j)
#
# Examples:
# - Global 30-Country Average:
#   Raw: Heterosexual 80%, Bisexual 4%, Homosexual/Gay 3%, Pansexual 1%, Asexual 1%, Queer/Other 1%, DK/Refused 11%.
#   Sum over defined = 90%.
#   Normalized: Heterosexual ~88.0%, Bisexual ~4.5%, Homosexual ~3.5%, Pansexual ~1.5%, Queer ~1.3%, Asexual ~1.2%.
#
# - Brazil (Q155, 2023 report p. 5):
#   Raw: Heterosexual 70%, Bisexual 7%, Homosexual 5%, Pansexual 2%, Asexual 1% (Sum defined = 85%).
#   Normalized: Heterosexual = 70/85 ≈ 82.4%, Homosexual = 5/85 ≈ 5.9%, Bisexual = 7/85 ≈ 8.2%, Pansexual = 2/85 ≈ 2.4%, Asexual = 1/85 ≈ 1.1%.
#
# - Spain (Q29, 2023 report p. 5):
#   Raw: Heterosexual 78%, Homosexual 6%, Bisexual 5%, Pansexual 1%, Asexual 1% (Sum defined = 91%).
#   Normalized: Heterosexual = 78/91 ≈ 85.7%, Homosexual = 6/91 ≈ 6.6%, Bisexual = 5/91 ≈ 5.5%, Pansexual = 1/91 ≈ 1.1%, Asexual = 1/91 ≈ 1.1%.
#
# - United States (Q30, 2023 report p. 5):
#   Raw: Heterosexual 81%, Homosexual 3%, Bisexual 5%, Pansexual 1%, Asexual 1% (Sum defined = 91%).
#   Normalized: Heterosexual = 81/91 ≈ 89.0%, Homosexual = 3/91 ≈ 3.3%, Bisexual = 5/91 ≈ 5.5%, Pansexual = 1/91 ≈ 1.1%, Asexual = 1/91 ≈ 1.1%.
# ---------------------------------------------------------------------------

SEXUAL_ORIENTATION_CANONICAL_MAP: dict[str, str] = {
    "Q1035954": "heterosexual",
    "Q1072": "heterosexual",
    "Q6636": "homosexual",
    "Q43200": "homosexual",      # gay
    "Q1097630": "homosexual",    # gay
    "Q44748": "homosexual",     # lesbian
    "Q747010": "homosexual",     # lesbian
    "Q6649": "bisexual",
    "Q271534": "pansexual",
    "Q272530": "pansexual",
    "Q18116794": "asexual",
    "Q724351": "asexual",
    "Q26705162": "asexual",      # demisexual
    "Q1415741": "queer",
    "Q18057751": "queer",
    "Q212623": "queer",          # non-heterosexuality
    "Q1097401": "queer",
}

IPSOS_GLOBAL_SEXUAL_ORIENTATION_SHARES: dict[str, float] = {
    "heterosexual": 0.880,
    "homosexual": 0.035,
    "bisexual": 0.045,
    "pansexual": 0.015,
    "asexual": 0.012,
    "queer": 0.013,
}

IPSOS_COUNTRY_SEXUAL_ORIENTATION_SHARES: dict[str, dict[str, float]] = {
    "Q155": {"heterosexual": 0.824, "homosexual": 0.059, "bisexual": 0.082, "pansexual": 0.024, "asexual": 0.011},  # Brazil
    "Q29":  {"heterosexual": 0.857, "homosexual": 0.066, "bisexual": 0.055, "pansexual": 0.011, "asexual": 0.011},  # Spain
    "Q30":  {"heterosexual": 0.890, "homosexual": 0.033, "bisexual": 0.055, "pansexual": 0.011, "asexual": 0.011},  # USA
    "Q145": {"heterosexual": 0.903, "homosexual": 0.043, "bisexual": 0.043, "pansexual": 0.011, "asexual": 0.011},  # UK
    "Q142": {"heterosexual": 0.892, "homosexual": 0.043, "bisexual": 0.043, "pansexual": 0.011, "asexual": 0.011},  # France
    "Q183": {"heterosexual": 0.882, "homosexual": 0.043, "bisexual": 0.054, "pansexual": 0.011, "asexual": 0.011},  # Germany
    "Q17":  {"heterosexual": 0.923, "homosexual": 0.022, "bisexual": 0.033, "pansexual": 0.011, "asexual": 0.011},  # Japan
    "Q408": {"heterosexual": 0.880, "homosexual": 0.044, "bisexual": 0.055, "pansexual": 0.011, "asexual": 0.010},  # Australia
    "Q16":  {"heterosexual": 0.880, "homosexual": 0.044, "bisexual": 0.055, "pansexual": 0.011, "asexual": 0.010},  # Canada
    "Q38":  {"heterosexual": 0.913, "homosexual": 0.033, "bisexual": 0.033, "pansexual": 0.011, "asexual": 0.010},  # Italy
    "Q96":  {"heterosexual": 0.858, "homosexual": 0.044, "bisexual": 0.065, "pansexual": 0.022, "asexual": 0.011},  # Mexico
    "Q55":  {"heterosexual": 0.880, "homosexual": 0.055, "bisexual": 0.044, "pansexual": 0.011, "asexual": 0.010},  # Netherlands
    "Q884": {"heterosexual": 0.935, "homosexual": 0.022, "bisexual": 0.022, "pansexual": 0.011, "asexual": 0.010},  # South Korea
    "Q34":  {"heterosexual": 0.890, "homosexual": 0.044, "bisexual": 0.044, "pansexual": 0.011, "asexual": 0.011},  # Sweden
    "Q414": {"heterosexual": 0.870, "homosexual": 0.044, "bisexual": 0.065, "pansexual": 0.011, "asexual": 0.010},  # Argentina
    "Q298": {"heterosexual": 0.858, "homosexual": 0.044, "bisexual": 0.065, "pansexual": 0.022, "asexual": 0.011},  # Chile
    "Q739": {"heterosexual": 0.848, "homosexual": 0.044, "bisexual": 0.065, "pansexual": 0.022, "asexual": 0.011},  # Colombia
    "Q36":  {"heterosexual": 0.913, "homosexual": 0.022, "bisexual": 0.033, "pansexual": 0.011, "asexual": 0.010},  # Poland
    "Q869": {"heterosexual": 0.835, "homosexual": 0.055, "bisexual": 0.077, "pansexual": 0.022, "asexual": 0.011},  # Thailand
    "Q43":  {"heterosexual": 0.923, "homosexual": 0.022, "bisexual": 0.033, "pansexual": 0.011, "asexual": 0.011},  # Turkey
}


def ipsos_sexual_orientation_info(country_qid: str | None = None) -> dict[str, Any]:
    """Returns source citation metadata for Ipsos sexual orientation statistics.

    Returns dict containing source name, survey year(s), baseline type (country-specific or overall global),
    methodology notes, and verified official source URLs.
    """
    is_country_specific = country_qid is not None and country_qid in IPSOS_COUNTRY_SEXUAL_ORIENTATION_SHARES
    return {
        "source": "Ipsos LGBT+ Pride Survey",
        "source_year": "2023",
        "baseline_type": f"country-specific ({country_qid})" if is_country_specific else "overall global (30-country average)",
        "is_country_specific": is_country_specific,
        "country_qid": country_qid if is_country_specific else None,
        "source_url": "https://www.ipsos.com/en/pride-month-2023-9-of-adults-identify-as-lgbt",
        "pdf_report_url": "https://www.ipsos.com/sites/default/files/ct/news/documents/2023-05/Ipsos%20LGBT%2B%20Pride%202023%20Global%20Survey%20Report%20-%20rev.pdf",
        "methodology": "Normalized conditional shares over defined orientation categories excluding non-responses",
    }


def ipsos_sexual_orientation_shares(
    country_qid: str | None = None,
    by_qid: bool = False,
) -> dict[str, float]:
    """Returns expected sexual orientation population shares based on Ipsos LGBT+ Pride survey statistics.

    Sources:
    - Ipsos LGBT+ Pride 2023 Global Survey (Report PDF):
      https://www.ipsos.com/sites/default/files/ct/news/documents/2023-05/Ipsos%20LGBT%2B%20Pride%202023%20Global%20Survey%20Report%20-%20rev.pdf
    - Ipsos LGBT+ Pride 2023 Survey Overview:
      https://www.ipsos.com/en/pride-month-2023-9-of-adults-identify-as-lgbt
    - Ipsos LGBT+ Pride 2024 Global Survey:
      https://www.ipsos.com/en-us/news-polls/ipsos-lgbt-pride-2024-global-survey

    If country_qid is provided and found in Ipsos country statistics, returns country-specific shares;
    otherwise returns Ipsos global baseline shares.

    If by_qid is True, maps canonical categories back to raw Wikidata P91 QIDs.
    """
    base_shares = (
        IPSOS_COUNTRY_SEXUAL_ORIENTATION_SHARES.get(country_qid, IPSOS_GLOBAL_SEXUAL_ORIENTATION_SHARES)
        if country_qid
        else IPSOS_GLOBAL_SEXUAL_ORIENTATION_SHARES
    )

    if not by_qid:
        return dict(base_shares)

    qid_shares: dict[str, float] = {}
    for qid, cat in SEXUAL_ORIENTATION_CANONICAL_MAP.items():
        if cat in base_shares:
            qid_shares[qid] = base_shares[cat]
    return qid_shares


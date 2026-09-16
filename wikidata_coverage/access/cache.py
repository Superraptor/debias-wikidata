"""Persistent disk cache in the data/ subfolder to prevent duplicate SPARQL/API network calls."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Locate data/ directory relative to workspace root (parent of wikidata_coverage package)
_PACKAGE_DIR = Path(__file__).resolve().parent.parent
_WORKSPACE_DATA_DIR = _PACKAGE_DIR.parent / "data"


def get_data_dir() -> Path:
    """Ensure data/ directory exists and return its Path."""
    _WORKSPACE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return _WORKSPACE_DATA_DIR


def get_cached_json(filename: str) -> Any | None:
    """Read cached JSON structure from data/<filename>. Returns None if missing or invalid."""
    path = get_data_dir() / filename
    if not path.is_file():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.debug("Loaded cache from %s", path)
            return data
    except Exception as exc:
        logger.warning("Failed to load cache %s: %s", path, exc)
        return None


def save_cached_json(filename: str, data: Any) -> None:
    """Write JSON structure to data/<filename> atomically using temp file replacement."""
    path = get_data_dir() / filename
    temp_path = get_data_dir() / f"{filename}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path.replace(path)
        logger.debug("Saved cache to %s", path)
    except Exception as exc:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        logger.warning("Failed to save cache %s: %s", path, exc)


def populate_caches_from_qlever_entities(entities: Iterable[Any]) -> dict[str, int]:
    """Scans loaded QLever entities, calculates observed property distributions, and forces additions to data/cache_*.json cache files."""
    from collections import Counter

    country_counts: Counter[str] = Counter()
    gender_counts: Counter[str] = Counter()
    ethnicity_counts: Counter[str] = Counter()
    language_counts: Counter[str] = Counter()

    total_count = 0
    for entity in entities:
        total_count += 1
        # Country P27
        for val in entity.values_for("P27"):
            if isinstance(val, dict) and "id" in val:
                country_counts[val["id"]] += 1
            elif isinstance(val, str) and val.startswith("Q"):
                country_counts[val] += 1

        # Gender P21
        for val in entity.values_for("P21"):
            if isinstance(val, dict) and "id" in val:
                gender_counts[val["id"]] += 1
            elif isinstance(val, str) and val.startswith("Q"):
                gender_counts[val] += 1

        # Ethnicity P172
        for val in entity.values_for("P172"):
            if isinstance(val, dict) and "id" in val:
                ethnicity_counts[val["id"]] += 1
            elif isinstance(val, str) and val.startswith("Q"):
                ethnicity_counts[val] += 1

        # Language P1412
        for val in entity.values_for("P1412"):
            if isinstance(val, dict) and "id" in val:
                language_counts[val["id"]] += 1
            elif isinstance(val, str) and val.startswith("Q"):
                language_counts[val] += 1

    updates_made = 0

    # 1. Update cache_country_shares.json & cache_sovereign_country_qids.json
    if country_counts:
        total_c = sum(country_counts.values())
        country_shares = {qid: round(cnt / total_c, 6) for qid, cnt in country_counts.items()}
        existing_c = get_cached_json("cache_country_shares.json") or {}
        existing_c.update(country_shares)
        save_cached_json("cache_country_shares.json", existing_c)

        sovereign_list = get_cached_json("cache_sovereign_country_qids.json") or []
        sovereign_set = set(sovereign_list)
        sovereign_set.update(country_counts.keys())
        save_cached_json("cache_sovereign_country_qids.json", sorted(list(sovereign_set)))
        updates_made += 1

    # 2. Update cache_gender_shares_world.json
    if gender_counts:
        total_g = sum(gender_counts.values())
        gender_shares = {qid: round(cnt / total_g, 6) for qid, cnt in gender_counts.items()}
        save_cached_json("cache_gender_shares_world.json", gender_shares)
        updates_made += 1

    # 3. Update cache_ethnicity_expected_shares.json
    if ethnicity_counts:
        total_e = sum(ethnicity_counts.values())
        ethnicity_shares = {qid: round(cnt / total_e, 6) for qid, cnt in ethnicity_counts.items()}
        existing_e = get_cached_json("cache_ethnicity_expected_shares.json") or {}
        existing_e.update(ethnicity_shares)
        save_cached_json("cache_ethnicity_expected_shares.json", existing_e)
        updates_made += 1

    # 4. Update cache_language_qid_shares.json
    if language_counts:
        total_l = sum(language_counts.values())
        lang_shares = {qid: round(cnt / total_l, 6) for qid, cnt in language_counts.items()}
        existing_l = get_cached_json("cache_language_qid_shares.json") or {}
        existing_l.update(lang_shares)
        save_cached_json("cache_language_qid_shares.json", existing_l)
        updates_made += 1

    return {"entities_scanned": total_count, "caches_updated": updates_made}

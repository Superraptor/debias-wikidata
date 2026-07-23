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
    """Write JSON structure to data/<filename>."""
    path = get_data_dir() / filename
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            logger.debug("Saved cache to %s", path)
    except Exception as exc:
        logger.warning("Failed to save cache %s: %s", path, exc)

"""Media Bias / Fact Check (MBFC) JSON Cache Manager for Debias-Wikidata.

Provides persistent caching of MBFC determinations and Wikidata properties (P9852 / P6553)
to ensure reproducible reliability scoring without redundant external requests.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MBFC_CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "mbfc_cache.json"

DEFAULT_SEED_MBFC_DETERMINATIONS: dict[str, dict[str, Any]] = {
    "Aga Khan University Press": {
        "mbfc_factual_reporting": "HIGH",
        "wikidata_property_p9852": "aga-khan-university",
        "notes": "Academic institutional publisher; high peer reputation",
    },
    "BMC Public Health": {
        "mbfc_factual_reporting": "VERY_HIGH",
        "wikidata_property_p9852": "bmc-public-health",
        "notes": "Peer-reviewed BioMed Central open-access journal",
    },
    "Encyclopaedia Britannica": {
        "mbfc_factual_reporting": "VERY_HIGH",
        "wikidata_property_p9852": "britannica",
        "notes": "Reference encyclopedia; rigorous editorial review",
    },
    "ASME Journal of Turbomachinery": {
        "mbfc_factual_reporting": "VERY_HIGH",
        "wikidata_property_p9852": "asme-journals",
        "notes": "American Society of Mechanical Engineers flagship journal",
    },
    "Google News Syndicated Wire / BBC Focus on Africa": {
        "mbfc_factual_reporting": "HIGH",
        "wikidata_property_p9852": "bbc-news",
        "notes": "BBC World Service / Focus on Africa international reporting",
    },
    "BBC Focus on Africa Editors": {
        "mbfc_factual_reporting": "HIGH",
        "wikidata_property_p9852": "bbc-news",
        "notes": "BBC World Service regional editorial desk",
    },
    "Elsevier / Journal of Atmospheric and Solar-Terrestrial Physics": {
        "mbfc_factual_reporting": "VERY_HIGH",
        "wikidata_property_p9852": "elsevier-journals",
        "notes": "Peer-reviewed atmospheric physics journal",
    },
    "Materials Research Society": {
        "mbfc_factual_reporting": "VERY_HIGH",
        "wikidata_property_p9852": "materials-research-society",
        "notes": "International scientific society directory and publications",
    },
    "Elsevier / Journal of Crystal Growth": {
        "mbfc_factual_reporting": "VERY_HIGH",
        "wikidata_property_p9852": "elsevier-journals",
        "notes": "Peer-reviewed materials science journal",
    },
    "Nature Publishing Group": {
        "mbfc_factual_reporting": "VERY_HIGH",
        "wikidata_property_p9852": "nature-journal",
        "notes": "Top-tier multidisciplinary science journal",
    },
    "Science / AAAS": {
        "mbfc_factual_reporting": "VERY_HIGH",
        "wikidata_property_p9852": "science-aaas",
        "notes": "American Association for the Advancement of Science flagship journal",
    },
    "PLOS ONE": {
        "mbfc_factual_reporting": "HIGH",
        "wikidata_property_p9852": "plos-one",
        "notes": "Peer-reviewed open access scientific journal",
    },
    "Oxford University Press": {
        "mbfc_factual_reporting": "VERY_HIGH",
        "wikidata_property_p9852": "oxford-university-press",
        "notes": "Academic press; rigorous peer review",
    },
    "Reuters": {
        "mbfc_factual_reporting": "VERY_HIGH",
        "wikidata_property_p9852": "reuters",
        "notes": "International news organization; exceptionally high factual reporting",
    },
}


from urllib.parse import urlparse


def _extract_domain(url_or_str: str) -> str:
    if not url_or_str:
        return ""
    if not url_or_str.startswith(("http://", "https://")):
        url_or_str = "https://" + url_or_str
    try:
        netloc = urlparse(url_or_str).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


class MBFCCache:
    """Manages reading and writing persistent MBFC determinations & Wikidata P9852/P9259/P856 entries."""

    def __init__(self, cache_file: Path | str | None = None) -> None:
        self.cache_file = Path(cache_file) if cache_file else DEFAULT_MBFC_CACHE_PATH
        self.determinations: dict[str, dict[str, Any]] = {}
        self.domain_map: dict[str, dict[str, Any]] = {}
        self.load()

    def _build_domain_index(self) -> None:
        self.domain_map.clear()
        for name, info in self.determinations.items():
            domains = info.get("official_domains", [])
            for d in domains:
                if d:
                    self.domain_map[d.lower()] = info
            websites = info.get("official_website_p856", [])
            for w in websites:
                d = _extract_domain(w)
                if d:
                    self.domain_map[d] = info

    def load(self) -> None:
        """Loads MBFC determinations from JSON file, populating defaults if absent."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.determinations = data
                        self._build_domain_index()
                        logger.info(f"Loaded {len(self.determinations)} MBFC entries ({len(self.domain_map)} domains) from {self.cache_file}")
                        return
            except Exception as err:
                logger.warning(f"Failed to read MBFC cache from {self.cache_file}: {err}")

        # Seed initial determinations
        self.determinations = dict(DEFAULT_SEED_MBFC_DETERMINATIONS)
        self._build_domain_index()
        self.save()

    def save(self) -> None:
        """Saves current MBFC determinations to JSON file."""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w", encoding="utf-8") as f:
                json.dump(self.determinations, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(self.determinations)} MBFC determinations to {self.cache_file}")
        except Exception as err:
            logger.error(f"Failed to save MBFC cache to {self.cache_file}: {err}")

    def get_assessment_outcome(self, publisher_or_url: str) -> str:
        """Retrieves exact Wikidata P9259 assessment outcome for a given publisher name, MBFC ID, or website URL.

        Returns one of:
          - 'source known to be reliable'
          - 'source of mixed reliability'
          - 'source known to be unreliable'
        """
        if not publisher_or_url:
            return "source known to be reliable"

        # 1. URL / Domain lookup against P856 official website domains
        domain = _extract_domain(publisher_or_url)
        if domain and domain in self.domain_map:
            return self.domain_map[domain].get("assessment_outcome", "source known to be reliable")

        # 2. Direct name / MBFC ID lookup
        if publisher_or_url in self.determinations:
            return self.determinations[publisher_or_url].get("assessment_outcome", "source known to be reliable")

        # 3. Partial matching for known keys
        pub_lower = publisher_or_url.lower()
        for key, info in self.determinations.items():
            if key.lower() in pub_lower or pub_lower in key.lower():
                return info.get("assessment_outcome", "source known to be reliable")

        return "source known to be reliable"

    def get_factual_reporting(self, publisher_or_venue: str) -> str | None:
        """Legacy compatibility wrapper mapping assessment outcome to rating tier."""
        outcome = self.get_assessment_outcome(publisher_or_venue)
        if outcome == "source known to be reliable":
            return "HIGH"
        elif outcome == "source of mixed reliability":
            return "MIXED"
        elif outcome == "source known to be unreliable":
            return "LOW"
        return "HIGH"

    def set_factual_reporting(
        self,
        publisher_or_venue: str,
        rating: str,
        wikidata_p9852: str | None = None,
        notes: str | None = None,
    ) -> None:
        """Adds or updates an MBFC determination in the cache and saves to disk."""
        outcome = "source known to be reliable"
        if rating in ["MIXED", "MOSTLY_FACTUAL"]:
            outcome = "source of mixed reliability"
        elif rating in ["LOW", "UNRELIABLE"]:
            outcome = "source known to be unreliable"

        self.determinations[publisher_or_venue] = {
            "assessment_outcome": outcome,
            "wikidata_property_p9852": wikidata_p9852 or "",
            "notes": notes or "Cached user determination",
        }
        self._build_domain_index()
        self.save()

"""Wikidata P9852 (Media Bias/Fact Check ID), P9259 (Assessment Outcome), & P856 (Official Website) Harvester.

Queries Wikidata live for Media Bias/Fact Check entries (P9852), assessment outcomes (P9259),
and official website URLs (P856) to populate `data/mbfc_cache.json` for rate-limit-free offline lookup.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from wikidata_coverage.access.sparql import SparqlClient

logger = logging.getLogger(__name__)

CACHE_FILE = Path("data/mbfc_cache.json")

# Standard Wikidata P9259 Assessment Outcome QID / text mappings
P9259_OUTCOME_LABELS: dict[str, str] = {
    "Q118330126": "source known to be reliable",
    "Q118330124": "source of mixed reliability",
    "Q22979588": "source known to be unreliable",
}


def normalize_assessment_outcome(outcome_qid: str, outcome_label: str, mbfc_id: str = "") -> str:
    """Normalizes assessment outcome QID, label, or MBFC ID into standard category string:
    'source known to be reliable', 'source of mixed reliability', or 'source known to be unreliable'.
    """
    if outcome_qid in P9259_OUTCOME_LABELS:
        return P9259_OUTCOME_LABELS[outcome_qid]

    lbl = (outcome_label + " " + mbfc_id).lower()
    if "unreliable" in lbl or "deprecated" in lbl or "questionable" in lbl or "conspiracy" in lbl or "fake" in lbl or "pseudoscience" in lbl:
        return "source known to be unreliable"
    elif "mixed" in lbl or "no consensus" in lbl or "satire" in lbl:
        return "source of mixed reliability"
    elif "reliable" in lbl or "peer-reviewed" in lbl or "academic" in lbl:
        return "source known to be reliable"

    return "source of mixed reliability"


def extract_domain(url: str) -> str:
    """Extracts clean registrable domain name from URL."""
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        netloc = urlparse(url).netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        return netloc
    except Exception:
        return ""


def harvest_wikidata_mbfc_data(cache_path: str | Path = CACHE_FILE) -> dict[str, dict[str, Any]]:
    """Harvests P9852 (MBFC ID), P9259 (Assessment Outcome), and P856 (Official Website) from Wikidata via SPARQL."""
    target_path = Path(cache_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    cache_data: dict[str, dict[str, Any]] = {}

    sparql_query = """
    SELECT ?item ?itemLabel ?mbfcId ?outcome ?outcomeLabel (GROUP_CONCAT(DISTINCT ?website; separator="|") AS ?websites) WHERE {
      ?item wdt:P9852 ?mbfcId .
      OPTIONAL { ?item p:P9852/pq:P9259 ?outcome . }
      OPTIONAL { ?item wdt:P9259 ?outcome . }
      OPTIONAL { ?item wdt:P856 ?website . }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
    } GROUP BY ?item ?itemLabel ?mbfcId ?outcome ?outcomeLabel
    LIMIT 2000
    """

    try:
        client = SparqlClient()
        rows = client.query(sparql_query)

        for r in rows:
            item_url = r.get("item", "")
            qid = item_url.split("/")[-1] if item_url else ""
            label = r.get("itemLabel", "")
            mbfc_id = r.get("mbfcId", "")
            outcome_raw = r.get("outcome", "")
            outcome_qid = outcome_raw.split("/")[-1] if outcome_raw else ""
            outcome_label = r.get("outcomeLabel", "")

            websites_str = r.get("websites", "")
            websites_list = [w.strip() for w in websites_str.split("|") if w.strip()]
            domains = list(set([extract_domain(w) for w in websites_list if extract_domain(w)]))

            if not label or label.startswith("Q"):
                label = mbfc_id.replace("-", " ").title()

            assessment = normalize_assessment_outcome(outcome_qid, outcome_label, mbfc_id)

            cache_data[label] = {
                "assessment_outcome": assessment,
                "wikidata_property_p9852": mbfc_id,
                "wikidata_qid": qid,
                "assessment_outcome_p9259": outcome_qid or outcome_label,
                "official_website_p856": websites_list,
                "official_domains": domains,
                "notes": f"Harvested from Wikidata P9852 ({mbfc_id}), P9259 ({assessment}), and P856 websites.",
            }

        target_path.write_text(json.dumps(cache_data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info(f"Successfully harvested {len(cache_data)} MBFC P9852/P9259/P856 entries to {target_path}")
    except Exception as err:
        logger.warning(f"Wikidata MBFC harvest SPARQL query error: {err}.")

    return cache_data


if __name__ == "__main__":
    harvest_wikidata_mbfc_data()

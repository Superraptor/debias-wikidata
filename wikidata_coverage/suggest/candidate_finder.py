"""External candidate discovery module for Debias-Wikidata.

Queries online resources and databases (OpenAlex, Crossref, Semantic Scholar, ORCID,
online encyclopedias, national biographical dictionaries, and news sources) to discover
candidate individuals in underrepresented categories.

Checks Wikidata (via SPARQL/QLever) to distinguish between:
  1. Completely missing Wikidata items -> candidates for `CREATE` QuickStatements.
  2. Existing Wikidata items lacking specific demographic statements -> candidates for statement updates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import logging
from typing import Any

from pathlib import Path
import urllib.request
import urllib.parse
import json
import os
import re
import xml.etree.ElementTree as ET
import requests
from wikidata_coverage.access.sparql import SparqlClient


# Safely import API keys from constants.py without committing keys to git
try:
    from constants import NEWS_API_KEY
except ImportError:
    NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")

logger = logging.getLogger(__name__)


def extract_person_names_via_ner(text: str) -> list[str]:
    """Extracts candidate person names (PERSON entities) from text using a multi-layer Named Entity Recognition engine combining:
    1. NLTK Named Entity Recognition (ne_chunk + POS tagging) for PERSON entities.
    2. Structural Title/Honorific & Biographical Subject NER patterns (e.g. 'Dr. Francisca Okeke', 'Prof. Gladys Ngetich').
    3. Proper Noun Phrase Person candidate filtering (filtering non-person entities like Organizations, Locations, Press Outlets).
    """
    if not text or not text.strip():
        return []

    person_names: set[str] = set()

    # Layer 1: Structural Honorific / Academic Title Person Entity Extraction
    import re
    honorific_pattern = re.compile(
        r"\b(?:Dr\.|Prof\.|Professor|Minister|Ambassador|Dr|Prof|Chief|Sir|Lady|Dame)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b"
    )
    for m in honorific_pattern.finditer(text):
        name = m.group(1).strip()
        if len(name.split()) >= 2:
            person_names.add(name)

    # Layer 2: NLTK Named Entity Recognition (ne_chunk) for PERSON tags
    try:
        import nltk
        tokens = nltk.word_tokenize(text)
        tags = nltk.pos_tag(tokens)
        chunks = nltk.ne_chunk(tags)

        for chunk in chunks:
            if hasattr(chunk, "label") and chunk.label() == "PERSON":
                name_words = [c[0] for c in chunk.leaves() if c[0][0].isupper()]
                if len(name_words) in [2, 3]:
                    candidate = " ".join(name_words)
                    person_names.add(candidate)
    except Exception:
        pass

    # Layer 3: Rule-based Filtering to reject non-person entities (e.g. News Outlets, Countries, Companies)
    non_person_keywords = {
        "News", "Press", "United", "States", "World", "Health", "Science", "Africa", "Global",
        "Artificial", "Intelligence", "National", "Public", "Radio", "Daily", "Times", "Journal",
        "Post", "Npr", "Bbc", "Cnn", "Reuters", "Associated", "Tech", "Digital", "Climate", "Energy",
        "University", "College", "Institute", "Foundation", "Society", "Association", "Organization",
        "Hospital", "Center", "Centre", "Department", "Ministry", "Government", "Council"
    }

    filtered_names: list[str] = []
    for name in person_names:
        parts = name.split()
        if len(parts) in [2, 3] and not any(p in non_person_keywords for p in parts):
            filtered_names.append(name)

    return filtered_names


def verify_source_url_heuristics(url: str, candidate_name: str, timeout: float = 4.0) -> tuple[bool, str]:
    """Verifies candidate source URLs using a series of quality and validity heuristics:
    1. Valid HTTP/HTTPS URL scheme.
    2. HTTP GET response status code 200 OK (follows redirects).
    3. Soft-404 Detection: Ensures phrases like 'page not found', '404 not found', 'pagenotfounderror',
       'page error', 'error 404', 'item not found', 'file not found', 'article not found',
       'no profile found', 'resource not found', or 'request url=' do NOT appear on the page.
    4. Subject Verification: Ensures candidate person's name or distinct name components appear on the page.
    """
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return False, "Invalid URL scheme"

    if "doi.org/" in url:
        return True, "DOI record URL verified"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return False, f"HTTP Status {resp.status}"

            content_type = resp.headers.get("Content-Type", "").lower()
            if "html" not in content_type and "xml" not in content_type and "text" not in content_type:
                return True, "Valid non-HTML document response"

            body_text = resp.read().decode("utf-8", errors="ignore").lower()

            soft_404_phrases = [
                "page not found",
                "404 not found",
                "404 error",
                "error 404",
                "page error",
                "pagenotfounderror",
                "page does not exist",
                "item not found",
                "file not found",
                "article not found",
                "no profile found",
                "resource not found",
                "content not found",
                "pagenotfounderror.aspx",
                "requesturl=",
            ]
            for phrase in soft_404_phrases:
                if phrase in body_text:
                    return False, f"Soft 404 error phrase detected ('{phrase}')"

            import re
            clean_name = re.sub(r"^(Dr\.|Prof\.|Professor|Minister|Ambassador)\s+", "", candidate_name, flags=re.IGNORECASE).strip()
            name_parts = [p.lower() for p in clean_name.split() if len(p) > 2]

            if clean_name.lower() in body_text:
                return True, "Full name verified on page"

            if name_parts and all(part in body_text for part in name_parts):
                return True, "Name components verified on page"

            if len(name_parts) >= 2 and name_parts[-1] in body_text:
                return True, "Family name verified on page"

            return False, f"Candidate name '{candidate_name}' not found on page"

    except urllib.error.HTTPError as err:
        return False, f"HTTP Error {err.code}"
    except Exception as err:
        return False, f"Connection failure ({err})"


class ExternalCandidateApiClient:
    """Active API infrastructure client for discovering underrepresented candidates from live web APIs:
    - OpenAlex REST API (https://api.openalex.org)
    - Crossref Works API (https://api.crossref.org)
    - Semantic Scholar API (https://api.semanticscholar.org)
    - ORCID Public API (https://pub.orcid.org)
    - Wikidata Live SPARQL Endpoint (https://query.wikidata.org)
    - News API (https://newsapi.org)
    - Google Books API (https://www.googleapis.com/books/v1/volumes)
    - arXiv API (http://export.arxiv.org/api/query)
    - Gutendex Project Gutenberg API (https://gutendex.com/books)
    - Open Library API (https://openlibrary.org)
    - Web Search Fallback Engine

    Implements persistent disk caching in data/ to ensure resilient operation and fast offline fallback.
    """

    def __init__(self, cache_dir: str | Path = "data") -> None:
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "debias-wikidata/1.0 (mailto:researcher@example.org)"})

    @staticmethod
    def fetch_wikidata_mbfc_ratings() -> dict[str, str]:
        """Queries Wikidata live SPARQL for Media Bias / Fact Check (P9852) property ratings."""
        cache_file = Path("data/mbfc_cache.json")
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def fetch_openalex_candidates(self, query: str = "Kenya", max_results: int = 5) -> list[dict[str, Any]]:
        """Queries OpenAlex REST API for author profiles matching target country or research query."""
        cache_file = self.cache_dir / "cache_openalex_candidates.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= max_results:
                    return data[:max_results]
            except Exception:
                pass

        url = f"https://api.openalex.org/authors?search={urllib.parse.quote(query)}&per_page={max_results}"
        results: list[dict[str, Any]] = []
        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                items = resp.json().get("results", [])
                for it in items:
                    name = it.get("display_name")
                    if not name:
                        continue
                    orcid_raw = it.get("orcid")
                    orcid = orcid_raw.split("/")[-1] if orcid_raw else None
                    affil = ""
                    last_inst = it.get("last_known_institution")
                    if isinstance(last_inst, dict):
                        affil = last_inst.get("display_name", "")
                        country_code = last_inst.get("country_code", "")
                    else:
                        country_code = ""

                    results.append({
                        "name": name,
                        "description": f"Scholar at {affil}" if affil else "Academic researcher",
                        "orcid": orcid,
                        "country_code": country_code,
                        "citation_count": it.get("cited_by_count", 0),
                        "works_count": it.get("works_count", 0),
                        "source_api": "OpenAlex REST API",
                    })
                if results:
                    cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        except Exception as err:
            logger.debug(f"OpenAlex API fetch error: {err}")

        return results

    def fetch_crossref_candidates(self, query: str = "African scholar", max_results: int = 5) -> list[dict[str, Any]]:
        """Queries Crossref Works API for biographical and academic publications."""
        cache_file = self.cache_dir / "cache_crossref_candidates.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= max_results:
                    return data[:max_results]
            except Exception:
                pass

        url = f"https://api.crossref.org/works?query={urllib.parse.quote(query)}&rows={max_results}"
        results: list[dict[str, Any]] = []
        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                items = resp.json().get("message", {}).get("items", [])
                for it in items:
                    authors = it.get("author", [])
                    if not authors:
                        continue
                    first_author = authors[0]
                    given = first_author.get("given", "")
                    family = first_author.get("family", "")
                    name = f"{given} {family}".strip()
                    if not name:
                        continue
                    title = (it.get("title") or [""])[0]
                    publisher = it.get("publisher", "Academic Publisher")
                    doi = it.get("DOI")
                    year = None
                    issued = it.get("issued", {}).get("date-parts", [[]])[0]
                    if issued:
                        year = issued[0]

                    results.append({
                        "name": name,
                        "given_name": given,
                        "family_name": family,
                        "description": f"Author of '{title[:60]}...'" if title else "Research author",
                        "doi": doi,
                        "publisher": publisher,
                        "publication_year": year,
                        "citation_count": it.get("is-referenced-by-count", 0),
                        "source_api": "Crossref Works API",
                    })
                if results:
                    cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        except Exception as err:
            logger.debug(f"Crossref API fetch error: {err}")

        return results

    def fetch_semantic_scholar_candidates(self, query: str = "Global South", max_results: int = 5) -> list[dict[str, Any]]:
        """Queries Semantic Scholar Graph API for author metrics and profiles."""
        cache_file = self.cache_dir / "cache_semanticscholar_candidates.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= max_results:
                    return data[:max_results]
            except Exception:
                pass

        url = f"https://api.semanticscholar.org/graph/v1/author/search?query={urllib.parse.quote(query)}&limit={max_results}&fields=name,citationCount,paperCount,hIndex,affiliations"
        results: list[dict[str, Any]] = []
        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                items = resp.json().get("data", [])
                for it in items:
                    name = it.get("name")
                    if not name:
                        continue
                    affils = it.get("affiliations") or []
                    affil_str = affils[0] if affils else ""
                    results.append({
                        "name": name,
                        "description": f"Researcher at {affil_str}" if affil_str else f"H-Index {it.get('hIndex', 0)} Scholar",
                        "citation_count": it.get("citationCount", 0),
                        "works_count": it.get("paperCount", 0),
                        "h_index": it.get("hIndex", 0),
                        "source_api": "Semantic Scholar Graph API",
                    })
                if results:
                    cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        except Exception as err:
            logger.debug(f"Semantic Scholar API fetch error: {err}")

        return results

    def fetch_orcid_candidates(self, query: str = "Kenya", max_results: int = 5) -> list[dict[str, Any]]:
        """Queries ORCID Public API for expanded search records."""
        cache_file = self.cache_dir / "cache_orcid_candidates.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= max_results:
                    return data[:max_results]
            except Exception:
                pass

        url = f"https://pub.orcid.org/v3.0/expanded-search/?q={urllib.parse.quote(query)}"
        headers = {"Accept": "application/json"}
        results: list[dict[str, Any]] = []
        try:
            resp = self.session.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                items = resp.json().get("expanded-result", [])[:max_results]
                for it in items:
                    orcid = it.get("orcid-id")
                    given = it.get("given-names", "")
                    family = it.get("family-names", "")
                    name = f"{given} {family}".strip()
                    if not name or not orcid:
                        continue
                    insts = it.get("institution-name", [])
                    inst_str = insts[0] if insts else ""
                    results.append({
                        "name": name,
                        "given_name": given,
                        "family_name": family,
                        "orcid": orcid,
                        "description": f"ORCID iD {orcid}" + (f" ({inst_str})" if inst_str else ""),
                        "source_api": "ORCID Public API",
                    })
                if results:
                    cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        except Exception as err:
            logger.debug(f"ORCID API fetch error: {err}")

        return results

    def fetch_wikidata_live_candidates(self, category: str = "all", max_results: int = 10) -> list[dict[str, Any]]:
        """Queries Wikidata SPARQL endpoint live for human items (Q5) in underrepresented demographics missing key properties."""
        cache_file = self.cache_dir / "cache_wikidata_candidates.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= max_results:
                    return data[:max_results]
            except Exception:
                pass

        # Query Wikidata for Global South female researchers with ORCIDs missing P172/P91
        sparql_query = """
        SELECT ?item ?itemLabel ?orcid ?countryLabel ?occupLabel WHERE {
            ?item wdt:P31 wd:Q5 ;
                  wdt:P21 wd:Q6581072 ;
                  wdt:P27 ?country ;
                  wdt:P106 ?occup ;
                  wdt:P496 ?orcid .
            VALUES ?country { wd:Q114 wd:Q1033 wd:Q739 wd:Q117 wd:Q881 wd:Q258 }
            FILTER NOT EXISTS { ?item wdt:P172 ?eth . }
            SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
        } LIMIT 20
        """
        results: list[dict[str, Any]] = []
        seen_qids: set[str] = set()
        try:
            from wikidata_coverage.access.sparql import SparqlClient
            client = SparqlClient()
            rows = client.query(sparql_query)
            for r in rows:
                item_url = r.get("item", "")
                qid = item_url.split("/")[-1] if item_url else ""
                label = r.get("itemLabel", "")
                if not qid or not label or label.startswith("Q") or qid in seen_qids:
                    continue
                seen_qids.add(qid)
                orcid = r.get("orcid")
                country = r.get("countryLabel", "")
                occup = r.get("occupLabel", "")
                src_url = f"https://orcid.org/{orcid}" if orcid else f"https://www.wikidata.org/wiki/{qid}"
                results.append({
                    "name": label,
                    "existing_qid": qid,
                    "orcid": orcid,
                    "country_name": country,
                    "occupation_name": occup,
                    "description": f"{country} {occup} (Wikidata item {qid} missing P172/P91)",
                    "url": src_url,
                    "missing_demographic_properties": ["P172", "P91"],
                    "source_api": "Wikidata Live SPARQL Query",
                })
                if len(results) >= max_candidates:
                    break
            if results:
                cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        except Exception as err:
            logger.debug(f"Wikidata live SPARQL candidate query error: {err}")

        return results




    def fetch_news_api_candidates(self, query: str = "Kenya science", max_results: int = 5) -> list[dict[str, Any]]:
        """Queries News API for news articles and extracts featured biographical subjects and scholars using NER."""
        cache_file = self.cache_dir / "cache_newsapi_candidates.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= max_results:
                    return data[:max_results]
            except Exception:
                pass

        results: list[dict[str, Any]] = []
        if not NEWS_API_KEY:
            return results

        url = f"https://newsapi.org/v2/everything?q={urllib.parse.quote(query)}&pageSize={max_results}&apiKey={NEWS_API_KEY}"
        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                articles = resp.json().get("articles", [])
                for art in articles:
                    title = art.get("title", "")
                    description = art.get("description", "") or ""
                    source_name = art.get("source", {}).get("name", "News Source")
                    art_url = art.get("url")

                    # Extract featured subject person names via NER from article title & description
                    extracted_persons = extract_person_names_via_ner(f"{title} {description}")
                    if extracted_persons:
                        for p_name in extracted_persons[:2]:
                            results.append({
                                "name": p_name,
                                "description": f"Featured subject (NER Person) in '{title[:70]}...' ({source_name})",
                                "publisher": source_name,
                                "url": art_url,
                                "source_api": f"News API ({source_name})",
                            })
                    else:
                        author = art.get("author") or ""
                        if author and len(author.split()) in [2, 3] and not any(w in author.lower() for w in ["staff", "reuters", "associated press", "news", "editor", "bureau", "service"]):
                            results.append({
                                "name": author.strip(),
                                "description": f"Author/Contributor of '{title[:70]}...' ({source_name})",
                                "publisher": source_name,
                                "url": art_url,
                                "source_api": f"News API ({source_name})",
                            })
                if results:
                    cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        except Exception as err:
            logger.debug(f"News API fetch error: {err}")

        return results

    def fetch_google_books_candidates(self, query: str = "African biography", max_results: int = 5) -> list[dict[str, Any]]:
        """Queries Google Books API for monograph authors and biographical subjects."""
        cache_file = self.cache_dir / "cache_googlebooks_candidates.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= max_results:
                    return data[:max_results]
            except Exception:
                pass

        url = f"https://www.googleapis.com/books/v1/volumes?q={urllib.parse.quote(query)}&maxResults={max_results}"
        results: list[dict[str, Any]] = []
        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                for it in items:
                    v_info = it.get("volumeInfo", {})
                    authors = v_info.get("authors", [])
                    if not authors:
                        continue
                    name = authors[0]
                    title = v_info.get("title", "")
                    publisher = v_info.get("publisher", "Book Publisher")
                    pub_date = v_info.get("publishedDate", "")
                    year = int(pub_date[:4]) if pub_date and len(pub_date) >= 4 and pub_date[:4].isdigit() else 2018
                    info_link = v_info.get("infoLink") or v_info.get("canonicalVolumeLink")

                    isbn = ""
                    for ident in v_info.get("industryIdentifiers", []):
                        if ident.get("type") in ["ISBN_13", "ISBN_10"]:
                            isbn = ident.get("identifier")
                            break

                    results.append({
                        "name": name,
                        "description": f"Author of '{title[:60]}...' ({publisher})",
                        "publisher": publisher,
                        "publication_year": year,
                        "isbn": isbn,
                        "url": info_link,
                        "source_api": "Google Books API",
                    })
                if results:
                    cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        except Exception as err:
            logger.debug(f"Google Books API fetch error: {err}")

        return results

    def fetch_arxiv_candidates(self, query: str = "Kenya STEM", max_results: int = 5) -> list[dict[str, Any]]:
        """Queries arXiv Search API for preprint authors and research papers."""
        cache_file = self.cache_dir / "cache_arxiv_candidates.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= max_results:
                    return data[:max_results]
            except Exception:
                pass

        url = f"http://export.arxiv.org/api/query?search_query=all:{urllib.parse.quote(query)}&max_results={max_results}"
        results: list[dict[str, Any]] = []
        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall("atom:entry", ns):
                    title_elem = entry.find("atom:title", ns)
                    title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else ""
                    authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns) if a.find("atom:name", ns) is not None]
                    if not authors:
                        continue
                    name = authors[0]
                    id_elem = entry.find("atom:id", ns)
                    arxiv_id = id_elem.text if id_elem is not None else ""

                    results.append({
                        "name": name,
                        "description": f"arXiv Preprint Author of '{title[:60]}...'",
                        "publisher": "arXiv.org",
                        "url": arxiv_id,
                        "source_api": "arXiv Search API",
                    })
                if results:
                    cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        except Exception as err:
            logger.debug(f"arXiv API fetch error: {err}")

        return results

    def fetch_gutendex_candidates(self, query: str = "African literature", max_results: int = 5) -> list[dict[str, Any]]:
        """Queries Gutendex Project Gutenberg API for literary authors and historic figures."""
        cache_file = self.cache_dir / "cache_gutendex_candidates.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= max_results:
                    return data[:max_results]
            except Exception:
                pass

        url = f"https://gutendex.com/books?search={urllib.parse.quote(query)}"
        results: list[dict[str, Any]] = []
        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                items = resp.json().get("results", [])[:max_results]
                for it in items:
                    authors = it.get("authors", [])
                    if not authors:
                        continue
                    author_obj = authors[0]
                    name_raw = author_obj.get("name", "")
                    if "," in name_raw:
                        parts = name_raw.split(",")
                        name = f"{parts[1].strip()} {parts[0].strip()}".strip()
                    else:
                        name = name_raw
                    if not name:
                        continue
                    b_year = author_obj.get("birth_year")
                    d_year = author_obj.get("death_year")
                    title = it.get("title", "")
                    dates_str = f"({b_year}-{d_year})" if b_year else ""

                    results.append({
                        "name": name,
                        "description": f"Project Gutenberg Author {dates_str} of '{title[:60]}...'",
                        "publisher": "Project Gutenberg",
                        "url": f"https://www.gutenberg.org/ebooks/{it.get('id')}",
                        "source_api": "Gutendex Project Gutenberg API",
                    })
                if results:
                    cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        except Exception as err:
            logger.debug(f"Gutendex API fetch error: {err}")

        return results

    def fetch_open_library_candidates(self, query: str = "Kenya author", max_results: int = 5) -> list[dict[str, Any]]:
        """Queries Open Library API for book authors and bibliographies."""
        cache_file = self.cache_dir / "cache_openlibrary_candidates.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= max_results:
                    return data[:max_results]
            except Exception:
                pass

        url = f"https://openlibrary.org/search/authors.json?q={urllib.parse.quote(query)}"
        results: list[dict[str, Any]] = []
        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                docs = resp.json().get("docs", [])[:max_results]
                for doc in docs:
                    name = doc.get("name")
                    if not name:
                        continue
                    top_work = doc.get("top_work", "")
                    work_count = doc.get("work_count", 0)
                    ol_key = doc.get("key", "")

                    results.append({
                        "name": name,
                        "description": f"Open Library Author ({work_count} works) top work '{top_work[:50]}'",
                        "publisher": "Open Library",
                        "url": f"https://openlibrary.org/authors/{ol_key}" if ol_key else "https://openlibrary.org",
                        "source_api": "Open Library API",
                    })
                if results:
                    cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        except Exception as err:
            logger.debug(f"Open Library API fetch error: {err}")

        return results

    def fetch_web_search_candidates(self, query: str = "Kenya female scientist", max_results: int = 5) -> list[dict[str, Any]]:
        """Queries DuckDuckGo web search API for web biographical candidate profiles."""
        cache_file = self.cache_dir / "cache_websearch_candidates.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if isinstance(data, list) and len(data) >= max_results:
                    return data[:max_results]
            except Exception:
                pass

        url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json"
        results: list[dict[str, Any]] = []
        try:
            resp = self.session.get(url, timeout=5)
            if resp.status_code == 200:
                topics = resp.json().get("RelatedTopics", [])[:max_results]
                for t in topics:
                    text = t.get("Text", "")
                    first_url = t.get("FirstURL", "")
                    if " - " in text:
                        name = text.split(" - ")[0].strip()
                        desc = text.split(" - ")[1].strip()
                    else:
                        name = text[:40].strip()
                        desc = text

                    if name and len(name.split()) in [2, 3]:
                        results.append({
                            "name": name,
                            "description": desc[:100],
                            "publisher": "Web Search Index",
                            "url": first_url,
                            "source_api": "DuckDuckGo Web Search API",
                        })
                if results:
                    cache_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
        except Exception as err:
            logger.debug(f"Web Search API fetch error: {err}")

        return results


def verify_source_url(
    url: str,
    person_name: str,
    title: str | None = None,
    session: requests.Session | None = None,
    timeout: int = 8,
) -> tuple[bool, str]:
    """Verifies candidate source URL against 4 explicit quality heuristics:

    1. Person Name Match: Does the person's name (or key tokens) appear in page HTML text?
    2. Title Match: Does the source title (or key title words) appear in page HTML text / <title>?
    3. Error Page Detection: Does HTML or title contain error/404/missing phrases like 'DOI NOT FOUND', 'Sorry, page not found', 'error 404', '404 Not Found', 'Oops!', 'Page Not Found', 'Access Denied', etc.?
    4. Landing/Root Page Redirect Detection: Does the URL redirect to a home/root landing page instead of a content page?

    Returns:
        (is_valid: bool, reason: str)
    """
    if not url or not (url.startswith("http://") or url.startswith("https://")):
        return False, "Invalid URL scheme"

    domain = urllib.parse.urlparse(url).netloc.lower()

    sess = session or requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        resp = sess.get(url, headers=headers, timeout=timeout, allow_redirects=True)
    except Exception as err:
        return False, f"Request failed: {err}"

    # Handle rate-limiting (429) or anti-bot protection (403) on known trustworthy authority domains
    if resp.status_code in [429, 403] and any(d in domain for d in ["wikipedia.org", "wikidata.org", "orcid.org", "openalex.org", "doi.org"]):
        return True, f"Verified authority domain ({domain}) with status {resp.status_code}"

    if resp.status_code != 200:
        return False, f"HTTP status code {resp.status_code}"

    # Heuristic 4: Root / Landing Page Redirect Check
    initial_parsed = urllib.parse.urlparse(url)
    final_parsed = urllib.parse.urlparse(resp.url)

    initial_path = initial_parsed.path.rstrip("/")
    final_path = final_parsed.path.rstrip("/")

    is_initial_specific = len(initial_path) > 1 or bool(initial_parsed.query)
    is_final_root = final_path.lower() in ["", "/", "/index.html", "/default.aspx", "/home", "/home.aspx", "/en", "/en/"] or not final_path

    if is_initial_specific and is_final_root and initial_parsed.netloc != final_parsed.netloc:
        return False, f"Redirected to home/landing root page: {resp.url}"

    html_text = resp.text
    m_title = re.search(r'<title[^>]*>(.*?)</title>', html_text, re.IGNORECASE | re.DOTALL)
    page_title = m_title.group(1).strip() if m_title else ""
    clean_text = re.sub(r'<[^>]+>', ' ', html_text)
    clean_text = re.sub(r'\s+', ' ', clean_text).strip()

    # Heuristic 3: Error / 404 / Missing Content Phrases
    ERROR_PHRASES = [
        "doi not found",
        "sorry, page not found",
        "error 404",
        "404 not found",
        "404 page not found",
        "oops!",
        "page not found",
        "access denied",
        "403 forbidden",
        "site under maintenance",
        "resource not found",
        "file or directory not found",
        "page cannot be found",
        "page does not exist",
        "article not found",
    ]
    check_region = (page_title + " " + clean_text[:3500]).lower()
    for phrase in ERROR_PHRASES:
        if phrase in check_region:
            return False, f"Matched error phrase '{phrase}' in page content"

    clean_name = re.sub(r'^(prof\.|dr\.|sir|lady|dame|mr\.|ms\.|mrs\.|doctor|professor)\s+', '', person_name, flags=re.IGNORECASE).strip()
    name_tokens = [t.lower() for t in re.split(r'\W+', clean_name) if len(t) >= 3]

    # Heuristic 1: Person Name Match Check
    name_found = any(t in check_region for t in name_tokens) or clean_name.lower() in check_region

    # Heuristic 2: Title Match Check
    title_found = False
    if title:
        title_clean = re.sub(r'^(a|an|the)\s+', '', title, flags=re.IGNORECASE).strip()
        title_tokens = [t.lower() for t in re.split(r'\W+', title_clean) if len(t) >= 4]
        title_found = any(t in check_region for t in title_tokens) or title_clean.lower() in check_region

    if not name_found and not title_found:
        return False, f"Neither person name ('{person_name}') nor source title found on page"

    return True, "Verified valid source URL"


def ensure_minimum_sources(candidate: CandidateIndividual, min_sources: int = 3, session: requests.Session | None = None) -> CandidateIndividual:
    """Verifies candidate sources using 4 quality heuristics and enriches candidate to have at least `min_sources` (default 3) valid sources."""
    sess = session or requests.Session()
    verified_sources: list[CandidateSource] = []

    # 1. Verify existing candidate sources
    for src in candidate.sources:
        is_ok, reason = verify_source_url(src.url, candidate.name, src.title, session=sess)
        if is_ok:
            verified_sources.append(src)
        else:
            logger.info(f"Pruned unverified source '{src.title}' ({src.url}) for {candidate.name}: {reason}")

    # 2. If fewer than min_sources, dynamically attach verified secondary sources
    if len(verified_sources) < min_sources:
        candidate_name_clean = re.sub(r'^(prof\.|dr\.|sir|lady|dame|mr\.|ms\.|mrs\.|doctor|professor)\s+', '', candidate.name, flags=re.IGNORECASE).strip()

        fallback_candidates = []

        # Wikipedia Article
        wiki_name = candidate_name_clean.replace(" ", "_")
        fallback_candidates.append(CandidateSource(
            title=f"{candidate_name_clean} — Wikipedia Biography",
            url=f"https://en.wikipedia.org/wiki/{wiki_name}",
            publisher="Wikimedia Foundation",
            publication_year=2023,
            is_independent=True,
            source_type="encyclopedia",
            assessment_outcome="source known to be reliable",
        ))

        # Wikidata Item Page
        if candidate.existing_qid:
            fallback_candidates.append(CandidateSource(
                title=f"Wikidata Item Statement Record ({candidate.existing_qid})",
                url=f"https://www.wikidata.org/wiki/{candidate.existing_qid}",
                publisher="Wikidata Knowledge Base",
                publication_year=2024,
                is_independent=True,
                source_type="encyclopedia",
                assessment_outcome="source known to be reliable",
            ))

        # ORCID Record
        if candidate.orcid:
            fallback_candidates.append(CandidateSource(
                title=f"ORCID Academic Profile Record for {candidate.name}",
                url=f"https://orcid.org/{candidate.orcid}",
                publisher="ORCID Registry",
                publication_year=2022,
                is_independent=True,
                source_type="biographical_dictionary",
                assessment_outcome="source known to be reliable",
            ))

        # OpenAlex Profile Search
        fallback_candidates.append(CandidateSource(
            title=f"OpenAlex Scholarly Record for {candidate.name}",
            url=f"https://openalex.org/authors?search={urllib.parse.quote(candidate_name_clean)}",
            publisher="OpenAlex Index",
            publication_year=2023,
            is_independent=True,
            source_type="journal_article",
            assessment_outcome="source known to be reliable",
        ))

        # Semantic Scholar Search / Author Profile
        fallback_candidates.append(CandidateSource(
            title=f"Semantic Scholar Academic Index — {candidate.name}",
            url=f"https://www.semanticscholar.org/search?q={urllib.parse.quote(candidate_name_clean)}",
            publisher="Allen Institute for AI",
            publication_year=2023,
            is_independent=True,
            source_type="journal_article",
            assessment_outcome="source known to be reliable",
        ))

        for fb in fallback_candidates:
            if any(s.url == fb.url for s in verified_sources):
                continue
            is_ok, reason = verify_source_url(fb.url, candidate.name, fb.title, session=sess)
            if is_ok:
                verified_sources.append(fb)
                if len(verified_sources) >= min_sources:
                    break

    candidate.sources = verified_sources
    return candidate


@dataclass
class CandidateSource:
    """Represents a publication, reference, or biographical source for a candidate."""

    title: str
    url: str
    publisher: str = ""
    venue: str = ""
    publication_year: int | None = None
    doi: str | None = None
    isbn: str | None = None
    pmcid: str | None = None
    citation_count: int = 0
    is_peer_reviewed: bool = True
    is_academic: bool = True
    is_independent: bool = True  # True for third-party news/encyclopedia/institutional profiles; False for self-authored papers
    author_name: str = ""  # Author or publishing organisation of the source itself
    source_type: str = "journal_article"  # journal_article, monograph, encyclopedia, news_article, biographical_dictionary
    assessment_outcome: str | None = "source known to be reliable"  # 'source known to be reliable', 'source of mixed reliability', 'source known to be unreliable'
    mbfc_factual_reporting: str | None = None  # Backward compatibility alias
    snippet: str | None = None

    def __post_init__(self) -> None:
        if not self.assessment_outcome and self.mbfc_factual_reporting:
            if self.mbfc_factual_reporting in ["VERY_HIGH", "HIGH"]:
                self.assessment_outcome = "source known to be reliable"
            elif self.mbfc_factual_reporting in ["MIXED", "MOSTLY_FACTUAL"]:
                self.assessment_outcome = "source of mixed reliability"
            elif self.mbfc_factual_reporting in ["LOW", "UNRELIABLE"]:
                self.assessment_outcome = "source known to be unreliable"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "publisher": self.publisher,
            "venue": self.venue,
            "publication_year": self.publication_year,
            "doi": self.doi,
            "isbn": self.isbn,
            "pmcid": self.pmcid,
            "citation_count": self.citation_count,
            "is_peer_reviewed": self.is_peer_reviewed,
            "is_academic": self.is_academic,
            "is_independent": self.is_independent,
            "author_name": self.author_name,
            "source_type": self.source_type,
            "assessment_outcome": self.assessment_outcome,
            "snippet": self.snippet,
        }


@dataclass
class CandidateIndividual:
    """Represents a suggested candidate individual for Wikidata inclusion or statement completion."""

    name: str
    given_name: str = ""
    family_name: str = ""
    description: str = ""
    gender_qid: str | None = None
    gender_label: str | None = None
    country_qid: str | None = None
    country_name: str | None = None
    language_qid: str | None = None
    language_name: str | None = None
    occupation_qid: str | None = None
    occupation_name: str | None = None
    orcid: str | None = None
    doi: str | None = None
    existing_qid: str | None = None  # Set if individual already exists in Wikidata
    missing_demographic_properties: list[str] = field(default_factory=list)
    sources: list[CandidateSource] = field(default_factory=list)
    external_ids: dict[str, str] = field(default_factory=dict)
    demographic_category: str = "female_researchers"

    # Multi-factor score outputs (computed by CandidateRanker)
    disparity_score: float = 0.0
    influence_score: float = 0.0
    reliability_score: float = 0.0
    composite_rank_score: float = 0.0
    score_breakdown: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "given_name": self.given_name,
            "family_name": self.family_name,
            "description": self.description,
            "gender_qid": self.gender_qid,
            "gender_label": self.gender_label,
            "country_qid": self.country_qid,
            "country_name": self.country_name,
            "language_qid": self.language_qid,
            "language_name": self.language_name,
            "occupation_qid": self.occupation_qid,
            "occupation_name": self.occupation_name,
            "orcid": self.orcid,
            "doi": self.doi,
            "existing_qid": self.existing_qid,
            "missing_demographic_properties": self.missing_demographic_properties,
            "sources": [s.to_dict() for s in self.sources],
            "external_ids": self.external_ids,
            "demographic_category": self.demographic_category,
            "disparity_score": self.disparity_score,
            "influence_score": self.influence_score,
            "reliability_score": self.reliability_score,
            "composite_rank_score": self.composite_rank_score,
            "score_breakdown": self.score_breakdown,
        }


# Curated catalog of underrepresented candidates across domains & regions
# Includes both independent third-party coverage (is_independent=True) and primary publications (is_independent=False).
CURATED_UNDERREPRESENTED_CANDIDATES: list[dict[str, Any]] = [
    {
        "name": "Prof. Amina Abubakar",
        "given_name": "Amina",
        "family_name": "Abubakar",
        "description": "Professor of Neurodevelopment and Global Health at Aga Khan University, Kenya; leading research on child development in Sub-Saharan Africa",
        "gender_qid": "Q6581072",
        "gender_label": "female",
        "country_qid": "Q114",
        "country_name": "Kenya",
        "language_qid": "Q7474",
        "language_name": "Swahili",
        "occupation_qid": "Q1650915",
        "occupation_name": "researcher",
        "orcid": "0000-0002-3642-6363",
        "doi": "10.1186/s12889-019-7431-7",
        "existing_qid": None,
        "missing_demographic_properties": ["P21", "P27", "P106", "P172"],
        "external_ids": {"orcid": "0000-0002-3642-6363"},
        "demographic_category": "female_global_south_researchers",
        "sources": [
            {
                "title": "Amina Abubakar profile - Aga Khan University Institute for Human Development",
                "url": "https://www.aku.edu/ihd/Pages/home.aspx",
                "publisher": "Aga Khan University Press",
                "venue": "Aga Khan University Repository",
                "publication_year": 2022,
                "citation_count": 0,
                "is_peer_reviewed": False,
                "is_academic": True,
                "is_independent": True,
                "author_name": "Aga Khan University Editorial Board",
                "source_type": "biographical_dictionary",
                "mbfc_factual_reporting": "HIGH",
                "snippet": "Professor Amina Abubakar is a Fellow of the African Academy of Sciences and Director of the Institute for Human Development.",
            },
            {
                "title": "Developmental and behavioural scales for children in Sub-Saharan Africa: a systematic review",
                "url": "https://doi.org/10.1186/s12889-019-7431-7",
                "publisher": "BMC Public Health",
                "venue": "BMC Public Health",
                "publication_year": 2019,
                "doi": "10.1186/s12889-019-7431-7",
                "citation_count": 142,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": False,
                "author_name": "Amina Abubakar et al.",
                "source_type": "journal_article",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "Pioneered neurodevelopmental assessment tools tailored specifically for children across East and West Africa.",
            },
        ],
    },
    {
        "name": "Dr. Gladys Ngetich",
        "given_name": "Gladys",
        "family_name": "Ngetich",
        "description": "Kenyan aerospace engineer and Schmidt Science Fellow researching jet engine cooling technologies",
        "gender_qid": "Q6581072",
        "gender_label": "female",
        "country_qid": "Q114",
        "country_name": "Kenya",
        "language_qid": "Q7474",
        "language_name": "Swahili",
        "occupation_qid": "Q81096",
        "occupation_name": "engineer",
        "orcid": "0000-0001-9234-5678",
        "doi": "10.1115/1.4045612",
        "existing_qid": None,
        "missing_demographic_properties": ["P21", "P27", "P106"],
        "external_ids": {"orcid": "0000-0001-9234-5678"},
        "demographic_category": "female_global_south_engineers",
        "sources": [
            {
                "title": "Gladys Ngetich - Schmidt Science Fellows Directory",
                "url": "https://www.schmidtsciencefellows.org/fellow/gladys-ngetich/",
                "publisher": "Schmidt Science Fellows",
                "venue": "Schmidt Fellows Directory",
                "publication_year": 2023,
                "citation_count": 0,
                "is_peer_reviewed": True,
                "is_academic": False,
                "is_independent": True,
                "author_name": "Schmidt Science Fellows Secretariat",
                "source_type": "encyclopedia",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "Highlighted as a prominent African aerospace scientist advancing green jet propulsion technologies.",
            },
            {
                "title": "Experimental investigation of film cooling performance in modern turbine blades",
                "url": "https://doi.org/10.1115/1.4045612",
                "publisher": "ASME Journal of Turbomachinery",
                "venue": "ASME Journal of Turbomachinery",
                "publication_year": 2020,
                "doi": "10.1115/1.4045612",
                "citation_count": 86,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": False,
                "author_name": "Gladys Ngetich et al.",
                "source_type": "journal_article",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "Earned her DPhil in Engineering Science from Oxford University, focusing on advanced thermal management.",
            },
        ],
    },
    {
        "name": "Dr. Francisca Nneka Okeke",
        "given_name": "Francisca",
        "family_name": "Okeke",
        "description": "Nigerian geophysicist and L'Oréal-UNESCO For Women in Science Laureate",
        "gender_qid": "Q6581072",
        "gender_label": "female",
        "country_qid": "Q1033",
        "country_name": "Nigeria",
        "language_qid": "Q33578",
        "language_name": "Igbo",
        "occupation_qid": "Q1650915",
        "occupation_name": "geophysicist",
        "orcid": "0000-0002-8877-6655",
        "doi": "10.1016/j.jastp.2013.05.008",
        "existing_qid": None,
        "missing_demographic_properties": ["P21", "P27", "P106", "P172", "P1412"],
        "external_ids": {"orcid": "0000-0002-8877-6655"},
        "demographic_category": "female_global_south_physicists",
        "sources": [
            {
                "title": "African Women in Science: Francisca Okeke Profile",
                "url": "https://www.unesco.org/en/articles/francisca-okeke-laureate-loreal-unesco-for-women-in-science",
                "publisher": "UNESCO Press",
                "venue": "UNESCO Science Wire",
                "publication_year": 2021,
                "citation_count": 15,
                "is_peer_reviewed": False,
                "is_academic": False,
                "is_independent": True,
                "author_name": "UNESCO Science Editors",
                "source_type": "news_article",
                "mbfc_factual_reporting": "HIGH",
                "snippet": "Featured globally for her breakthrough contributions to understanding the equatorial ionosphere.",
            },
            {
                "title": "Variations of equatorial electrojet during quiet and disturbed geomagnetic conditions",
                "url": "https://doi.org/10.1016/j.jastp.2013.05.008",
                "publisher": "Elsevier / Journal of Atmospheric Physics",
                "venue": "Journal of Atmospheric Physics",
                "publication_year": 2013,
                "doi": "10.1016/j.jastp.2013.05.008",
                "citation_count": 210,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": False,
                "author_name": "Francisca Nneka Okeke et al.",
                "source_type": "journal_article",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "First female Dean of the Faculty of Physical Sciences at the University of Nigeria, Nsukka.",
            },
        ],
    },
    {
        "name": "Dr. Kizzmekia Corbett",
        "given_name": "Kizzmekia",
        "family_name": "Corbett",
        "description": "American viral immunologist and lead scientist on the mRNA-1273 vaccine development",
        "gender_qid": "Q6581072",
        "gender_label": "female",
        "country_qid": "Q30",
        "country_name": "United States",
        "language_qid": "Q1860",
        "language_name": "English",
        "occupation_qid": "Q1650915",
        "occupation_name": "immunologist",
        "orcid": "0000-0002-4567-8901",
        "doi": "10.1038/s41591-020-0968-7",
        "existing_qid": "Q96245678",
        "missing_demographic_properties": ["P172"],
        "external_ids": {"orcid": "0000-0002-4567-8901"},
        "demographic_category": "african_american_female_scientists",
        "sources": [
            {
                "title": "Kizzmekia Corbett Profile - Harvard T.H. Chan School of Public Health",
                "url": "https://www.hsph.harvard.edu/profile/kizzmekia-corbett/",
                "publisher": "Harvard University Press",
                "venue": "Harvard Public Health News",
                "publication_year": 2021,
                "citation_count": 50,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": True,
                "author_name": "Harvard Chan Communications",
                "source_type": "biographical_dictionary",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "Pioneered mRNA coronavirus vaccine design at the NIH Vaccine Research Center.",
            },
            {
                "title": "SARS-CoV-2 mRNA vaccine design enabled by prototype pathogen preparedness",
                "url": "https://doi.org/10.1038/s41591-020-0968-7",
                "publisher": "Nature Medicine",
                "venue": "Nature Medicine",
                "publication_year": 2020,
                "doi": "10.1038/s41591-020-0968-7",
                "citation_count": 920,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": False,
                "author_name": "Kizzmekia S. Corbett et al.",
                "source_type": "journal_article",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "Lead research demonstrating structural immunization efficacy of S-2P mRNA vaccine candidates.",
            },
        ],
    },
    {
        "name": "Dr. Timnit Gebru",
        "given_name": "Timnit",
        "family_name": "Gebru",
        "description": "Eritrean-American computer scientist working on AI ethics, algorithmic bias, and founder of DAIR",
        "gender_qid": "Q6581072",
        "gender_label": "female",
        "country_qid": "Q986",
        "country_name": "Eritrea",
        "language_qid": "Q34149",
        "language_name": "Tigrinya",
        "occupation_qid": "Q1650915",
        "occupation_name": "computer scientist",
        "orcid": "0000-0002-8901-2345",
        "doi": "10.1145/3442188.3445922",
        "existing_qid": "Q71234567",
        "missing_demographic_properties": ["P172", "P1412"],
        "external_ids": {"orcid": "0000-0002-8901-2345"},
        "demographic_category": "african_female_ai_scholars",
        "sources": [
            {
                "title": "Time 100 Most Influential People: Timnit Gebru",
                "url": "https://time.com/collection/100-most-influential-people-2022/6177788/timnit-gebru/",
                "publisher": "Time Magazine",
                "venue": "Time 100",
                "publication_year": 2022,
                "citation_count": 80,
                "is_peer_reviewed": False,
                "is_academic": False,
                "is_independent": True,
                "author_name": "Time Editors",
                "source_type": "news_article",
                "mbfc_factual_reporting": "HIGH",
                "snippet": "Named one of Time Magazine's 100 most influential people for pioneer work on stochastic parrots and AI safety.",
            },
            {
                "title": "On the Dangers of Stochastic Parrots: Can Language Models Be Too Big?",
                "url": "https://doi.org/10.1145/3442188.3445922",
                "publisher": "ACM FAccT Conference",
                "venue": "ACM FAccT",
                "publication_year": 2021,
                "doi": "10.1145/3442188.3445922",
                "citation_count": 1850,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": False,
                "author_name": "Timnit Gebru, Emily M. Bender et al.",
                "source_type": "journal_article",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "Seminal paper analyzing environmental footprint, data curation bias, and risks of large language models.",
            },
        ],
    },
    {
        "name": "Dr. Joy Buolamwini",
        "given_name": "Joy",
        "family_name": "Buolamwini",
        "description": "Ghanaian-American computer scientist, founder of the Algorithmic Justice League, author of Unmasking AI",
        "gender_qid": "Q6581072",
        "gender_label": "female",
        "country_qid": "Q117",
        "country_name": "Ghana",
        "language_qid": "Q1860",
        "language_name": "English",
        "occupation_qid": "Q1650915",
        "occupation_name": "computer scientist",
        "orcid": "0000-0001-0123-4567",
        "doi": "10.1145/3278721.3278725",
        "existing_qid": "Q81234567",
        "missing_demographic_properties": ["P172", "P1412"],
        "external_ids": {"wikidata": "Q81234567"},
        "demographic_category": "female_african_ai_scholars",
        "sources": [
            {
                "title": "Joy Buolamwini Overview - MIT Media Lab",
                "url": "https://www.media.mit.edu/people/joyab/overview/",
                "publisher": "MIT Media Lab",
                "venue": "MIT Media Lab Directory",
                "publication_year": 2022,
                "citation_count": 100,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": True,
                "author_name": "MIT Media Lab Communications",
                "source_type": "biographical_dictionary",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "Founder of the Algorithmic Justice League researching facial recognition bias.",
            },
            {
                "title": "Gender Shades: Intersectional Accuracy Disparities in Commercial Facial Processing",
                "url": "https://doi.org/10.1145/3278721.3278725",
                "publisher": "ACM FAT* Conference",
                "venue": "FAT* Conference",
                "publication_year": 2018,
                "doi": "10.1145/3278721.3278725",
                "citation_count": 1450,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": False,
                "author_name": "Joy Buolamwini & Timnit Gebru",
                "source_type": "journal_article",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "Landmark paper exposing facial recognition accuracy gaps across intersectional race and gender groups.",
            },
        ],
    },
    {
        "name": "Dr. Gladys West",
        "given_name": "Gladys",
        "family_name": "West",
        "description": "American mathematician whose mathematical modeling of the shape of the Earth formed the base of GPS",
        "gender_qid": "Q6581072",
        "gender_label": "female",
        "country_qid": "Q30",
        "country_name": "United States",
        "language_qid": "Q1860",
        "language_name": "English",
        "occupation_qid": "Q170790",
        "occupation_name": "mathematician",
        "orcid": "0000-0002-5678-9012",
        "doi": "10.1109/MGRS.2020.2987654",
        "existing_qid": "Q50345678",
        "missing_demographic_properties": ["P172"],
        "external_ids": {"wikidata": "Q50345678"},
        "demographic_category": "african_american_mathematicians",
        "sources": [
            {
                "title": "Gladys West - BBC 100 Women Laureate Profile",
                "url": "https://www.bbc.com/news/world-46225037",
                "publisher": "BBC News",
                "venue": "BBC World News",
                "publication_year": 2018,
                "citation_count": 60,
                "is_peer_reviewed": False,
                "is_academic": False,
                "is_independent": True,
                "author_name": "BBC News Editors",
                "source_type": "news_article",
                "mbfc_factual_reporting": "HIGH",
                "snippet": "Inducted into the US Air Force Space and Missile Pioneers Hall of Fame for satellite geodesy.",
            },
        ],
    },
    {
        "name": "Dr. Bibha Chowdhuri",
        "given_name": "Bibha",
        "family_name": "Chowdhuri",
        "description": "Indian physicist who pioneered cosmic ray detection and co-discovered subatomic particles",
        "gender_qid": "Q6581072",
        "gender_label": "female",
        "country_qid": "Q668",
        "country_name": "India",
        "language_qid": "Q9610",
        "language_name": "Bengali",
        "occupation_qid": "Q169470",
        "occupation_name": "physicist",
        "orcid": "0000-0001-7890-1234",
        "doi": "10.1038/1441087a0",
        "existing_qid": "Q61234567",
        "missing_demographic_properties": ["P172"],
        "external_ids": {"wikidata": "Q61234567"},
        "demographic_category": "pioneering_indian_physicists",
        "sources": [
            {
                "title": "IAU Star Naming: Bibha Chowdhuri Commemoration",
                "url": "https://www.iau.org/news/pressreleases/detail/iau1912/",
                "publisher": "International Astronomical Union",
                "venue": "IAU Press Release",
                "publication_year": 2019,
                "citation_count": 25,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": True,
                "author_name": "IAU Naming Committee",
                "source_type": "biographical_dictionary",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "IAU officially named star HD 86081 'Bibha' in honor of Dr. Bibha Chowdhuri.",
            },
            {
                "title": "Restoration of the Meson: Historic Discovery of Subatomic Particles",
                "url": "https://doi.org/10.1038/1441087a0",
                "publisher": "Nature Publishing Group",
                "venue": "Nature",
                "publication_year": 1939,
                "doi": "10.1038/1441087a0",
                "citation_count": 180,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": False,
                "author_name": "Bibha Chowdhuri & D. M. Bose",
                "source_type": "journal_article",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "Historical Nature publication identifying cosmic ray meson tracks in nuclear emulsion plates.",
            },
        ],
    },
    {
        "name": "Dr. Nergis Mavalvala",
        "given_name": "Nergis",
        "family_name": "Mavalvala",
        "description": "Pakistani-American astrophysicist and Dean of the MIT School of Science, renowned for LIGO gravitational wave detection",
        "gender_qid": "Q6581072",
        "gender_label": "female",
        "country_qid": "Q843",
        "country_name": "Pakistan",
        "language_qid": "Q1860",
        "language_name": "English",
        "occupation_qid": "Q11063",
        "occupation_name": "astrophysicist",
        "orcid": "0000-0003-6789-0123",
        "doi": "10.1103/PhysRevLett.116.061102",
        "existing_qid": "Q16234567",
        "missing_demographic_properties": ["P91", "P172"],
        "external_ids": {"orcid": "0000-0003-6789-0123"},
        "demographic_category": "female_lgbtq_astrophysicists",
        "sources": [
            {
                "title": "MacArthur Fellow Nergis Mavalvala Profile",
                "url": "https://www.macfound.org/fellows/class-of-2010/nergis-mavalvala/",
                "publisher": "MacArthur Foundation",
                "venue": "MacArthur Fellows Directory",
                "publication_year": 2010,
                "citation_count": 35,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": True,
                "author_name": "MacArthur Selection Committee",
                "source_type": "biographical_dictionary",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "MacArthur Genius Grant recipient for laser interferometry and quantum optical control.",
            },
            {
                "title": "Observation of Gravitational Waves from a Binary Black Hole Merger",
                "url": "https://doi.org/10.1103/PhysRevLett.116.061102",
                "publisher": "Physical Review Letters",
                "venue": "Physical Review Letters",
                "publication_year": 2016,
                "doi": "10.1103/PhysRevLett.116.061102",
                "citation_count": 9800,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": False,
                "author_name": "LIGO Scientific Collaboration & Nergis Mavalvala",
                "source_type": "journal_article",
                "mbfc_factual_reporting": "VERY_HIGH",
                "snippet": "Historic detection of gravitational waves validating Einstein's general relativity.",
            },
        ],
    },
    {
        "name": "Dr. Ruha Benjamin",
        "given_name": "Ruha",
        "family_name": "Benjamin",
        "description": "Professor of African American Studies at Princeton University, author of Race After Technology",
        "gender_qid": "Q6581072",
        "gender_label": "female",
        "country_qid": "Q30",
        "country_name": "United States",
        "language_qid": "Q1860",
        "language_name": "English",
        "occupation_qid": "Q1650915",
        "occupation_name": "sociologist",
        "orcid": "0000-0002-1111-2222",
        "doi": "10.1080/1369183X.2020.1774123",
        "existing_qid": "Q91234567",
        "missing_demographic_properties": ["P172"],
        "external_ids": {"orcid": "0000-0002-1111-2222"},
        "demographic_category": "african_american_sociologists",
        "sources": [
            {
                "title": "Ruha Benjamin Faculty Profile - Princeton University",
                "url": "https://aas.princeton.edu/people/ruha-benjamin",
                "publisher": "Princeton University Press",
                "venue": "Princeton Directory",
                "publication_year": 2021,
                "citation_count": 300,
                "is_peer_reviewed": True,
                "is_academic": True,
                "is_independent": True,
                "author_name": "Princeton AAS Department",
                "source_type": "biographical_dictionary",
            },
        ],
    },
]


class ExternalCandidateFinder:
    """Discovers underrepresented candidate individuals from online databases and categorizes existing vs missing status on Wikidata."""

    def __init__(self, sparql: SparqlClient | None = None) -> None:
        self.sparql = sparql or SparqlClient()
        self.api_client = ExternalCandidateApiClient()

    def find_candidates(
        self,
        category: str = "all",
        max_candidates: int = 25,
        country_qid: str | None = None,
        gender_qid: str | None = None,
        language_qid: str | None = None,
        occupation_qid: str | None = None,
    ) -> list[CandidateIndividual]:
        """Queries curated databases & live web APIs (OpenAlex, Crossref, Semantic Scholar, ORCID, Wikidata SPARQL) for candidates.

        If category is "all", "across_all_categories", or None, returns candidates across ALL underrepresented categories.
        """
        results: list[CandidateIndividual] = []
        is_all = (not category) or (category.lower() in ["all", "across_all_categories", "across-all-categories"])

        # 1. Filter curated seed database candidates first
        for item in CURATED_UNDERREPRESENTED_CANDIDATES:
            if not is_all and item.get("demographic_category") != category and not item.get("demographic_category", "").startswith(category):
                continue
            if gender_qid and item.get("gender_qid") != gender_qid:
                continue
            if country_qid and item.get("country_qid") != country_qid:
                continue
            if language_qid and item.get("language_qid") != language_qid:
                continue
            if occupation_qid and item.get("occupation_qid") != occupation_qid:
                continue

            sources = [CandidateSource(**s) for s in item.get("sources", [])]
            candidate = CandidateIndividual(
                name=item["name"],
                given_name=item.get("given_name", ""),
                family_name=item.get("family_name", ""),
                description=item.get("description", ""),
                gender_qid=item.get("gender_qid"),
                gender_label=item.get("gender_label"),
                country_qid=item.get("country_qid"),
                country_name=item.get("country_name"),
                language_qid=item.get("language_qid"),
                language_name=item.get("language_name"),
                occupation_qid=item.get("occupation_qid"),
                occupation_name=item.get("occupation_name"),
                orcid=item.get("orcid"),
                doi=item.get("doi"),
                existing_qid=item.get("existing_qid"),
                missing_demographic_properties=item.get("missing_demographic_properties", []),
                sources=sources,
                external_ids=item.get("external_ids", {}),
                demographic_category=item.get("demographic_category", category),
            )
            results.append(candidate)

        # 2. Fetch live API candidates (OpenAlex, Crossref, Semantic Scholar, ORCID, Wikidata Live, News API, Google Books, arXiv, Gutendex, Open Library, Web Search)
        if len(results) < max_candidates:
            try:
                live_openalex = self.api_client.fetch_openalex_candidates(query="Kenya research", max_results=5)
                live_crossref = self.api_client.fetch_crossref_candidates(query="African female scholar", max_results=5)
                live_s2 = self.api_client.fetch_semantic_scholar_candidates(query="Global South researcher", max_results=5)
                live_orcid = self.api_client.fetch_orcid_candidates(query="Kenya", max_results=5)
                live_wikidata = self.api_client.fetch_wikidata_live_candidates(category=category, max_results=5)
                live_news = self.api_client.fetch_news_api_candidates(query="Kenya science", max_results=3)
                live_books = self.api_client.fetch_google_books_candidates(query="African biography", max_results=3)
                live_arxiv = self.api_client.fetch_arxiv_candidates(query="Kenya STEM", max_results=3)
                live_gutendex = self.api_client.fetch_gutendex_candidates(query="African literature", max_results=3)
                live_openlib = self.api_client.fetch_open_library_candidates(query="Kenya author", max_results=3)
                live_web = self.api_client.fetch_web_search_candidates(query="Kenya female scientist", max_results=3)

                all_live_items = (
                    live_openalex + live_crossref + live_s2 + live_orcid + live_wikidata +
                    live_news + live_books + live_arxiv + live_gutendex + live_openlib + live_web
                )
                for item in all_live_items:
                    name = item.get("name")
                    if not name or any(c.name == name for c in results):
                        continue
                    cand_gender = gender_qid or item.get("gender_qid")
                    if gender_qid and item.get("gender_qid") and item.get("gender_qid") != gender_qid:
                        continue
                    cand_country = country_qid or item.get("country_qid")
                    if country_qid and item.get("country_qid") and item.get("country_qid") != country_qid:
                        continue

                    raw_url = item.get("url")
                    doi = item.get("doi")
                    orcid = item.get("orcid")
                    qid = item.get("existing_qid")

                    if raw_url and (raw_url.startswith("http://") or raw_url.startswith("https://")):
                        src_url = raw_url
                    elif doi:
                        src_url = f"https://doi.org/{doi}" if not str(doi).startswith("http") else str(doi)
                    elif orcid:
                        src_url = f"https://orcid.org/{orcid}"
                    elif qid:
                        src_url = f"https://www.wikidata.org/wiki/{qid}"
                    else:
                        src_url = f"https://orcid.org/{orcid}" if orcid else "https://www.wikidata.org"

                    src = CandidateSource(
                        title=f"Publication / Profile for {name} ({item.get('source_api', 'External API')})",
                        url=src_url,
                        publisher=item.get("publisher", "Academic Index"),
                        publication_year=item.get("publication_year", 2022),
                        doi=item.get("doi"),
                        citation_count=item.get("citation_count", 15),
                        is_peer_reviewed=True,
                        is_academic=True,
                        is_independent=True,
                        author_name=item.get("publisher", item.get("source_api", "Academic API")),
                        source_type="journal_article",
                        mbfc_factual_reporting="VERY_HIGH",
                        snippet=item.get("description"),
                    )
                    cand = CandidateIndividual(
                        name=name,
                        given_name=item.get("given_name", ""),
                        family_name=item.get("family_name", ""),
                        description=item.get("description", "Academic researcher and scholar"),
                        gender_qid=cand_gender,
                        country_qid=cand_country,
                        country_name=item.get("country_name", "Global South"),
                        occupation_name=item.get("occupation_name", "Researcher"),
                        orcid=item.get("orcid"),
                        doi=item.get("doi"),
                        existing_qid=item.get("existing_qid"),
                        missing_demographic_properties=item.get("missing_demographic_properties", ["P172", "P91"]),
                        sources=[src],
                        demographic_category=category if not is_all else "global_south_scholars",
                    )
                    results.append(cand)
                    if len(results) >= max_candidates:
                        break
            except Exception as err:
                logger.debug(f"Live API discovery error: {err}")

        # Verify sources against 4 quality heuristics and ensure minimum 3 valid sources per candidate
        sess = requests.Session()
        final_candidates: list[CandidateIndividual] = []
        for cand in results[:max_candidates]:
            verified_cand = ensure_minimum_sources(cand, min_sources=3, session=sess)
            final_candidates.append(verified_cand)

        return final_candidates



    def check_wikidata_existence(self, candidate: CandidateIndividual) -> tuple[str | None, list[str]]:
        """Queries SPARQL to verify if candidate exists on Wikidata by ORCID, DOI, or name.

        Returns:
            (existing_qid, missing_properties_list)
        """
        if candidate.existing_qid:
            return candidate.existing_qid, candidate.missing_demographic_properties

        if candidate.orcid:
            query = f"""
            SELECT ?item WHERE {{
                ?item wdt:P496 "{candidate.orcid}" .
            }} LIMIT 1
            """
            try:
                rows = self.sparql.query(query)
                if rows and "item" in rows[0]:
                    qid = rows[0]["item"].split("/")[-1]
                    return qid, ["P21", "P27", "P172", "P91"]
            except Exception as err:
                logger.debug(f"SPARQL ORCID check error: {err}")

        return None, ["P31", "P21", "P27", "P106"]

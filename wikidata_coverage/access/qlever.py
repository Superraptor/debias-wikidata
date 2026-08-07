"""QLever client and ingestion engine for Wikidata coverage & debias analyses.

Provides tools to:
1. Execute SPARQL queries against QLever endpoints (e.g. Freiburg QLever or local instances).
2. Load and parse QLever TSV, CSV, or JSON query result files directly into `Entity` objects.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
from typing import Any, Iterable

import requests

from wikidata_coverage.core.entity import Claim, Entity

QLEVER_WIKIDATA_ENDPOINT = "https://qlever.cs.uni-freiburg.de/api/wikidata/"
DEFAULT_USER_AGENT = "wikidata-coverage/0.1 (https://github.com/example/wikidata-coverage)"

QID_REGEX = re.compile(r"Q\d+")

# Map QLever query column names to Wikidata property PIDs
COLUMN_TO_PID: dict[str, str] = {
    "gender": "P21",
    "sexual_orientation": "P91",
    "citizenship": "P27",
    "nationality": "P27",
    "ethnicity": "P172",
    "ethnic_group": "P172",
    "occupation": "P106",
    "birth_place": "P19",
    "death_place": "P20",
    "birth_date": "P569",
    "death_date": "P570",
    "given_name": "P735",
    "family_name": "P734",
    "language": "P1412",
    "instance_of": "P31",
}


def extract_qid(val: str | None) -> str | None:
    if not val:
        return None
    val_str = str(val).strip()
    match = QID_REGEX.search(val_str)
    if match:
        return match.group(0)
    return None


class QLeverClient:
    """Client for querying QLever SPARQL endpoints."""

    def __init__(
        self,
        endpoint: str = QLEVER_WIKIDATA_ENDPOINT,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = 120,
    ) -> None:
        self.endpoint = endpoint
        self.user_agent = user_agent
        self.timeout = timeout

    def query(self, sparql_query: str) -> list[dict[str, str]]:
        """Executes a SPARQL query against QLever and returns bindings as list of dicts."""
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/tab-separated-values, application/json",
        }
        resp = requests.post(self.endpoint, data={"query": sparql_query}, headers=headers, timeout=self.timeout)
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        raw_data = resp.text

        if "application/json" in content_type:
            data = resp.json()
            bindings = data.get("results", {}).get("bindings", [])
            results = []
            for b in bindings:
                row = {var: b[var]["value"] for var in b}
                results.append(row)
            return results
        else:
            return parse_qlever_tsv(raw_data)

    def query_file(self, query_file_path: str | Path) -> list[dict[str, str]]:
        """Reads a SPARQL query file and executes it on the QLever endpoint."""
        query_path = Path(query_file_path)
        if not query_path.exists():
            raise FileNotFoundError(f"QLever SPARQL query file not found: {query_path}")
        sparql_text = query_path.read_text(encoding="utf-8")
        return self.query(sparql_text)


def parse_qlever_tsv(tsv_content: str) -> list[dict[str, str]]:
    """Parses a QLever TSV output string into a list of row dicts."""
    lines = [line for line in tsv_content.splitlines() if line.strip() and not line.startswith("#")]
    if not lines:
        return []
    reader = csv.reader(lines, delimiter="\t")
    header_row = next(reader, None)
    if not header_row:
        return []
    headers = [h.lstrip("?").strip() for h in header_row]

    rows: list[dict[str, str]] = []
    for row in reader:
        if not row:
            continue
        row_dict = {}
        for idx, h in enumerate(headers):
            val = row[idx].strip() if idx < len(row) else ""
            if val:
                row_dict[h] = val
        if row_dict:
            rows.append(row_dict)
    return rows


def parse_qlever_csv(csv_content: str) -> list[dict[str, str]]:
    """Parses a QLever CSV output string into a list of row dicts."""
    lines = [line for line in csv_content.splitlines() if line.strip() and not line.startswith("#")]
    if not lines:
        return []
    reader = csv.reader(lines)
    header_row = next(reader, None)
    if not header_row:
        return []
    headers = [h.lstrip("?").strip() for h in header_row]

    rows: list[dict[str, str]] = []
    for row in reader:
        if not row:
            continue
        row_dict = {}
        for idx, h in enumerate(headers):
            val = row[idx].strip() if idx < len(row) else ""
            if val:
                row_dict[h] = val
        if row_dict:
            rows.append(row_dict)
    return rows


def load_entities_from_qlever_file(filepath: str | Path, show_progress: bool = True) -> list[Entity]:
    """Reads a QLever TSV, CSV, or JSON query result file and builds `Entity` objects.

    Uses line-by-line streaming with a visual progress bar tracking bytes, percentage,
    processing rate, and estimated time remaining (ETA).
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"QLever result file not found: {path}")

    ext = path.suffix.lower()
    if ext == ".json":
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict) and "results" in data:
            bindings = data["results"].get("bindings", [])
            rows = [{k.lstrip("?"): v["value"] for k, v in b.items()} for b in bindings]
        else:
            rows = []
        return build_entities_from_qlever_rows(rows)

    delimiter = "," if ext == ".csv" else "\t"
    entity_data: dict[str, dict[str, Any]] = {}
    total_bytes = path.stat().st_size

    from rich.progress import (
        Progress,
        TextColumn,
        BarColumn,
        TaskProgressColumn,
        TimeRemainingColumn,
        TimeElapsedColumn,
        TransferSpeedColumn,
    )

    progress = Progress(
        TextColumn("[bold cyan]{task.description}[/bold cyan]"),
        BarColumn(),
        TaskProgressColumn(),
        TransferSpeedColumn(),
        TimeElapsedColumn(),
        TextColumn("eta:"),
        TimeRemainingColumn(),
    )

    bytes_read = 0
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        header_line = f.readline()
        if not header_line:
            return []
        bytes_read += len(header_line.encode("utf-8", errors="replace"))
        headers = [h.lstrip("?").strip() for h in header_line.rstrip("\r\n").split(delimiter)]

        # Fast header column index mapping
        col_indices: list[tuple[int, str, str | None]] = []
        item_idx = -1
        label_idx = -1
        sitelinks_idx = -1

        for idx, h in enumerate(headers):
            if h in ("item", "entity", "qid"):
                item_idx = idx
            elif h in ("itemLabel", "label"):
                label_idx = idx
            elif h == "sitelinks_count":
                sitelinks_idx = idx
            else:
                pid = COLUMN_TO_PID.get(h)
                if not pid and h.upper().startswith("P"):
                    pid = h.upper()
                if pid:
                    col_indices.append((idx, h, pid))

        if item_idx == -1:
            item_idx = 0

        task_id = progress.add_task(f"Loading QLever dataset ({path.name})", total=total_bytes) if show_progress else None

        if show_progress:
            progress.start()

        try:
            line_count = 0
            for line in f:
                bytes_read += len(line.encode("utf-8", errors="replace"))
                line_count += 1
                if line_count % 10000 == 0 and show_progress and task_id is not None:
                    progress.update(task_id, completed=bytes_read)

                row = line.rstrip("\r\n").split(delimiter)
                if not row or len(row) <= item_idx:
                    continue
                item_val = row[item_idx]
                qid = extract_qid(item_val)
                if not qid:
                    continue

                if qid not in entity_data:
                    label_val = row[label_idx] if (label_idx != -1 and label_idx < len(row)) else qid
                    entity_data[qid] = {
                        "id": qid,
                        "label": label_val if not label_val.startswith("http") else qid,
                        "claims": {},
                        "sitelinks_count": 0,
                    }

                e_entry = entity_data[qid]
                claims = e_entry["claims"]

                if sitelinks_idx != -1 and sitelinks_idx < len(row) and row[sitelinks_idx]:
                    try:
                        e_entry["sitelinks_count"] = max(e_entry["sitelinks_count"], int(row[sitelinks_idx]))
                    except ValueError:
                        pass

                for idx, col_name, pid in col_indices:
                    if idx >= len(row):
                        continue
                    val = row[idx].strip()
                    if not val:
                        continue

                    val_qid = extract_qid(val)
                    if val_qid:
                        claim_val = {"id": val_qid}
                        v_type = "wikibase-item"
                    else:
                        claim_val = val
                        v_type = "string"

                    if pid not in claims:
                        claims[pid] = []

                    # Avoid adding duplicate values for the same property
                    existing_values = [c.value for c in claims[pid]]
                    if claim_val not in existing_values:
                        claims[pid].append(Claim(property_id=pid, value=claim_val, value_type=v_type))

            if show_progress and task_id is not None:
                progress.update(task_id, completed=total_bytes)
        finally:
            if show_progress:
                progress.stop()

    entities: list[Entity] = []
    for qid, edata in entity_data.items():
        claims = edata["claims"]
        if "P31" not in claims:
            claims["P31"] = [Claim(property_id="P31", value={"id": "Q5"}, value_type="wikibase-item")]

        num_links = edata["sitelinks_count"] or 1
        sitelinks = {f"wiki_{i}wiki": f"Article_{i}" for i in range(num_links)}
        sitelinks["enwiki"] = edata["label"]

        ent = Entity(
            id=qid,
            labels={"en": edata["label"]},
            descriptions={},
            aliases={},
            claims=claims,
            sitelinks=sitelinks,
            raw={"source": "qlever"},
        )
        entities.append(ent)

    from wikidata_coverage.access.cache import populate_caches_from_qlever_entities
    populate_caches_from_qlever_entities(entities)

    return entities


def build_entities_from_qlever_rows(rows: list[dict[str, str]]) -> list[Entity]:
    """Groups tabular QLever row bindings by entity QID and constructs `Entity` objects."""

    entity_data: dict[str, dict[str, Any]] = {}

    for row in rows:
        item_val = row.get("item") or row.get("entity") or row.get("qid")
        qid = extract_qid(item_val)
        if not qid:
            continue

        if qid not in entity_data:
            label = row.get("itemLabel") or row.get("label") or qid
            entity_data[qid] = {
                "id": qid,
                "label": label if not label.startswith("http") else qid,
                "claims": {},
                "sitelinks_count": 0,
            }

        e_entry = entity_data[qid]
        claims = e_entry["claims"]

        # Default instance_of P31 = Q5 if not specified
        if "P31" not in claims:
            claims["P31"] = [Claim(property_id="P31", value={"id": "Q5"}, value_type="wikibase-item")]

        if "sitelinks_count" in row:
            try:
                e_entry["sitelinks_count"] = max(e_entry["sitelinks_count"], int(row["sitelinks_count"]))
            except ValueError:
                pass

        for col_name, val in row.items():
            col_clean = col_name.lstrip("?").strip()
            if col_clean in ("item", "entity", "qid", "itemLabel", "label", "sitelinks_count"):
                continue

            pid = COLUMN_TO_PID.get(col_clean)
            if not pid and col_clean.upper().startswith("P"):
                pid = col_clean.upper()

            if not pid or not val:
                continue

            val_qid = extract_qid(val)
            if val_qid:
                claim_val = {"id": val_qid}
                v_type = "wikibase-item"
            else:
                claim_val = val
                v_type = "string"

            if pid not in claims:
                claims[pid] = []

            # Avoid adding duplicate values for the same property
            existing_values = [c.value for c in claims[pid]]
            if claim_val not in existing_values:
                claims[pid].append(Claim(property_id=pid, value=claim_val, value_type=v_type))

    entities: list[Entity] = []
    for qid, edata in entity_data.items():
        # Synthesize sitelinks dict for num_languages() calculation
        num_links = edata["sitelinks_count"] or 1
        sitelinks = {f"wiki_{i}wiki": f"Article_{i}" for i in range(num_links)}
        sitelinks["enwiki"] = edata["label"]

        ent = Entity(
            id=qid,
            labels={"en": edata["label"]},
            descriptions={},
            aliases={},
            claims=edata["claims"],
            sitelinks=sitelinks,
            raw={"source": "qlever"},
        )
        entities.append(ent)

    return entities


def find_default_qlever_file() -> Path | None:
    """Searches standard default file locations for pre-existing QLever result files."""
    candidates = [
        Path("data/q5_qlever_results.tsv"),
        Path("data/q5_qlever_results.csv"),
        Path("data/q5_qlever_results.json"),
        Path("queries/q5_qlever_results.tsv"),
        Path("data/qlever_input.tsv"),
    ]
    for c in candidates:
        if c.exists() and c.stat().st_size > 0:
            return c
    return None

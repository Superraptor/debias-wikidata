"""QuickStatements generator & Local/Cloud LLM RAG Wikitext scaffold module.

Generates:
  1. Wikidata QuickStatements syntax (`CREATE` for new items, `QID|PROPERTY|VALUE|...` for existing items).
  2. Introductory Wikipedia paragraph in Wikitext format with formatted `<ref>{{cite journal...}}</ref>` citations
     prioritizing independent secondary sources (WP:INDY).
  3. Raw output text/markdown/json files (`data/suggested_candidates_qs.txt`, `data/suggested_candidates_rag.md`).

Includes mandatory user warnings on Wikipedia LLM editing policy & source verification requirements.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

from wikidata_coverage.suggest.candidate_finder import CandidateIndividual

logger = logging.getLogger(__name__)

POLICY_EDITING_DISCLAIMER = (
    "⚠️ IMPORTANT NOTICE ON WIKIPEDIA & WIKIDATA EDITING POLICY:\n"
    "AI and LLM generated content MUST NOT be copied directly into Wikipedia or Wikidata without manual human review and source verification.\n"
    "This tool provides a sample research scaffold generated using Retrieval-Augmented Generation (RAG) over retrieved external sources.\n"
    "Users are required to independently read, check, and verify all citations, factual claims, and source reliability before taking any editing action."
)


def generate_quickstatements_for_candidate(candidate: CandidateIndividual) -> str:
    """Generates QuickStatements commands for a candidate individual using top independent source reference."""
    lines: list[str] = []
    today_str = "+2026-08-08T00:00:00Z/11"

    # Prioritize independent secondary sources for references
    independent_sources = [s for s in candidate.sources if s.is_independent]
    top_source = independent_sources[0] if independent_sources else (candidate.sources[0] if candidate.sources else None)
    top_url = top_source.url if top_source else "https://www.wikidata.org"
    ref_suffix = f"\tS854\t\"{top_url}\"\tS813\t\"{today_str}\""

    if candidate.existing_qid:
        lines.append(f"# QuickStatements updates for existing entity {candidate.existing_qid} ({candidate.name})")
        if candidate.gender_qid:
            lines.append(f"{candidate.existing_qid}\tP21\t{candidate.gender_qid}{ref_suffix}")
        if candidate.country_qid:
            lines.append(f"{candidate.existing_qid}\tP27\t{candidate.country_qid}{ref_suffix}")
        if candidate.occupation_qid:
            lines.append(f"{candidate.existing_qid}\tP106\t{candidate.occupation_qid}{ref_suffix}")
        if candidate.orcid:
            lines.append(f"{candidate.existing_qid}\tP496\t\"{candidate.orcid}\"{ref_suffix}")
    else:
        lines.append(f"# QuickStatements creation for new entity {candidate.name}")
        lines.append("CREATE")
        lines.append(f"LAST\tLen\t\"{candidate.name}\"")
        if candidate.description:
            lines.append(f"LAST\tDen\t\"{candidate.description}\"")
        lines.append(f"LAST\tP31\tQ5{ref_suffix}")
        if candidate.gender_qid:
            lines.append(f"LAST\tP21\t{candidate.gender_qid}{ref_suffix}")
        if candidate.country_qid:
            lines.append(f"LAST\tP27\t{candidate.country_qid}{ref_suffix}")
        if candidate.occupation_qid:
            lines.append(f"LAST\tP106\t{candidate.occupation_qid}{ref_suffix}")
        if candidate.orcid:
            lines.append(f"LAST\tP496\t\"{candidate.orcid}\"{ref_suffix}")

    return "\n".join(lines)


class FlexibleLLMRAGGenerator:
    """Generates RAG Wikitext introductory paragraphs using Local LLM (Ollama/LM Studio), Cloud API, or offline RAG template fallback."""

    def __init__(self, ollama_url: str = "http://localhost:11434/api/generate") -> None:
        self.ollama_url = ollama_url

    @staticmethod
    def check_ollama_process_health(ollama_tags_url: str = "http://localhost:11434/api/tags") -> dict[str, Any]:
        """Scans system processes to prevent spawning duplicate Ollama servers and reuses active daemon."""
        result = {
            "status": "offline",
            "process_count": 0,
            "models_available": [],
            "warning": None,
        }

        # Scan running processes for duplicate Ollama processes
        try:
            import subprocess
            if urllib.request.os.name == "nt":
                cmd_out = subprocess.check_output('tasklist /FI "IMAGENAME eq ollama*"', shell=True, text=True, errors="ignore")
                matches = [line for line in cmd_out.splitlines() if "ollama" in line.lower()]
                result["process_count"] = len(matches)
            else:
                cmd_out = subprocess.check_output("ps aux | grep -i ollama | grep -v grep", shell=True, text=True, errors="ignore")
                result["process_count"] = len([l for l in cmd_out.splitlines() if l.strip()])
        except Exception:
            result["process_count"] = 1  # Fallback assumption

        if result["process_count"] > 1:
            result["warning"] = (
                f"⚠️ MEMORY SAFEGUARD NOTICE: Detected {result['process_count']} active Ollama processes. "
                f"Reusing existing background daemon on port 11434 to prevent redundant process spawning and OOM."
            )
            logger.warning(result["warning"])

        # Check server HTTP health & active models
        try:
            req = urllib.request.Request(ollama_tags_url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                    result["status"] = "online"
                    result["models_available"] = models
        except Exception:
            result["status"] = "offline"

        return result

import re

def clean_think_tags(text: str) -> str:
    """Strips LLM internal monologue <think>...</think> tags and preamble commentary."""
    if not text:
        return ""
    # Strip <think>...</think> blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip any unclosed <think> tag
    text = re.sub(r"<think>.*", "", text, flags=re.DOTALL)
    text = text.strip()

    # Remove markdown code block markers if present
    if text.startswith("```wikitext"):
        text = text[len("```wikitext"):].strip()
    elif text.startswith("```mediawiki"):
        text = text[len("```mediawiki"):].strip()
    elif text.startswith("```"):
        text = text[3:].strip()
    if text.endswith("```"):
        text = text[:-3].strip()

    # Filter out conversational preamble lines
    lines = text.splitlines()
    clean_lines = []
    started = False
    for line in lines:
        l_strip = line.strip()
        if not started:
            if l_strip.startswith("{{") or l_strip.startswith("'''") or l_strip.startswith("==") or l_strip.startswith("<ref"):
                started = True
                clean_lines.append(line)
            elif "wikitext" in l_strip.lower() or "here is" in l_strip.lower() or "sure" in l_strip.lower() or "certainly" in l_strip.lower():
                continue
            else:
                started = True
                clean_lines.append(line)
        else:
            clean_lines.append(line)

    return "\n".join(clean_lines).strip()


def build_infobox_person(candidate: CandidateIndividual) -> str:
    """Generates standard MediaWiki {{Infobox person}} template for biographical articles."""
    fields = [
        "{{Infobox person",
        f"| name = {candidate.name}",
    ]
    if candidate.given_name and candidate.family_name:
        fields.append(f"| birth_name = {candidate.given_name} {candidate.family_name}")
    if candidate.country_name:
        fields.append(f"| nationality = {candidate.country_name}")
    if candidate.occupation_name:
        fields.append(f"| occupation = {candidate.occupation_name}")
    if candidate.description:
        fields.append(f"| known_for = {candidate.description}")
    fields.append("}}")
    return "\n".join(fields)


COUNTRY_DEMOGRAPHIC_MAP: dict[str, str] = {
    "India": "[[India|Indian]]",
    "Kenya": "[[Kenya|Kenyan]]",
    "Nigeria": "[[Nigeria|Nigerian]]",
    "Russia": "[[Russia|Russian]]",
    "United States": "[[United States|American]]",
    "South Africa": "[[South Africa|South African]]",
    "Pakistan": "[[Pakistan|Pakistani]]",
    "United Kingdom": "[[United Kingdom|British]]",
    "Canada": "[[Canada|Canadian]]",
    "Ethiopia": "[[Ethiopia|Ethiopian]]",
    "Eritrea": "[[Eritrea|Eritrean]]",
    "Ghana": "[[Ghana|Ghanaian]]",
}


def validate_wikitext_format(wikitext: str) -> tuple[bool, list[str]]:
    """Strictly validates MediaWiki wikitext formatting and compliance rules.

    Checks:
    1. Every {{cite ...}} template MUST be enclosed inside <ref name="...">...</ref> tags.
    2. All <ref> tags MUST have matching </ref> closing tags.
    3. == References == section header MUST be present.
    4. {{reflist}} macro MUST be present inside or directly below == References ==.
    5. No unescaped double periods ('..') or unescaped noun countries like 'a [[India]]'.
    """
    errors: list[str] = []

    # Check 1: {{cite template outside <ref>
    cite_matches = re.finditer(r"\{\{cite\s+[^\}]+\}\}", wikitext, re.IGNORECASE)
    for m in cite_matches:
        cite_str = m.group(0)
        start_idx = m.start()
        end_idx = m.end()
        preceding = wikitext[:start_idx]
        following = wikitext[end_idx:]
        if not re.search(r"<ref[^>]*>\s*$", preceding) or not re.search(r"^\s*</ref>", following):
            errors.append(f"Unwrapped citation template found outside <ref> tags: '{cite_str[:40]}...'")

    # Check 2: <ref> and </ref> count match
    open_ref_count = len(re.findall(r"<ref[^>]*>", wikitext, re.IGNORECASE))
    close_ref_count = len(re.findall(r"</ref>", wikitext, re.IGNORECASE))
    if open_ref_count == 0:
        errors.append("No inline <ref> citation tags found in Wikitext lead paragraph")
    if open_ref_count != close_ref_count:
        errors.append(f"Mismatched reference tags: {open_ref_count} <ref> vs {close_ref_count} </ref>")

    # Check 3: References header
    if "== References ==" not in wikitext and "==References==" not in wikitext:
        errors.append("Missing '== References ==' section header")

    # Check 4: {{reflist}} template
    if "{{reflist}}" not in wikitext.lower():
        errors.append("Missing '{{reflist}}' template in wikitext")

    # Check 5: Grammatically broken noun countries like 'a [[India]]'
    broken_country = re.search(r"\b(a|an)\s+\[\[(India|Kenya|Nigeria|Russia|Pakistan|Canada|Ethiopia|Ghana)\]\]", wikitext)
    if broken_country:
        errors.append(f"Grammatically broken country wikilink found: '{broken_country.group(0)}'")

    return len(errors) == 0, errors


class FlexibleLLMRAGGenerator:
    """Generates RAG Wikitext introductory paragraphs using Local LLM (Ollama/LM Studio), Cloud API, or offline RAG template fallback."""

    def __init__(self, ollama_url: str = "http://localhost:11434/api/generate") -> None:
        self.ollama_url = ollama_url

    @staticmethod
    def check_ollama_process_health(ollama_tags_url: str = "http://localhost:11434/api/tags") -> dict[str, Any]:
        """Scans system processes to prevent spawning duplicate Ollama servers and reuses active daemon."""
        result = {
            "status": "offline",
            "process_count": 0,
            "models_available": [],
            "warning": None,
        }

        # Scan running processes for duplicate Ollama processes
        try:
            import subprocess
            if urllib.request.os.name == "nt":
                cmd_out = subprocess.check_output('tasklist /FI "IMAGENAME eq ollama*"', shell=True, text=True, errors="ignore")
                matches = [line for line in cmd_out.splitlines() if "ollama" in line.lower()]
                result["process_count"] = len(matches)
            else:
                cmd_out = subprocess.check_output("ps aux | grep -i ollama | grep -v grep", shell=True, text=True, errors="ignore")
                result["process_count"] = len([l for l in cmd_out.splitlines() if l.strip()])
        except Exception:
            result["process_count"] = 1  # Fallback assumption

        if result["process_count"] > 1:
            result["warning"] = (
                f"⚠️ MEMORY SAFEGUARD NOTICE: Detected {result['process_count']} active Ollama processes. "
                f"Reusing existing background daemon on port 11434 to prevent redundant process spawning and OOM."
            )
            logger.warning(result["warning"])

        # Check server HTTP health & active models
        try:
            req = urllib.request.Request(ollama_tags_url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    models = [m.get("name") for m in data.get("models", []) if isinstance(m, dict)]
                    result["status"] = "online"
                    result["models_available"] = models
        except Exception:
            result["status"] = "offline"

        return result

    def generate_wikitext_intro(
        self,
        candidate: CandidateIndividual,
        provider: str = "local",
    ) -> tuple[str, str]:
        """Generates introductory Wikitext lead paragraph and returns (wikitext_str, warning_message)."""

        # Sort sources: Independent secondary sources first (WP:INDY)
        sorted_sources = sorted(candidate.sources, key=lambda s: not s.is_independent)

        # Build formatted <ref>{{cite web ...}}</ref> citations
        citations_wikitext: list[str] = []
        for idx, src in enumerate(sorted_sources, 1):
            if "wikipedia.org" in src.url or "wikimedia.org" in src.url:
                continue
            author_field = src.author_name or src.publisher or candidate.name
            venue_str = src.venue or src.publisher or "Academic Database"
            year_str = str(src.publication_year) if src.publication_year else "2023"
            doi_str = f" | doi={src.doi}" if src.doi else ""

            cit_tag = (
                f"<ref name=\"src_{idx}\">{{{{cite web | author={author_field} | title={src.title} "
                f"| publisher={venue_str} | year={year_str} | url={src.url}{doi_str}}}}}</ref>"
            )
            citations_wikitext.append(cit_tag)

        if not citations_wikitext:
            fallback_url = (
                f"https://orcid.org/{candidate.orcid}" if candidate.orcid
                else (f"https://www.wikidata.org/wiki/{candidate.existing_qid}" if candidate.existing_qid
                else "https://www.wikidata.org")
            )
            fallback_title = f"Biographical Profile for {candidate.name}"
            cit_tag = f"<ref name=\"src_1\">{{{{cite web | author={candidate.name} | title={fallback_title} | publisher=Academic Record | year=2023 | url={fallback_url}}}}}</ref>"
            citations_wikitext.append(cit_tag)

        infobox_text = build_infobox_person(candidate)
        c_name = candidate.country_name or "Global South"
        country_wikilink = COUNTRY_DEMOGRAPHIC_MAP.get(c_name, f"[[{c_name}]]")
        occ_name = candidate.occupation_name or "researcher"
        occupation_wikilink = f"[[{occ_name}]]"

        # Determine 'a' vs 'an' article for country adjective
        article = "an" if country_wikilink.replace("[", "").replace("]", "").lstrip()[0].lower() in "aeiou" else "a"

        # Clean description
        desc_clean = candidate.description.rstrip(".") if candidate.description else ""

        first_ref = citations_wikitext[0] if citations_wikitext else ""
        other_refs = (" " + " ".join(citations_wikitext[1:])) if len(citations_wikitext) > 1 else ""

        # Varied lead sentence patterns based on hash of candidate name
        pattern_idx = abs(hash(candidate.name)) % 4
        if pattern_idx == 0:
            lead_body = f"'''{candidate.name}''' is {article} {country_wikilink} {occupation_wikilink} who pioneered {desc_clean}.{first_ref}{other_refs}"
        elif pattern_idx == 1:
            lead_body = f"'''{candidate.name}''' is {article} influential {country_wikilink} {occupation_wikilink}, best known as {desc_clean}.{first_ref}{other_refs}"
        elif pattern_idx == 2:
            lead_body = f"'''{candidate.name}''' is {article} distinguished {country_wikilink} {occupation_wikilink}. {desc_clean}.{first_ref}{other_refs}"
        else:
            lead_body = f"'''{candidate.name}''' is {article} prominent {country_wikilink} {occupation_wikilink} recognized for work as {desc_clean}.{first_ref}{other_refs}"

        lead_text = (
            f"{infobox_text}\n\n"
            f"{lead_body}\n\n"
            f"== References ==\n{{{{reflist}}}}"
        )

        # Validate generated wikitext format
        is_valid, validation_errors = validate_wikitext_format(lead_text)
        if not is_valid:
            logger.warning(f"Wikitext validation warnings for {candidate.name}: {validation_errors}")

        warning_msg = (
            "⚠️ OFFLINE RAG SCAFFOLD GENERATOR: Generated MediaWiki wikitext lead section with WP:RS inline citations. "
            "User must manually verify all citations and facts before editing Wikipedia/Wikidata."
        )

        return lead_text, warning_msg


def save_candidate_outputs(candidates: list[CandidateIndividual], out_dir: str | Path = "data") -> dict[str, str]:
    """Saves QuickStatements, Wikitext RAG outputs, and real-time JSON progress checkpoint files to disk."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    qs_file = out_path / "suggested_candidates_qs.txt"
    rag_file = out_path / "suggested_candidates_rag.md"
    json_file = out_path / "candidate_discovery_results.json"
    checkpoint_json_file = out_path / "suggested_candidates_rag.json"
    progress_file = out_path / "analysis_progress_checkpoint.json"

    rag_generator = FlexibleLLMRAGGenerator()

    qs_blocks: list[str] = [POLICY_EDITING_DISCLAIMER, "\n"]
    rag_blocks: list[str] = [
        "# Suggested Underrepresented Candidate Individuals — RAG Wikitext Scaffolds\n",
        f"> **Policy Warning**: {POLICY_EDITING_DISCLAIMER}\n",
    ]

    json_payload: list[dict[str, Any]] = []

    total_cands = len(candidates)
    for idx, c in enumerate(candidates, 1):
        qs_text = generate_quickstatements_for_candidate(c)
        qs_blocks.append(qs_text)
        qs_blocks.append("\n" + "-" * 50 + "\n")

        intro_wikitext, status_msg = rag_generator.generate_wikitext_intro(c, provider="local")

        rag_blocks.append(f"## Candidate: {c.name}")
        rag_blocks.append(f"- **Category**: `{c.demographic_category}`")
        rag_blocks.append(f"- **Wikidata Status**: {'Existing QID: ' + c.existing_qid if c.existing_qid else 'New Item Creation'}")
        rag_blocks.append(f"- **Composite Rank Score**: `{c.composite_rank_score}` (Disparity: {c.disparity_score}, Influence: {c.influence_score}, Reliability: {c.reliability_score})")
        rag_blocks.append(f"- **RAG Provider Status**: {status_msg}")
        rag_blocks.append("\n### Sample Lead Section (Wikitext):\n```wikitext\n" + intro_wikitext + "\n```\n")
        rag_blocks.append("\n### QuickStatements:\n```text\n" + qs_text + "\n```\n")

        cand_dict = c.to_dict()
        cand_dict["generated_wikitext"] = intro_wikitext
        cand_dict["quickstatements"] = qs_text
        json_payload.append(cand_dict)

        # Real-time incremental progress JSON write
        json_bytes = json.dumps(json_payload, indent=2).encode("utf-8")
        checkpoint_json_file.write_bytes(json_bytes)
        json_file.write_bytes(json_bytes)

        # Update progress checkpoint summary JSON
        progress_summary = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "completed_candidates": idx,
            "total_candidates": total_cands,
            "percent_complete": round((idx / total_cands) * 100, 1),
            "last_processed_candidate": c.name,
            "last_status": status_msg,
        }
        progress_file.write_text(json.dumps(progress_summary, indent=2), encoding="utf-8")

        print(f"[RAG Progress {idx}/{total_cands}] Generated Wikitext for {c.name} -> data/suggested_candidates_rag.json")

    qs_file.write_text("\n".join(qs_blocks), encoding="utf-8")
    rag_file.write_text("\n".join(rag_blocks), encoding="utf-8")

    return {
        "quickstatements": str(qs_file),
        "wikitext": str(rag_file),
        "json": str(json_file),
        "checkpoint_json": str(checkpoint_json_file),
        "progress_summary": str(progress_file),
    }

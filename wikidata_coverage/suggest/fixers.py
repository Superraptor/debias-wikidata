"""Turns Findings into concrete, human-reviewable proposed edits.

This module NEVER writes to Wikidata. It only produces:
  - QuickStatements-format strings (pasteable into
    https://quickstatements.toolforge.org for manual/batch review), or
  - wbeditentity-style API payload dicts (for a separate, explicitly
    opt-in bot execution path that this package does not itself implement).

Keeping "detect/suggest" and "apply" as fully separate concerns is a
deliberate safety boundary, not an oversight -- see project design notes.
"""

from __future__ import annotations

from wikidata_coverage.core.finding import Finding, FindingKind


def to_quickstatements_batch(findings: list[Finding]) -> str:
    """Collects every finding's suggested_fix.quickstatements line (if any)
    into a single batch, one statement per line, ready for manual review
    and submission via QuickStatements. Findings without an actionable
    suggested fix (e.g. most CONSTRAINT_VIOLATION or all MISSING_ENTITY
    findings, which need a human to pick/create a value) are skipped --
    call out_of_band_findings() to see what was excluded and why.
    """
    lines = [
        f.suggested_fix.quickstatements
        for f in findings
        if f.suggested_fix and f.suggested_fix.quickstatements
    ]
    return "\n".join(lines)


def out_of_band_findings(findings: list[Finding]) -> list[Finding]:
    """Findings that need human judgment before any edit can be proposed
    -- e.g. a MISSING_STATEMENT finding tells you *which* property is
    missing but not what value to fill in, and MISSING_ENTITY findings
    imply creating a whole new item, which this package won't attempt to
    automate."""
    return [
        f
        for f in findings
        if not (f.suggested_fix and f.suggested_fix.quickstatements)
    ]


def summarize_for_review(findings: list[Finding]) -> str:
    """Human-readable text summary grouping findings by whether they have
    an actionable suggestion or need manual triage first."""
    actionable = [f for f in findings if f.suggested_fix and f.suggested_fix.quickstatements]
    manual = out_of_band_findings(findings)

    lines = [
        f"{len(findings)} findings total: "
        f"{len(actionable)} with a draft suggestion, {len(manual)} needing manual review.",
        "",
    ]
    if actionable:
        lines.append("-- Draft suggestions (review before submitting) --")
        for f in actionable:
            lines.append(f"  [{f.kind.value}] {f.entity_id}: {f.suggested_fix.description}")
        lines.append("")
    if manual:
        lines.append("-- Needs manual triage --")
        for f in manual:
            lines.append(f"  [{f.kind.value}] {f.entity_id}: {f.message}")

    return "\n".join(lines)

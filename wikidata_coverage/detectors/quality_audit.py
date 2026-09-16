"""Quality and Constraint Audit engine for QLever dataset entities.

Implements two-stage audit workflow:
1. Profiles full peer population in the QLever dataset for a target class (e.g. Q5 Human)
   to determine peer-expected properties (frequency threshold >= 80%).
2. Identifies top N entities in the QLever dataset with lowest quality / fewest statement
   values in the TSV file relative to peers.
3. Fetches full entity statements and claims from Wikidata Action API (or QLever) for the top N.
4. Calculates constraint violation scores (P2302 rules) and class-profile missing statement
   scores on the enriched full entity data.
"""

from __future__ import annotations

from typing import Any, Iterable
from dataclasses import dataclass, field

from wikidata_coverage.access.api import ActionApiClient
from wikidata_coverage.core.entity import Entity
from wikidata_coverage.core.finding import Finding, FindingKind, Severity, SuggestedFix
from wikidata_coverage.core.report import CoverageReport, EntityScore
from wikidata_coverage.detectors.class_profile import ClassProfileDetector
from wikidata_coverage.detectors.constraints import ConstraintDetector


@dataclass
class QualityAuditResult:
    """Summary result of a quality & constraint audit run."""

    class_qid: str
    total_population_size: int
    audited_count: int
    offset: int
    top_n: int
    frequency_threshold: float
    coverage_report: CoverageReport
    profile_expected_properties: list[str]
    audited_qids: list[str] = field(default_factory=list)
    next_candidate_qids: list[str] = field(default_factory=list)


def run_qlever_quality_audit(
    entities: Iterable[Entity],
    class_qid: str = "Q5",
    top_n: int = 50,
    offset: int = 0,
    frequency_threshold: float = 0.8,
    api_client: ActionApiClient | None = None,
    exclude_fictional: bool = True,
) -> QualityAuditResult:
    """Runs a quality & constraint audit across instances of `class_qid` in the QLever dataset.

    Parameters
    ----------
    entities : Iterable[Entity]
        The population of entities parsed from QLever query results.
    class_qid : str
        Target Wikidata class QID (default "Q5" human).
    top_n : int
        Number of lowest-quality entities to fetch & evaluate (default 50).
    offset : int
        Pagination offset within the sorted lowest-quality entities list (default 0).
    frequency_threshold : float
        Peer consensus prevalence threshold (default 0.8 / 80%).
    api_client : ActionApiClient | None
        Action API client for fetching full entity details & label resolution.
    exclude_fictional : bool
        Whether to exclude fictional entities from constraint checks (default True).
    """
    entities_list = list(entities)

    # 1. Filter entities matching target class_qid (or default Q5)
    class_members: list[Entity] = []
    for e in entities_list:
        e_classes = e.classes()
        if not e_classes or class_qid in e_classes or "P31" not in e.claims:
            class_members.append(e)

    total_pop = len(class_members)
    if total_pop == 0:
        return QualityAuditResult(
            class_qid=class_qid,
            total_population_size=0,
            audited_count=0,
            offset=offset,
            top_n=top_n,
            frequency_threshold=frequency_threshold,
            coverage_report=CoverageReport(),
            profile_expected_properties=[],
            audited_qids=[],
        )

    # 2. Build peer class profile across the QLever population
    cp_detector = ClassProfileDetector(frequency_threshold=frequency_threshold)
    profile = cp_detector.build_profile(class_members, class_qid)
    expected_props = list(
        {
            prop
            for prop, freq in profile.property_frequency.items()
            if freq >= frequency_threshold
        }
        | (
            {"P21", "P27", "P106", "P19", "P569", "P172", "P91", "P1412", "P69"}
            if class_qid == "Q5"
            else set()
        )
    )

    # 3. Rank QLever TSV entities by fewest populated properties first (lowest initial quality in TSV)
    sorted_members = sorted(class_members, key=lambda e: len(e.property_ids()))
    candidate_slice = sorted_members[offset : offset + top_n]
    candidate_qids = [e.id for e in candidate_slice]
    next_candidate_qids = [e.id for e in sorted_members[offset + top_n : offset + top_n + 250]]

    if not candidate_qids:
        return QualityAuditResult(
            class_qid=class_qid,
            total_population_size=total_pop,
            audited_count=0,
            offset=offset,
            top_n=top_n,
            frequency_threshold=frequency_threshold,
            coverage_report=CoverageReport(),
            profile_expected_properties=expected_props,
            audited_qids=[],
            next_candidate_qids=[],
        )

    # 4. Fetch full entity statements & claims from Wikidata Action API for candidate QIDs
    api = api_client or ActionApiClient()
    enriched_entities: list[Entity] = []

    try:
        raw_entities = api.get_entities(candidate_qids)
        for tsv_ent in candidate_slice:
            qid = tsv_ent.id
            if qid in raw_entities and "claims" in raw_entities[qid]:
                full_ent = Entity.from_wbgetentities_json(qid, raw_entities[qid])
                enriched_entities.append(full_ent)
            else:
                enriched_entities.append(tsv_ent)
    except Exception:
        # Fallback to TSV entity representations if live API fails
        enriched_entities = candidate_slice

    # 5. Evaluate Class Profile missing statements on enriched entities
    all_findings: list[Finding] = []

    for entity in enriched_entities:
        missing = [p for p in expected_props if not entity.has_property(p)]
        for prop_id in missing:
            freq = profile.property_frequency.get(prop_id, 0.85)
            # Missing peer statement penalty: 1.0 for high peer frequency (>=90%), 0.85 for >=80%
            sev = (
                1.0
                if freq >= 0.90
                else (0.85 if freq >= 0.80 else 0.60)
            )
            all_findings.append(
                Finding(
                    entity_id=entity.id,
                    entity_label=entity.label(),
                    kind=FindingKind.MISSING_STATEMENT,
                    detector="class_profile_detector",
                    property_id=prop_id,
                    message=(
                        f"{entity.label() or entity.id} ({entity.id}) is missing expected peer statement {prop_id}, "
                        f"common on peers classified as {class_qid}."
                    ),
                    severity=sev,
                    evidence={
                        "class_id": class_qid,
                        "peer_frequency": freq,
                        "population_size": profile.population_size,
                    },
                    suggested_fix=SuggestedFix(
                        description=(
                            f"Consider adding {prop_id} to {entity.id}, common "
                            f"among peers of class {class_qid}."
                        ),
                        quickstatements=f"{entity.id}|{prop_id}|<VALUE>",
                    ),
                )
            )

    # 6. Evaluate P2302 Property Constraints on enriched entities
    c_detector = ConstraintDetector(exclude_fictional=exclude_fictional, max_items=None)
    constraint_findings = c_detector.run(enriched_entities)
    all_findings.extend(constraint_findings)

    # 7. Aggregate into CoverageReport and resolve labels
    cov_report = CoverageReport(findings=all_findings)
    cov_report.resolve_labels(api_client=api)

    return QualityAuditResult(
        class_qid=class_qid,
        total_population_size=total_pop,
        audited_count=len(enriched_entities),
        offset=offset,
        top_n=top_n,
        frequency_threshold=frequency_threshold,
        coverage_report=cov_report,
        profile_expected_properties=expected_props,
        audited_qids=candidate_qids,
        next_candidate_qids=next_candidate_qids,
    )

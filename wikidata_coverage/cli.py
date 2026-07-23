"""CLI entry point: wdcoverage

Examples:
    wdcoverage constraints --class Q5 --limit 100 --property P569 --property P21
    wdcoverage class-profile --class Q5 --limit 200 --threshold 0.8
    wdcoverage bias gender --class Q5 --limit 500 --live-baselines
    wdcoverage bias geographic --class Q5 --limit 500 --live-baselines
    wdcoverage bias demographic --class Q5 --property P106 --limit 500
    wdcoverage bias linguistic --class Q5 --limit 500 --top-languages 20
    wdcoverage bias sexual-orientation --class Q5 --limit 500
    wdcoverage bias rural-urban --class Q5 --limit 500
    wdcoverage bias ethnicity --class Q5 --limit 500
    wdcoverage bias intersectional --class Q5 --axis nationality+gender --limit 500
    wdcoverage bias intersectional --class Q5 --axis language+gender --occupation Q169470 --limit 500
"""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from wikidata_coverage.access.api import ActionApiClient
from wikidata_coverage.access.sparql import SparqlClient
from wikidata_coverage.bias.demographic import DemographicBalanceDetector, PROPERTY_AXIS_NAMES
from wikidata_coverage.bias.ethnicity import EthnicityBalanceDetector
from wikidata_coverage.bias.gender import GenderBalanceDetector
from wikidata_coverage.bias.geographic import GeographicDisparityDetector
from wikidata_coverage.bias.intersectionality import (
    ethnicity_and_gender_detector,
    language_and_gender_detector,
    nationality_and_gender_detector,
    occupation_and_gender_detector,
)
from wikidata_coverage.bias.linguistic import LinguisticCoverageDetector
from wikidata_coverage.bias.report import BiasReport
from wikidata_coverage.bias.rural_urban import RuralUrbanDetector
from wikidata_coverage.bias.sexual_orientation import SexualOrientationDetector
from wikidata_coverage.core.entity import Entity
from wikidata_coverage.core.report import CoverageReport
from wikidata_coverage.detectors.class_profile import ClassProfileDetector
from wikidata_coverage.detectors.constraints import ConstraintDetector

console = Console()


def scope_filter_options(f):
    """Reusable Click options for scoping entity sampling by nationality, occupation, ethnicity, etc."""
    f = click.option("--nationality", default=None, help="Filter scope by nationality (P27 QID), e.g. Q142 (France)")(f)
    f = click.option("--occupation", default=None, help="Filter scope by occupation (P106 QID), e.g. Q169470 (physicist)")(f)
    f = click.option("--ethnicity", default=None, help="Filter scope by ethnic group (P172 QID), e.g. Q539050")(f)
    f = click.option("--filter", "custom_filters", multiple=True, help="Custom property filter in Pxx=Qyy format, e.g. P27=Q142")(f)
    return f


def _fetch_entities(qids: list[str]) -> list[Entity]:
    api = ActionApiClient()
    raw = api.get_entities(qids)
    return [Entity.from_wbgetentities_json(qid, data) for qid, data in raw.items()]


def _fetch_class_entities(
    class_qid: str,
    limit: int,
    nationality: str | None = None,
    occupation: str | None = None,
    ethnicity: str | None = None,
    custom_filters: tuple[str, ...] = (),
    required_properties: list[str] | None = None,
) -> list[Entity]:
    property_filters: dict[str, str] = {}
    if nationality:
        property_filters["P27"] = nationality
    if occupation:
        property_filters["P106"] = occupation
    if ethnicity:
        property_filters["P172"] = ethnicity
    for item in custom_filters:
        if "=" in item:
            p, v = item.split("=", 1)
            property_filters[p.strip()] = v.strip()

    sparql = SparqlClient()
    filter_str = f" with filters {property_filters}" if property_filters else ""
    console.print(f"[bold]Fetching up to {limit} items of class {class_qid}{filter_str}...[/bold]")
    qids = sparql.qids_of_class(
        class_qid,
        property_filters=property_filters,
        required_properties=required_properties,
        limit=limit,
    )
    console.print(f"Found {len(qids)} items. Fetching entity data...")
    return _fetch_entities(qids)


@click.group()
def main() -> None:
    """wikidata_coverage: detect and assess Wikidata modeling/coverage gaps."""


# ---------------------------------------------------------------------------
# Coverage commands (entity-level, emit Finding -> CoverageReport)
# ---------------------------------------------------------------------------

@main.command()
@click.option("--class", "class_qid", required=True, help="QID of the class to scope to, e.g. Q5")
@click.option("--property", "properties", multiple=True, required=True, help="PID(s) to constraint-check")
@click.option("--limit", default=100, show_default=True, help="Max entities to pull for the class")
@click.option("--out", "out_path", default=None, help="Write JSON report to this path instead of stdout")
def constraints(class_qid: str, properties: tuple[str, ...], limit: int, out_path: str | None) -> None:
    """Run constraint-based detection over items of a given class."""
    entities = _fetch_class_entities(class_qid, limit)
    detector = ConstraintDetector(properties_to_check=list(properties))

    console.print("Running constraint detector...")
    findings = detector.run(entities)

    report = CoverageReport()
    report.add(findings)
    _emit_coverage(report, out_path)


@main.command(name="class-profile")
@click.option("--class", "class_qid", required=True, help="QID of the class to scope to, e.g. Q5")
@click.option("--limit", default=200, show_default=True, help="Max entities to pull for the class")
@click.option("--threshold", default=0.8, show_default=True, help="Peer-frequency threshold")
@click.option("--out", "out_path", default=None, help="Write JSON report to this path instead of stdout")
def class_profile(class_qid: str, limit: int, threshold: float, out_path: str | None) -> None:
    """Run class-profile (peer statistical) detection over items of a given class."""
    entities = _fetch_class_entities(class_qid, limit)
    detector = ClassProfileDetector(frequency_threshold=threshold)

    console.print("Running class-profile detector...")
    findings = detector.run(entities)

    report = CoverageReport()
    report.add(findings)
    _emit_coverage(report, out_path)


# ---------------------------------------------------------------------------
# Bias commands (group-level, emit DisparityMetric -> BiasReport)
# ---------------------------------------------------------------------------

@main.group()
def bias() -> None:
    """Run bias detectors that measure group-level disparities."""


@bias.command(name="gender")
@click.option("--class", "class_qid", required=True, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, help="Max entities to sample")
@scope_filter_options
@click.option("--live-baselines", is_flag=True, default=False, help="Fetch live population baselines from Wikidata via SPARQL")
@click.option("--out", "out_path", default=None, help="Write JSON/CSV report; use .csv extension for CSV")
def bias_gender(
    class_qid: str,
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    live_baselines: bool,
    out_path: str | None,
) -> None:
    """Measure gender balance (P21) vs. a population baseline."""
    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters
    )
    sparql = SparqlClient() if live_baselines else None
    detector = GenderBalanceDetector(sparql=sparql, country_qid=nationality)

    console.print("Running gender-balance detector...")
    metrics = detector.run(entities)

    report = BiasReport()
    report.add(metrics)
    _emit_bias(report, out_path, axis="gender")


@bias.command(name="geographic")
@click.option("--class", "class_qid", required=True, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, help="Max entities to sample")
@scope_filter_options
@click.option(
    "--property", "property_id", default="P27", show_default=True,
    help="Country property to group by (P27=citizenship, P17=country, P19=place of birth)"
)
@click.option("--live-baselines", is_flag=True, default=False, help="Fetch live population baselines from Wikidata via SPARQL")
@click.option("--out", "out_path", default=None, help="Write JSON/CSV report; use .csv extension for CSV")
def bias_geographic(
    class_qid: str,
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    property_id: str,
    live_baselines: bool,
    out_path: str | None,
) -> None:
    """Measure geographic disparity vs. world population shares."""
    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters
    )
    sparql = SparqlClient() if live_baselines else None
    detector = GeographicDisparityDetector(property_id=property_id, sparql=sparql)

    console.print(f"Running geographic-disparity detector (property={property_id})...")
    metrics = detector.run(entities)

    report = BiasReport()
    report.add(metrics)
    _emit_bias(report, out_path, axis="geographic")


@bias.command(name="demographic")
@click.option("--class", "class_qid", required=True, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--property", "properties", multiple=True, help="PID(s) to group by, e.g. P27, P172, P106 (defaults to nationality, ethnicity, occupation)")
@click.option("--limit", default=500, show_default=True, help="Max entities to sample")
@scope_filter_options
@click.option("--out", "out_path", default=None, help="Write JSON/CSV report; use .csv extension for CSV")
def bias_demographic(
    class_qid: str,
    properties: tuple[str, ...],
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    out_path: str | None,
) -> None:
    """Measure demographic balance across categorical properties (nationality P27, ethnicity P172, occupation P106, etc.)."""
    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters
    )
    props_to_check = list(properties) if properties else ["P27", "P172", "P106"]

    report = BiasReport()
    for prop_id in props_to_check:
        axis_name = PROPERTY_AXIS_NAMES.get(prop_id, prop_id)
        console.print(f"Running demographic-balance detector (property={prop_id} — {axis_name})...")
        detector = DemographicBalanceDetector(property_id=prop_id, expected_shares={})
        report.add(detector.run(entities))

    _emit_bias(
        report,
        out_path,
        axis=PROPERTY_AXIS_NAMES.get(props_to_check[0], props_to_check[0]) if len(props_to_check) == 1 else None,
    )


@bias.command(name="linguistic")
@click.option("--class", "class_qid", required=True, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, help="Max entities to sample")
@scope_filter_options
@click.option("--top-languages", default=30, show_default=True, help="Number of languages by speaker count to fetch for baseline")
@click.option("--out", "out_path", default=None, help="Write JSON/CSV report; use .csv extension for CSV")
def bias_linguistic(
    class_qid: str,
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    top_languages: int,
    out_path: str | None,
) -> None:
    """Measure multilingual label, description, and alias coverage vs. speaker population."""
    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters
    )
    sparql = SparqlClient()
    detector = LinguisticCoverageDetector(sparql=sparql, top_n_languages=top_languages)

    console.print("Running linguistic-coverage detector...")
    metrics = detector.run(entities)

    report = BiasReport()
    report.add(metrics)
    _emit_bias(report, out_path, axis=None)


@bias.command(name="sexual-orientation")
@click.option("--class", "class_qid", required=True, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, help="Max entities to sample")
@scope_filter_options
@click.option("--out", "out_path", default=None, help="Write JSON/CSV report; use .csv extension for CSV")
def bias_sexual_orientation(
    class_qid: str,
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    out_path: str | None,
) -> None:
    """Measure distribution of P91 (sexual orientation) values among entities with P91 recorded."""
    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters
    )
    detector = SexualOrientationDetector()

    console.print("Running sexual-orientation detector...")
    metrics = detector.run(entities)

    report = BiasReport()
    report.add(metrics)
    _emit_bias(report, out_path, axis="sexual_orientation")


@bias.command(name="rural-urban")
@click.option("--class", "class_qid", required=True, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, help="Max entities to sample")
@scope_filter_options
@click.option("--property", "property_id", default="P19", show_default=True, help="Place property to analyze (P19=place of birth, P20=place of death)")
@click.option("--out", "out_path", default=None, help="Write JSON/CSV report; use .csv extension for CSV")
def bias_rural_urban(
    class_qid: str,
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    property_id: str,
    out_path: str | None,
) -> None:
    """Measure urban vs. rural representation (by birthplace P19) vs. world population split."""
    entities = _fetch_class_entities(
        class_qid,
        limit,
        nationality=nationality,
        occupation=occupation,
        ethnicity=ethnicity,
        custom_filters=custom_filters,
        required_properties=[property_id],
    )
    sparql = SparqlClient()
    detector = RuralUrbanDetector(sparql=sparql, property_id=property_id)

    console.print(f"Running rural-urban detector (property={property_id})...")
    metrics = detector.run(entities)

    report = BiasReport()
    report.add(metrics)
    _emit_bias(report, out_path, axis="rural_urban")


@bias.command(name="ethnicity")
@click.option("--class", "class_qid", required=True, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, help="Max entities to sample")
@scope_filter_options
@click.option("--out", "out_path", default=None, help="Write JSON/CSV report; use .csv extension for CSV")
def bias_ethnicity(
    class_qid: str,
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    out_path: str | None,
) -> None:
    """Measure representation across recorded P172 (ethnic group) values."""
    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters
    )
    detector = EthnicityBalanceDetector()

    console.print("Running ethnicity-balance detector...")
    metrics = detector.run(entities)

    report = BiasReport()
    report.add(metrics)
    _emit_bias(report, out_path, axis="ethnicity")


@bias.command(name="intersectional")
@click.option("--class", "class_qid", required=True, help="QID of the class/scope, e.g. Q5 (human)")
@click.option(
    "--axis", "intersectional_axis", required=True,
    type=click.Choice(["nationality+gender", "language+gender", "occupation+gender", "ethnicity+gender"]),
    help="Pair of axes to evaluate"
)
@click.option("--limit", default=500, show_default=True, help="Max entities to sample")
@scope_filter_options
@click.option("--live-baselines", is_flag=True, default=False, help="Fetch live population baselines from Wikidata via SPARQL")
@click.option("--out", "out_path", default=None, help="Write JSON/CSV report; use .csv extension for CSV")
def bias_intersectional(
    class_qid: str,
    intersectional_axis: str,
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    live_baselines: bool,
    out_path: str | None,
) -> None:
    """Measure joint representation disparities across paired axes (e.g. nationality + gender)."""
    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters
    )
    sparql = SparqlClient() if live_baselines else None

    if intersectional_axis == "nationality+gender":
        detector = nationality_and_gender_detector(sparql=sparql)
    elif intersectional_axis == "language+gender":
        detector = language_and_gender_detector(sparql=sparql)
    elif intersectional_axis == "occupation+gender":
        detector = occupation_and_gender_detector()
    elif intersectional_axis == "ethnicity+gender":
        detector = ethnicity_and_gender_detector()
    else:
        raise click.BadParameter(f"Unknown intersectional axis: {intersectional_axis}")

    console.print(f"Running intersectional detector ({intersectional_axis})...")
    metrics = detector.run(entities)

    report = BiasReport()
    report.add(metrics)
    _emit_bias(report, out_path, axis=detector.axis)


@bias.command(name="all")
@click.option("--class", "class_qid", required=True, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, help="Max entities to sample")
@scope_filter_options
@click.option("--live-baselines", is_flag=True, default=False, help="Fetch live population baselines from Wikidata via SPARQL")
@click.option("--out", "out_path", default=None, help="Write combined JSON report to this path")
def bias_all(
    class_qid: str,
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    live_baselines: bool,
    out_path: str | None,
) -> None:
    """Run all built-in bias detectors and combine into one report."""
    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters
    )
    sparql = SparqlClient()

    report = BiasReport()

    console.print("Running gender-balance detector...")
    gender_det = GenderBalanceDetector(sparql=sparql if live_baselines else None, country_qid=nationality)
    report.add(gender_det.run(entities))

    console.print("Running geographic-disparity detector...")
    geo_det = GeographicDisparityDetector(sparql=sparql if live_baselines else None)
    report.add(geo_det.run(entities))

    console.print("Running linguistic-coverage detector...")
    ling_det = LinguisticCoverageDetector(sparql=sparql)
    report.add(ling_det.run(entities))

    console.print("Running sexual-orientation detector...")
    so_det = SexualOrientationDetector()
    report.add(so_det.run(entities))

    console.print("Running rural-urban detector...")
    ru_det = RuralUrbanDetector(sparql=sparql)
    report.add(ru_det.run(entities))

    console.print("Running ethnicity-balance detector...")
    eth_det = EthnicityBalanceDetector()
    report.add(eth_det.run(entities))

    console.print("Running intersectional (nationality+gender) detector...")
    nat_gen_det = nationality_and_gender_detector(sparql=sparql if live_baselines else None)
    report.add(nat_gen_det.run(entities))

    _emit_bias(report, out_path, axis=None)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _emit_coverage(report: CoverageReport, out_path: str | None) -> None:
    if out_path:
        with open(out_path, "w") as f:
            f.write(report.to_json())
        console.print(f"[green]Report written to {out_path}[/green]")
        return

    summary = report.summary()
    table = Table(title="Coverage Report Summary")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Total findings", str(summary["total_findings"]))
    table.add_row("Entities with findings", str(summary["entities_with_findings"]))
    for kind, count in summary["findings_by_kind"].items():
        table.add_row(f"  kind: {kind}", str(count))
    console.print(table)

    if summary["worst_entities"]:
        worst_table = Table(
            title="Worst Entities",
            caption="Ranked by cumulative severity score (sum of finding severities: Critical=1.0, High=0.85, Med=0.6, Low=0.3, Info=0.1)",
        )
        worst_table.add_column("Entity ID")
        worst_table.add_column("Label")
        worst_table.add_column("Score")
        worst_table.add_column("# Findings")
        for row in summary["worst_entities"]:
            worst_table.add_row(
                row["entity_id"],
                row.get("entity_label", row["entity_id"]),
                str(row["score"]),
                str(row["n_findings"]),
            )
        console.print(worst_table)


def _emit_bias(report: BiasReport, out_path: str | None, axis: str | None) -> None:
    # Resolve any remaining raw QIDs in group labels (e.g. "Q110161171 x male" -> "householder x male")
    report.resolve_labels()

    if out_path:
        if out_path.endswith(".csv"):
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                f.write(report.to_csv())
        else:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(report.to_json())
        console.print(f"[green]Bias report written to {out_path}[/green]")
        return

    summary = report.summary()
    summary_table = Table(title="Bias Report Summary")
    summary_table.add_column("Axis")
    summary_table.add_column("Groups measured")
    for ax, count in summary["metrics_per_axis"].items():
        summary_table.add_row(ax, str(count))
    console.print(summary_table)

    axes_to_show = [axis] if axis else list(report.by_axis().keys())
    for ax in axes_to_show:
        metrics = report.by_axis().get(ax, [])
        if not metrics:
            continue
        detail_table = Table(title=f"[bold]{ax}[/bold] — observed vs. expected")
        detail_table.add_column("Group")
        detail_table.add_column("N")
        detail_table.add_column("Observed")
        detail_table.add_column("Expected")
        detail_table.add_column("Ratio")
        detail_table.add_column("Severity")
        detail_table.add_column("Note")
        for m in sorted(metrics, key=lambda m: (m.disparity_ratio or 9999)):
            ratio_str = f"{m.disparity_ratio:.3f}" if m.disparity_ratio is not None else "—"
            expected_str = f"{m.expected_value:.3f}" if m.expected_value is not None else "—"
            low_conf = "⚠ low-n" if m.evidence.get("low_confidence") else ""
            detail_table.add_row(
                m.group_label,
                str(m.group_size),
                f"{m.observed_value:.3f}",
                expected_str,
                ratio_str,
                f"{m.severity:.2f}",
                low_conf,
            )
        console.print(detail_table)

    if summary["most_underrepresented"]:
        worst_table = Table(title="Most Underrepresented Groups (across all axes)")
        worst_table.add_column("Axis")
        worst_table.add_column("Group")
        worst_table.add_column("Observed")
        worst_table.add_column("Expected")
        worst_table.add_column("Ratio")
        for row in summary["most_underrepresented"]:
            worst_table.add_row(
                row["axis"],
                row["group"],
                f"{row['observed']:.3f}",
                f"{row['expected']:.3f}" if row["expected"] is not None else "—",
                f"{row['disparity_ratio']:.3f}" if row["disparity_ratio"] is not None else "—",
            )
        console.print(worst_table)


if __name__ == "__main__":
    main()

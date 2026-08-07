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

import re

import click
from rich.console import Console
from rich.table import Table

import csv
from pathlib import Path
from wikidata_coverage.access.api import ActionApiClient
from wikidata_coverage.access.qlever import (
    QLeverClient,
    load_entities_from_qlever_file,
    find_default_qlever_file,
)
from wikidata_coverage.access.sparql import SparqlClient
from wikidata_coverage.bias.demographic import DemographicBalanceDetector, PROPERTY_AXIS_NAMES
from wikidata_coverage.bias.ethnicity import EthnicityBalanceDetector
from wikidata_coverage.bias.gender import GenderBalanceDetector
from wikidata_coverage.bias.geographic import GeographicDisparityDetector
from wikidata_coverage.bias.intersectionality import (
    ethnicity_and_gender_detector,
    language_and_gender_detector,
    nationality_and_gender_detector,
    nationality_and_sexual_orientation_detector,
    occupation_and_gender_detector,
    sexual_orientation_and_gender_detector,
)
from wikidata_coverage.bias.linguistic import LinguisticCoverageDetector
from wikidata_coverage.bias.report import BiasReport
from wikidata_coverage.bias.rural_urban import RuralUrbanDetector
from wikidata_coverage.bias.sexual_orientation import SexualOrientationDetector
from wikidata_coverage.core.entity import Entity
from wikidata_coverage.core.report import CoverageReport
from wikidata_coverage.detectors.class_profile import ClassProfileDetector
from wikidata_coverage.detectors.constraints import ConstraintDetector
from wikidata_coverage.generate_paper_figures import generate_all_figures

console = Console()

QID_PATTERN = re.compile(r"^Q\d+$", re.IGNORECASE)
PID_PATTERN = re.compile(r"^P\d+$", re.IGNORECASE)


def validate_qid_option(ctx, param, value):
    if value is None:
        return None
    val_clean = str(value).strip().upper()
    if not QID_PATTERN.match(val_clean):
        raise click.BadParameter(
            f"Invalid Wikidata Item QID '{value}'. QIDs must be in format 'Q' followed by digits (e.g. Q5, Q142)."
        )
    return val_clean


def validate_pid_option(ctx, param, value):
    if not value:
        return value
    if isinstance(value, (tuple, list)):
        cleaned = []
        for item in value:
            item_clean = str(item).strip().upper()
            if not PID_PATTERN.match(item_clean):
                raise click.BadParameter(
                    f"Invalid Wikidata Property PID '{item}'. Property PIDs must be in format 'P' followed by digits (e.g. P21, P106)."
                )
            cleaned.append(item_clean)
        return tuple(cleaned) if isinstance(value, tuple) else cleaned
    else:
        val_clean = str(value).strip().upper()
        if not PID_PATTERN.match(val_clean):
            raise click.BadParameter(
                f"Invalid Wikidata Property PID '{value}'. Property PIDs must be in format 'P' followed by digits (e.g. P21, P106)."
            )
        return val_clean


def validate_filter_option(ctx, param, value):
    if not value:
        return value
    cleaned = []
    for item in value:
        if "=" not in item:
            raise click.BadParameter(
                f"Invalid filter format '{item}'. Filters must be in 'Pxx=Qyy' format (e.g. P27=Q142)."
            )
        p, v = item.split("=", 1)
        p_clean = p.strip().upper()
        if not PID_PATTERN.match(p_clean):
            raise click.BadParameter(
                f"Invalid property PID '{p}' in filter '{item}'. Property PIDs must be in format 'P' followed by digits (e.g. P27)."
            )
        v_clean = v.strip()
        if v_clean.upper().startswith("Q") and not QID_PATTERN.match(v_clean.upper()):
            raise click.BadParameter(
                f"Invalid QID '{v}' in filter '{item}'. QIDs must be in format 'Q' followed by digits (e.g. Q142)."
            )
        cleaned.append(f"{p_clean}={v_clean.upper() if v_clean.upper().startswith('Q') else v_clean}")
    return tuple(cleaned)


def validate_limit_option(ctx, param, value):
    if value is not None and value <= 0:
        raise click.BadParameter(f"Limit must be a positive integer greater than 0, got {value}.")
    return value


def scope_filter_options(f):
    """Reusable Click options for scoping entity sampling by nationality, occupation, ethnicity, etc."""
    f = click.option("--nationality", default=None, callback=validate_qid_option, help="Filter scope by nationality (P27 QID), e.g. Q142 (France)")(f)
    f = click.option("--occupation", default=None, callback=validate_qid_option, help="Filter scope by occupation (P106 QID), e.g. Q169470 (physicist)")(f)
    f = click.option("--ethnicity", default=None, callback=validate_qid_option, help="Filter scope by ethnic group (P172 QID), e.g. Q539050")(f)
    f = click.option("--filter", "custom_filters", multiple=True, callback=validate_filter_option, help="Custom property filter in Pxx=Qyy format, e.g. P27=Q142")(f)
    f = click.option("--qlever-file", "--qlever-data", "qlever_file", default=None, help="Path to QLever query result file (TSV, CSV, JSON) to run analysis offline")(f)
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
    exclude_fictional: bool = True,
    qlever_file: str | None = None,
) -> list[Entity]:
    target_qlever = Path(qlever_file) if qlever_file else find_default_qlever_file()
    if target_qlever and target_qlever.exists():
        console.print(f"[bold green]Loading entity population from QLever result file {target_qlever}...[/bold green]")
        entities = load_entities_from_qlever_file(target_qlever)

        # Apply in-memory property filters if specified
        if nationality:
            entities = [e for e in entities if nationality in [v.get("id") for v in e.values_for("P27") if isinstance(v, dict)]]
        if occupation:
            entities = [e for e in entities if occupation in [v.get("id") for v in e.values_for("P106") if isinstance(v, dict)]]
        if ethnicity:
            entities = [e for e in entities if ethnicity in [v.get("id") for v in e.values_for("P172") if isinstance(v, dict)]]

        if limit and len(entities) > limit:
            entities = entities[:limit]

        console.print(f"Loaded {len(entities)} matching entity objects from QLever file.")
        return entities

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
    fictional_str = " (excluding fictional)" if exclude_fictional else ""
    console.print(f"[bold]Fetching up to {limit} items of class {class_qid}{filter_str}{fictional_str}...[/bold]")
    qids = sparql.qids_of_class(
        class_qid,
        property_filters=property_filters,
        required_properties=required_properties,
        exclude_fictional=exclude_fictional,
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
@click.option("--class", "class_qid", required=True, callback=validate_qid_option, help="QID of the class to scope to, e.g. Q5")
@click.option("--property", "properties", multiple=True, required=False, callback=validate_pid_option, help="PID(s) to constraint-check (omitting checks all properties on sampled entities)")
@click.option("--limit", default=100, show_default=True, callback=validate_limit_option, help="Max entities to pull for the class")
@click.option("--include-fictional", is_flag=True, default=False, help="Include fictional entities/characters in constraint checks (excluded by default)")
@click.option("--lang", "--language", "lang", default="en", show_default=True, help="Language code for property and entity labels (e.g. en, fr, de, es, ja)")
@click.option("--out", "out_path", default=None, help="Write JSON report to this path instead of stdout")
def constraints(class_qid: str, properties: tuple[str, ...], limit: int, include_fictional: bool, lang: str, out_path: str | None) -> None:
    """Run constraint-based detection over items of a given class."""
    exclude_fictional = not include_fictional
    entities = _fetch_class_entities(class_qid, limit, exclude_fictional=exclude_fictional)
    props = list(properties) if properties else None
    detector = ConstraintDetector(properties_to_check=props, exclude_fictional=exclude_fictional)

    console.print("Running constraint detector...")
    findings = detector.run(entities)

    report = CoverageReport()
    report.add(findings)
    _emit_coverage(report, out_path, lang=lang)


@main.command(name="class-profile")
@click.option("--class", "class_qid", required=True, callback=validate_qid_option, help="QID of the class to scope to, e.g. Q5")
@click.option("--limit", default=200, show_default=True, callback=validate_limit_option, help="Max entities to pull for the class")
@click.option("--threshold", default=0.8, show_default=True, help="Peer-frequency threshold")
@click.option("--lang", "--language", "lang", default="en", show_default=True, help="Language code for property and entity labels (e.g. en, fr, de, es, ja)")
@click.option("--out", "out_path", default=None, help="Write JSON report to this path instead of stdout")
def class_profile(class_qid: str, limit: int, threshold: float, lang: str, out_path: str | None) -> None:
    """Run class-profile (peer statistical) detection over items of a given class."""
    entities = _fetch_class_entities(class_qid, limit)
    detector = ClassProfileDetector(frequency_threshold=threshold)

    console.print("Running class-profile detector...")
    findings = detector.run(entities)

    report = CoverageReport()
    report.add(findings)
    _emit_coverage(report, out_path, lang=lang)


# ---------------------------------------------------------------------------
# Bias commands (group-level, emit DisparityMetric -> BiasReport)
# ---------------------------------------------------------------------------

@main.group()
def bias() -> None:
    """Run bias detectors that measure group-level disparities."""


@bias.command(name="gender")
@click.option("--class", "class_qid", required=True, callback=validate_qid_option, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, callback=validate_limit_option, help="Max entities to sample")
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
@click.option("--class", "class_qid", required=True, callback=validate_qid_option, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, callback=validate_limit_option, help="Max entities to sample")
@scope_filter_options
@click.option(
    "--property", "property_id", default="P27", show_default=True, callback=validate_pid_option,
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
@click.option("--class", "class_qid", required=True, callback=validate_qid_option, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--property", "properties", multiple=True, callback=validate_pid_option, help="PID(s) to group by, e.g. P27, P172, P106 (defaults to nationality, ethnicity, occupation)")
@click.option("--limit", default=500, show_default=True, callback=validate_limit_option, help="Max entities to sample")
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

    sparql = SparqlClient()
    report = BiasReport()
    for prop_id in props_to_check:
        axis_name = PROPERTY_AXIS_NAMES.get(prop_id, prop_id)
        console.print(f"Running demographic-balance detector (property={prop_id} — {axis_name})...")
        detector = DemographicBalanceDetector(property_id=prop_id, sparql=sparql)
        report.add(detector.run(entities))

    _emit_bias(
        report,
        out_path,
        axis=PROPERTY_AXIS_NAMES.get(props_to_check[0], props_to_check[0]) if len(props_to_check) == 1 else None,
    )


@bias.command(name="linguistic")
@click.option("--class", "class_qid", required=True, callback=validate_qid_option, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, callback=validate_limit_option, help="Max entities to sample")
@scope_filter_options
@click.option("--top-languages", default=None, type=int, help="Optional: limit baseline evaluation to top N languages by speaker count (e.g. --top-languages 30)")
@click.option("--out", "out_path", default=None, help="Write JSON/CSV report; use .csv extension for CSV")
def bias_linguistic(
    class_qid: str,
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    top_languages: int | None,
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
@click.option("--class", "class_qid", required=True, callback=validate_qid_option, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, callback=validate_limit_option, help="Max entities to sample")
@scope_filter_options
@click.option("--assume-heterosexual-default", "--assume-heterosexual", "assume_heterosexual", is_flag=True, default=False, help="Assume entities without explicit P91 statements are heterosexual")
@click.option("--compare-heterosexual-assumption", "compare_assumption", is_flag=True, default=False, help="Display side-by-side comparison of explicit P91 vs. assumed-heterosexual models")
@click.option("--out", "out_path", default=None, help="Write JSON/CSV report; use .csv extension for CSV")
def bias_sexual_orientation(
    class_qid: str,
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    qlever_file: str | None,
    assume_heterosexual: bool,
    compare_assumption: bool,
    out_path: str | None,
) -> None:
    """Measure distribution of P91 (sexual orientation) values vs. Ipsos global and country-specific baselines."""
    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters, qlever_file=qlever_file
    )

    if compare_assumption:
        console.print(f"[bold cyan]Running Sexual Orientation Comparative Analysis (Explicit P91 vs. Assumed Heterosexual)...[/bold cyan]")
        det_explicit = SexualOrientationDetector(country_qid=nationality, assume_heterosexual_if_missing=False)
        det_assumed = SexualOrientationDetector(country_qid=nationality, assume_heterosexual_if_missing=True)

        m_explicit = det_explicit.run(entities)
        m_assumed = det_assumed.run(entities)

        comp_table = Table(title="Sexual Orientation Representation: Explicit P91 vs. Assumed Heterosexual Model")
        comp_table.add_column("Category / Group")
        comp_table.add_column("Explicit P91 (N)")
        comp_table.add_column("Explicit Share")
        comp_table.add_column("Assumed Het. (N)")
        comp_table.add_column("Assumed Het. Share")
        comp_table.add_column("Ipsos Baseline")

        all_keys = set([m.group_key for m in m_explicit] + [m.group_key for m in m_assumed])
        map_exp = {m.group_key: m for m in m_explicit}
        map_ass = {m.group_key: m for m in m_assumed}

        for k in sorted(all_keys):
            e_m = map_exp.get(k)
            a_m = map_ass.get(k)
            label = e_m.group_label if e_m else (a_m.group_label if a_m else k)
            e_n = str(e_m.group_size) if e_m else "0"
            e_share = f"{e_m.observed_value:.2%}" if e_m else "0.00%"
            a_n = str(a_m.group_size) if a_m else "0"
            a_share = f"{a_m.observed_value:.2%}" if a_m else "0.00%"
            base = f"{e_m.expected_value:.2%}" if (e_m and e_m.expected_value) else "—"

            comp_table.add_row(label, e_n, e_share, a_n, a_share, base)

        console.print(comp_table)

        report = BiasReport()
        report.add(m_explicit)
        report.add(m_assumed)
        _emit_bias(report, out_path, axis="sexual_orientation")
        return

    detector = SexualOrientationDetector(country_qid=nationality, assume_heterosexual_if_missing=assume_heterosexual)
    mode_desc = "Assumed Heterosexual for Missing P91" if assume_heterosexual else "Explicit P91 Only"
    console.print(f"Running sexual-orientation detector [baseline={nationality or 'Ipsos Global'}, mode={mode_desc}]...")
    metrics = detector.run(entities)

    report = BiasReport()
    report.add(metrics)
    _emit_bias(report, out_path, axis="sexual_orientation")


@bias.command(name="rural-urban")
@click.option("--class", "class_qid", required=True, callback=validate_qid_option, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, callback=validate_limit_option, help="Max entities to sample")
@scope_filter_options
@click.option("--property", "property_id", default="P19", show_default=True, callback=validate_pid_option, help="Place property to analyze (P19=place of birth, P20=place of death)")
@click.option("--out", "out_path", default=None, help="Write JSON/CSV report; use .csv extension for CSV")
def bias_rural_urban(
    class_qid: str,
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    qlever_file: str | None,
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
        qlever_file=qlever_file,
    )
    sparql = SparqlClient()
    detector = RuralUrbanDetector(sparql=sparql, property_id=property_id)

    console.print(f"Running rural-urban detector (property={property_id})...")
    metrics = detector.run(entities)

    report = BiasReport()
    report.add(metrics)
    _emit_bias(report, out_path, axis="rural_urban")


@bias.command(name="ethnicity")
@click.option("--class", "class_qid", required=True, callback=validate_qid_option, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, callback=validate_limit_option, help="Max entities to sample")
@scope_filter_options
@click.option("--out", "out_path", default=None, help="Write JSON/CSV report; use .csv extension for CSV")
def bias_ethnicity(
    class_qid: str,
    limit: int,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
    qlever_file: str | None,
    out_path: str | None,
) -> None:
    """Measure representation across recorded P172 (ethnic group) values."""
    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters, qlever_file=qlever_file
    )
    sparql = SparqlClient()
    detector = EthnicityBalanceDetector(sparql=sparql)

    console.print("Running ethnicity-balance detector...")
    metrics = detector.run(entities)

    report = BiasReport()
    report.add(metrics)
    _emit_bias(report, out_path, axis="ethnicity")


@bias.command(name="intersectional")
@click.option("--class", "class_qid", required=True, callback=validate_qid_option, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=500, show_default=True, callback=validate_limit_option, help="Max entities to sample")
@click.option(
    "--axis", "intersectional_axis", required=True,
    type=click.Choice([
        "nationality+gender",
        "language+gender",
        "occupation+gender",
        "ethnicity+gender",
        "nationality+sexual_orientation",
        "sexual_orientation+gender",
    ]),
    help="Pair of axes to evaluate"
)
@scope_filter_options
@click.option("--assume-heterosexual-default", "--assume-heterosexual", "assume_heterosexual", is_flag=True, default=False, help="Assume entities without explicit P91 statements are heterosexual for sexual orientation axes")
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
    qlever_file: str | None,
    assume_heterosexual: bool,
    live_baselines: bool,
    out_path: str | None,
) -> None:
    """Measure joint representation disparities across paired axes (e.g. nationality + sexual orientation)."""
    from wikidata_coverage.bias.intersectionality import (
        ethnicity_and_gender_detector,
        language_and_gender_detector,
        nationality_and_gender_detector,
        nationality_and_sexual_orientation_detector,
        occupation_and_gender_detector,
        sexual_orientation_and_gender_detector,
    )

    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters, qlever_file=qlever_file
    )
    sparql = SparqlClient() if live_baselines or "nationality" in intersectional_axis else None

    if intersectional_axis == "nationality+gender":
        detector = nationality_and_gender_detector(sparql=sparql)
    elif intersectional_axis == "language+gender":
        detector = language_and_gender_detector(sparql=sparql)
    elif intersectional_axis == "occupation+gender":
        detector = occupation_and_gender_detector(sparql=sparql)
    elif intersectional_axis == "ethnicity+gender":
        detector = ethnicity_and_gender_detector(sparql=sparql)
    elif intersectional_axis == "nationality+sexual_orientation":
        detector = nationality_and_sexual_orientation_detector(sparql=sparql, assume_heterosexual_if_missing=assume_heterosexual)
    elif intersectional_axis == "sexual_orientation+gender":
        detector = sexual_orientation_and_gender_detector(sparql=sparql, assume_heterosexual_if_missing=assume_heterosexual)
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


def _run_bias_demo(
    class_qid: str,
    limit: int,
    out_path: str,
    live_baselines: bool,
    lang: str,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
) -> None:
    from wikidata_coverage.bias.html_report import generate_html_report

    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters
    )
    sparql = SparqlClient() if live_baselines else None
    report = BiasReport()

    console.print(f"[bold cyan]Running demographic & intersectional bias audit across {len(entities):,} entities of class {class_qid}...[/bold cyan]")

    detectors = [
        ("Gender Balance", GenderBalanceDetector(sparql=sparql if live_baselines else None, country_qid=nationality)),
        ("Geographic Disparity", GeographicDisparityDetector(sparql=sparql if live_baselines else None)),
        ("Sexual Orientation Disparity", SexualOrientationDetector()),
        ("Ethnicity Balance", EthnicityBalanceDetector(sparql=sparql if live_baselines else None)),
        ("Linguistic Coverage", LinguisticCoverageDetector(sparql=sparql)),
        ("Intersectional (Nationality × Gender)", nationality_and_gender_detector(sparql=sparql if live_baselines else None)),
        ("Intersectional (Language × Gender)", language_and_gender_detector(sparql=sparql if live_baselines else None)),
        ("Intersectional (Occupation × Gender)", occupation_and_gender_detector(sparql=sparql if live_baselines else None)),
        ("Intersectional (Ethnicity × Gender)", ethnicity_and_gender_detector(sparql=sparql if live_baselines else None)),
        ("Intersectional (Nationality × Sexual Orientation)", nationality_and_sexual_orientation_detector(sparql=sparql if live_baselines else None)),
        ("Intersectional (Sexual Orientation × Gender)", sexual_orientation_and_gender_detector(sparql=sparql if live_baselines else None)),
    ]

    for label, det in detectors:
        console.print(f" -> Running {label}...")
        report.add(det.run(entities))

    console.print(" -> Resolving QID labels for human readability...")
    report.resolve_labels(lang=lang)

    console.print(f" -> Generating interactive HTML demo report at [bold green]{out_path}[/bold green]...")
    generate_html_report(report, sample_size=len(entities), class_qid=class_qid, out_path=out_path)
    console.print(f"[bold green][OK] Interactive HTML Demo Report successfully generated: {out_path}[/bold green]")


@main.command(name="demo")
@click.option("--class", "class_qid", default="Q5", show_default=True, callback=validate_qid_option, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=10000, show_default=True, callback=validate_limit_option, help="Max entities to sample")
@click.option("--out", "out_path", default="debias_wikidata_demo.html", show_default=True, help="Path to write interactive HTML demo report")
@click.option("--live-baselines/--no-live-baselines", default=True, show_default=True, help="Fetch live baselines via SPARQL")
@click.option("--lang", default="en", show_default=True, help="Language code for labels")
@scope_filter_options
def cli_demo(
    class_qid: str,
    limit: int,
    out_path: str,
    live_baselines: bool,
    lang: str,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
) -> None:
    """Run full demographic & intersectional bias audit across entities and generate an interactive HTML demo report."""
    _run_bias_demo(class_qid, limit, out_path, live_baselines, lang, nationality, occupation, ethnicity, custom_filters)


@bias.command(name="demo")
@click.option("--class", "class_qid", default="Q5", show_default=True, callback=validate_qid_option, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=10000, show_default=True, callback=validate_limit_option, help="Max entities to sample")
@click.option("--out", "out_path", default="debias_wikidata_demo.html", show_default=True, help="Path to write interactive HTML demo report")
@click.option("--live-baselines/--no-live-baselines", default=True, show_default=True, help="Fetch live baselines via SPARQL")
@click.option("--lang", default="en", show_default=True, help="Language code for labels")
@scope_filter_options
def bias_demo(
    class_qid: str,
    limit: int,
    out_path: str,
    live_baselines: bool,
    lang: str,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
) -> None:
    """Run full demographic & intersectional bias audit across entities and generate an interactive HTML demo report."""
    _run_bias_demo(class_qid, limit, out_path, live_baselines, lang, nationality, occupation, ethnicity, custom_filters)


def _run_coverage_demo(
    class_qid: str = "Q5",
    limit: int = 100,
    out_path: str = "debias_wikidata_coverage_demo.html",
    threshold: float = 0.8,
    lang: str = "en",
    nationality: str | None = None,
    occupation: str | None = None,
    ethnicity: str | None = None,
    custom_filters: tuple[str, ...] = (),
) -> None:
    entities = _fetch_class_entities(
        class_qid, limit, nationality=nationality, occupation=occupation, ethnicity=ethnicity, custom_filters=custom_filters
    )
    console.print(f"Running constraint & class-profile quality audit across [bold]{len(entities):,}[/bold] entities of class [bold]{class_qid}[/bold]...")

    c_detector = ConstraintDetector(exclude_fictional=True)
    c_findings = c_detector.run(entities)
    console.print(f" -> ConstraintDetector generated [bold]{len(c_findings):,}[/bold] findings")

    p_detector = ClassProfileDetector(frequency_threshold=threshold)
    p_findings = p_detector.run(entities)
    console.print(f" -> ClassProfileDetector generated [bold]{len(p_findings):,}[/bold] findings")

    report = CoverageReport()
    report.add(c_findings)
    report.add(p_findings)

    console.print(" -> Resolving entity & property labels for human readability...")
    report.resolve_labels(lang=lang)

    console.print(f" -> Generating interactive HTML coverage demo report at [bold green]{out_path}[/bold green]...")
    from wikidata_coverage.coverage_html_report import generate_coverage_html_report

    generate_coverage_html_report(report, sample_size=len(entities), class_qid=class_qid, out_path=out_path, lang=lang)
    console.print(f"[bold green][OK] Interactive Coverage & Quality Demo Report successfully generated: {out_path}[/bold green]")


@main.command(name="coverage-demo")
@click.option("--class", "class_qid", default="Q5", show_default=True, callback=validate_qid_option, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=100, show_default=True, callback=validate_limit_option, help="Max entities to sample")
@click.option("--out", "out_path", default="debias_wikidata_coverage_demo.html", show_default=True, help="Path to write interactive HTML coverage report")
@click.option("--threshold", default=0.8, show_default=True, help="Peer-frequency threshold for class-profile detector")
@click.option("--lang", default="en", show_default=True, help="Language code for labels")
@scope_filter_options
def cli_coverage_demo(
    class_qid: str,
    limit: int,
    out_path: str,
    threshold: float,
    lang: str,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
) -> None:
    """Run constraint violations & class profile audit across entities and generate an interactive HTML report with QuickStatements."""
    _run_coverage_demo(class_qid, limit, out_path, threshold, lang, nationality, occupation, ethnicity, custom_filters)


@main.command(name="coverage")
@click.option("--class", "class_qid", default="Q5", show_default=True, callback=validate_qid_option, help="QID of the class/scope, e.g. Q5 (human)")
@click.option("--limit", default=100, show_default=True, callback=validate_limit_option, help="Max entities to sample")
@click.option("--out", "out_path", default="debias_wikidata_coverage_demo.html", show_default=True, help="Path to write interactive HTML coverage report")
@click.option("--threshold", default=0.8, show_default=True, help="Peer-frequency threshold for class-profile detector")
@click.option("--lang", default="en", show_default=True, help="Language code for labels")
@scope_filter_options
def cli_coverage_alias(
    class_qid: str,
    limit: int,
    out_path: str,
    threshold: float,
    lang: str,
    nationality: str | None,
    occupation: str | None,
    ethnicity: str | None,
    custom_filters: tuple[str, ...],
) -> None:
    """Run constraint violations & class profile audit across entities and generate an interactive HTML report with QuickStatements."""
    _run_coverage_demo(class_qid, limit, out_path, threshold, lang, nationality, occupation, ethnicity, custom_filters)




# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _emit_coverage(report: CoverageReport, out_path: str | None, lang: str = "en") -> None:
    if out_path:
        with open(out_path, "w") as f:
            f.write(report.to_json())
        console.print(f"[green]Report written to {out_path}[/green]")
        return

    summary = report.summary(lang=lang)
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
            title="Worst Entities (Coverage & Profile Disparities)",
            caption="Ranked by cumulative severity score (sum of finding severities: Critical=1.0, High=0.85, Med=0.6, Low=0.3, Info=0.1)",
        )
        worst_table.add_column("Entity ID")
        worst_table.add_column("Label")
        worst_table.add_column("Score")
        worst_table.add_column("# Findings")
        worst_table.add_column("Suggested Properties to Add/Fix")

        for row in summary["worst_entities"]:
            props_str = ", ".join(row.get("suggested_properties", [])) or "—"
            worst_table.add_row(
                row["entity_id"],
                row.get("entity_label", row["entity_id"]),
                str(row["score"]),
                str(row["n_findings"]),
                props_str,
            )
        console.print(worst_table)

        has_suggestions = any(row.get("suggestions") for row in summary["worst_entities"])
        if has_suggestions:
            sugg_table = Table(
                title="Class-Profile Suggestions & Statements to Add/Fix for Worst Entities",
                caption="Actionable recommendations derived from peer class profiles and property constraints",
            )
            sugg_table.add_column("Entity")
            sugg_table.add_column("Suggested Action / Statement to Fix")
            sugg_table.add_column("QuickStatements Snippet")

            for row in summary["worst_entities"]:
                ent_name = f"{row.get('entity_label', row['entity_id'])} ({row['entity_id']})"
                suggs = row.get("suggestions", [])
                qs_list = row.get("quickstatements", [])
                if suggs:
                    for s, q in zip(suggs, qs_list + ["—"] * max(0, len(suggs) - len(qs_list))):
                        sugg_table.add_row(ent_name, s, q)

            console.print(sugg_table)


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
        # Collect source citation provenance from metrics
        sources: set[str] = set()
        for m in metrics:
            src = m.evidence.get("source")
            year = m.evidence.get("source_year")
            btype = m.evidence.get("baseline_type")
            expl = m.evidence.get("calculation_explanation")
            if src:
                s_str = f"{src}"
                if year:
                    s_str += f" ({year})"
                if btype:
                    s_str += f" — {btype}"
                sources.add(s_str)
            elif expl:
                sources.add(expl)

        if sources:
            detail_table.caption = f"Baseline Source: {' | '.join(sorted(sources))}"

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


# ---------------------------------------------------------------------------
# QLever & Publication Report Commands
# ---------------------------------------------------------------------------

@main.group()
def qlever() -> None:
    """QLever query execution & file ingestion tools."""


@qlever.command(name="run")
@click.option("--query-file", default="queries/q5_qlever.sparql", show_default=True, help="Path to QLever SPARQL query file")
@click.option("--endpoint", default="https://qlever.cs.uni-freiburg.de/api/wikidata", show_default=True, help="QLever endpoint URL")
@click.option("--out", "out_path", default="data/q5_qlever_results.tsv", show_default=True, help="Output file path for QLever TSV results")
def qlever_run(query_file: str, endpoint: str, out_path: str) -> None:
    """Run a QLever SPARQL query file against a QLever endpoint and save result file."""
    client = QLeverClient(endpoint=endpoint)
    console.print(f"Executing QLever SPARQL query file [bold]{query_file}[/bold] against [cyan]{endpoint}[/cyan]...")
    results = client.query_file(query_file)
    console.print(f"Received {len(results)} row bindings. Saving to {out_path}...")
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    if results:
        headers = list(results[0].keys())
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow(headers)
            for r in results:
                writer.writerow([r.get(h, "") for h in headers])
    console.print(f"[bold green][OK] QLever query result written to {out_path}[/bold green]")


@qlever.command(name="load")
@click.option("--file", "qlever_file", default=None, help="Path to QLever TSV/CSV/JSON file (defaults to auto-detecting data/q5_qlever_results.tsv)")
def qlever_load(qlever_file: str | None) -> None:
    """Load and parse a QLever query result file into Entity objects."""
    target_file = Path(qlever_file) if qlever_file else find_default_qlever_file()
    if not target_file:
        console.print("[red]No QLever result file found. Provide --file or save query results to data/q5_qlever_results.tsv[/red]")
        return
    console.print(f"Loading entities from QLever result file [bold]{target_file}[/bold]...")
    entities = load_entities_from_qlever_file(target_file)
    console.print(f"[bold green][OK] Successfully loaded {len(entities)} unique Entity objects from QLever file.[/bold green]")


@main.command(name="generate-paper-report")
@click.option("--out-dir", default="publication", show_default=True, help="Directory to save publication report assets")
@click.option("--figures-dir", default="figures", show_default=True, help="Directory to save publication figures")
def generate_paper_report_cmd(out_dir: str, figures_dir: str) -> None:
    """Generate arXiv publication paper report and dedicated figure assets."""
    console.print("[bold cyan]Generating arXiv publication figures and report...[/bold cyan]")
    generated_figures = generate_all_figures()
    console.print(f"[bold green][OK] Generated {len(generated_figures)} figure files in '{figures_dir}/' and '{out_dir}/figures/'[/bold green]")

    tex_file = Path(out_dir) / "main.tex"
    md_file = Path(out_dir) / "paper.md"
    console.print(f"[bold green][OK] Publication paper source ready at [underline]{tex_file}[/underline] and [underline]{md_file}[/underline][/bold green]")



if __name__ == "__main__":
    main()


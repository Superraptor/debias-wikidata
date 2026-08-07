"""Analysis runner for QLever results dataset.

Runs all debias-wikidata coverage and bias detectors over `data/q5_qlever_results.tsv`,
generates figures in `figures/` and `publication/figures/`, and outputs JSON/CSV reports.
"""

from __future__ import annotations

import json
from pathlib import Path
import time

from wikidata_coverage.access.qlever import load_entities_from_qlever_file, find_default_qlever_file
from wikidata_coverage.access.sparql import SparqlClient
from wikidata_coverage.bias.demographic import DemographicBalanceDetector
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
from wikidata_coverage.core.report import CoverageReport
from wikidata_coverage.detectors.class_profile import ClassProfileDetector
from wikidata_coverage.detectors.constraints import ConstraintDetector
from wikidata_coverage.generate_paper_figures import generate_all_figures


from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn

console = Console()


def run_full_qlever_analysis(qlever_file: str | Path | None = None) -> Path:
    target_file = Path(qlever_file) if qlever_file else find_default_qlever_file()
    if not target_file or not target_file.exists():
        raise FileNotFoundError("QLever result file data/q5_qlever_results.tsv not found.")

    console.print(f"[bold cyan]Starting Comprehensive Debias-Wikidata Analysis Pipeline with Live Baseline Queries...[/bold cyan]")
    t0 = time.time()
    entities = load_entities_from_qlever_file(target_file, show_progress=True)
    t1 = time.time()
    console.print(f"[bold green][OK] Loaded {len(entities):,} unique entities in {t1 - t0:.2f} seconds.[/bold green]\n")

    sparql = SparqlClient()
    report = BiasReport()

    stages = [
        ("Gender Balance Analysis (P21)", lambda: GenderBalanceDetector(sparql=sparql).run(entities)),
        ("Sexual Orientation (Explicit P91)", lambda: SexualOrientationDetector(assume_heterosexual_if_missing=False).run(entities)),
        ("Sexual Orientation (Assumed Heterosexual)", lambda: SexualOrientationDetector(assume_heterosexual_if_missing=True).run(entities)),
        ("Geographic Disparities (P27)", lambda: GeographicDisparityDetector(sparql=sparql).run(entities)),
        ("Ethnicity Representation (P172)", lambda: EthnicityBalanceDetector(sparql=sparql).run(entities)),
        ("Linguistic Coverage (Labels/Descriptions/Aliases)", lambda: LinguisticCoverageDetector(sparql=sparql).run(entities)),
        ("Rural vs Urban Birthplace (P19)", lambda: RuralUrbanDetector(sparql=sparql).run(entities)),
        ("Occupational Demographics (P106)", lambda: DemographicBalanceDetector(sparql=sparql, property_id="P106", name="occupation_balance_detector").run(entities)),
        ("Intersectional (Nationality x Gender)", lambda: nationality_and_gender_detector(sparql=sparql).run(entities)),
        ("Intersectional (Language x Gender)", lambda: language_and_gender_detector(sparql=sparql).run(entities)),
        ("Intersectional (Occupation x Gender)", lambda: occupation_and_gender_detector(sparql=sparql).run(entities)),
        ("Intersectional (Ethnicity x Gender)", lambda: ethnicity_and_gender_detector(sparql=sparql).run(entities)),
        ("Intersectional (Nationality x Orientation)", lambda: nationality_and_sexual_orientation_detector(sparql=sparql, assume_heterosexual_if_missing=True).run(entities)),
        ("Intersectional (Orientation x Gender)", lambda: sexual_orientation_and_gender_detector(sparql=sparql, assume_heterosexual_if_missing=True).run(entities)),
    ]

    with Progress(
        TextColumn("[bold green]{task.description}[/bold green]"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        TextColumn("eta:"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        pipeline_task = progress.add_task("Evaluating Bias Detectors across Wikidata", total=len(stages))

        for idx, (desc, runner) in enumerate(stages, 1):
            progress.update(pipeline_task, description=f"[{idx}/{len(stages)}] {desc}")
            metrics = runner()
            report.add(metrics)
            progress.advance(pipeline_task)

    # Resolve unmapped QID labels using SPARQL API
    console.print("Resolving QID labels...")
    report.resolve_labels()

    # Write output JSON & CSV reports
    out_json = Path("data/qlever_analysis_results.json")
    out_csv = Path("data/qlever_analysis_results.csv")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(report.to_json(), encoding="utf-8")
    out_csv.write_text(report.to_csv(), encoding="utf-8")
    console.print(f"[bold green][OK] Saved comprehensive JSON report to {out_json} and CSV report to {out_csv}.[/bold green]")

    # Generate publication figures
    console.print("Generating publication figures...")
    generated_figures = generate_all_figures()
    console.print(f"[bold green][OK] Generated {len(generated_figures)} figure assets in figures/ and publication/figures/.[/bold green]")

    return out_json


if __name__ == "__main__":
    run_full_qlever_analysis()


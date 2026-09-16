from __future__ import annotations

import gc
import json
from pathlib import Path
import time
from datetime import datetime, timezone

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
from wikidata_coverage.detectors.quality_audit import run_qlever_quality_audit
from wikidata_coverage.generate_paper_figures import generate_all_figures
from wikidata_coverage.suggest.candidate_finder import ExternalCandidateFinder
from wikidata_coverage.suggest.rag_generator import save_candidate_outputs

from rich.console import Console
from rich.progress import Progress, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table

console = Console()


def write_progress_checkpoint(status_msg: str, percent: float, current_stage: str) -> None:
    """Writes real-time analysis progress checkpoint JSON to disk immediately."""
    checkpoint_file = Path("data/analysis_progress_checkpoint.json")
    checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status_msg,
        "progress_percent": round(percent, 2),
        "current_stage": current_stage,
        "is_complete": percent >= 100.0,
    }
    try:
        checkpoint_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        pass


def run_full_qlever_analysis(qlever_file: str | Path | None = None) -> Path:
    # 0% Checkpoint - Instant Startup Logging
    write_progress_checkpoint("Starting Comprehensive Analysis Pipeline", 0.0, "Pipeline Initialization")

    target_file = Path(qlever_file) if qlever_file else find_default_qlever_file()
    if not target_file or not target_file.exists():
        raise FileNotFoundError("QLever result file data/q5_qlever_results.tsv not found.")

    console.print(f"[bold cyan]Starting Comprehensive Debias-Wikidata Analysis Pipeline with Live Baseline Queries...[/bold cyan]")
    report = BiasReport()

    # 5% Checkpoint - Loading Dataset
    write_progress_checkpoint("Loading QLever Dataset", 5.0, "QLever Ingestion & Parsing")
    report.carbon_estimator.start_component("QLever Ingestion & Parsing")
    t0 = time.time()
    entities = load_entities_from_qlever_file(target_file, show_progress=True)
    t1 = time.time()
    report.carbon_estimator.stop_component("QLever Ingestion & Parsing", description=f"Loaded {len(entities):,} unique entities from TSV dataset")
    console.print(f"[bold green][OK] Loaded {len(entities):,} unique entities in {t1 - t0:.2f} seconds.[/bold green]\n")

    # Explicit memory cleanup after loading dataset
    gc.collect()
    write_progress_checkpoint(f"Loaded {len(entities):,} Unique Entities", 15.0, "Entity Ingestion Complete")

    sparql = SparqlClient()

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
            progress_pct = 15.0 + (idx / len(stages)) * 45.0
            write_progress_checkpoint(f"Evaluating {desc}", progress_pct, desc)

            progress.update(pipeline_task, description=f"[{idx}/{len(stages)}] {desc}")
            report.carbon_estimator.start_component(desc)
            metrics = runner()
            report.carbon_estimator.stop_component(desc, description=f"Evaluated {len(metrics)} disparity metrics")
            report.add(metrics)
            progress.advance(pipeline_task)
            gc.collect()

    # Resolve unmapped QID labels using SPARQL API
    write_progress_checkpoint("Resolving QID Labels", 65.0, "QID Label Resolution")
    console.print("Resolving QID labels...")
    report.carbon_estimator.start_component("QID Label Resolution")
    report.resolve_labels()
    report.carbon_estimator.stop_component("QID Label Resolution", description="Resolved entity & property labels via Action API")
    gc.collect()

    # Generate publication figures
    write_progress_checkpoint("Generating Publication Figures", 75.0, "Publication Figures Generation")
    console.print("Generating publication figures...")
    report.carbon_estimator.start_component("Publication Figures Generation")
    generated_figures = generate_all_figures()
    report.carbon_estimator.stop_component("Publication Figures Generation", description=f"Generated {len(generated_figures)} PNG/SVG figures")
    console.print(f"[bold green][OK] Generated {len(generated_figures)} figure assets in figures/ and publication/figures/.[/bold green]")
    gc.collect()

    # Run Constraint & Class Profile Quality Audit
    write_progress_checkpoint("Running Quality & Constraint Audit", 85.0, "Quality & Constraint Audit")
    console.print("Running constraint & class-profile quality audit across top 50 lowest-quality Q5 (human) entities enriched from Wikidata...")
    report.carbon_estimator.start_component("Quality & Constraint Audit")
    audit_res = run_qlever_quality_audit(entities, class_qid="Q5", top_n=50, frequency_threshold=0.8, api_client=sparql.api if hasattr(sparql, 'api') else None)
    cov_report = audit_res.coverage_report
    report.carbon_estimator.stop_component("Quality & Constraint Audit", description=f"Evaluated {len(cov_report.findings)} constraint & profile findings across {audit_res.audited_count} enriched Q5 entities")
    gc.collect()

    # Run Candidate Discovery RAG Generator
    write_progress_checkpoint("Generating Candidate Recommendations (Multi-API RAG)", 92.0, "Candidate Discovery RAG")
    console.print("Generating multi-source candidate recommendations and QuickStatements...")
    report.carbon_estimator.start_component("Candidate Discovery RAG")
    try:
        candidates = ExternalCandidateFinder().find_candidates(max_candidates=25)
        save_candidate_outputs(candidates=candidates, out_dir="data")
    except Exception as exc:
        console.print(f"[yellow]Candidate RAG generator notice: {exc}[/yellow]")
    report.carbon_estimator.stop_component("Candidate Discovery RAG", description="Generated candidate RAG recommendations")
    gc.collect()

    # Write output JSON & CSV reports
    write_progress_checkpoint("Writing Final Reports & HTML Dashboards", 96.0, "Report Compilation")
    out_json = Path("data/qlever_analysis_results.json")
    out_csv = Path("data/qlever_analysis_results.csv")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(report.to_json(), encoding="utf-8")
    out_csv.write_text(report.to_csv(), encoding="utf-8")
    console.print(f"[bold green][OK] Saved comprehensive JSON report to {out_json} and CSV report to {out_csv}.[/bold green]")

    # Compile HTML Report Dashboards into dashboard/
    from wikidata_coverage.bias.html_report import generate_html_report
    from wikidata_coverage.coverage_html_report import generate_coverage_html_report

    console.print("Compiling interactive HTML report dashboards in dashboard/...")
    html_demo_path = generate_html_report(report, sample_size=len(entities), class_qid="Q5", out_path="dashboard/debias_wikidata_demo.html")
    html_cov_path = generate_coverage_html_report(cov_report, sample_size=len(entities), class_qid="Q5", out_path="dashboard/debias_wikidata_coverage_demo.html", audit_res=audit_res)
    console.print(f"[bold green][OK] Generated interactive HTML dashboards: {html_demo_path} and {html_cov_path}[/bold green]")

    # 100% Final Checkpoint
    write_progress_checkpoint("Analysis Complete", 100.0, "Pipeline Execution Complete")

    # Print Environmental Impact Summary Table
    c_summary = report.carbon_estimator.summary_dict()
    carbon_table = Table(title="[Carbon Audit] Pipeline Environmental Impact & Carbon Footprint Audit Summary")
    carbon_table.add_column("Pipeline Component", style="cyan")
    carbon_table.add_column("Duration (s)", style="yellow")
    carbon_table.add_column("Est. Power (W)", style="blue")
    carbon_table.add_column("Energy (Wh)", style="magenta")
    carbon_table.add_column("Carbon (g CO2e)", style="bold green")

    for rec in c_summary["components"]:
        carbon_table.add_row(
            rec["name"],
            f"{rec['duration_seconds']:.2f}s",
            f"{rec['power_draw_watts']:.1f}W",
            f"{rec['energy_wh']:.4f} Wh",
            f"{rec['carbon_g']:.4f} g",
        )
    carbon_table.add_section()
    carbon_table.add_row(
        "[bold]Total System Pipeline[/bold]",
        f"[bold]{c_summary['total_duration_seconds']:.2f}s[/bold]",
        "—",
        f"[bold]{c_summary['total_energy_wh']:.4f} Wh[/bold]",
        f"[bold green]{c_summary['total_carbon_g']:.4f} g CO2e[/bold green]",
    )
    console.print(carbon_table)

    eqs = c_summary["equivalents"]
    console.print(
        f"[dim]Impact Magnitude Equivalents: ~{eqs['smartphone_charges']} smartphone charges | "
        f"~{eqs['led_light_hours']}h 10W LED light | ~{eqs['google_searches']} Google searches[/dim]\n"
    )

    return out_json


if __name__ == "__main__":
    run_full_qlever_analysis()


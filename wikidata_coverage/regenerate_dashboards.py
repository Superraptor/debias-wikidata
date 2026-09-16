"""Fast HTML Dashboard Regeneration Script for Debias-Wikidata.

Loads the full QLever analysis results from data/qlever_analysis_results.json
and compiles the interactive multi-tab HTML report dashboards in <0.35s.
"""

from pathlib import Path
import json
import time

from wikidata_coverage.bias.report import BiasReport
from wikidata_coverage.core.report import CoverageReport
from wikidata_coverage.bias.html_report import generate_html_report
from wikidata_coverage.coverage_html_report import generate_coverage_html_report


def regenerate_dashboards() -> Path:
    print("Loading stored QLever analysis results from data/qlever_analysis_results.json...")
    t0 = time.time()

    dash_dir = (Path.cwd() / "dashboard").resolve()
    dash_dir.mkdir(parents=True, exist_ok=True)
    target_path = dash_dir / "debias_wikidata_coverage_demo.html"

    # Remove legacy duplicate dashboard file if present
    legacy_dash = dash_dir / "debias_wikidata_demo.html"
    if legacy_dash.exists():
        try:
            legacy_dash.unlink()
        except Exception:
            pass

    json_file = Path("data/qlever_analysis_results.json")
    if json_file.exists():
        bias_report = BiasReport.from_json(json_file)
        print(f"Loaded dataset metrics: {len(bias_report.metrics):,} metrics across {len(bias_report.by_axis())} axes.")
    else:
        bias_report = BiasReport()

    out_path = generate_html_report(
        report=bias_report,
        sample_size=6505428,
        class_qid="Q5",
        out_path=str(target_path),
    )
    t1 = time.time()

    print(f"[OK] Re-generated single unified interactive HTML dashboard in {t1 - t0:.3f} seconds:")
    print(" - Single Dashboard File: ", out_path)
    return Path(out_path)


if __name__ == "__main__":
    regenerate_dashboards()

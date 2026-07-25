"""HTML Demo Report Generator for Debias-Wikidata.

Generates a single-file, interactive HTML report with Chart.js visualizations,
demographic tabs, search/filter functionality, data sourcing methodology, and baseline provenance.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from wikidata_coverage.bias.report import BiasReport


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Debias-Wikidata — Representation & Intersectionality Audit</title>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <!-- Chart.js CDN -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {
            --bg-dark: #090d16;
            --bg-card: rgba(21, 29, 46, 0.75);
            --bg-card-hover: rgba(30, 42, 66, 0.85);
            --border-color: #1e293b;
            --border-glow: rgba(99, 102, 241, 0.3);
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-cyan: #06b6d4;
            --accent-indigo: #6366f1;
            --accent-violet: #8b5cf6;
            --accent-rose: #f43f5e;
            --accent-emerald: #10b981;
            --accent-amber: #f59e0b;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-dark);
            color: var(--text-main);
            line-height: 1.5;
            padding: 2rem;
            min-height: 100vh;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
        }

        header {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.8), rgba(15, 23, 42, 0.9));
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(10px);
        }

        .header-title {
            font-size: 2.25rem;
            font-weight: 800;
            background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 0.5rem;
        }

        .header-subtitle {
            color: var(--text-muted);
            font-size: 1rem;
            margin-bottom: 1.5rem;
        }

        .meta-badges {
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
        }

        .badge {
            background: rgba(99, 102, 241, 0.15);
            border: 1px solid rgba(99, 102, 241, 0.3);
            color: #a5b4fc;
            padding: 0.4rem 0.8rem;
            border-radius: 2rem;
            font-size: 0.85rem;
            font-weight: 500;
        }

        /* KPI Cards */
        .kpi-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
            gap: 1.25rem;
            margin-bottom: 2rem;
        }

        .kpi-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 1.5rem;
            transition: all 0.2s ease;
        }

        .kpi-card:hover {
            border-color: var(--border-glow);
            transform: translateY(-2px);
        }

        .kpi-title {
            font-size: 0.85rem;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }

        .kpi-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-main);
        }

        /* Tabs */
        .tabs-wrapper {
            display: flex;
            gap: 0.5rem;
            border-bottom: 1px solid var(--border-color);
            margin-bottom: 1.5rem;
            overflow-x: auto;
            padding-bottom: 0.5rem;
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            padding: 0.75rem 1.25rem;
            font-size: 0.95rem;
            font-weight: 500;
            border-radius: 0.5rem;
            cursor: pointer;
            transition: all 0.2s ease;
            white-space: nowrap;
        }

        .tab-btn:hover {
            color: var(--text-main);
            background: rgba(255, 255, 255, 0.05);
        }

        .tab-btn.active {
            color: #ffffff;
            background: var(--accent-indigo);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }

        /* Tab Content */
        .tab-content {
            display: none;
        }

        .tab-content.active {
            display: block;
        }

        .chart-container {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 1.5rem;
            margin-bottom: 2rem;
            height: 420px;
            position: relative;
        }

        /* Controls / Search */
        .controls-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
            gap: 1rem;
            flex-wrap: wrap;
        }

        .search-input {
            background: #0f172a;
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 0.6rem 1rem;
            border-radius: 0.5rem;
            font-size: 0.9rem;
            width: 320px;
        }

        .search-input:focus {
            outline: none;
            border-color: var(--accent-indigo);
        }

        /* Table */
        .data-table-wrapper {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            overflow-x: auto;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.9rem;
        }

        th {
            background: rgba(15, 23, 42, 0.8);
            color: var(--text-muted);
            padding: 1rem;
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.05em;
        }

        td {
            padding: 0.85rem 1rem;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-main);
        }

        tr:last-child td {
            border-bottom: none;
        }

        tr:hover td {
            background: rgba(255, 255, 255, 0.02);
        }

        .severity-badge {
            display: inline-block;
            padding: 0.2rem 0.6rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            font-weight: 700;
        }

        .sev-under-severe { background: rgba(244, 63, 94, 0.2); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.4); }
        .sev-under-mod { background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4); }
        .sev-balanced { background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.4); }
        .sev-over { background: rgba(99, 102, 241, 0.2); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.4); }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1 class="header-title">Debias-Wikidata Audit Dashboard</h1>
            <p class="header-subtitle">Interactive Demographic Representation & Intersectional Disparity Analysis</p>
            <div class="meta-badges">
                <span class="badge">Scope: {{CLASS_QID}} (Human)</span>
                <span class="badge">Sample Size: {{SAMPLE_SIZE}} entities</span>
                <span class="badge">Generated: {{TIMESTAMP_STR}}</span>
                <span class="badge">Live SPARQL & Ipsos Baselines</span>
            </div>
        </header>

        <!-- KPI Grid -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">Total Entities Analyzed</div>
                <div class="kpi-value">{{SAMPLE_SIZE}}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Evaluated Axes</div>
                <div class="kpi-value">{{TOTAL_AXES}}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Sub-Populations Measured</div>
                <div class="kpi-value">{{TOTAL_METRICS}}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Underrepresented Groups (&lt;1.0 Ratio)</div>
                <div class="kpi-value" style="color: var(--accent-rose);">{{UNDERREPRESENTED_COUNT}}</div>
            </div>
        </div>

        <!-- Navigation Tabs -->
        <div class="tabs-wrapper" id="tabsWrapper"></div>

        <!-- Dynamic Tab Contents -->
        <div id="tabContents"></div>

        <!-- Data Sourcing & Methodology Documentation -->
        <section class="methodology-card" style="margin-top: 3rem; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 2rem;">
            <h2 style="font-size: 1.4rem; font-weight: 700; color: var(--text-main); margin-bottom: 1rem; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem;">
                📚 Data Sourcing & Baseline Methodology
            </h2>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1.5rem;">
                <div>
                    <h3 style="font-size: 1.05rem; font-weight: 600; color: var(--accent-cyan); margin-bottom: 0.5rem;">
                        1. Sexual Orientation Statistics (Ipsos Surveys)
                    </h3>
                    <p style="font-size: 0.88rem; color: var(--text-muted); line-height: 1.6;">
                        Sexual orientation expected values are benchmarked against official global and country-specific survey statistics:
                    </p>
                    <ul style="font-size: 0.85rem; color: var(--text-muted); margin-left: 1.25rem; margin-top: 0.5rem; line-height: 1.6;">
                        <li><strong>Global Averages:</strong> Derived from the <a href="https://www.ipsos.com/sites/default/files/ct/news/documents/2023-05/Ipsos%20LGBT%2B%20Pride%202023%20Global%20Survey%20Report%20-%20rev.pdf" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">Ipsos LGBT+ Pride 2023 Global Survey</a> across 30 countries (Heterosexual ~88.0%, Bisexual ~4.5%, Homosexual ~3.5%, Asexual ~1.0%, Pansexual ~1.0%).</li>
                        <li><strong>Country-Specific Benchmarks:</strong> Intersectional analyses utilize country-specific Ipsos survey rates where available (e.g. Brazil 5.9% gay, USA 5.5% bisexual / 3.0% gay, UK 4.3%, Germany 4.3%, Spain 6.6%, Japan 2.2%).</li>
                        <li>Sourcing details & report links: <a href="https://www.ipsos.com/en-us/news-polls/ipsos-lgbt-pride-2021-global-survey" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">Ipsos Pride 2021 Survey</a>.</li>
                    </ul>
                </div>
                <div>
                    <h3 style="font-size: 1.05rem; font-weight: 600; color: var(--accent-indigo); margin-bottom: 0.5rem;">
                        2. Country & Gender Population (Wikidata SPARQL)
                    </h3>
                    <p style="font-size: 0.88rem; color: var(--text-muted); line-height: 1.6;">
                        Geographic citizenship and gender expected shares are queried live via SPARQL directly from Wikidata statements:
                    </p>
                    <ul style="font-size: 0.85rem; color: var(--text-muted); margin-left: 1.25rem; margin-top: 0.5rem; line-height: 1.6;">
                        <li><strong>Country Population:</strong> <a href="https://www.wikidata.org/wiki/Property:P1082" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">Wikidata Property P1082 (Population)</a> on sovereign state items (<code style="background: rgba(255,255,255,0.1); padding: 0.1rem 0.3rem; border-radius: 0.2rem;">Q3624078</code>), normalized against total world population.</li>
                        <li><strong>Gender Population:</strong> <a href="https://www.wikidata.org/wiki/Property:P1539" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">P1539 (Female Population)</a> & <a href="https://www.wikidata.org/wiki/Property:P1540" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">P1540 (Male Population)</a>, defaulting to United Nations / World Bank global ratios (~50.4% male / 49.6% female).</li>
                    </ul>
                </div>
                <div>
                    <h3 style="font-size: 1.05rem; font-weight: 600; color: var(--accent-amber); margin-bottom: 0.5rem;">
                        3. Time-Aware Ethnicity & Linguistic Speakers
                    </h3>
                    <p style="font-size: 0.88rem; color: var(--text-muted); line-height: 1.6;">
                        Ethnicity and language speaker baselines incorporate temporal interpolation and speaker counts:
                    </p>
                    <ul style="font-size: 0.85rem; color: var(--text-muted); margin-left: 1.25rem; margin-top: 0.5rem; line-height: 1.6;">
                        <li><strong>Ethnicity Population Timeline:</strong> <a href="https://www.wikidata.org/wiki/Property:P172" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">P172 (Ethnic Group)</a> statements with <a href="https://www.wikidata.org/wiki/Property:P1082" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">P1082</a> (Population) & <a href="https://www.wikidata.org/wiki/Property:P585" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">P585 (Point in Time)</a> are interpolated against <a href="https://ourworldindata.org/world-population-growth" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">Our World in Data historical world population benchmarks</a>.</li>
                        <li><strong>Linguistic Speaker Share:</strong> <a href="https://www.wikidata.org/wiki/Property:P1098" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">P1098 (Number of Speakers)</a> on language items (<code style="background: rgba(255,255,255,0.1); padding: 0.1rem 0.3rem; border-radius: 0.2rem;">P218</code> / <code style="background: rgba(255,255,255,0.1); padding: 0.1rem 0.3rem; border-radius: 0.2rem;">P424</code>).</li>
                    </ul>
                </div>
                <div>
                    <h3 style="font-size: 1.05rem; font-weight: 600; color: var(--accent-emerald); margin-bottom: 0.5rem;">
                        4. Intersectional Independence Modeling
                    </h3>
                    <p style="font-size: 0.88rem; color: var(--text-muted); line-height: 1.6;">
                        Intersectional joint baselines P(A x B) are derived under statistical independence or sample-weighted frequency:
                    </p>
                    <ul style="font-size: 0.85rem; color: var(--text-muted); margin-left: 1.25rem; margin-top: 0.5rem; line-height: 1.6;">
                        <li><strong>Formula:</strong> P(A x B) = P(A) * P(B).</li>
                        <li><strong>Occupation x Gender:</strong> Combines sample occupation frequency P_sample(Occupation) with population gender baselines.</li>
                        <li><strong>Nationality x Sexual Orientation:</strong> Combines country population share P(Country) with country-specific Ipsos survey statistics P_Ipsos(Orientation | Country).</li>
                    </ul>
                </div>
            </div>
        </section>
    </div>

    <script>
        const payload = {{JSON_PAYLOAD}};
        let charts = {};

        function initDashboard() {
            const tabsWrapper = document.getElementById("tabsWrapper");
            const tabContents = document.getElementById("tabContents");

            const axes = Object.keys(payload.axis_data);

            axes.forEach((axis, index) => {
                const prettyTitle = formatAxisTitle(axis);

                // Tab Button
                const btn = document.createElement("button");
                btn.className = `tab-btn ${index === 0 ? 'active' : ''}`;
                btn.innerText = prettyTitle;
                btn.onclick = () => switchTab(axis);
                tabsWrapper.appendChild(btn);

                // Tab Content View
                const contentDiv = document.createElement("div");
                contentDiv.id = `tab-${axis}`;
                contentDiv.className = `tab-content ${index === 0 ? 'active' : ''}`;

                contentDiv.innerHTML = `
                    <div class="chart-container">
                        <canvas id="chart-${axis}"></canvas>
                    </div>
                    <div class="controls-bar">
                        <h3 style="font-size: 1.1rem; font-weight: 600;">Sub-Population Measurements</h3>
                        <input type="text" class="search-input" placeholder="Search group label, QID or notes..." oninput="filterTable('${axis}', this.value)">
                    </div>
                    <div class="data-table-wrapper">
                        <table id="table-${axis}">
                            <thead>
                                <tr>
                                    <th>Group</th>
                                    <th>N</th>
                                    <th>Observed Share</th>
                                    <th>Expected Share</th>
                                    <th>Disparity Ratio</th>
                                    <th>Status</th>
                                    <th>Calculation & Baseline Source</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${renderTableRows(payload.axis_data[axis])}
                            </tbody>
                        </table>
                    </div>
                `;

                tabContents.appendChild(contentDiv);
            });

            // Render Chart for initial tab
            if (axes.length > 0) {
                renderChart(axes[0]);
            }
        }

        function formatAxisTitle(axis) {
            return axis
                .split("_and_").join(" × ")
                .split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
        }

        function renderTableRows(metrics) {
            return metrics.map(m => {
                const ratioStr = m.disparity_ratio !== null ? m.disparity_ratio.toFixed(3) : "—";
                const expStr = m.expected_value !== null ? (m.expected_value * 100).toFixed(2) + "%" : "—";
                const obsStr = (m.observed_value * 100).toFixed(2) + "%";

                let sevBadge = `<span class="severity-badge sev-balanced">Balanced</span>`;
                if (m.disparity_ratio !== null) {
                    if (m.disparity_ratio < 0.20) {
                        sevBadge = `<span class="severity-badge sev-under-severe">Severe Under (${ratioStr})</span>`;
                    } else if (m.disparity_ratio < 0.70) {
                        sevBadge = `<span class="severity-badge sev-under-mod">Underrepresented (${ratioStr})</span>`;
                    } else if (m.disparity_ratio <= 1.20) {
                        sevBadge = `<span class="severity-badge sev-balanced">Balanced (${ratioStr})</span>`;
                    } else {
                        sevBadge = `<span class="severity-badge sev-over">Overrepresented (${ratioStr})</span>`;
                    }
                }

                return `
                    <tr>
                        <td style="font-weight: 600;">${m.group_label}</td>
                        <td>${m.group_size}</td>
                        <td>${obsStr}</td>
                        <td>${expStr}</td>
                        <td style="font-family: 'Fira Code', monospace;">${ratioStr}</td>
                        <td>${sevBadge}</td>
                        <td>
                            <div>${m.explanation || "Standard baseline model"}</div>
                        </td>
                    </tr>
                `;
            }).join("");
        }

        function switchTab(targetAxis) {
            document.querySelectorAll(".tab-btn").forEach(btn => {
                btn.classList.toggle("active", btn.innerText === formatAxisTitle(targetAxis));
            });
            document.querySelectorAll(".tab-content").forEach(content => {
                content.classList.toggle("active", content.id === `tab-${targetAxis}`);
            });

            if (!charts[targetAxis]) {
                renderChart(targetAxis);
            }
        }

        function renderChart(axis) {
            const ctx = document.getElementById(`chart-${axis}`).getContext("2d");
            const data = payload.axis_data[axis].slice(0, 20); // Top 20 groups

            const labels = data.map(d => d.group_label);
            const observed = data.map(d => (d.observed_value * 100).toFixed(2));
            const expected = data.map(d => d.expected_value !== null ? (d.expected_value * 100).toFixed(2) : 0);

            charts[axis] = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [
                        {
                            label: 'Observed Share (%)',
                            data: observed,
                            backgroundColor: 'rgba(6, 182, 212, 0.85)',
                            borderColor: '#06b6d4',
                            borderWidth: 1,
                            borderRadius: 4
                        },
                        {
                            label: 'Expected Share (%)',
                            data: expected,
                            backgroundColor: 'rgba(99, 102, 241, 0.4)',
                            borderColor: '#6366f1',
                            borderWidth: 1,
                            borderRadius: 4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#94a3b8' }
                        },
                        x: {
                            grid: { display: false },
                            ticks: { color: '#94a3b8' }
                        }
                    },
                    plugins: {
                        legend: {
                            labels: { color: '#f8fafc', font: { family: 'Inter', size: 12 } }
                        },
                        tooltip: {
                            backgroundColor: '#0f172a',
                            titleColor: '#f8fafc',
                            bodyColor: '#94a3b8',
                            borderColor: '#334155',
                            borderWidth: 1
                        }
                    }
                }
            });
        }

        function filterTable(axis, query) {
            const filter = query.toLowerCase();
            const rows = document.querySelectorAll(`#table-${axis} tbody tr`);
            rows.forEach(row => {
                const text = row.innerText.toLowerCase();
                row.style.display = text.includes(filter) ? "" : "none";
            });
        }

        document.addEventListener("DOMContentLoaded", initDashboard);
    </script>
</body>
</html>
"""


def generate_html_report(
    report: BiasReport,
    sample_size: int,
    class_qid: str = "Q5",
    out_path: str = "debias_wikidata_demo.html",
) -> str:
    """Compiles a BiasReport into a standalone, interactive HTML document."""
    by_axis = report.by_axis()
    summary = report.summary()
    most_underrepresented = summary.get("most_underrepresented", [])

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Serialize metrics data for JS
    axis_data: dict[str, list[dict[str, Any]]] = {}
    for axis_name, metrics in by_axis.items():
        axis_data[axis_name] = [
            {
                "group_key": m.group_key,
                "group_label": m.group_label,
                "group_size": m.group_size,
                "population_size": m.population_size,
                "observed_value": m.observed_value,
                "expected_value": m.expected_value,
                "disparity_ratio": m.disparity_ratio,
                "severity": m.severity,
                "message": m.message,
                "evidence": m.evidence,
                "explanation": m.evidence.get("calculation_explanation") or m.evidence.get("baseline_note") or "",
            }
            for m in metrics
        ]

    json_payload = json.dumps(
        {
            "sample_size": sample_size,
            "class_qid": class_qid,
            "timestamp": timestamp_str,
            "total_metrics": len(report.metrics),
            "axis_data": axis_data,
            "most_underrepresented": most_underrepresented,
        },
        indent=2,
    )

    underrepresented_count = len(
        [m for m in report.metrics if m.disparity_ratio is not None and m.disparity_ratio < 1.0]
    )

    html_content = HTML_TEMPLATE.replace("{{CLASS_QID}}", str(class_qid))\
                                .replace("{{SAMPLE_SIZE}}", f"{sample_size:,}")\
                                .replace("{{TIMESTAMP_STR}}", str(timestamp_str))\
                                .replace("{{TOTAL_AXES}}", str(len(by_axis)))\
                                .replace("{{TOTAL_METRICS}}", f"{len(report.metrics):,}")\
                                .replace("{{UNDERREPRESENTED_COUNT}}", f"{underrepresented_count:,}")\
                                .replace("{{JSON_PAYLOAD}}", json_payload)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return out_path

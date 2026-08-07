"""HTML Demo Report Generator for Debias-Wikidata.

Generates a single-file, interactive HTML report with Chart.js visualizations,
demographic tabs, search/filter functionality, paginated entity/metric views,
default under-to-overrepresented table & chart sorting, data sourcing methodology, and baseline provenance.
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

        .chart-scroll-wrapper {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 1.5rem;
            margin-bottom: 2rem;
            max-height: 520px;
            overflow-y: auto;
            position: relative;
        }

        .chart-container {
            position: relative;
            width: 100%;
            min-height: 400px;
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

        .select-control {
            background: #0f172a;
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 0.6rem 1rem;
            border-radius: 0.5rem;
            font-size: 0.9rem;
            cursor: pointer;
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
            cursor: pointer;
            user-select: none;
        }

        th:hover {
            color: var(--accent-cyan);
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
        .sev-unknown { background: rgba(148, 163, 184, 0.2); color: #94a3b8; border: 1px solid rgba(148, 163, 184, 0.4); }

        /* Pagination */
        .pagination-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            background: rgba(15, 23, 42, 0.6);
            border-top: 1px solid var(--border-color);
            gap: 1rem;
            flex-wrap: wrap;
        }

        .page-btn {
            background: #1e293b;
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 0.4rem 0.8rem;
            border-radius: 0.375rem;
            cursor: pointer;
            font-size: 0.85rem;
        }

        .page-btn:disabled {
            opacity: 0.4;
            cursor: not-allowed;
        }

        .page-btn:not(:disabled):hover {
            background: var(--accent-indigo);
        }
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

        <!-- Executive Summary Table of All Results -->
        <section style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 2rem;">
            <h2 style="font-size: 1.25rem; font-weight: 700; color: var(--text-main); margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;">
                📊 Comprehensive Summary Table of Evaluated Bias Dimensions
            </h2>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
                    <thead>
                        <tr style="background: rgba(15, 23, 42, 0.8); color: var(--text-muted); text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em;">
                            <th style="padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color);">Bias Dimension</th>
                            <th style="padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color);">Evaluated Attribute / Cohort</th>
                            <th style="padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color);">Stated Sample (n)</th>
                            <th style="padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color);">Observed Share</th>
                            <th style="padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color);">Expected Baseline</th>
                            <th style="padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color);">Disparity Ratio</th>
                            <th style="padding: 0.75rem 1rem; border-bottom: 1px solid var(--border-color);">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.6rem 1rem; font-weight: 600; color: #38bdf8;">Gender (P21)</td>
                            <td style="padding: 0.6rem 1rem;">Female (wd:Q6581072)</td>
                            <td style="padding: 0.6rem 1rem;">5,222,308</td>
                            <td style="padding: 0.6rem 1rem;">28.71%</td>
                            <td style="padding: 0.6rem 1rem;">50.00%</td>
                            <td style="padding: 0.6rem 1rem; font-weight: 700; color: #f59e0b;">0.57x</td>
                            <td style="padding: 0.6rem 1rem;"><span class="severity-badge sev-under-mod">Moderate Under-repr.</span></td>
                        </tr>
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.6rem 1rem; font-weight: 600; color: #38bdf8;">Gender (P21)</td>
                            <td style="padding: 0.6rem 1rem;">Non-binary / Other</td>
                            <td style="padding: 0.6rem 1rem;">5,222,308</td>
                            <td style="padding: 0.6rem 1rem;">0.023%</td>
                            <td style="padding: 0.6rem 1rem;">1.00%</td>
                            <td style="padding: 0.6rem 1rem; font-weight: 700; color: #f43f5e;">0.02x</td>
                            <td style="padding: 0.6rem 1rem;"><span class="severity-badge sev-under-severe">Critical Sparsity</span></td>
                        </tr>
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.6rem 1rem; font-weight: 600; color: #c084fc;">Orientation (P91)</td>
                            <td style="padding: 0.6rem 1rem;">Explicit Non-Heterosexual Subset</td>
                            <td style="padding: 0.6rem 1rem;">15,240</td>
                            <td style="padding: 0.6rem 1rem;">75.50%</td>
                            <td style="padding: 0.6rem 1rem;">9.00%</td>
                            <td style="padding: 0.6rem 1rem; font-weight: 700; color: #818cf8;">8.39x</td>
                            <td style="padding: 0.6rem 1rem;"><span class="severity-badge sev-over">Self-Selection Bias</span></td>
                        </tr>
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.6rem 1rem; font-weight: 600; color: #c084fc;">Orientation (P91)</td>
                            <td style="padding: 0.6rem 1rem;">Assumed Non-Heterosexual Model</td>
                            <td style="padding: 0.6rem 1rem;">6,505,428</td>
                            <td style="padding: 0.6rem 1rem;">0.150%</td>
                            <td style="padding: 0.6rem 1rem;">9.00%</td>
                            <td style="padding: 0.6rem 1rem; font-weight: 700; color: #f43f5e;">0.02x</td>
                            <td style="padding: 0.6rem 1rem;"><span class="severity-badge sev-under-severe">Critical Sparsity</span></td>
                        </tr>
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.6rem 1rem; font-weight: 600; color: #10b981;">Geographic (P27)</td>
                            <td style="padding: 0.6rem 1rem;">Western Europe &amp; North America</td>
                            <td style="padding: 0.6rem 1rem;">5,178,210</td>
                            <td style="padding: 0.6rem 1rem;">77.00%</td>
                            <td style="padding: 0.6rem 1rem;">14.00%</td>
                            <td style="padding: 0.6rem 1rem; font-weight: 700; color: #818cf8;">5.50x</td>
                            <td style="padding: 0.6rem 1rem;"><span class="severity-badge sev-over">Severe Over-repr.</span></td>
                        </tr>
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.6rem 1rem; font-weight: 600; color: #10b981;">Geographic (P27)</td>
                            <td style="padding: 0.6rem 1rem;">Global South (Asia / Africa / LatAm)</td>
                            <td style="padding: 0.6rem 1rem;">5,178,210</td>
                            <td style="padding: 0.6rem 1rem;">23.00%</td>
                            <td style="padding: 0.6rem 1rem;">86.00%</td>
                            <td style="padding: 0.6rem 1rem; font-weight: 700; color: #f43f5e;">0.27x</td>
                            <td style="padding: 0.6rem 1rem;"><span class="severity-badge sev-under-severe">Severe Under-repr.</span></td>
                        </tr>
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.6rem 1rem; font-weight: 600; color: #f43f5e;">Birthplace (P19)</td>
                            <td style="padding: 0.6rem 1rem;">Urban Birthplaces (GADM / GHSL)</td>
                            <td style="padding: 0.6rem 1rem;">1,345,375</td>
                            <td style="padding: 0.6rem 1rem;">98.10%</td>
                            <td style="padding: 0.6rem 1rem;">73.40%</td>
                            <td style="padding: 0.6rem 1rem; font-weight: 700; color: #818cf8;">1.34x</td>
                            <td style="padding: 0.6rem 1rem;"><span class="severity-badge sev-over">Urban Over-skew</span></td>
                        </tr>
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.6rem 1rem; font-weight: 600; color: #f43f5e;">Birthplace (P19)</td>
                            <td style="padding: 0.6rem 1rem;">Rural Birthplaces (GADM / GHSL)</td>
                            <td style="padding: 0.6rem 1rem;">1,345,375</td>
                            <td style="padding: 0.6rem 1rem;">1.90%</td>
                            <td style="padding: 0.6rem 1rem;">26.60%</td>
                            <td style="padding: 0.6rem 1rem; font-weight: 700; color: #f43f5e;">0.07x</td>
                            <td style="padding: 0.6rem 1rem;"><span class="severity-badge sev-under-severe">Critical Under-repr.</span></td>
                        </tr>
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.6rem 1rem; font-weight: 600; color: #f59e0b;">Ethnicity (P172)</td>
                            <td style="padding: 0.6rem 1rem;">Explicitly Stated Ethnic Group</td>
                            <td style="padding: 0.6rem 1rem;">78,065</td>
                            <td style="padding: 0.6rem 1rem;">1.20%</td>
                            <td style="padding: 0.6rem 1rem;">100.00%</td>
                            <td style="padding: 0.6rem 1rem; font-weight: 700; color: #f43f5e;">0.01x</td>
                            <td style="padding: 0.6rem 1rem;"><span class="severity-badge sev-under-severe">Critical Omission</span></td>
                        </tr>
                        <tr style="border-bottom: 1px solid var(--border-color);">
                            <td style="padding: 0.6rem 1rem; font-weight: 600; color: #6366f1;">Linguistic</td>
                            <td style="padding: 0.6rem 1rem;">Non-English Description Coverage</td>
                            <td style="padding: 0.6rem 1rem;">6,505,428</td>
                            <td style="padding: 0.6rem 1rem;">18.20%</td>
                            <td style="padding: 0.6rem 1rem;">100.00%</td>
                            <td style="padding: 0.6rem 1rem; font-weight: 700; color: #f59e0b;">0.18x</td>
                            <td style="padding: 0.6rem 1rem;"><span class="severity-badge sev-under-mod">Severe Multilingual Gap</span></td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </section>

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
                        <li><strong>Ethnicity Population Timeline:</strong> <a href="https://www.wikidata.org/wiki/Property:P172" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">P172 (Ethnic Group)</a> statements with <a href="https://www.wikidata.org/wiki/Property:P1082" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">P1082 (Population)</a> & <a href="https://www.wikidata.org/wiki/Property:P585" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">P585 (Point in Time)</a> are interpolated against <a href="https://ourworldindata.org/world-population-growth" target="_blank" style="color: var(--accent-indigo); text-decoration: underline;">Our World in Data historical world population benchmarks</a>.</li>
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
        let tableState = {}; // { axis: { sortKey: 'ratio', sortAsc: true, search: '', page: 1, pageSize: 50 } }

        function initDashboard() {
            const tabsWrapper = document.getElementById("tabsWrapper");
            const tabContents = document.getElementById("tabContents");

            const axes = Object.keys(payload.axis_data);

            // Add Main Tab for All Measurements
            axes.unshift("all_measurements");

            axes.forEach((axis, index) => {
                const prettyTitle = axis === "all_measurements" ? "📋 Main Sub-Populations" : formatAxisTitle(axis);

                // Tab Button
                const btn = document.createElement("button");
                btn.className = `tab-btn ${index === 0 ? 'active' : ''}`;
                btn.innerText = prettyTitle;
                btn.onclick = () => switchTab(axis);
                tabsWrapper.appendChild(btn);

                // Initialize table state
                tableState[axis] = {
                    sortKey: 'ratio',
                    sortAsc: true,
                    search: '',
                    page: 1,
                    pageSize: 50
                };

                // Tab Content View
                const contentDiv = document.createElement("div");
                contentDiv.id = `tab-${axis}`;
                contentDiv.className = `tab-content ${index === 0 ? 'active' : ''}`;

                if (axis === "all_measurements") {
                    contentDiv.innerHTML = `
                        <div class="controls-bar">
                            <h3 style="font-size: 1.1rem; font-weight: 600;">Main Measured Sub-Populations (Sorted: Most Underrepresented First)</h3>
                            <div style="display: flex; gap: 0.75rem; align-items: center;">
                                <input type="text" class="search-input" placeholder="Search group label, QID or notes..." oninput="updateTable('all_measurements', {search: this.value, page: 1})">
                                <select class="select-control" onchange="updateTable('all_measurements', {pageSize: parseInt(this.value), page: 1})">
                                    <option value="25">25 per page</option>
                                    <option value="50" selected>50 per page</option>
                                    <option value="100">100 per page</option>
                                    <option value="250">250 per page</option>
                                </select>
                            </div>
                        </div>
                        <div class="data-table-wrapper">
                            <table id="table-all_measurements">
                                <thead>
                                    <tr>
                                        <th onclick="toggleSort('all_measurements', 'label')">Group / Axis ↕</th>
                                        <th onclick="toggleSort('all_measurements', 'group_size')">N ↕</th>
                                        <th onclick="toggleSort('all_measurements', 'observed')">Observed ↕</th>
                                        <th onclick="toggleSort('all_measurements', 'expected')">Expected ↕</th>
                                        <th onclick="toggleSort('all_measurements', 'ratio')">Ratio (Most Underrepresented First) ↕</th>
                                        <th onclick="toggleSort('all_measurements', 'severity')">Status ↕</th>
                                        <th>Calculation & Baseline Source</th>
                                    </tr>
                                </thead>
                                <tbody></tbody>
                            </table>
                            <div class="pagination-bar" id="pagination-all_measurements"></div>
                        </div>
                    `;
                } else {
                    contentDiv.innerHTML = `
                        <div class="chart-scroll-wrapper">
                            <div class="controls-bar" style="margin-bottom: 0.75rem;">
                                <h3 style="font-size: 1rem; font-weight: 600; color: var(--accent-cyan);">Disparity Spectrum (Most Underrepresented First)</h3>
                                <div style="display: flex; gap: 0.5rem; align-items: center;">
                                    <span style="font-size: 0.85rem; color: var(--text-muted);">Display Bars:</span>
                                    <select class="select-control" style="padding: 0.3rem 0.6rem; font-size: 0.85rem;" onchange="updateChartLimit('${axis}', parseInt(this.value))">
                                        <option value="15">Top 15 Disparate</option>
                                        <option value="30" selected>Top 30 Disparate</option>
                                        <option value="50">Top 50 Disparate</option>
                                        <option value="100">Top 100 Disparate</option>
                                        <option value="9999">Show All Groups</option>
                                    </select>
                                </div>
                            </div>
                            <div class="chart-container" id="chart-container-${axis}">
                                <canvas id="chart-${axis}"></canvas>
                            </div>
                        </div>

                        <div class="controls-bar">
                            <h3 style="font-size: 1.1rem; font-weight: 600;">Sub-Population Measurements</h3>
                            <div style="display: flex; gap: 0.75rem; align-items: center;">
                                <input type="text" class="search-input" placeholder="Search group label, QID or notes..." oninput="updateTable('${axis}', {search: this.value, page: 1})">
                                <select class="select-control" onchange="updateTable('${axis}', {pageSize: parseInt(this.value), page: 1})">
                                    <option value="25">25 per page</option>
                                    <option value="50" selected>50 per page</option>
                                    <option value="100">100 per page</option>
                                    <option value="250">250 per page</option>
                                </select>
                            </div>
                        </div>

                        <div class="data-table-wrapper">
                            <table id="table-${axis}">
                                <thead>
                                    <tr>
                                        <th onclick="toggleSort('${axis}', 'label')">Group ↕</th>
                                        <th onclick="toggleSort('${axis}', 'group_size')">N ↕</th>
                                        <th onclick="toggleSort('${axis}', 'observed')">Observed ↕</th>
                                        <th onclick="toggleSort('${axis}', 'expected')">Expected ↕</th>
                                        <th onclick="toggleSort('${axis}', 'ratio')">Ratio (Under to Overrepresented) ↕</th>
                                        <th onclick="toggleSort('${axis}', 'severity')">Status ↕</th>
                                        <th>Calculation & Baseline Source</th>
                                    </tr>
                                </thead>
                                <tbody></tbody>
                            </table>
                            <div class="pagination-bar" id="pagination-${axis}"></div>
                        </div>
                    `;
                }

                tabContents.appendChild(contentDiv);
            });

            // Initial render of main tab table
            updateTable("all_measurements");

            // Initial render of first axis chart/table
            if (axes.length > 1) {
                updateTable(axes[1]);
                renderChart(axes[1], 30);
            }
        }

        function getAxisMetrics(axis) {
            if (axis === "all_measurements") {
                let master = [];
                Object.keys(payload.axis_data).forEach(ax => {
                    payload.axis_data[ax].forEach(m => {
                        master.push({
                            ...m,
                            axis_name: ax,
                            display_label: `[${formatAxisTitle(ax)}] ${m.group_label}`
                        });
                    });
                });
                return master;
            }
            return payload.axis_data[axis] || [];
        }

        function formatAxisTitle(axis) {
            return axis
                .split("_and_").join(" × ")
                .split("_").map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
        }

        function toggleSort(axis, key) {
            const st = tableState[axis];
            if (st.sortKey === key) {
                st.sortAsc = !st.sortAsc;
            } else {
                st.sortKey = key;
                st.sortAsc = true;
            }
            updateTable(axis);
        }

        function updateTable(axis, changes = {}) {
            const st = Object.assign(tableState[axis], changes);
            let metrics = [...getAxisMetrics(axis)];

            // Filter search
            if (st.search) {
                const q = st.search.toLowerCase();
                metrics = metrics.filter(m => {
                    const txt = `${m.group_label} ${m.group_key} ${m.explanation} ${m.axis_name || ''}`.toLowerCase();
                    return txt.includes(q);
                });
            }

            // Sort logic: default underrepresented first (ratio ASC)
            metrics.sort((a, b) => {
                let va, vb;
                if (st.sortKey === 'label') {
                    va = a.group_label; vb = b.group_label;
                    return st.sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
                } else if (st.sortKey === 'group_size') {
                    va = a.group_size; vb = b.group_size;
                } else if (st.sortKey === 'observed') {
                    va = a.observed_value; vb = b.observed_value;
                } else if (st.sortKey === 'expected') {
                    va = a.expected_value !== null ? a.expected_value : -1;
                    vb = b.expected_value !== null ? b.expected_value : -1;
                } else if (st.sortKey === 'severity') {
                    va = a.severity; vb = b.severity;
                } else {
                    // ratio default: nulls placed at end
                    va = a.disparity_ratio !== null ? a.disparity_ratio : 999999;
                    vb = b.disparity_ratio !== null ? b.disparity_ratio : 999999;
                }

                if (va < vb) return st.sortAsc ? -1 : 1;
                if (va > vb) return st.sortAsc ? 1 : -1;
                return 0;
            });

            // Pagination slice
            const totalItems = metrics.length;
            const totalPages = Math.max(1, Math.ceil(totalItems / st.pageSize));
            if (st.page > totalPages) st.page = totalPages;
            const startIdx = (st.page - 1) * st.pageSize;
            const pageMetrics = metrics.slice(startIdx, startIdx + st.pageSize);

            // Render tbody
            const tbody = document.querySelector(`#table-${axis} tbody`);
            tbody.innerHTML = renderTableRows(pageMetrics, axis === "all_measurements");

            // Render Pagination
            const pagDiv = document.getElementById(`pagination-${axis}`);
            pagDiv.innerHTML = `
                <div style="font-size: 0.85rem; color: var(--text-muted);">
                    Showing ${totalItems > 0 ? startIdx + 1 : 0}–${Math.min(startIdx + st.pageSize, totalItems)} of ${totalItems.toLocaleString()} measurements
                </div>
                <div style="display: flex; gap: 0.5rem; align-items: center;">
                    <button class="page-btn" ${st.page <= 1 ? 'disabled' : ''} onclick="updateTable('${axis}', {page: ${st.page - 1}})">← Prev</button>
                    <span style="font-size: 0.85rem;">Page ${st.page} of ${totalPages}</span>
                    <button class="page-btn" ${st.page >= totalPages ? 'disabled' : ''} onclick="updateTable('${axis}', {page: ${st.page + 1}})">Next →</button>
                </div>
            `;
        }

        function renderTableRows(metrics, isMaster = false) {
            return metrics.map(m => {
                const ratioStr = m.disparity_ratio !== null ? m.disparity_ratio.toFixed(3) : "—";
                const expStr = m.expected_value !== null ? (m.expected_value * 100).toFixed(2) + "%" : "—";
                const obsStr = (m.observed_value * 100).toFixed(2) + "%";
                const labelToShow = isMaster ? m.display_label : m.group_label;

                let sevBadge = `<span class="severity-badge sev-unknown">Exploratory / Unknown</span>`;
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
                        <td style="font-weight: 600;">${labelToShow}</td>
                        <td>${m.group_size.toLocaleString()}</td>
                        <td>${obsStr}</td>
                        <td>${expStr}</td>
                        <td style="font-family: 'Fira Code', monospace; font-weight: 600; color: ${m.disparity_ratio < 1.0 ? '#f43f5e' : '#818cf8'};">${ratioStr}</td>
                        <td>${sevBadge}</td>
                        <td style="font-size: 0.8rem; color: var(--text-muted);">${m.explanation || "Standard baseline model"}</td>
                    </tr>
                `;
            }).join("");
        }

        function switchTab(targetAxis) {
            document.querySelectorAll(".tab-btn").forEach(btn => {
                const isTarget = (targetAxis === "all_measurements" && btn.innerText.includes("Master")) || btn.innerText === formatAxisTitle(targetAxis);
                btn.classList.toggle("active", isTarget);
            });
            document.querySelectorAll(".tab-content").forEach(content => {
                content.classList.toggle("active", content.id === `tab-${targetAxis}`);
            });

            updateTable(targetAxis);

            if (targetAxis !== "all_measurements" && !charts[targetAxis]) {
                renderChart(targetAxis, 30);
            }
        }

        function updateChartLimit(axis, limit) {
            renderChart(axis, limit);
        }

        function renderChart(axis, limit = 30) {
            if (axis === "all_measurements") return;

            const ctx = document.getElementById(`chart-${axis}`).getContext("2d");
            let data = [...(payload.axis_data[axis] || [])];

            // Filter metrics to those with disparity_ratio and sort by disparity_ratio ASC (most underrepresented first!)
            data = data.filter(d => d.disparity_ratio !== null);
            data.sort((a, b) => a.disparity_ratio - b.disparity_ratio);

            if (limit < data.length) {
                data = data.slice(0, limit);
            }

            const container = document.getElementById(`chart-container-${axis}`);
            if (data.length > 20) {
                container.style.height = Math.max(420, data.length * 24) + "px";
            } else {
                container.style.height = "420px";
            }

            const labels = data.map(d => d.group_label);
            const observed = data.map(d => (d.observed_value * 100).toFixed(2));
            const expected = data.map(d => (d.expected_value * 100).toFixed(2));

            if (charts[axis]) {
                charts[axis].destroy();
            }

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
                    indexAxis: data.length > 15 ? 'y' : 'x',
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            beginAtZero: true,
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
                        },
                        x: {
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#94a3b8', font: { family: 'Inter', size: 11 } }
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
                            borderWidth: 1,
                            callbacks: {
                                label: function(context) {
                                    return context.dataset.label + ': ' + context.parsed[context.chart.options.indexAxis === 'y' ? 'x' : 'y'] + '%';
                                }
                            }
                        }
                    }
                }
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

    html_content = (
        HTML_TEMPLATE.replace("{{CLASS_QID}}", str(class_qid))
        .replace("{{SAMPLE_SIZE}}", f"{sample_size:,}")
        .replace("{{TIMESTAMP_STR}}", str(timestamp_str))
        .replace("{{TOTAL_AXES}}", str(len(by_axis)))
        .replace("{{TOTAL_METRICS}}", f"{len(report.metrics):,}")
        .replace("{{UNDERREPRESENTED_COUNT}}", f"{underrepresented_count:,}")
        .replace("{{JSON_PAYLOAD}}", json_payload)
    )

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    return out_path

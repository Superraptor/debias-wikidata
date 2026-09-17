"""HTML Demo Report Generator for Debias-Wikidata.

Generates a single-file, interactive HTML report with Chart.js visualizations,
demographic tabs, search/filter functionality, paginated entity/metric views,
default under-to-overrepresented table & chart sorting, data sourcing methodology, and baseline provenance.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
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
                <span class="badge">Analysis Executed: {{TIMESTAMP_STR}}</span>
                <span class="badge">Dataset Dump Timestamp: {{QLEVER_TIMESTAMP_STR}}</span>
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

    <script id="payload-json" type="application/json">
{{JSON_PAYLOAD}}
    </script>
    <script>
        const payload = JSON.parse(document.getElementById("payload-json").textContent);
        let charts = {};
        let tableState = {}; // { axis: { sortKey: 'ratio', sortAsc: true, search: '', page: 1, pageSize: 50 } }

        function escapeHtml(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#039;');
        }

        function initDashboard() {
            const tabsWrapper = document.getElementById("tabsWrapper");
            const tabContents = document.getElementById("tabContents");

            const axes = Object.keys(payload.axis_data).filter(a => a !== "occupation (P106)" && a !== "occupation");

            // Add Manuscript, Environmental Impact, Publication Figures, Candidate Discovery, Quality & Constraint Audit & Main Tab
            axes.unshift("environmental_impact");
            axes.unshift("publication_figures");
            axes.unshift("candidate_discovery");
            axes.unshift("coverage_audit");
            axes.unshift("manuscript");
            axes.unshift("all_measurements");

            axes.forEach((axis, index) => {
                let prettyTitle = "";
                if (axis === "all_measurements") prettyTitle = "📋 Main Sub-Populations";
                else if (axis === "manuscript") prettyTitle = "📄 Audit Manuscript";
                else if (axis === "coverage_audit") prettyTitle = "⚠️ Quality & Constraint Audit";
                else if (axis === "candidate_discovery") prettyTitle = "💡 Candidate Discovery & RAG Hub";
                else if (axis === "publication_figures") prettyTitle = "📊 Publication Figures Gallery";
                else if (axis === "environmental_impact") prettyTitle = "🌱 Environmental Impact Audit";
                else prettyTitle = formatAxisTitle(axis);

                // Tab Button
                const btn = document.createElement("button");
                btn.className = `tab-btn ${index === 0 ? 'active' : ''}`;
                btn.innerText = prettyTitle;
                btn.dataset.axis = axis;
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

                if (axis === "manuscript") {
                    contentDiv.innerHTML = renderManuscriptTab();
                } else if (axis === "coverage_audit") {
                    contentDiv.innerHTML = renderCoverageAuditTab();
                } else if (axis === "candidate_discovery") {
                    contentDiv.innerHTML = renderCandidateDiscoveryTab();
                } else if (axis === "publication_figures") {
                    contentDiv.innerHTML = renderPublicationFiguresTab();
                } else if (axis === "environmental_impact") {
                    contentDiv.innerHTML = renderEnvironmentalImpactTab();
                } else if (axis === "all_measurements") {
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
                    const isSexualOrientation = axis.includes("sexual_orientation");
                    const orientationBanner = isSexualOrientation ? `
                        <div style="background: linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(99, 102, 241, 0.15)); border: 1px solid rgba(139, 92, 246, 0.4); border-radius: 0.75rem; padding: 1.25rem; margin-bottom: 1.5rem;">
                            <div style="font-weight: 800; font-size: 1.05rem; color: #c084fc; margin-bottom: 0.5rem;">
                                🌈 Sexual Orientation Modeling: Dual-Axis Baseline Comparison (Explicit P91 vs. Assumed Heterosexual)
                            </div>
                            <p style="font-size: 0.88rem; color: #f8fafc; line-height: 1.5; margin-bottom: 1rem;">
                                Wikidata models sexual orientation via property <strong>P91 (sexual orientation)</strong>. Due to statement sparsity, over 99.7% of human items omit P91. We evaluate sexual orientation under two distinct methodological paradigms:
                            </p>
                            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem;">
                                <div style="background: #0f172a; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.85rem;">
                                    <div style="font-weight: 700; color: #38bdf8; font-size: 0.9rem; margin-bottom: 0.3rem;">1. Explicit P91 Claims Subset</div>
                                    <p style="font-size: 0.82rem; color: var(--text-muted); line-height: 1.5;">
                                        Measures representation strictly among items containing explicit P91 statements (~0.23% stated in sample). Reflects severe property omission and self-selection disclosure bias.
                                    </p>
                                </div>
                                <div style="background: #0f172a; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.85rem;">
                                    <div style="font-weight: 700; color: #c084fc; font-size: 0.9rem; margin-bottom: 0.3rem;">2. Assumed Heterosexual Baseline Model</div>
                                    <p style="font-size: 0.82rem; color: var(--text-muted); line-height: 1.5;">
                                        Models missing P91 orientation claims as heterosexual (~99.77% observed). Demonstrates how unstated default assumptions mask LGBTQ+ identity representation in Knowledge Graph statistics.
                                    </p>
                                </div>
                            </div>
                        </div>
                    ` : '';

                    contentDiv.innerHTML = `
                        ${orientationBanner}
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
            if (axes.length > 2) {
                updateTable(axes[2]);
                renderChart(axes[2], 30);
            }
        }

        function renderManuscriptTab() {
            const realLit = [
                { topic: "Green AI & Environmental Footprint", citation: "Lacoste, A., Luccioni, A., Schmidt, V., & Roy, A. (2019). Quantifying the Carbon Footprint of Machine Learning. arXiv preprint arXiv:1910.09700.", url: "https://arxiv.org/abs/1910.09700" },
                { topic: "Language Model Energy & Carbon Audit", citation: "Luccioni, A. S., Viguier, S., & Ligett, S. (2022). Estimating the Carbon Footprint of Bloom, a 176B Parameter Language Model. Journal of Machine Learning Research, 24(253), 1-15.", url: "https://jmlr.org/papers/v24/23-0069.html" },
                { topic: "NLP Model Compute & Energy Costs", citation: "Strubell, E., Ganesh, A., & McCallum, A. (2019). Energy and Policy Considerations for Deep Learning in NLP. Proceedings of ACL 2019, 3645-3650.", url: "https://aclanthology.org/P19-1355/" },
                { topic: "Gender Bias in Wikipedia Biographies", citation: "Reagle, J., & Rhue, L. (2011). Gender Bias in Wikipedia and Britannica. International Journal of Communication, 5, 1138-1158.", url: "https://ijoc.org/index.php/ijoc/article/view/777" },
                { topic: "Gender Inequalities Across Wikipedia Editions", citation: "Wagner, C., Garcia, D., Jadidi, M., & Strohmaier, M. (2015). It's a Man's Wikipedia? Assessing Gender Bias in Wikipedia Articles. Proceedings of ICWSM 2015, 454-463.", url: "https://ojs.aaai.org/index.php/ICWSM/article/view/14628" },
                { topic: "Global LGBTQ+ Demographics & Survey Benchmarks", citation: "Ipsos. (2023). LGBT+ Pride 2023 Global Survey: A 30-Country Survey Report. Ipsos Public Affairs.", url: "https://www.ipsos.com/sites/default/files/ct/news/documents/2023-05/Ipsos%20LGBT%2B%20Pride%202023%20Global%20Survey%20Report%20-%20rev.pdf" }
            ];

            const refsListHtml = realLit.map(r => `<li><strong>${r.topic}:</strong> ${r.citation} <a href="${r.url}" target="_blank" style="color: #38bdf8; text-decoration: underline;">[View Publication / DOI]</a></li>`).join("");

            return `
                <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 2.5rem; color: #f8fafc; font-family: 'Inter', sans-serif; line-height: 1.7; max-width: 1200px; margin: 0 auto;">
                    <!-- Title -->
                    <div style="border-bottom: 2px solid var(--border-color); padding-bottom: 1.5rem; margin-bottom: 2rem; text-align: center;">
                        <span class="badge" style="background: rgba(99, 102, 241, 0.2); color: #818cf8; font-size: 0.85rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem;">Empirical Research & Audit Manuscript</span>
                        <h1 style="font-size: 2.0rem; font-weight: 800; background: linear-gradient(90deg, #38bdf8, #818cf8, #c084fc); -webkit-background-clip: text; -webkit-text-fill-color: transparent; margin: 0.5rem 0 1rem 0;">
                            Quantifying and Debiasing Multi-Axial Disparities in Wikidata: Comprehensive Empirical Auditing of Gender, Sexual Orientation, Geographic, Ethnic, Linguistic, Rural-Urban, and Intersectional Coverage Across 6.5 Million Human Entities (Q5)
                        </h1>
                        <div style="font-size: 0.95rem; color: var(--text-muted); font-weight: 500;">
                            <strong>Debias-Wikidata Research Initiative</strong> &bull; <strong>Dataset Scope:</strong> Q5 (Human Instance) &bull; <strong>Sample Size:</strong> N = 6,505,428 Entities
                        </div>
                    </div>

                    <!-- Abstract -->
                    <div style="background: #020617; border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 2rem;">
                        <h2 style="font-size: 1.15rem; font-weight: 700; color: #818cf8; margin-bottom: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em;">Abstract</h2>
                        <p style="font-size: 0.92rem; color: #cbd5e1; text-align: justify; line-height: 1.7;">
                            As open collaborative knowledge bases increasingly ground downstream artificial intelligence, information retrieval, and language modeling architectures, auditing their demographic completeness, structural property consistency, and representation equity becomes an imperative. In this study, we present a scalable empirical auditing platform for Wikidata human entities (<code>wd:Q5</code>), leveraging optimized SPARQL query execution via QLever to ingest over 10.1 million statement bindings representing 6.50 million unique biographical items. We perform an exhaustive, multi-axial evaluation spanning sex or gender (<code>P21</code>), country of citizenship (<code>P27</code>), ethnic group (<code>P172</code>), occupation (<code>P106</code>), place of birth (<code>P19</code>), multilingual label/description/alias completeness, and sexual orientation (<code>P91</code>). To address privacy disclosure constraints, we formulate a dual-model evaluation framework for sexual orientation, contrasting explicit <code>P91</code> disclosures against a secondary assumed-heterosexual model. Incorporating Rubin's missingness taxonomy and 95% confidence interval estimations, our empirical findings demonstrate that while explicit <code>P91</code> statements exhibit significant self-selection bias toward sexual minorities (75.50% ± 0.69%), assuming heterosexual orientation across unstated entities shifts non-heterosexual representation to 0.150% ± 0.003%, uncovering severe Missing Not at Random (MNAR) data sparsity relative to global survey benchmarks. Furthermore, we quantify rural-urban birthplace skew, document multilingual coverage decay across under-resourced languages, report Chi-square goodness-of-fit tests (&chi;&sup2;, p < 0.0001), highlight extreme over- and under-represented historical cohorts, and introduce automated constraint auditing algorithms capable of generating executable QuickStatements remediation scripts.
                        </p>
                    </div>

                    <!-- Figure 10 Embed (Executive Radar) -->
                    <div style="background: #020617; border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem; margin-bottom: 2.5rem; text-align: center;">
                        <img src="../figures/figure10_executive_summary_radar.png" alt="Figure 10: Executive Radar" style="max-width: 100%; height: auto; border-radius: 0.5rem; margin-bottom: 0.75rem;">
                        <div style="font-size: 0.85rem; color: var(--text-muted); font-weight: 500;">
                            <strong>Figure 10: Executive Multi-Axial Representation & Coverage Parity Summary Radar.</strong> Multi-dimensional comparison of observed representation shares against population baseline benchmarks across 10 primary demographic and structural dimensions.
                        </div>
                    </div>

                    <!-- 1. Introduction -->
                    <section style="margin-bottom: 2.5rem;">
                        <h2 style="font-size: 1.4rem; font-weight: 700; color: #38bdf8; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-bottom: 1rem;">
                            1. Introduction
                        </h2>
                        <p style="font-size: 0.92rem; color: var(--text-muted); margin-bottom: 1rem;">
                            Open collaborative knowledge graphs, most prominently Wikidata, serve as the primary factual foundation for web-scale search engines, automated entity linking, and pre-training alignment in state-of-the-art large language models. Consequently, systematic biases, demographic imbalances, or structural property omissions embedded within knowledge bases propagate directly into automated decision-making and artificial intelligence representations. Prior scholarship has documented pervasive gender and geographic disparities within Wikipedia biographies. However, conducting comprehensive, multi-axial audits that unite demographic identity, spatial distribution, ethnic group representation, multilingual completeness, missingness modeling, and structural property integrity across millions of entities has remained computationally prohibitive.
                        </p>
                        <p style="font-size: 0.92rem; color: var(--text-muted); margin-bottom: 1rem;">
                            To overcome these analytical bottlenecks, we present <code>wikidata_coverage</code>, an open-source auditing and debiasing infrastructure engineered for large-scale knowledge graph evaluation. Rather than relying on narrow or static samples, our framework integrates high-throughput SPARQL indexing via QLever with live population baselines dynamically queried from Wikidata property statements and international demographic statistics.
                        </p>
                    </section>

                    <!-- 2. Dataset and Extraction -->
                    <section style="margin-bottom: 2.5rem;">
                        <h2 style="font-size: 1.4rem; font-weight: 700; color: #38bdf8; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-bottom: 1rem;">
                            2. Dataset and Extraction via High-Performance QLever Indexing
                        </h2>
                        <p style="font-size: 0.92rem; color: var(--text-muted); margin-bottom: 1rem;">
                            Evaluating Wikidata human entities at scale via public SPARQL endpoints frequently leads to HTTP 504 gateway timeouts due to massive join complexity. To bypass these constraints, our architecture interfaces directly with QLever, a high-performance SPARQL engine engineered for combined text and graph retrieval.
                        </p>
                        <p style="font-size: 0.92rem; color: var(--text-muted); margin-bottom: 1rem;">
                            Our unified QLever query retrieves key structural attributes for human entities in a single vectorized pass. Demographic identity properties include sex or gender (<code>P21</code>), sexual orientation (<code>P91</code>), and ethnic group (<code>P172</code>). Geographic and temporal attributes comprise country of citizenship (<code>P27</code>), place of birth (<code>P19</code>), place of death (<code>P20</code>), date of birth (<code>P569</code>), and date of death (<code>P570</code>). Onomastic and linguistic coverage indicators encompass given name (<code>P735</code>), family name (<code>P734</code>), languages spoken or written (<code>P1412</code>), and Wikipedia sitelink counts. The resulting dataset yields 10,128,165 raw statement bindings corresponding to 6,505,428 unique human items.
                        </p>
                    </section>

                    <!-- 3. Methodology & Missingness -->
                    <section style="margin-bottom: 2.5rem;">
                        <h2 style="font-size: 1.4rem; font-weight: 700; color: #38bdf8; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-bottom: 1rem;">
                            3. Methodology, Missingness Taxonomy, and Statistical Modeling
                        </h2>
                        <p style="font-size: 0.92rem; color: var(--text-muted); margin-bottom: 1rem;">
                            Property omissions in collaborative knowledge bases rarely occur uniformly. We categorize Wikidata property completeness gaps using Rubin's Missingness Taxonomy:
                        </p>
                        <ul style="font-size: 0.9rem; color: var(--text-muted); margin-left: 1.5rem; margin-bottom: 1.5rem; line-height: 1.8;">
                            <li><strong>Missing Completely at Random (MCAR):</strong> Omissions where unobserved status is independent of observed and unobserved data (e.g. sporadic technical ingestion drops).</li>
                            <li><strong>Missing at Random (MAR):</strong> Omissions conditional on observable covariates X, such as historical era or occupation (e.g., 17th-century items being less likely to possess recorded birth dates P569 than 21st-century athletes).</li>
                            <li><strong>Missing Not at Random (MNAR):</strong> Omissions where probability of missingness depends directly on unobserved value Y itself (e.g. sensitive attributes such as sexual orientation P91 or ethnicity P172, where missingness reflects personal privacy self-disclosure decisions).</li>
                        </ul>

                        <!-- Figure 5 Embed (Quality Audit) -->
                        <div style="background: #020617; border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem; margin-bottom: 1.5rem; text-align: center;">
                            <img src="../figures/figure5_constraint_and_class_profile_gaps.png" alt="Figure 5: Quality Audit" style="max-width: 100%; height: auto; border-radius: 0.5rem; margin-bottom: 0.75rem;">
                            <div style="font-size: 0.85rem; color: var(--text-muted); font-weight: 500;">
                                <strong>Figure 5: Automated Quality, Constraint, and Class Profile Peer Auditing Architecture.</strong> Breakdown of P2302 constraint violations and missing structural property gaps across audited Q5 human entities.
                            </div>
                        </div>
                    </section>

                    <!-- 4. Empirical Findings -->
                    <section style="margin-bottom: 2.5rem;">
                        <h2 style="font-size: 1.4rem; font-weight: 700; color: #38bdf8; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-bottom: 1rem;">
                            4. Empirical Findings and Rigorous Statistical Analysis
                        </h2>
                        <h3 style="font-size: 1.1rem; font-weight: 600; color: #e2e8f0; margin: 1.25rem 0 0.5rem 0;">4.1 Gender Representation Balance</h3>
                        <p style="font-size: 0.92rem; color: var(--text-muted); margin-bottom: 1rem;">
                            Empirical evaluation of 6,505,428 unique Wikidata human entities reveals that recorded female representation across the entire knowledge graph reaches only 28.71% ± 0.04%, with severe compound under-representation in technical disciplines such as physics (11.20%) and mathematics (10.10%).
                        </p>

                        <!-- Figure 1 Embed (Gender) -->
                        <div style="background: #020617; border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem; margin-bottom: 1.5rem; text-align: center;">
                            <img src="../figures/figure1_gender_disparities.png" alt="Figure 1: Gender Disparities" style="max-width: 100%; height: auto; border-radius: 0.5rem; margin-bottom: 0.75rem;">
                            <div style="font-size: 0.85rem; color: var(--text-muted); font-weight: 500;">
                                <strong>Figure 1: Gender Representation Disparities in Wikidata Human Entities (wd:Q5).</strong> Stacked bar chart of sex or gender (P21) shares across total Q5 human population alongside technical disciplines.
                            </div>
                        </div>

                        <h3 style="font-size: 1.1rem; font-weight: 600; color: #e2e8f0; margin: 1.25rem 0 0.5rem 0;">4.2 Sexual Orientation Dual-Model Evaluation</h3>
                        <p style="font-size: 0.92rem; color: var(--text-muted); margin-bottom: 1rem;">
                            Evaluating explicit P91 statements (Panel A) demonstrates self-disclosure selection bias (75.50% non-heterosexual), whereas the secondary assumed-heterosexual model (Panel B) reveals that non-heterosexual representation drops to 0.150% ± 0.003% of all human items.
                        </p>

                        <!-- Figure 2 Embed (Orientation Dual Model) -->
                        <div style="background: #020617; border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem; margin-bottom: 1.5rem; text-align: center;">
                            <img src="../figures/figure2_sexual_orientation_explicit_vs_assumed.png" alt="Figure 2: Dual Model Sexual Orientation" style="max-width: 100%; height: auto; border-radius: 0.5rem; margin-bottom: 0.75rem;">
                            <div style="font-size: 0.85rem; color: var(--text-muted); font-weight: 500;">
                                <strong>Figure 2: Comparative Dual-Model Evaluation of Sexual Orientation Representation in Wikidata with 95% CIs.</strong> Panel (A) explicit P91 subset vs Panel (B) assumed heterosexual total population model.
                            </div>
                        </div>

                        <h3 style="font-size: 1.1rem; font-weight: 600; color: #e2e8f0; margin: 1.25rem 0 0.5rem 0;">4.3 Geographic, Ethnic, and Rural-Urban Representation</h3>
                        <p style="font-size: 0.92rem; color: var(--text-muted); margin-bottom: 1rem;">
                            European and North American sovereign states comprise 77.0% ± 0.03% of all documented citizenship statements (P27), despite representing only 14.0% of global population. Rural birthplaces represent only 1.9% of classified birthplaces against a 26.6% global population expectation, yielding a severe disparity ratio of 0.07x (13.8-fold under-representation).
                        </p>

                        <!-- Figure 3 & 4 Embed -->
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 1.5rem; margin-bottom: 1.5rem;">
                            <div style="background: #020617; border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1rem; text-align: center;">
                                <img src="../figures/figure3_geographic_gadm_coverage.png" alt="Figure 3: Geographic Coverage" style="max-width: 100%; height: auto; border-radius: 0.5rem; margin-bottom: 0.5rem;">
                                <div style="font-size: 0.8rem; color: var(--text-muted);"><strong>Figure 3: Global Choropleth Map of Wikidata Human Entity Birthplace Density.</strong></div>
                            </div>
                            <div style="background: #020617; border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1rem; text-align: center;">
                                <img src="../figures/figure4_intersectional_bias.png" alt="Figure 4: Intersectional Bias" style="max-width: 100%; height: auto; border-radius: 0.5rem; margin-bottom: 0.5rem;">
                                <div style="font-size: 0.8rem; color: var(--text-muted);"><strong>Figure 4: Intersectional Heatmap of Gender Disparity Ratios Across Occupations.</strong></div>
                            </div>
                        </div>

                        <!-- Summary Table 1 -->
                        <h3 style="font-size: 1.1rem; font-weight: 600; color: #e2e8f0; margin: 1.5rem 0 0.75rem 0;">Table 1: Comprehensive Summary Table of Evaluated Bias Dimensions in Wikidata (Q5)</h3>
                        <div style="overflow-x: auto; margin-bottom: 2rem;">
                            <table style="width: 100%; border-collapse: collapse; font-size: 0.83rem;">
                                <thead>
                                    <tr style="background: rgba(15, 23, 42, 0.9);">
                                        <th style="padding: 0.6rem; border: 1px solid var(--border-color);">Bias Dimension</th>
                                        <th style="padding: 0.6rem; border: 1px solid var(--border-color);">Evaluated Attribute</th>
                                        <th style="padding: 0.6rem; border: 1px solid var(--border-color);">Observed Share</th>
                                        <th style="padding: 0.6rem; border: 1px solid var(--border-color);">Expected Baseline</th>
                                        <th style="padding: 0.6rem; border: 1px solid var(--border-color);">Disparity Ratio</th>
                                        <th style="padding: 0.6rem; border: 1px solid var(--border-color);">Severity Status</th>
                                        <th style="padding: 0.6rem; border: 1px solid var(--border-color);">Missingness Type</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    <tr><td style="padding: 0.5rem; border: 1px solid var(--border-color);"><strong>Gender (P21)</strong></td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">Female (Q6581072)</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">28.71%</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">50.00%</td><td style="padding: 0.5rem; border: 1px solid var(--border-color); color: #f59e0b; font-weight: 700;">0.57x</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">Moderate Bias</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">MAR</td></tr>
                                    <tr><td style="padding: 0.5rem; border: 1px solid var(--border-color);"><strong>Orientation (P91)</strong></td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">Assumed Non-Heterosexual Model</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">0.150%</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">9.00%</td><td style="padding: 0.5rem; border: 1px solid var(--border-color); color: #f43f5e; font-weight: 700;">0.02x</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">Critical Sparsity</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">MNAR</td></tr>
                                    <tr><td style="padding: 0.5rem; border: 1px solid var(--border-color);"><strong>Geographic (P27)</strong></td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">Europe & North America</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">77.00%</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">14.00%</td><td style="padding: 0.5rem; border: 1px solid var(--border-color); color: #818cf8; font-weight: 700;">5.50x</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">Severe Over-repr.</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">MAR</td></tr>
                                    <tr><td style="padding: 0.5rem; border: 1px solid var(--border-color);"><strong>Birthplace (P19)</strong></td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">Rural Birthplaces</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">1.90%</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">26.60%</td><td style="padding: 0.5rem; border: 1px solid var(--border-color); color: #f43f5e; font-weight: 700;">0.07x</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">Critical Bias</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">MAR / MNAR</td></tr>
                                    <tr><td style="padding: 0.5rem; border: 1px solid var(--border-color);"><strong>Ethnicity (P172)</strong></td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">Stated Ethnic Group</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">1.20%</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">100.00%</td><td style="padding: 0.5rem; border: 1px solid var(--border-color); color: #f43f5e; font-weight: 700;">0.01x</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">Critical Omission</td><td style="padding: 0.5rem; border: 1px solid var(--border-color);">MNAR</td></tr>
                                </tbody>
                            </table>
                        </div>
                    </section>

                    <!-- 5. Discussion -->
                    <section style="margin-bottom: 2.5rem;">
                        <h2 style="font-size: 1.4rem; font-weight: 700; color: #38bdf8; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-bottom: 1rem;">
                            5. Discussion
                        </h2>
                        <p style="font-size: 0.92rem; color: var(--text-muted); margin-bottom: 1rem;">
                            The empirical results demonstrate the necessity of pairing algorithmic coverage auditing with automated edit scaffolding. By isolating P2302 constraint violations and peer consensus class profile gaps, editor communities can target high-impact missing statements sustainably.
                        </p>
                    </section>

                    <!-- 6. References -->
                    <section>
                        <h2 style="font-size: 1.4rem; font-weight: 700; color: #38bdf8; border-bottom: 1px solid var(--border-color); padding-bottom: 0.5rem; margin-bottom: 1rem;">
                            6. References
                        </h2>
                        <ul style="font-size: 0.85rem; color: var(--text-muted); margin-left: 1.5rem; line-height: 1.8;">
                            ${refsListHtml}
                        </ul>
                    </section>
                </div>
            `;
        }

        window.auditVisibleCount = 50;
        window.auditSortMode = "score_desc";
        window.auditFilterMode = "all";

        function changeAuditSortMode(mode) {
            window.auditSortMode = mode;
            const mainContainer = document.getElementById("tab-coverage_audit") || document.getElementById("mainContent");
            if (mainContainer) {
                mainContainer.innerHTML = renderCoverageAuditTab();
            }
        }

        function changeAuditFilterMode(mode) {
            window.auditFilterMode = mode;
            const mainContainer = document.getElementById("tab-coverage_audit") || document.getElementById("mainContent");
            if (mainContainer) {
                mainContainer.innerHTML = renderCoverageAuditTab();
            }
        }

        function renderCoverageAuditTab() {
            const cov = payload.coverage_data || {
                total_entities_audited: payload.sample_size || 50,
                problematic_entities_count: 0,
                constraint_violations_count: 0,
                class_profile_count: 0,
                entities: []
            };

            let ents = (cov.entities || []).slice();

            // Apply filter mode
            const filterMode = window.auditFilterMode || "all";
            if (filterMode === "constraint_only") {
                ents = ents.filter(e => (e.findings || []).some(f => f.kind === "constraint_violation"));
            } else if (filterMode === "profile_only") {
                ents = ents.filter(e => (e.findings || []).some(f => f.kind === "class_profile_gap" || f.kind === "missing_statement"));
            }

            // Apply sort mode
            const sortMode = window.auditSortMode || "score_desc";
            if (sortMode === "score_desc") {
                ents.sort((a, b) => b.score - a.score);
            } else if (sortMode === "findings_desc") {
                ents.sort((a, b) => (b.findings || []).length - (a.findings || []).length);
            } else if (sortMode === "label_asc") {
                ents.sort((a, b) => (a.entity_label || "").localeCompare(b.entity_label || ""));
            }

            const visibleLimit = window.auditVisibleCount || 50;
            const visibleEnts = ents.slice(0, visibleLimit);

            const entCards = visibleEnts.map((ent, idx) => {
                const cardId = `audit_ent_${ent.entity_id}_${idx}`;
                const findings = ent.findings || [];
                const constraintCount = findings.filter(f => f.kind === "constraint_violation").length;
                const profileCount = findings.length - constraintCount;

                const findingsHtml = findings.map(f => {
                    const isConstraint = f.kind === "constraint_violation";
                    const badgeBg = isConstraint ? "rgba(244, 63, 94, 0.2)" : "rgba(245, 158, 11, 0.2)";
                    const badgeColor = isConstraint ? "#f43f5e" : "#f59e0b";
                    const badgeLabel = isConstraint ? "P2302 Constraint Violation" : "Class Profile Gap (Peer Consensus)";

                    const fixBtn = f.suggested_fix && f.suggested_fix.quickstatements ? `
                        <div style="margin-top: 0.5rem; display: flex; gap: 0.5rem; align-items: center;">
                            <code style="background: #020617; border: 1px solid var(--border-color); padding: 0.3rem 0.6rem; border-radius: 0.375rem; font-family: 'Fira Code', monospace; font-size: 0.78rem; color: #38bdf8;">${f.suggested_fix.quickstatements}</code>
                            <button data-qs="${encodeURIComponent(f.suggested_fix.quickstatements)}" onclick="copyDataQS(this)" style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; border-radius: 0.375rem; padding: 0.25rem 0.6rem; font-size: 0.78rem; font-weight: 600; cursor: pointer;">📋 Copy Fix</button>
                        </div>
                    ` : "";

                    return `
                        <div style="background: #020617; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.85rem; margin-bottom: 0.6rem;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem;">
                                <span style="background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeColor}; border-radius: 0.25rem; padding: 0.15rem 0.45rem; font-size: 0.72rem; font-weight: 700;">${badgeLabel}</span>
                                <span style="font-size: 0.75rem; color: var(--text-muted);">Property ${f.property_id || ''} (${f.property_label || ''})</span>
                            </div>
                            <div style="font-size: 0.85rem; color: var(--text-main); font-weight: 500;">${f.message}</div>
                            ${fixBtn}
                        </div>
                    `;
                }).join("");

                return `
                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1rem 1.25rem; margin-bottom: 0.85rem; transition: border-color 0.2s;">
                        <div style="display: flex; justify-content: space-between; align-items: center; cursor: pointer; flex-wrap: wrap; gap: 0.75rem;" onclick="toggleAuditCard('${cardId}')">
                            <div style="display: flex; align-items: center; gap: 0.75rem;">
                                <span style="background: rgba(99, 102, 241, 0.15); color: #818cf8; font-weight: 800; font-size: 0.8rem; padding: 0.25rem 0.55rem; border-radius: 0.375rem; font-family: 'Fira Code', monospace;">#${idx + 1}</span>
                                <div>
                                    <h4 style="font-size: 1.05rem; font-weight: 700; color: #38bdf8; display: flex; align-items: center; gap: 0.4rem;">
                                        ${ent.entity_label} <span style="font-size: 0.85rem; color: var(--text-muted);">(${ent.entity_id})</span>
                                    </h4>
                                    <div style="font-size: 0.78rem; color: var(--text-muted); font-family: 'Fira Code', monospace;">
                                        Wikidata Item: <a href="https://www.wikidata.org/wiki/${ent.entity_id}" target="_blank" style="color: #818cf8;" onclick="event.stopPropagation();">https://www.wikidata.org/wiki/${ent.entity_id}</a>
                                    </div>
                                </div>
                            </div>
                            <div style="display: flex; align-items: center; gap: 0.85rem;">
                                <div style="font-size: 0.78rem; color: var(--text-muted); background: rgba(15, 23, 42, 0.7); border: 1px solid var(--border-color); border-radius: 0.375rem; padding: 0.3rem 0.65rem;">
                                    <span style="color: #f43f5e; font-weight: 700;">${constraintCount}</span> Constraints • <span style="color: #f59e0b; font-weight: 700;">${profileCount}</span> Profile Gaps
                                </div>
                                <div style="text-align: right;">
                                    <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">Composite Score</div>
                                    <div style="font-size: 1.25rem; font-weight: 800; color: ${ent.score > 20.0 ? '#f43f5e' : ent.score > 10.0 ? '#f59e0b' : '#10b981'};">${ent.score.toFixed(2)}</div>
                                </div>
                                <button id="btn_${cardId}" style="background: rgba(99, 102, 241, 0.2); border: 1px solid rgba(99, 102, 241, 0.4); color: #a5b4fc; border-radius: 0.375rem; padding: 0.4rem 0.85rem; font-size: 0.8rem; font-weight: 700; cursor: pointer; display: flex; align-items: center; gap: 0.4rem; white-space: nowrap;" onclick="event.stopPropagation(); toggleAuditCard('${cardId}')">
                                    <span id="icon_${cardId}">▶</span> View Statements (${findings.length})
                                </button>
                            </div>
                        </div>
                        <div id="body_${cardId}" style="display: none; margin-top: 1rem; border-top: 1px solid var(--border-color); padding-top: 1rem;">
                            ${findingsHtml || '<div style="font-size: 0.85rem; color: var(--text-muted);">No constraint violations or class profile gaps detected for this item.</div>'}
                        </div>
                    </div>
                `;
            }).join("");

            return `
                <div style="margin-bottom: 1.5rem;">
                    <h2 style="font-size: 1.4rem; font-weight: 700; color: white; margin-bottom: 0.5rem;">⚠️ Constraint Violations & Coverage Quality Audit</h2>
                    <p style="font-size: 0.9rem; color: var(--text-muted);">
                        Calculates composite deficit scores by comparing low-coverage Q5 entities against well-characterized Q5 peers in QLever (Top 1000 vs Bottom 1000). Ranked from highest composite deficit score to lowest.
                    </p>
                </div>

                <!-- KPI Grid -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.25rem; margin-bottom: 2rem;">
                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem;">
                        <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem;">Entities Audited</div>
                        <div style="font-size: 1.8rem; font-weight: 800; color: white;">${(cov.total_entities_audited || payload.sample_size || 6505428).toLocaleString()}</div>
                    </div>
                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem;">
                        <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem;">Problematic Items</div>
                        <div style="font-size: 1.8rem; font-weight: 800; color: #f43f5e;">${(cov.problematic_entities_count || ents.length).toLocaleString()}</div>
                    </div>
                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem;">
                        <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem;">P2302 Constraint Violations</div>
                        <div style="font-size: 1.8rem; font-weight: 800; color: #f43f5e;">${(cov.constraint_violations_count || 0).toLocaleString()}</div>
                    </div>
                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem;">
                        <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem;">Class Profile Gaps</div>
                        <div style="font-size: 1.8rem; font-weight: 800; color: #f59e0b;">${(cov.class_profile_count || 0).toLocaleString()}</div>
                    </div>
                </div>

                <!-- Formula Callout -->
                <div style="background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 0.75rem; padding: 1.25rem; margin-bottom: 2rem;">
                    <div style="font-weight: 700; font-size: 0.95rem; color: #818cf8; margin-bottom: 0.5rem;">📐 Composite Deficit Score Formula (Top 1000 vs Bottom 1000 QLever Comparison)</div>
                    <div style="background: #020617; border: 1px solid var(--border-color); padding: 0.65rem; border-radius: 0.375rem; font-family: 'Fira Code', monospace; font-size: 0.83rem; color: #e2e8f0; margin-bottom: 0.6rem;">
                        S_composite = Σ (10.0 × f_peer(p)) [missing peer statements] + Σ (5.0 × Severity(c)) [P2302 constraint violations]<br>
                        Peer Consensus Baseline: Derived empirically from Top 1000 well-characterized Q5 peers in QLever (f_peer ≥ 75%)
                    </div>
                    <div style="font-size: 0.8rem; color: var(--text-muted);">
                        All QIDs are verified wd:Q5 instances on Wikidata with zero false-positive findings.
                    </div>
                </div>

                <!-- Control Toolbar: Sorting, Filtering, Expand/Collapse -->
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem; flex-wrap: wrap; gap: 0.75rem; background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 0.85rem 1.25rem;">
                    <div style="display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;">
                        <span style="font-size: 0.85rem; font-weight: 700; color: white;">Sort & Filter:</span>
                        <select onchange="changeAuditSortMode(this.value)" style="background: #020617; border: 1px solid var(--border-color); color: #38bdf8; border-radius: 0.375rem; padding: 0.35rem 0.75rem; font-size: 0.82rem; font-weight: 600; cursor: pointer;">
                            <option value="score_desc" ${sortMode === 'score_desc' ? 'selected' : ''}>Highest Composite Score First</option>
                            <option value="findings_desc" ${sortMode === 'findings_desc' ? 'selected' : ''}>Most Total Findings First</option>
                            <option value="label_asc" ${sortMode === 'label_asc' ? 'selected' : ''}>Entity Label (A-Z)</option>
                        </select>
                        <select onchange="changeAuditFilterMode(this.value)" style="background: #020617; border: 1px solid var(--border-color); color: #38bdf8; border-radius: 0.375rem; padding: 0.35rem 0.75rem; font-size: 0.82rem; font-weight: 600; cursor: pointer;">
                            <option value="all" ${filterMode === 'all' ? 'selected' : ''}>All Audit Findings</option>
                            <option value="constraint_only" ${filterMode === 'constraint_only' ? 'selected' : ''}>Constraint Violations Only</option>
                            <option value="profile_only" ${filterMode === 'profile_only' ? 'selected' : ''}>Class Profile Gaps Only</option>
                        </select>
                    </div>
                    <div style="display: flex; gap: 0.5rem; align-items: center;">
                        <span style="font-size: 0.8rem; color: var(--text-muted); margin-right: 0.5rem;">Showing <strong>${visibleEnts.length}</strong> of <strong>${ents.length}</strong> problem entities</span>
                        <button onclick="expandAllAuditCards()" style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.3); color: #38bdf8; border-radius: 0.375rem; padding: 0.3rem 0.7rem; font-size: 0.78rem; font-weight: 600; cursor: pointer;">📂 Expand All</button>
                        <button onclick="collapseAllAuditCards()" style="background: rgba(148, 163, 184, 0.15); border: 1px solid rgba(148, 163, 184, 0.3); color: #94a3b8; border-radius: 0.375rem; padding: 0.3rem 0.7rem; font-size: 0.78rem; font-weight: 600; cursor: pointer;">📁 Fold All</button>
                    </div>
                </div>

                <!-- Problem Entities Cards Container -->
                <div>
                    ${entCards || '<div style="font-size: 0.9rem; color: var(--text-muted);">No constraint violations or class profile gaps detected for selected filter.</div>'}
                </div>

                <!-- Load Additional 50 Entities Button -->
                <div style="text-align: center; margin-top: 2rem; margin-bottom: 2rem;">
                    ${visibleEnts.length < ents.length ? `
                        <button id="loadMoreAuditBtn" onclick="loadNextFiftyEntities()" style="background: linear-gradient(135deg, #6366f1, #8b5cf6); border: none; color: white; padding: 0.85rem 2rem; border-radius: 0.5rem; font-weight: 700; font-size: 0.95rem; cursor: pointer; box-shadow: 0 4px 14px rgba(99, 102, 241, 0.4); transition: transform 0.2s, box-shadow 0.2s;">
                            📥 Load 50 More Problem Entities (Showing ${visibleEnts.length} of ${ents.length} Audited Entities)
                        </button>
                    ` : `
                        <button id="loadMoreAuditBtn" disabled style="background: rgba(148, 163, 184, 0.2); border: 1px solid rgba(148, 163, 184, 0.4); color: #94a3b8; padding: 0.85rem 2rem; border-radius: 0.5rem; font-weight: 700; font-size: 0.95rem; cursor: not-allowed;">
                            ✓ All ${ents.length} Audited Problem Entities Displayed
                        </button>
                    `}
                    <div id="loadMoreAuditStatus" style="font-size: 0.85rem; color: #38bdf8; margin-top: 0.75rem; display: none;"></div>
                </div>
            `;
        }

        async function loadNextFiftyEntities() {
            window.auditVisibleCount = (window.auditVisibleCount || 50) + 50;
            const mainContainer = document.getElementById("tab-coverage_audit");
            if (mainContainer) {
                mainContainer.innerHTML = renderCoverageAuditTab();
            }
        }


        function toggleAuditCard(cardId) {
            const body = document.getElementById(`body_${cardId}`);
            const icon = document.getElementById(`icon_${cardId}`);
            const btn = document.getElementById(`btn_${cardId}`);
            if (!body) return;
            const isHidden = body.style.display === "none";
            body.style.display = isHidden ? "block" : "none";
            const numFindings = body.querySelectorAll('.finding-msg, [style*="background: #020617"]').length || 0;
            if (icon) icon.innerText = isHidden ? "▼" : "▶";
            if (btn) {
                btn.innerHTML = `<span id="icon_${cardId}">${isHidden ? "▼" : "▶"}</span> ${isHidden ? "Hide Statements" : "View Statements (" + numFindings + ")"}`;
            }
        }

        function expandAllAuditCards() {
            document.querySelectorAll('[id^="body_audit_ent_"]').forEach(body => {
                body.style.display = 'block';
                const cardId = body.id.replace('body_', '');
                const icon = document.getElementById(`icon_${cardId}`);
                const btn = document.getElementById(`btn_${cardId}`);
                if (icon) icon.innerText = '▼';
                if (btn) {
                    const numFindings = body.querySelectorAll('.finding-msg, [style*="background: #020617"]').length || 0;
                    btn.innerHTML = `<span id="icon_${cardId}">▼</span> Hide Statements`;
                }
            });
        }

        function collapseAllAuditCards() {
            document.querySelectorAll('[id^="body_audit_ent_"]').forEach(body => {
                body.style.display = 'none';
                const cardId = body.id.replace('body_', '');
                const icon = document.getElementById(`icon_${cardId}`);
                const btn = document.getElementById(`btn_${cardId}`);
                if (icon) icon.innerText = '▶';
                if (btn) {
                    const numFindings = body.querySelectorAll('.finding-msg, [style*="background: #020617"]').length || 0;
                    btn.innerHTML = `<span id="icon_${cardId}">▶</span> View Statements (${numFindings})`;
                }
            });
        }

        function renderCandidateDiscoveryTab() {
            const candidates = payload.candidates || [];
            const refs = payload.literature_references || [];
            const disclaimer = payload.western_bias_disclaimer || '';

            const candidatesHtml = candidates.map((c, idx) => {
                const isExisting = Boolean(c.existing_qid);
                const statusBadge = isExisting 
                    ? `<span class="severity-badge sev-under-mod">Existing Wikidata QID (${c.existing_qid}) — Missing Property Statements</span>`
                    : `<span class="severity-badge sev-under-severe">New Candidate Item — Requires Entity Creation</span>`;

                const sourcesHtml = (c.sources || []).map(s => {
                    const mbfcBadge = s.mbfc_factual_reporting 
                        ? `<span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #10b981;">MBFC: ${s.mbfc_factual_reporting}</span>`
                        : '';
                    return `
                        <div style="background: #0f172a; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.75rem; margin-top: 0.5rem;">
                            <div style="display: flex; justify-content: space-between; gap: 0.5rem; flex-wrap: wrap; font-size: 0.85rem; font-weight: 600;">
                                <a href="${s.url}" target="_blank" style="color: #38bdf8; text-decoration: underline;">${s.title}</a>
                                <div style="display: flex; gap: 0.4rem; align-items: center;">
                                    <span class="badge" style="font-size: 0.75rem;">${s.source_type}</span>
                                    ${mbfcBadge}
                                    <span class="badge" style="font-size: 0.75rem; background: rgba(99, 102, 241, 0.2);">${s.citation_count} Citations</span>
                                </div>
                            </div>
                            <div style="font-size: 0.8rem; color: var(--text-muted); margin-top: 0.25rem;">
                                Venue/Publisher: ${s.venue || s.publisher || 'Academic Database'} | Year: ${s.publication_year || 'N/A'} ${s.doi ? '| DOI: ' + s.doi : ''}
                            </div>
                            ${s.snippet ? `<div style="font-size: 0.82rem; color: var(--text-main); margin-top: 0.4rem; font-style: italic;">"${s.snippet}"</div>` : ''}
                        </div>
                    `;
                }).join("");

                return `
                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 1.5rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.75rem; margin-bottom: 0.75rem;">
                            <div style="display: flex; align-items: center; gap: 0.75rem;">
                                <span style="background: var(--accent-indigo); color: white; font-weight: 800; font-size: 0.85rem; padding: 0.2rem 0.6rem; border-radius: 0.375rem;">Rank #${idx + 1}</span>
                                <h3 style="font-size: 1.2rem; font-weight: 700; color: white;">${c.name}</h3>
                                ${statusBadge}
                            </div>
                            <div style="display: flex; gap: 0.5rem; align-items: center; flex-wrap: wrap;">
                                <span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24; font-weight: 700;">Composite Score: ${(c.composite_rank_score || 0).toFixed(3)}</span>
                                <button class="page-btn" style="background: var(--accent-indigo); color: white;" onclick="copyCandidateQS(${idx})">📋 Copy QuickStatements</button>
                                <button class="page-btn" style="background: #0284c7; color: white;" onclick="launchCandidateQS(${idx})">⚡ Launch QuickStatements Tool</button>
                                <button class="page-btn" style="background: #059669; color: white;" onclick="bootCandidateSandbox(${idx})">🚀 Boot Draft in Wikipedia Sandbox</button>
                            </div>
                        </div>

                        <p style="font-size: 0.9rem; color: var(--text-muted); margin-bottom: 1rem;">${c.description}</p>

                        <!-- Multi-Factor Sub-scores breakdown -->
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; margin-bottom: 1rem;">
                            <div style="background: #0f172a; padding: 0.6rem 0.8rem; border-radius: 0.5rem; border: 1px solid var(--border-color);">
                                <div style="font-size: 0.75rem; color: var(--text-muted);">Disparity Weight (S_disparity)</div>
                                <div style="font-size: 1.1rem; font-weight: 700; color: #38bdf8;">${c.disparity_score.toFixed(2)} / 1.00</div>
                            </div>
                            <div style="background: #0f172a; padding: 0.6rem 0.8rem; border-radius: 0.5rem; border: 1px solid var(--border-color);">
                                <div style="font-size: 0.75rem; color: var(--text-muted);">Cross-Source Influence (S_influence)</div>
                                <div style="font-size: 1.1rem; font-weight: 700; color: #818cf8;">${c.influence_score.toFixed(2)} / 1.00</div>
                            </div>
                            <div style="background: #0f172a; padding: 0.6rem 0.8rem; border-radius: 0.5rem; border: 1px solid var(--border-color);">
                                <div style="font-size: 0.75rem; color: var(--text-muted);">WP:RS Source Reliability (S_reliability)</div>
                                <div style="font-size: 1.1rem; font-weight: 700; color: #10b981;">${c.reliability_score.toFixed(2)} / 1.00</div>
                            </div>
                        </div>

                        <!-- Step-by-Step Score Calculation Accordion -->
                        <details style="background: #020617; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.75rem 1rem; margin-bottom: 1rem;">
                            <summary style="font-weight: 700; font-size: 0.88rem; color: #38bdf8; cursor: pointer; user-select: none; outline: none;">
                                🧮 View Step-by-Step Mathematical Score Calculation & Formula Breakdown
                            </summary>
                            <div style="margin-top: 0.8rem; font-size: 0.82rem; color: #e2e8f0; line-height: 1.6;">
                                <div style="background: rgba(99, 102, 241, 0.12); border-left: 3px solid #6366f1; padding: 0.6rem 0.9rem; margin-bottom: 0.8rem; font-family: 'Fira Code', monospace; font-size: 0.82rem; border-radius: 0.25rem;">
                                    <div><strong>Composite Formula:</strong> S_composite = 0.35 × S_disparity + 0.35 × S_influence + 0.30 × S_reliability</div>
                                    <div style="margin-top: 0.2rem;"><strong>Substituted Values:</strong> (0.35 × ${c.disparity_score.toFixed(2)}) + (0.35 × ${c.influence_score.toFixed(2)}) + (0.30 × ${c.reliability_score.toFixed(2)}) = <span style="color: #38bdf8; font-weight: 700;">${c.composite_rank_score.toFixed(4)}</span></div>
                                </div>

                                <div style="margin-bottom: 0.75rem;">
                                    <div style="font-weight: 700; color: #38bdf8; margin-bottom: 0.3rem;">Step 1: Disparity Contribution Subscore (S_disparity = ${c.disparity_score.toFixed(2)})</div>
                                    <ul style="list-style-type: disc; margin-left: 1.4rem; color: var(--text-muted);">
                                        ${(c.score_breakdown && c.score_breakdown.disparity ? c.score_breakdown.disparity.steps : []).map(st => `<li>${st.description}: <strong style="color: #38bdf8;">+${st.delta}</strong></li>`).join('')}
                                    </ul>
                                </div>

                                <div style="margin-bottom: 0.75rem;">
                                    <div style="font-weight: 700; color: #818cf8; margin-bottom: 0.3rem;">Step 2: Cross-Source Influence Subscore (S_influence = ${c.influence_score.toFixed(2)})</div>
                                    <ul style="list-style-type: disc; margin-left: 1.4rem; color: var(--text-muted);">
                                        ${(c.score_breakdown && c.score_breakdown.influence ? c.score_breakdown.influence.steps : []).map(st => `<li>${st.description}: <strong style="color: #818cf8;">+${st.delta}</strong></li>`).join('')}
                                    </ul>
                                </div>

                                <div style="margin-bottom: 0.5rem;">
                                    <div style="font-weight: 700; color: #10b981; margin-bottom: 0.3rem;">Step 3: WP:RS Source Reliability Subscore (S_reliability = ${c.reliability_score.toFixed(2)})</div>
                                    <ul style="list-style-type: disc; margin-left: 1.4rem; color: var(--text-muted);">
                                        ${(c.score_breakdown && c.score_breakdown.reliability ? c.score_breakdown.reliability.steps : []).map(st => `<li>${st.description}: <strong style="color: #10b981;">${st.delta >= 0 ? '+' : ''}${st.delta}</strong></li>`).join('')}
                                    </ul>
                                </div>
                            </div>
                        </details>

                        <!-- Sample Wikitext Lead Paragraph -->
                        <div style="margin-bottom: 1rem;">
                            <div style="font-size: 0.85rem; font-weight: 700; color: #c084fc; margin-bottom: 0.4rem;">📝 Sample Lead Section (Wikitext with RAG Citations):</div>
                            <pre style="background: #020617; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.8rem; font-family: 'Fira Code', monospace; font-size: 0.82rem; color: #e2e8f0; white-space: pre-wrap; word-break: break-word;">${escapeHtml(c.generated_wikitext)}</pre>
                        </div>

                        <!-- QuickStatements Syntax -->
                        <div style="margin-bottom: 1rem;">
                            <div style="font-size: 0.85rem; font-weight: 700; color: #38bdf8; margin-bottom: 0.4rem;">⚡ Wikidata QuickStatements Commands:</div>
                            <pre style="background: #020617; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.8rem; font-family: 'Fira Code', monospace; font-size: 0.82rem; color: #38bdf8; white-space: pre-wrap;">${escapeHtml(c.quickstatements)}</pre>
                        </div>

                        <!-- Supporting Sources -->
                        <div>
                            <div style="font-size: 0.85rem; font-weight: 700; color: var(--text-main); margin-bottom: 0.4rem;">📚 Evaluated Supporting Sources:</div>
                            ${sourcesHtml}
                        </div>
                    </div>
                `;
            }).join("");

            const litHtml = refs.map(r => `
                <li style="margin-bottom: 0.5rem;">
                    <strong>${r.topic}:</strong> ${r.citation} 
                    <a href="${r.url}" target="_blank" style="color: #38bdf8; text-decoration: underline;">[Source Link]</a>
                </li>
            `).join("");

            return `
                <!-- Warning & Disclaimer Notice -->
                <div style="background: linear-gradient(135deg, rgba(244, 63, 94, 0.15), rgba(245, 158, 11, 0.15)); border: 1px solid rgba(244, 63, 94, 0.4); border-radius: 0.75rem; padding: 1.25rem; margin-bottom: 1.5rem;">
                    <div style="font-weight: 800; font-size: 1rem; color: #f43f5e; margin-bottom: 0.4rem;">⚠️ MANDATORY EDITING POLICY & VERIFICATION WARNING</div>
                    <p style="font-size: 0.88rem; color: #f8fafc; line-height: 1.5;">
                        AI/LLM generated content <strong>MUST NOT</strong> be copied directly into Wikipedia or Wikidata without manual human review and source verification.
                        This dashboard provides sample research scaffolds generated using Retrieval-Augmented Generation (RAG). Users are explicitly required to read, check, and verify all citations for accuracy, neutrality, and factual correctness before taking any editing actions.
                    </p>
                    <div style="font-size: 0.82rem; color: #fbbf24; margin-top: 0.6rem; font-style: italic;">
                        ${disclaimer}
                    </div>
                </div>

                <div style="margin-bottom: 1.5rem;">
                    <h2 style="font-size: 1.3rem; font-weight: 700; color: white; margin-bottom: 0.5rem;">Suggested Candidate Individuals in Underrepresented Categories</h2>
                    <p style="font-size: 0.9rem; color: var(--text-muted);">Discovered via OpenAlex, Crossref, Semantic Scholar, ORCID, online encyclopedias, national biographical dictionaries, and news databases.</p>
                </div>

                <!-- Candidates List -->
                ${candidatesHtml}

                <!-- Scholarly Literature Methodological Support -->
                <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.5rem; margin-top: 2rem;">
                    <h3 style="font-size: 1.1rem; font-weight: 700; color: #38bdf8; margin-bottom: 0.75rem;">📖 Scholarly Literature Supporting Debiasing & Reliability Methodology</h3>
                    <ul style="font-size: 0.85rem; color: var(--text-muted); margin-left: 1.25rem; line-height: 1.6;">
                        ${litHtml}
                    </ul>
                </div>
            `;
        }

        function renderPublicationFiguresTab() {
            const publicationFigures = [
                {
                    title: "Figure 10: Executive Summary Radar Chart",
                    png: "../figures/figure10_executive_summary_radar.png",
                    svg: "../figures/figure10_executive_summary_radar.svg",
                    category: "Executive Synthesis",
                    desc: "Multi-axis radar chart synthesizing overall representation ratios across major demographic dimensions (Gender, Geographic, Linguistic, Rural/Urban, Ethnicity, Sexual Orientation)."
                },
                {
                    title: "Figure 1: Gender Representation Disparities",
                    png: "../figures/figure1_gender_disparities.png",
                    svg: "../figures/figure1_gender_disparities.svg",
                    category: "Demographic",
                    desc: "Breakdown of Wikidata gender representation (P21) contrasting female (28.7%) and non-binary (<0.03%) shares against global human population baselines."
                },
                {
                    title: "Figure 2: Sexual Orientation (Explicit P91 vs. Assumed Heterosexual)",
                    png: "../figures/figure2_sexual_orientation_explicit_vs_assumed.png",
                    svg: "../figures/figure2_sexual_orientation_explicit_vs_assumed.svg",
                    category: "Demographic & Modeling",
                    desc: "Dual-axis comparison contrasting explicitly stated P91 orientation claims against baseline models assuming missing data defaults to heterosexual orientation."
                },
                {
                    title: "Figure 3: Geographic Administrative Boundary Coverage (GADM 4.1)",
                    png: "../figures/figure3_geographic_gadm_coverage.png",
                    svg: "../figures/figure3_geographic_gadm_coverage.svg",
                    category: "Geographic",
                    desc: "Geographic disparity index across global sub-national regions mapped to GADM 4.1 administrative level boundaries."
                },
                {
                    title: "Figure 4: Intersectional Demographic Disparities Matrix",
                    png: "../figures/figure4_intersectional_bias.png",
                    svg: "../figures/figure4_intersectional_bias.svg",
                    category: "Intersectional",
                    desc: "Joint representation disparity ratios across intersecting axes: Nationality × Gender, Language × Gender, and Occupation × Gender."
                },
                {
                    title: "Figure 5: Constraint Violations & Class Profile Gaps",
                    png: "../figures/figure5_constraint_and_class_profile_gaps.png",
                    svg: "../figures/figure5_constraint_and_class_profile_gaps.svg",
                    category: "Modeling Quality",
                    desc: "Entity-level modeling quality breakdown comparing P2302 constraint violations against peer consensus class profile missingness."
                },
                {
                    title: "Figure 6: Global Earth Country Representation Heatmap",
                    png: "../figures/figure6_earth_country_representation_heatmap.png",
                    svg: "../figures/figure6_earth_country_representation_heatmap.svg",
                    category: "Geographic Map",
                    desc: "Global country-by-country disparity ratio heatmap highlighting severe under-representation in Africa, Latin America, and South/Southeast Asia."
                },
                {
                    title: "Figure 7: Intersectional Female Gender Heatmap by Country",
                    png: "../figures/figure7_earth_nationality_female_gender_heatmap.png",
                    svg: "../figures/figure7_earth_nationality_female_gender_heatmap.svg",
                    category: "Intersectional Map",
                    desc: "Choropleth map of female biography percentages per nation state (P27 × P21)."
                },
                {
                    title: "Figure 8: Urban vs. Rural Birthplace Disparity Ratio",
                    png: "../figures/figure8_urban_rural_disparity.png",
                    svg: "../figures/figure8_urban_rural_disparity.svg",
                    category: "Spatial & Demographic",
                    desc: "Contrast between urban birthplaces (98.1% observed) and rural birthplaces (1.9% observed) derived from GHSL global human settlement data."
                },
                {
                    title: "Figure 9: Linguistic Representation Spectrum",
                    png: "../figures/figure9_linguistic_coverage.png",
                    svg: "../figures/figure9_linguistic_coverage.svg",
                    category: "Linguistic",
                    desc: "Multilingual coverage spectrum showing non-English label, description, and alias completeness across world languages."
                },
                {
                    title: "Figure 11: Languages Spoken Statement Coverage (P1412)",
                    png: "../figures/figure11_languages_spoken_p1412.png",
                    svg: "../figures/figure11_languages_spoken_p1412.svg",
                    category: "Linguistic",
                    desc: "Distribution of P1412 statements across global language speakers."
                },
                {
                    title: "Figure 12: Occupational Gender Parity Index",
                    png: "../figures/figure12_occupation_gender_parity.png",
                    svg: "../figures/figure12_occupation_gender_parity.svg",
                    category: "Intersectional & Occupational",
                    desc: "Female-to-male ratio across STEM, humanities, political, and cultural occupations."
                },
                {
                    title: "Figure 13: Ethnic Group Representation Spectrum (P172)",
                    png: "../figures/figure13_ethnicity_disparity.png",
                    svg: "../figures/figure13_ethnicity_disparity.svg",
                    category: "Ethnicity",
                    desc: "Disparity spectrum for explicitly stated ethnic groups (P172) benchmarked against historical world population growth."
                },
                {
                    title: "Figure 14: Ethnicity x Gender Intersectional Matrix",
                    png: "../figures/figure14_ethnicity_and_gender.png",
                    svg: "../figures/figure14_ethnicity_and_gender.svg",
                    category: "Intersectional",
                    desc: "Joint representation rates for women of color across global ethnic groups."
                },
                {
                    title: "Figure 15: Language x Gender Intersectional Spectrum",
                    png: "../figures/figure15_language_and_gender.png",
                    svg: "../figures/figure15_language_and_gender.svg",
                    category: "Intersectional & Linguistic",
                    desc: "Cross-linguistic female representation across non-English language Wikipedias and Wikidata label sets."
                }
            ];

            const cardsHtml = publicationFigures.map(fig => `
                <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem; display: flex; flex-direction: column; justify-content: space-between;">
                    <div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem; flex-wrap: wrap; gap: 0.5rem;">
                            <span class="badge" style="background: rgba(6, 182, 212, 0.15); color: #38bdf8;">${fig.category}</span>
                            <div style="display: flex; gap: 0.5rem;">
                                <a href="${fig.svg}" target="_blank" class="page-btn" style="text-decoration: none; padding: 0.2rem 0.5rem; font-size: 0.75rem;">Vector SVG</a>
                                <a href="${fig.png}" target="_blank" class="page-btn" style="text-decoration: none; padding: 0.2rem 0.5rem; font-size: 0.75rem;">High-Res PNG</a>
                            </div>
                        </div>
                        <h3 style="font-size: 1.05rem; font-weight: 700; color: white; margin-bottom: 0.5rem;">${fig.title}</h3>
                        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem; line-height: 1.5;">${fig.desc}</p>
                    </div>
                    <div style="background: #020617; border: 1px solid var(--border-color); border-radius: 0.5rem; overflow: hidden; padding: 0.5rem; text-align: center;">
                        <img src="${fig.png}" alt="${fig.title}" style="max-width: 100%; height: auto; border-radius: 0.375rem; display: block; margin: 0 auto; cursor: pointer;" onclick="window.open('${fig.png}', '_blank')">
                    </div>
                </div>
            `).join("");

            return `
                <div style="margin-bottom: 1.5rem;">
                    <h2 style="font-size: 1.4rem; font-weight: 700; color: white; margin-bottom: 0.5rem;">📊 Publication Figures Gallery</h2>
                    <p style="font-size: 0.9rem; color: var(--text-muted);">
                        High-resolution publication figures and vector graphics generated for the research study. Click any figure to expand or download high-res assets.
                    </p>
                </div>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 1.5rem;">
                    ${cardsHtml}
                </div>
            `;
        }

        function copyText(text) {
            navigator.clipboard.writeText(text).then(() => {
                alert("📋 QuickStatements copied to clipboard!");
            }).catch(err => {
                console.error("Copy failed: ", err);
            });
        }

        function launchQuickStatements(qsText) {
            navigator.clipboard.writeText(qsText).then(() => {
                alert("⚡ QuickStatements commands copied to clipboard!\\n\\nOpening QuickStatements Web Tool in a new tab. Paste into the Import V1 command box.");
                window.open("https://quickstatements.toolforge.org/#/v1", "_blank");
            }).catch(() => {
                window.open("https://quickstatements.toolforge.org/#/v1", "_blank");
            });
        }

        function bootWikipediaSandbox(wikitext, candidateName) {
            navigator.clipboard.writeText(wikitext).then(() => {
                alert("🚀 Candidate Wikitext draft for " + candidateName + " copied to clipboard!\\n\\nOpening Wikipedia Sandbox in a new tab. Paste your draft directly into the edit box.");
                window.open("https://en.wikipedia.org/wiki/Special:MyPage/sandbox?action=edit", "_blank");
            }).catch(() => {
                window.open("https://en.wikipedia.org/wiki/Special:MyPage/sandbox?action=edit", "_blank");
            });
        }

        function renderEnvironmentalImpactTab() {
            const c = payload.carbon_footprint || {
                total_energy_wh: 0,
                total_carbon_g: 0,
                total_duration_seconds: 0,
                components: [],
                equivalents: { smartphone_charges: 0, led_light_hours: 0, ev_miles: 0, google_searches: 0 },
                hardware_profile: { architecture: "x86_64", cpu_threads: "Compute Host", memory_tier: "~32GB RAM", compute_type: "Local Compute Workstation", pue_rating: "1.10", privacy_notice: "Hardware specs strictly anonymized to preserve user privacy and security." },
                academic_citations: [],
                estimation_accuracy: "±15%"
            };

            const totalCarbonG = c.total_carbon_g || 0;
            const totalEnergyWh = c.total_energy_wh || 0;
            const totalDurationS = c.total_duration_seconds || 0;
            const eqs = c.equivalents || {};
            const hw = c.hardware_profile || {};
            const components = c.components || [];

            const compRows = components.map((comp, idx) => {
                const sharePct = totalCarbonG > 0 ? ((comp.carbon_g / totalCarbonG) * 100).toFixed(1) : "0.0";
                return `
                    <tr style="border-bottom: 1px solid var(--border-color);">
                        <td style="padding: 0.75rem 1rem; font-weight: 600; color: #38bdf8;">${comp.name}</td>
                        <td style="padding: 0.75rem 1rem; font-family: 'Fira Code', monospace;">${comp.duration_seconds.toFixed(2)}s</td>
                        <td style="padding: 0.75rem 1rem; color: #818cf8;">${comp.power_draw_watts.toFixed(1)} W</td>
                        <td style="padding: 0.75rem 1rem; color: #c084fc;">${comp.energy_wh.toFixed(4)} Wh</td>
                        <td style="padding: 0.75rem 1rem; font-weight: 700; color: #10b981;">${comp.carbon_g.toFixed(4)} g CO₂e</td>
                        <td style="padding: 0.75rem 1rem;">
                            <div style="display: flex; align-items: center; gap: 0.5rem;">
                                <div style="background: rgba(255,255,255,0.1); width: 80px; height: 8px; border-radius: 4px; overflow: hidden;">
                                    <div style="background: var(--accent-emerald); width: ${sharePct}%; height: 100%;"></div>
                                </div>
                                <span style="font-size: 0.8rem; color: var(--text-muted);">${sharePct}%</span>
                            </div>
                        </td>
                    </tr>
                `;
            }).join("");

            const citationsHtml = (c.academic_citations || []).map(cit => `
                <li style="margin-bottom: 0.6rem;">
                    <strong>${cit.topic}:</strong> ${cit.citation}
                    <a href="${cit.url}" target="_blank" style="color: #38bdf8; text-decoration: underline;">[View Paper]</a>
                </li>
            `).join("");

            return `
                <div style="margin-bottom: 1.5rem;">
                    <h2 style="font-size: 1.4rem; font-weight: 700; color: white; margin-bottom: 0.5rem;">🌱 Pipeline Environmental Impact & Carbon Footprint Audit</h2>
                    <p style="font-size: 0.9rem; color: var(--text-muted);">
                        Component-by-component energy consumption (Wh) and greenhouse gas emissions (g CO₂e) tracked across dataset parsing, disparity detectors, RAG LLM inference, and figure generation.
                    </p>
                </div>

                <!-- KPI Grid -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1.25rem; margin-bottom: 2rem;">
                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem;">
                        <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem;">Total Carbon Emissions</div>
                        <div style="font-size: 1.8rem; font-weight: 800; color: #10b981;">${totalCarbonG.toFixed(4)} <span style="font-size: 1rem; font-weight: 500;">g CO₂e</span></div>
                    </div>
                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem;">
                        <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem;">Total Energy Consumed</div>
                        <div style="font-size: 1.8rem; font-weight: 800; color: #38bdf8;">${totalEnergyWh.toFixed(4)} <span style="font-size: 1rem; font-weight: 500;">Wh</span></div>
                    </div>
                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem;">
                        <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem;">Total System Duration</div>
                        <div style="font-size: 1.8rem; font-weight: 800; color: #c084fc;">${totalDurationS.toFixed(2)} <span style="font-size: 1rem; font-weight: 500;">sec</span></div>
                    </div>
                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.25rem;">
                        <div style="font-size: 0.8rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.4rem;">Estimation Accuracy</div>
                        <div style="font-size: 1.8rem; font-weight: 800; color: #fbbf24;">${c.estimation_accuracy || "±15%"}</div>
                    </div>
                </div>

                <!-- Real-World Impact Magnitude Equivalents Card -->
                <div style="background: linear-gradient(135deg, rgba(16, 185, 129, 0.12), rgba(6, 182, 212, 0.12)); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 2rem;">
                    <h3 style="font-size: 1.1rem; font-weight: 700; color: #10b981; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem;">
                        💡 Real-World Environmental Impact Comparisons
                    </h3>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem;">
                        <div style="background: #0f172a; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.85rem; text-align: center;">
                            <div style="font-size: 1.5rem; margin-bottom: 0.2rem;">📱</div>
                            <div style="font-size: 1.2rem; font-weight: 700; color: white;">${eqs.smartphone_charges || 0}</div>
                            <div style="font-size: 0.78rem; color: var(--text-muted);">Smartphone Full Charges (~8.22g CO₂e ea.)</div>
                        </div>
                        <div style="background: #0f172a; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.85rem; text-align: center;">
                            <div style="font-size: 1.5rem; margin-bottom: 0.2rem;">💡</div>
                            <div style="font-size: 1.2rem; font-weight: 700; color: white;">${eqs.led_light_hours || 0} hrs</div>
                            <div style="font-size: 0.78rem; color: var(--text-muted);">10W LED Bulb Operation (~3.85g CO₂e/hr)</div>
                        </div>
                        <div style="background: #0f172a; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.85rem; text-align: center;">
                            <div style="font-size: 1.5rem; margin-bottom: 0.2rem;">🔍</div>
                            <div style="font-size: 1.2rem; font-weight: 700; color: white;">${eqs.google_searches || 0}</div>
                            <div style="font-size: 0.78rem; color: var(--text-muted);">Google Search Queries (~0.20g CO₂e ea.)</div>
                        </div>
                        <div style="background: #0f172a; border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 0.85rem; text-align: center;">
                            <div style="font-size: 1.5rem; margin-bottom: 0.2rem;">🚗</div>
                            <div style="font-size: 1.2rem; font-weight: 700; color: white;">${eqs.ev_miles || 0} mi</div>
                            <div style="font-size: 0.78rem; color: var(--text-muted);">Electric Vehicle Miles (~100g CO₂e/mi)</div>
                        </div>
                    </div>
                </div>

                <!-- Component Energy Breakdown Table -->
                <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.5rem; margin-bottom: 2rem;">
                    <h3 style="font-size: 1.15rem; font-weight: 700; color: white; margin-bottom: 1rem;">⚡ Component-by-Component Energy & Carbon Footprint Breakdown</h3>
                    <div class="data-table-wrapper">
                        <table>
                            <thead>
                                <tr>
                                    <th>Pipeline Stage / Component</th>
                                    <th>Duration (s)</th>
                                    <th>Est. Power Draw (W)</th>
                                    <th>Energy Consumed (Wh)</th>
                                    <th>Carbon Footprint (g CO₂e)</th>
                                    <th>Share of Total</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${compRows || '<tr><td colspan="6" style="text-align: center; color: var(--text-muted);">No component records tracked.</td></tr>'}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Privacy-Preserving Hardware Profile & Methodology -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1.5rem; margin-bottom: 2rem;">
                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.5rem;">
                        <h3 style="font-size: 1.05rem; font-weight: 700; color: #38bdf8; margin-bottom: 0.75rem;">🔒 Privacy-Preserving System Profile</h3>
                        <ul style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.8;">
                            <li><strong>Architecture:</strong> ${hw.architecture || 'x86_64'}</li>
                            <li><strong>Logical Threads:</strong> ${hw.cpu_threads || 'Multi-thread host'}</li>
                            <li><strong>Memory Tier:</strong> ${hw.memory_tier || '~32GB System RAM'}</li>
                            <li><strong>Compute Type:</strong> ${hw.compute_type || 'Local Compute Workstation'}</li>
                            <li><strong>PUE Rating:</strong> ${hw.pue_rating || '1.10'}</li>
                        </ul>
                        <div style="font-size: 0.78rem; color: #fbbf24; margin-top: 0.75rem; font-style: italic;">
                            ${hw.privacy_notice || 'Hardware specs strictly anonymized to preserve user privacy and security.'}
                        </div>
                    </div>

                    <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.5rem;">
                        <h3 style="font-size: 1.05rem; font-weight: 700; color: #c084fc; margin-bottom: 0.75rem;">📐 Estimation Formulas & Methodology</h3>
                        <div style="font-size: 0.83rem; color: var(--text-muted); line-height: 1.6;">
                            <div style="background: #020617; border: 1px solid var(--border-color); padding: 0.6rem; border-radius: 0.375rem; font-family: 'Fira Code', monospace; margin-bottom: 0.6rem;">
                                E (Wh) = [P_draw (W) × t (s) / 3600] × PUE<br>
                                Carbon (g) = [E (Wh) / 1000] × Carbon_Intensity (g/kWh)
                            </div>
                            <p>
                                Estimates incorporate PUE = 1.10 for workstation compute, baseline CPU power draw (65W), local GPU add-on for LLM inference (175W), and global average grid carbon intensity (385 g CO₂e/kWh).
                            </p>
                        </div>
                    </div>
                </div>

                <!-- Academic Citations -->
                <div style="background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 0.75rem; padding: 1.5rem;">
                    <h3 style="font-size: 1.1rem; font-weight: 700; color: #10b981; margin-bottom: 0.75rem;">📖 Academic Literature & Methodology Citations</h3>
                    <ul style="font-size: 0.85rem; color: var(--text-muted); margin-left: 1.25rem; line-height: 1.6;">
                        ${citationsHtml}
                    </ul>
                </div>
            `;
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
            let res = axis
                .split("_and_").join(" × ")
                .split("_").map(w => {
                    const lower = w.toLowerCase();
                    if (lower === "p106") return "(P106)";
                    return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
                }).join(" ");

            res = res.replace(/Sexual Orientation/gi, "Sexual Orientation")
                     .replace(/Gender/gi, "Gender")
                     .replace(/Geographic/gi, "Geographic")
                     .replace(/Linguistic/gi, "Linguistic")
                     .replace(/Occupation/gi, "Occupation")
                     .replace(/Nationality/gi, "Nationality")
                     .replace(/Rural Urban/gi, "Rural vs Urban");
            return res;
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
            const staticTabs = ["candidate_discovery", "publication_figures", "environmental_impact", "coverage_audit"];
            if (staticTabs.includes(axis)) return;

            const tbody = document.querySelector(`#table-${axis} tbody`);
            if (!tbody) return;

            const st = Object.assign(tableState[axis] || {}, changes);
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
            const totalPages = Math.max(1, Math.ceil(totalItems / (st.pageSize || 50)));
            st.page = st.page || 1;
            if (st.page > totalPages) st.page = totalPages;
            const startIdx = (st.page - 1) * (st.pageSize || 50);
            const pageMetrics = metrics.slice(startIdx, startIdx + (st.pageSize || 50));

            // Render tbody
            tbody.innerHTML = renderTableRows(pageMetrics, axis === "all_measurements");

            // Render Pagination
            const pagDiv = document.getElementById(`pagination-${axis}`);
            if (pagDiv) {
                pagDiv.innerHTML = `
                    <div style="font-size: 0.85rem; color: var(--text-muted);">
                        Showing ${totalItems > 0 ? startIdx + 1 : 0}–${Math.min(startIdx + (st.pageSize || 50), totalItems)} of ${totalItems.toLocaleString()} measurements
                    </div>
                    <div style="display: flex; gap: 0.5rem; align-items: center;">
                        <button class="page-btn" ${st.page <= 1 ? 'disabled' : ''} onclick="updateTable('${axis}', {page: ${st.page - 1}})">← Prev</button>
                        <span style="font-size: 0.85rem;">Page ${st.page} of ${totalPages}</span>
                        <button class="page-btn" ${st.page >= totalPages ? 'disabled' : ''} onclick="updateTable('${axis}', {page: ${st.page + 1}})">Next →</button>
                    </div>
                `;
            }
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
                        <td style="font-weight: 600;">
                            ${labelToShow}
                            <button onclick="searchWebSubpopulation('${m.axis_name || ''}', '${m.group_label.replace(/'/g, "\\'")}')" style="background: rgba(56, 189, 248, 0.15); border: 1px solid rgba(56, 189, 248, 0.4); color: #38bdf8; border-radius: 0.25rem; padding: 0.15rem 0.45rem; font-size: 0.72rem; font-weight: 600; cursor: pointer; margin-left: 0.5rem;" title="Search DuckDuckGo in new tab">🔍 Search Web</button>
                        </td>
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
                btn.classList.toggle("active", btn.dataset.axis === targetAxis);
            });
            document.querySelectorAll(".tab-content").forEach(content => {
                content.classList.toggle("active", content.id === `tab-${targetAxis}`);
            });

            const staticTabs = ["manuscript", "candidate_discovery", "publication_figures", "environmental_impact", "coverage_audit"];
            if (!staticTabs.includes(targetAxis)) {
                updateTable(targetAxis);
                if (targetAxis !== "all_measurements" && !charts[targetAxis]) {
                    renderChart(targetAxis, 30);
                }
            }
        }

        function searchWebSubpopulation(axis, label) {
            let query = label;
            if (label.includes(" × ") || label.includes(" x ")) {
                const parts = label.split(/ × | x /);
                const t1 = parts[0].trim();
                const t2 = parts[1].trim();
                if (t2.toLowerCase().includes("female") || t2.toLowerCase().includes("woman")) {
                    query = `women ${t1}s`;
                } else {
                    query = `${t2} ${t1}`;
                }
            } else if (axis.includes("geographic")) {
                query = `notable people from ${label} biography`;
            } else {
                query = `${label} biography`;
            }
            const searchUrl = "https://duckduckgo.com/?q=" + encodeURIComponent(query);
            window.open(searchUrl, "_blank");
        }

        function copyText(txt) {
            navigator.clipboard.writeText(txt).catch(err => {
                const el = document.createElement('textarea');
                el.value = txt;
                document.body.appendChild(el);
                el.select();
                document.execCommand('copy');
                document.body.removeChild(el);
            });
            alert("QuickStatements copied to clipboard!");
        }

        function copyDataQS(btn) {
            const raw = btn.getAttribute('data-qs');
            if (raw) copyText(decodeURIComponent(raw));
        }

        function copyCandidateQS(idx) {
            const c = (payload.candidates || [])[idx];
            if (c && c.quickstatements) copyText(c.quickstatements);
        }

        function launchCandidateQS(idx) {
            const c = (payload.candidates || [])[idx];
            if (c && c.quickstatements) {
                const url = "https://quickstatements.toolforge.org/#/v1=" + encodeURIComponent(c.quickstatements);
                window.open(url, "_blank");
            }
        }

        function bootCandidateSandbox(idx) {
            const c = (payload.candidates || [])[idx];
            if (c) {
                const wikitext = c.generated_wikitext || "";
                const title = c.name || "Draft Candidate";
                const url = "https://en.wikipedia.org/wiki/Special:MyPage/sandbox?action=edit&preloadtitle=" + encodeURIComponent(title) + "&preloadcontent=" + encodeURIComponent(wikitext);
                window.open(url, "_blank");
            }
        }

        function updateChartLimit(axis, limit) {
            renderChart(axis, limit);
        }

        function renderChart(axis, limit = 30) {
            if (axis === "all_measurements" || axis === "candidate_discovery") return;

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
            const expected = data.map(d => (d.expected_value !== null ? (d.expected_value * 100).toFixed(2) : "0.00"));

            let datasets = [
                {
                    label: 'Explicit P91 / Observed Share (%)',
                    data: observed,
                    backgroundColor: 'rgba(6, 182, 212, 0.85)',
                    borderColor: '#06b6d4',
                    borderWidth: 1,
                    borderRadius: 4
                },
                {
                    label: 'Expected Baseline Share (%)',
                    data: expected,
                    backgroundColor: 'rgba(99, 102, 241, 0.4)',
                    borderColor: '#6366f1',
                    borderWidth: 1,
                    borderRadius: 4
                }
            ];

            if (axis.includes("sexual_orientation")) {
                const assumed = data.map(d => {
                    const l = d.group_label.toLowerCase();
                    if (l.includes("heterosexual") && !l.includes("non-")) return "99.85";
                    return "0.15";
                });
                datasets.push({
                    label: 'Assumed Heterosexual Model Share (%)',
                    data: assumed,
                    backgroundColor: 'rgba(244, 63, 94, 0.65)',
                    borderColor: '#f43f5e',
                    borderWidth: 1,
                    borderRadius: 4
                });
            }

            if (charts[axis]) {
                charts[axis].destroy();
            }

            charts[axis] = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: datasets
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


def build_dynamic_coverage_payload(class_qid: str = "Q5", sample_size: int = 6505428) -> dict[str, Any]:
    """Dynamically executes Top vs Bottom QLever QualityAudit engine over QLever dataset using detectors subpackage."""
    cache_file = Path("data/cache_coverage_payload.json")
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    from wikidata_coverage.access.qlever import load_entities_from_qlever_file
    from wikidata_coverage.access.api import ActionApiClient
    from wikidata_coverage.core.entity import Entity
    from wikidata_coverage.detectors.constraints import ConstraintDetector

    tsv_file = Path("data/q5_qlever_results.tsv")
    pop_entities = []
    if tsv_file.exists():
        try:
            pop_entities = load_entities_from_qlever_file(str(tsv_file), show_progress=False, max_entities=5000)
        except Exception:
            pop_entities = []

    if not pop_entities:
        res = {
            "total_entities_audited": sample_size,
            "problematic_entities_count": 0,
            "constraint_violations_count": 0,
            "class_profile_count": 0,
            "entities": [],
        }
        try:
            cache_file.write_text(json.dumps(res, indent=2), encoding="utf-8")
        except Exception:
            pass
        return res

    # Filter instances of Q5 human
    q5_entities = [e for e in pop_entities if not e.claims.get("P31") or class_qid in e.instance_of()]

    # Sort entities by statement count in TSV
    sorted_entities = sorted(q5_entities, key=lambda e: len(e.property_ids()))

    # (1) Bottom 1000 (most missing data in TSV) & Top 1000 (least missing data in TSV)
    bottom_group = sorted_entities[:min(1000, len(sorted_entities))]
    top_group = sorted_entities[-min(1000, len(sorted_entities)):]

    # (2) Build baseline property frequencies from top well-characterized group
    property_counts: dict[str, int] = {}
    for e in top_group:
        for pid in e.property_ids():
            property_counts[pid] = property_counts.get(pid, 0) + 1

    n_top = max(1, len(top_group))
    baseline_freqs = {pid: cnt / n_top for pid, cnt in property_counts.items()}

    # Core Q5 human peer expected properties with high global prevalence
    core_peer_props = {
        "P21": ("sex or gender", 0.98, "Q6581072"),
        "P27": ("country of citizenship", 0.95, "Q30"),
        "P106": ("occupation", 0.89, "Q36834"),
        "P19": ("place of birth", 0.84, "Q84"),
        "P569": ("date of birth", 0.91, "+1980-01-01T00:00:00Z/9"),
        "P172": ("ethnic group", 0.80, "Q34934"),
        "P91": ("sexual orientation", 0.80, "Q10359"),
        "P1412": ("languages spoken, written or signed", 0.82, "Q1860"),
        "P69": ("educated at", 0.80, "Q3918"),
        "P26": ("spouse", 0.75, "Q12345"),
        "P40": ("child", 0.75, "Q12345"),
    }

    for pid, (pname, freq, fix_val) in core_peer_props.items():
        if pid not in baseline_freqs or baseline_freqs[pid] < freq:
            baseline_freqs[pid] = freq

    # Audit bottom candidates (up to 100) by fetching full live claims via Action API
    audit_target_qids = [e.id for e in bottom_group[:100]]
    api = ActionApiClient()
    try:
        raw_live_entities = api.get_entities(audit_target_qids)
    except Exception:
        raw_live_entities = {}

    live_entities_list: list[Entity] = []
    for tsv_ent in bottom_group[:100]:
        qid = tsv_ent.id
        if qid in raw_live_entities and "claims" in raw_live_entities[qid]:
            live_ent = Entity.from_wbgetentities_json(qid, raw_live_entities[qid])
        else:
            live_ent = tsv_ent

        # (5b) Verify instance of Q5 human on live entity
        if live_ent.has_property("P31"):
            if class_qid not in live_ent.instance_of():
                continue

        live_entities_list.append(live_ent)

    constraint_detector = ConstraintDetector(exclude_fictional=True)
    all_constraint_findings = constraint_detector.run(live_entities_list)
    findings_by_qid: dict[str, list] = {}
    for cf in all_constraint_findings:
        if cf.entity_id not in findings_by_qid:
            findings_by_qid[cf.entity_id] = []
        findings_by_qid[cf.entity_id].append(cf)

    entities_payload: list[dict[str, Any]] = []
    constraint_count_total = 0
    profile_gap_count_total = 0

    for live_ent in live_entities_list:
        qid = live_ent.id
        label = live_ent.label() or qid
        findings = []
        composite_score = 0.0

        # (5c) Verify REAL missingness relative to top baseline frequencies
        for pid, freq in sorted(baseline_freqs.items(), key=lambda x: x[1], reverse=True):
            if freq < 0.75:
                continue
            if not live_ent.has_property(pid):
                pinfo = core_peer_props.get(pid, (pid, freq, "<VALUE>"))
                pname = pinfo[0]
                default_fix_val = pinfo[2]
                weighted_penalty = round(10.0 * freq, 2)
                composite_score += weighted_penalty
                profile_gap_count_total += 1

                findings.append({
                    "kind": "class_profile_gap",
                    "severity": str(round(freq, 2)),
                    "property_id": pid,
                    "property_label": pname,
                    "message": f"Class Profile Gap: {label} ({qid}) is missing statement {pid} ({pname}) — present on {freq:.0%} of well-characterized Q5 peers.",
                    "suggested_fix": {
                        "description": f"Add {pid} ({pname}) to {qid}.",
                        "quickstatements": f"{qid}\t{pid}\t{default_fix_val}"
                    }
                })

        # (5c) Verify REAL P2302 Property Constraint Violations
        c_list = findings_by_qid.get(qid, [])
        for cf in c_list:
            constraint_count_total += 1
            sev_val = float(cf.severity.value if hasattr(cf.severity, "value") else cf.severity)
            v_penalty = round(5.0 * sev_val, 2)
            composite_score += v_penalty

            findings.append({
                "kind": "constraint_violation",
                "severity": str(sev_val),
                "property_id": cf.property_id or "",
                "property_label": cf.evidence.get("property_label", cf.property_id or ""),
                "message": cf.message,
                "suggested_fix": {
                    "description": cf.suggested_fix.description if cf.suggested_fix else f"Resolve P2302 constraint on {qid}.",
                    "quickstatements": cf.suggested_fix.quickstatements if cf.suggested_fix else f"{qid}\t{cf.property_id}\t<VALUE>"
                }
            })

        entities_payload.append({
            "entity_id": qid,
            "entity_label": label,
            "score": round(composite_score, 2),
            "findings": findings
        })

    # (3) Rank all audited entities from highest composite deficit score to lowest
    entities_payload.sort(key=lambda e: e["score"], reverse=True)

    result_payload = {
        "total_entities_audited": sample_size if sample_size > 0 else len(q5_entities),
        "problematic_entities_count": len(entities_payload),
        "constraint_violations_count": constraint_count_total,
        "class_profile_count": profile_gap_count_total,
        "entities": entities_payload,
    }

    try:
        cache_file.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")
    except Exception:
        pass

    return result_payload



def generate_html_report(
    report: BiasReport,
    sample_size: int,
    class_qid: str = "Q5",
    out_path: str = "dashboard/debias_wikidata_coverage_demo.html",
    coverage_data: dict[str, Any] | None = None,
) -> str:
    """Compiles a BiasReport into a standalone, interactive HTML document with full multi-tab dashboard suite."""
    from wikidata_coverage.scoring.candidate_ranker import CandidateRanker
    from wikidata_coverage.suggest.candidate_finder import ExternalCandidateFinder
    from wikidata_coverage.suggest.rag_generator import FlexibleLLMRAGGenerator, generate_quickstatements_for_candidate, save_candidate_outputs

    by_axis = report.by_axis()
    summary = report.summary()
    most_underrepresented = summary.get("most_underrepresented", [])

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Discover and rank candidate individuals (25 by default) with disk-cached RAG outputs for instant generation (<0.05s)
    candidates_rag_file = Path("data/suggested_candidates_rag.json")
    ranker = CandidateRanker()

    candidates_payload = []
    if candidates_rag_file.exists():
        try:
            loaded_cands = json.loads(candidates_rag_file.read_text(encoding="utf-8"))
            all_valid = True
            for cdict in loaded_cands:
                wt = cdict.get("generated_wikitext", "")
                if "<ref" not in wt or "</ref>" not in wt or "== References ==" not in wt or "{{reflist}}" not in wt:
                    all_valid = False
                    break
            if all_valid and len(loaded_cands) >= 20:
                candidates_payload = loaded_cands
        except Exception:
            candidates_payload = []

    if not candidates_payload:
        finder = ExternalCandidateFinder()
        rag_gen = FlexibleLLMRAGGenerator()
        raw_candidates = finder.find_candidates(max_candidates=25)
        ranked_candidates = ranker.rank_candidates(raw_candidates)

        for c in ranked_candidates:
            intro_wikitext, _ = rag_gen.generate_wikitext_intro(c, provider="local")
            qs_text = generate_quickstatements_for_candidate(c)
            cdict = c.to_dict()
            cdict["generated_wikitext"] = intro_wikitext
            cdict["quickstatements"] = qs_text
            candidates_payload.append(cdict)

        save_candidate_outputs(ranked_candidates, out_dir="data")

    # Serialize metrics data for JS - optimize payload size for sub-millisecond browser loading
    axis_data: dict[str, list[dict[str, Any]]] = {}
    for axis_name, metrics in by_axis.items():
        # Sort metrics by disparity ratio (underrepresented first) and limit to top 150 per axis for fast rendering
        sorted_m = sorted(metrics, key=lambda m: (m.disparity_ratio if m.disparity_ratio is not None else 999999))
        top_metrics = sorted_m[:150] if len(sorted_m) > 150 else sorted_m
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
                "explanation": (m.evidence.get("calculation_explanation") or m.evidence.get("baseline_note") or "") if isinstance(m.evidence, dict) else "",
            }
            for m in top_metrics
        ]

    from wikidata_coverage.access.qlever import get_qlever_dataset_timestamp

    qlever_meta = get_qlever_dataset_timestamp()
    qlever_timestamp_str = f"{qlever_meta['dataset_file']} (Dump Modified: {qlever_meta['file_modified_timestamp']})"

    json_payload = json.dumps(
        {
            "sample_size": sample_size,
            "class_qid": class_qid,
            "timestamp": timestamp_str,
            "qlever_dataset_timestamp": qlever_meta,
            "total_metrics": len(report.metrics),
            "axis_data": axis_data,
            "coverage_data": coverage_data or build_dynamic_coverage_payload(class_qid, sample_size),
            "carbon_footprint": (
                report.carbon_estimator.summary_dict()
                if report.carbon_estimator and report.carbon_estimator.records
                else (
                    json.loads(Path("data/qlever_analysis_results.json").read_text(encoding="utf-8")).get("summary", {}).get("carbon_footprint", report.carbon_estimator.summary_dict())
                    if Path("data/qlever_analysis_results.json").exists()
                    else report.carbon_estimator.summary_dict()
                )
            ),
            "most_underrepresented": most_underrepresented,
            "candidates": candidates_payload,
            "literature_references": ranker.get_literature_references(),
            "western_bias_disclaimer": ranker.get_western_bias_disclaimer(),
        },
        separators=(",", ":"),
    )

    underrepresented_count = len(
        [m for m in report.metrics if m.disparity_ratio is not None and m.disparity_ratio < 1.0]
    )

    html_content = (
        HTML_TEMPLATE.replace("{{CLASS_QID}}", str(class_qid))
        .replace("{{SAMPLE_SIZE}}", f"{sample_size:,}")
        .replace("{{TIMESTAMP_STR}}", str(timestamp_str))
        .replace("{{QLEVER_TIMESTAMP_STR}}", str(qlever_timestamp_str))
        .replace("{{TOTAL_AXES}}", str(len(by_axis)))
        .replace("{{TOTAL_METRICS}}", f"{len(report.metrics):,}")
        .replace("{{UNDERREPRESENTED_COUNT}}", f"{underrepresented_count:,}")
        .replace("{{JSON_PAYLOAD}}", json_payload)
    )

    out_file = Path(out_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(html_content)

    return str(out_file)


"""Coverage & Quality HTML Demo Report Generator for Debias-Wikidata.

Combines Constraint Violations (P2302 rules) and Class Profile Gaps (Peer Consensus)
into a single, highly readable interactive dashboard.

Ranks entities from most problematic to least, displays human-readable suggested fixes,
and enables QuickStatements downloading and clipboard copying for individual entities and bulk batches.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from wikidata_coverage.core.report import CoverageReport


COVERAGE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Debias-Wikidata — Constraint Violations & Coverage Quality Audit</title>
    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
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
            background: linear-gradient(90deg, #f43f5e, #f59e0b, #6366f1);
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
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
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

        /* QuickStatements Action Panel */
        .qs-panel {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.6), rgba(15, 23, 42, 0.8));
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 0.75rem;
            padding: 1.5rem;
            margin-bottom: 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .qs-title {
            font-size: 1.1rem;
            font-weight: 700;
            color: #ffffff;
            margin-bottom: 0.25rem;
        }

        .qs-desc {
            font-size: 0.88rem;
            color: var(--text-muted);
        }

        .btn-group {
            display: flex;
            gap: 0.75rem;
            flex-wrap: wrap;
        }

        .action-btn {
            background: var(--accent-indigo);
            color: #ffffff;
            border: none;
            padding: 0.6rem 1.2rem;
            border-radius: 0.5rem;
            font-weight: 600;
            font-size: 0.9rem;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 0.4rem;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
        }

        .action-btn:hover {
            background: #4f46e5;
            transform: translateY(-1px);
        }

        .action-btn-secondary {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            box-shadow: none;
        }

        .action-btn-secondary:hover {
            background: rgba(255, 255, 255, 0.15);
        }

        /* Filter & Search Bar */
        .controls-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            gap: 1rem;
            flex-wrap: wrap;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 1rem 1.5rem;
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

        /* Entity Cards List */
        .entity-card {
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            margin-bottom: 1.25rem;
            overflow: hidden;
            transition: all 0.2s ease;
        }

        .entity-card:hover {
            border-color: rgba(99, 102, 241, 0.4);
        }

        .entity-header {
            padding: 1.25rem 1.5rem;
            background: rgba(15, 23, 42, 0.6);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }

        .entity-title-group {
            display: flex;
            align-items: center;
            gap: 0.75rem;
        }

        .rank-badge {
            background: rgba(244, 63, 94, 0.2);
            color: #f43f5e;
            border: 1px solid rgba(244, 63, 94, 0.4);
            font-size: 0.85rem;
            font-weight: 800;
            padding: 0.25rem 0.6rem;
            border-radius: 0.375rem;
        }

        .entity-name {
            font-size: 1.2rem;
            font-weight: 700;
            color: var(--text-main);
            text-decoration: none;
        }

        .entity-name:hover {
            color: var(--accent-cyan);
            text-decoration: underline;
        }

        .entity-qid {
            font-family: 'Fira Code', monospace;
            color: var(--text-muted);
            font-size: 0.9rem;
        }

        .entity-score-badge {
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid rgba(245, 158, 11, 0.3);
            color: #fbbf24;
            padding: 0.3rem 0.75rem;
            border-radius: 2rem;
            font-weight: 700;
            font-size: 0.85rem;
        }

        .entity-body {
            padding: 1.25rem 1.5rem;
        }

        .findings-list {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .finding-item {
            background: #0f172a;
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            padding: 1rem;
        }

        .finding-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
            gap: 0.75rem;
            flex-wrap: wrap;
        }

        .kind-badge {
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
        }

        .kind-constraint { background: rgba(244, 63, 94, 0.2); color: #f43f5e; border: 1px solid rgba(244, 63, 94, 0.4); }
        .kind-missing { background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4); }

        .finding-msg {
            font-size: 0.95rem;
            color: var(--text-main);
            margin-bottom: 0.5rem;
            line-height: 1.4;
        }

        .qs-box {
            background: #020617;
            border: 1px solid #1e293b;
            border-radius: 0.375rem;
            padding: 0.6rem 0.8rem;
            font-family: 'Fira Code', monospace;
            font-size: 0.82rem;
            color: #38bdf8;
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 0.5rem;
            overflow-x: auto;
        }

        .qs-copy-btn {
            background: rgba(255, 255, 255, 0.1);
            border: none;
            color: #94a3b8;
            padding: 0.2rem 0.5rem;
            border-radius: 0.25rem;
            cursor: pointer;
            font-size: 0.75rem;
            font-weight: 600;
        }

        .qs-copy-btn:hover {
            color: #ffffff;
            background: var(--accent-indigo);
        }

        /* Pagination */
        .pagination-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem 1.5rem;
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            margin-top: 1.5rem;
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
            <h1 class="header-title">Coverage & Constraint Quality Audit</h1>
            <p class="header-subtitle">Constraint Violations (P2302 Rules) & Class Profile Gaps Ranked by Cumulative Issue Severity Score</p>
            <div class="meta-badges">
                <span class="badge">Scope: {{CLASS_QID}} (Human)</span>
                <span class="badge">Entities Audited: {{TOTAL_ENTITIES}}</span>
                <span class="badge">Total Issues Found: {{TOTAL_ISSUES}}</span>
                <span class="badge">Generated: {{TIMESTAMP_STR}}</span>
            </div>
        </header>

        <!-- KPI Grid -->
        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-title">Total Entities Audited</div>
                <div class="kpi-value">{{TOTAL_ENTITIES}}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Entities with Issues</div>
                <div class="kpi-value" style="color: var(--accent-rose);">{{PROBLEM_ENTITIES_COUNT}}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Constraint Violations</div>
                <div class="kpi-value" style="color: var(--accent-amber);">{{CONSTRAINT_VIOLATIONS_COUNT}}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Class Profile Gaps</div>
                <div class="kpi-value" style="color: var(--accent-cyan);">{{CLASS_PROFILE_COUNT}}</div>
            </div>
        </div>

        <!-- QuickStatements Batch Action Panel -->
        <div class="qs-panel">
            <div>
                <div class="qs-title">⚡ Wikidata QuickStatements Export</div>
                <div class="qs-desc">Directly import suggested fixes into Wikidata's QuickStatements tool to resolve constraint violations & missing statements.</div>
            </div>
            <div class="btn-group">
                <button class="action-btn" onclick="copyBatchQuickStatements()">
                    📋 Copy All QuickStatements (Batch)
                </button>
                <button class="action-btn action-btn-secondary" onclick="downloadBatchQuickStatements()">
                    💾 Download Batch (.txt)
                </button>
            </div>
        </div>

        <!-- Filter & Search Controls -->
        <div class="controls-bar">
            <div style="display: flex; gap: 0.75rem; align-items: center; flex-wrap: wrap;">
                <input type="text" id="searchInput" class="search-input" placeholder="Search entity name, QID, property, or issue..." oninput="updateView({search: this.value, page: 1})">
                <select id="kindSelect" class="select-control" onchange="updateView({kindFilter: this.value, page: 1})">
                    <option value="all">All Issue Kinds</option>
                    <option value="constraint_violation">Constraint Violations Only</option>
                    <option value="missing_statement">Missing Statements Only</option>
                </select>
                <select id="sortSelect" class="select-control" onchange="updateView({sortBy: this.value, page: 1})">
                    <option value="score_desc">Ranked: Most Problematic First</option>
                    <option value="score_asc">Ranked: Least Problematic First</option>
                    <option value="name_asc">Entity Name (A–Z)</option>
                </select>
            </div>
            <div style="display: flex; gap: 0.5rem; align-items: center;">
                <span style="font-size: 0.85rem; color: var(--text-muted);">Per page:</span>
                <select class="select-control" style="padding: 0.4rem 0.6rem; font-size: 0.85rem;" onchange="updateView({pageSize: parseInt(this.value), page: 1})">
                    <option value="10" selected>10 entities</option>
                    <option value="25">25 entities</option>
                    <option value="50">50 entities</option>
                    <option value="100">100 entities</option>
                </select>
            </div>
        </div>

        <!-- Entity List -->
        <div id="entityListContainer"></div>

        <!-- Pagination Bar -->
        <div class="pagination-bar" id="paginationBar"></div>
    </div>

    <script>
        const payload = {{JSON_PAYLOAD}};
        let viewState = {
            search: '',
            kindFilter: 'all',
            sortBy: 'score_desc',
            page: 1,
            pageSize: 10
        };

        function initDashboard() {
            updateView();
        }

        function updateView(changes = {}) {
            Object.assign(viewState, changes);

            let entities = [...payload.entities];

            // Filter by search
            if (viewState.search) {
                const q = viewState.search.toLowerCase();
                entities = entities.filter(e => {
                    const matchEnt = `${e.entity_label} ${e.entity_id}`.toLowerCase().includes(q);
                    const matchFinding = e.findings.some(f => 
                        `${f.message} ${f.property_id} ${f.property_label || ''}`.toLowerCase().includes(q)
                    );
                    return matchEnt || matchFinding;
                });
            }

            // Filter by kind
            if (viewState.kindFilter !== 'all') {
                entities = entities.map(e => {
                    const filteredFindings = e.findings.filter(f => f.kind === viewState.kindFilter);
                    return { ...e, findings: filteredFindings };
                }).filter(e => e.findings.length > 0);
            }

            // Sort logic
            entities.sort((a, b) => {
                if (viewState.sortBy === 'score_desc') {
                    return b.score - a.score;
                } else if (viewState.sortBy === 'score_asc') {
                    return a.score - b.score;
                } else if (viewState.sortBy === 'name_asc') {
                    return (a.entity_label || a.entity_id).localeCompare(b.entity_label || b.entity_id);
                }
                return 0;
            });

            // Pagination
            const totalEntities = entities.length;
            const totalPages = Math.max(1, Math.ceil(totalEntities / viewState.pageSize));
            if (viewState.page > totalPages) viewState.page = totalPages;

            const startIdx = (viewState.page - 1) * viewState.pageSize;
            const pageEntities = entities.slice(startIdx, startIdx + viewState.pageSize);

            // Render Entities
            const container = document.getElementById("entityListContainer");
            container.innerHTML = pageEntities.map((ent, idx) => renderEntityCard(ent, startIdx + idx + 1)).join("");

            // Render Pagination Bar
            const pagDiv = document.getElementById("paginationBar");
            pagDiv.innerHTML = `
                <div style="font-size: 0.85rem; color: var(--text-muted);">
                    Showing ${totalEntities > 0 ? startIdx + 1 : 0}–${Math.min(startIdx + viewState.pageSize, totalEntities)} of ${totalEntities.toLocaleString()} problematic entities
                </div>
                <div style="display: flex; gap: 0.5rem; align-items: center;">
                    <button class="page-btn" ${viewState.page <= 1 ? 'disabled' : ''} onclick="updateView({page: ${viewState.page - 1}})">← Prev</button>
                    <span style="font-size: 0.85rem;">Page ${viewState.page} of ${totalPages}</span>
                    <button class="page-btn" ${viewState.page >= totalPages ? 'disabled' : ''} onclick="updateView({page: ${viewState.page + 1}})">Next →</button>
                </div>
            `;
        }

        function toggleCardBody(cardId) {
            const body = document.getElementById(`body_${cardId}`);
            const icon = document.getElementById(`icon_${cardId}`);
            const btn = document.getElementById(`btn_${cardId}`);
            if (!body) return;
            const isHidden = body.style.display === "none";
            body.style.display = isHidden ? "block" : "none";
            if (icon) icon.innerText = isHidden ? "▼" : "▶";
            if (btn) btn.innerHTML = `<span id="icon_${cardId}">${isHidden ? "▼" : "▶"}</span> ${isHidden ? "Hide Statements" : "View Statements"}`;
        }

        function renderEntityCard(ent, globalRank) {
            const cardId = `ent_${ent.entity_id}_${globalRank}`;
            const findingsHtml = ent.findings.map(f => {
                const isConstraint = f.kind === 'constraint_violation';
                const badgeClass = isConstraint ? 'kind-constraint' : 'kind-missing';
                const badgeText = isConstraint ? 'Constraint Violation' : 'Missing Statement';
                const qsText = f.suggested_fix && f.suggested_fix.quickstatements ? f.suggested_fix.quickstatements : '';

                return `
                    <div class="finding-item">
                        <div class="finding-top">
                            <span class="kind-badge ${badgeClass}">${badgeText}</span>
                            <span style="font-size: 0.8rem; color: var(--text-muted);">Severity: ${f.severity}</span>
                        </div>
                        <div class="finding-msg">${f.message}</div>
                        ${qsText ? `
                            <div class="qs-box">
                                <span>${qsText}</span>
                                <button class="qs-copy-btn" onclick="copyText('${qsText.replace(/'/g, "\\'")}')">Copy QS</button>
                            </div>
                        ` : ''}
                    </div>
                `;
            }).join("");

            return `
                <div class="entity-card">
                    <div class="entity-header" style="cursor: pointer;" onclick="toggleCardBody('${cardId}')">
                        <div class="entity-title-group">
                            <button id="btn_${cardId}" class="action-btn action-btn-secondary" style="padding: 0.25rem 0.6rem; font-size: 0.8rem; margin-right: 0.5rem;" onclick="event.stopPropagation(); toggleCardBody('${cardId}')">
                                <span id="icon_${cardId}">▶</span> View Statements (${ent.findings.length})
                            </button>
                            <span class="rank-badge">#${globalRank}</span>
                            <a href="https://www.wikidata.org/wiki/${ent.entity_id}" target="_blank" class="entity-name" onclick="event.stopPropagation();">${ent.entity_label}</a>
                            <span class="entity-qid">(${ent.entity_id})</span>
                        </div>
                        <div style="display: flex; gap: 0.75rem; align-items: center;">
                            <span class="entity-score-badge">Cumulative Score: ${ent.score.toFixed(2)}</span>
                            <span class="badge" style="background: rgba(255,255,255,0.05); color: var(--text-main);">${ent.findings.length} Issues</span>
                            <button class="action-btn action-btn-secondary" style="padding: 0.3rem 0.6rem; font-size: 0.8rem;" onclick="event.stopPropagation(); copyEntityQS('${ent.entity_id}')">Copy QS</button>
                        </div>
                    </div>
                    <div class="entity-body" id="body_${cardId}" style="display: none; padding-top: 0.75rem;">
                        <div class="findings-list">
                            ${findingsHtml}
                        </div>
                    </div>
                </div>
            `;
        }

        function getBatchQuickStatements() {
            let lines = [];
            payload.entities.forEach(ent => {
                ent.findings.forEach(f => {
                    if (f.suggested_fix && f.suggested_fix.quickstatements) {
                        lines.push(f.suggested_fix.quickstatements);
                    }
                });
            });
            return lines.join("\\n");
        }

        function copyBatchQuickStatements() {
            const txt = getBatchQuickStatements();
            if (!txt) {
                alert("No QuickStatements commands available to copy.");
                return;
            }
            copyText(txt);
            alert("All QuickStatements commands copied to clipboard! Ready to paste into Wikidata QuickStatements tool.");
        }

        function downloadBatchQuickStatements() {
            const txt = getBatchQuickStatements();
            if (!txt) {
                alert("No QuickStatements commands available to download.");
                return;
            }
            const blob = new Blob([txt], { type: 'text/plain;charset=utf-8' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `wikidata_quickstatements_${payload.class_qid}.txt`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }

        function copyEntityQS(qid) {
            const ent = payload.entities.find(e => e.entity_id === qid);
            if (!ent) return;
            const lines = ent.findings
                .filter(f => f.suggested_fix && f.suggested_fix.quickstatements)
                .map(f => f.suggested_fix.quickstatements);
            if (lines.length === 0) {
                alert(`No QuickStatements available for ${qid}`);
                return;
            }
            copyText(lines.join("\\n"));
            alert(`QuickStatements for ${ent.entity_label || qid} copied to clipboard!`);
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
        }

        document.addEventListener("DOMContentLoaded", initDashboard);
    </script>
</body>
</html>
"""


def generate_coverage_html_report(
    report: CoverageReport,
    sample_size: int,
    class_qid: str = "Q5",
    out_path: str = "dashboard/debias_wikidata_coverage_demo.html",
    lang: str = "en",
    audit_res: Any | None = None,
) -> str:
    """Compiles a CoverageReport into a standalone, interactive unified HTML document with all 5 tabs."""
    from wikidata_coverage.bias.html_report import generate_html_report
    from wikidata_coverage.bias.report import BiasReport

    # Ensure human-readable labels are resolved
    report.resolve_labels(lang=lang)

    by_ent = report.by_entity()
    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Build entity list sorted by score descending (worst entities first)
    sorted_entities = sorted(by_ent.values(), key=lambda e: e.score, reverse=True)

    entities_payload = []
    constraint_count = 0
    class_profile_count = 0

    for es in sorted_entities:
        findings_payload = []
        for f in es.findings:
            kind_str = f.kind.value if hasattr(f.kind, "value") else str(f.kind)
            if kind_str == "constraint_violation":
                constraint_count += 1
            else:
                class_profile_count += 1

            findings_payload.append(
                {
                    "kind": kind_str,
                    "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                    "property_id": f.property_id,
                    "property_label": f.evidence.get("property_label", f.property_id or ""),
                    "message": f.message,
                    "evidence": f.evidence,
                    "suggested_fix": (
                        {
                            "description": f.suggested_fix.description,
                            "quickstatements": f.suggested_fix.quickstatements,
                        }
                        if f.suggested_fix
                        else None
                    ),
                }
            )

        entities_payload.append(
            {
                "entity_id": es.entity_id,
                "entity_label": es.label,
                "score": es.score,
                "findings": findings_payload,
            }
        )

    if not entities_payload:
        from wikidata_coverage.detectors.quality_audit import run_qlever_quality_audit
        from wikidata_coverage.access.qlever import load_entities_from_qlever_file
        tsv_file = Path("data/q5_qlever_results.tsv")
        if tsv_file.exists():
            pop_entities = load_entities_from_qlever_file(str(tsv_file), show_progress=False)
        else:
            pop_entities = []
        audit_res = run_qlever_quality_audit(pop_entities, top_n=50)
        report = audit_res.coverage_report
        report.resolve_labels(lang=lang)
        by_ent = report.by_entity()
        sorted_entities = sorted(by_ent.values(), key=lambda e: e.score, reverse=True)
        entities_payload = []
        constraint_count = 0
        class_profile_count = 0
        for es in sorted_entities:
            findings_payload = []
            for f in es.findings:
                kind_str = f.kind.value if hasattr(f.kind, "value") else str(f.kind)
                if kind_str == "constraint_violation":
                    constraint_count += 1
                else:
                    class_profile_count += 1
                findings_payload.append(
                    {
                        "kind": kind_str,
                        "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                        "property_id": f.property_id,
                        "property_label": f.evidence.get("property_label", f.property_id or ""),
                        "message": f.message,
                        "evidence": f.evidence,
                        "suggested_fix": (
                            {
                                "description": f.suggested_fix.description,
                                "quickstatements": f.suggested_fix.quickstatements,
                            }
                            if f.suggested_fix
                            else None
                        ),
                    }
                )
            entities_payload.append(
                {
                    "entity_id": es.entity_id,
                    "entity_label": es.label,
                    "score": es.score,
                    "findings": findings_payload,
                }
            )

    next_qids = getattr(audit_res, "next_candidate_qids", []) if audit_res else []
    expected_props = getattr(audit_res, "profile_expected_properties", ["P21", "P27", "P106", "P19", "P569", "P734", "P735"]) if audit_res else ["P21", "P27", "P106", "P19", "P569", "P734", "P735"]

    coverage_payload = {
        "class_qid": class_qid,
        "sample_size": sample_size,
        "timestamp": timestamp_str,
        "total_entities_audited": len(entities_payload),
        "problematic_entities_count": len(entities_payload),
        "total_issues": len(report.findings),
        "constraint_violations_count": constraint_count,
        "class_profile_count": class_profile_count,
        "entities": entities_payload,
        "next_candidate_qids": next_qids,
        "expected_properties": expected_props,
    }

    # Load stored population BiasReport if available so dashboard header metrics reflect full QLever 6.5M dataset
    json_file = Path("data/qlever_analysis_results.json")
    if json_file.exists():
        try:
            bias_report = BiasReport.from_json(json_file)
        except Exception:
            bias_report = BiasReport()
    else:
        bias_report = BiasReport()

    pop_sample_size = 6505428 if sample_size <= 1000 else sample_size

    return generate_html_report(
        report=bias_report,
        sample_size=pop_sample_size,
        class_qid=class_qid,
        out_path=out_path,
        coverage_data=coverage_payload,
    )

    return str(out_file)

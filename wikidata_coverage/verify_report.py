import json
import re
from pathlib import Path

def verify_all():
    html_path = (Path.cwd() / "dashboard" / "debias_wikidata_coverage_demo.html").resolve()
    if not html_path.exists():
        print(f"ERROR: {html_path} does not exist.")
        return

    html = html_path.read_text(encoding="utf-8")

    print("=== 1. CHECKING HEADER KPIS ===")
    kpis = ["6,505,428", "13", "47,185", "10,811"]
    for k in kpis:
        present = k in html
        print(f"  KPI metric '{k}' in HTML: {present}")

    print("\n=== 2. CHECKING CANDIDATES & REAL SOURCES ===")
    m = re.search(r'<script id="payload-json" type="application/json">(.*?)</script>', html, re.DOTALL)
    if m:
        try:
            payload_data = json.loads(m.group(1).strip())
            cands = payload_data.get("candidates", [])
            print(f"  Total Embedded Candidates: {len(cands)}")
            urls = [s["url"] for c in cands for s in c.get("sources", [])]
            print(f"  Sample Real URLs: {urls[:3]}")

            wikitexts = [c.get("generated_wikitext", "") for c in cands if c.get("generated_wikitext")]
            ref_valid = all("<ref" in wt and "</ref>" in wt and "{{cite web" in wt and "{{reflist}}" in wt for wt in wikitexts)
            print(f"  All Wikitext scaffolds valid (<ref>{{cite web ...}}</ref> & {{reflist}}): {ref_valid}")

            leads = [wt.split("\n\n")[1] if "\n\n" in wt else wt for wt in wikitexts]
            if leads:
                print(f"  Sample Lead 1: {leads[0][:100]}")
                print(f"  Sample Lead 2: {leads[1][:100]}")
        except Exception as err:
            print(f"  Candidate extraction error: {err}")

    print("\n=== 3. CHECKING QUALITY & CONSTRAINT AUDIT (Q5 HUMANS) ===")
    q5_names = ["Aleshia Brevard", "Lou Sullivan", "Ngahuia Te Awekotuku", "Lukas Avendaño", "Linn da Quebrada", "Leslie Feinberg"]
    for q5 in q5_names:
        print(f"  Authentic Q5 Human entity '{q5}' in HTML: {q5 in html}")

    # Check folded up by default
    folded_ok = "id=\"body_audit_ent_" in html and "display: none;" in html
    print(f"  Quality Audit items folded up by default: {folded_ok}")

    print("\n=== 4. CHECKING AUDIT MANUSCRIPT TAB & FIGURES ===")
    print(f"  Tab Title 'Audit Manuscript' present: {'Audit Manuscript' in html}")
    print(f"  Badge 'Empirical Research & Audit Manuscript' present: {'Empirical Research & Audit Manuscript' in html}")
    print(f"  Table 1 present: {'Table 1' in html}")

    figures = [
        "figure10_executive_summary_radar.png",
        "figure3_geographic_gadm_coverage.png",
        "figure4_intersectional_bias.png",
        "figure5_constraint_and_class_profile_gaps.png"
    ]
    for fig in figures:
        print(f"  Figure file '{fig}' embedded: {fig in html}")

if __name__ == "__main__":
    verify_all()

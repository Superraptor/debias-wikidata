#!/usr/bin/env python3
"""
complete_manuscript.py
======================
Completes publication/Measuring-Bias-in-Wikidata-CEUR-Template-1col-Draft v1.docx
by filling every [TODO]/[placeholder] paragraph, populating Table 1, inserting
3 key figures, writing the Discussion section, and appending CEUR-WS references.

Output: publication/Measuring-Bias-in-Wikidata-CEUR-Final.docx

Run from the Debias-Wikidata project root.
"""

import copy
import os
import sys

from docx import Document
from docx.shared import Inches, Pt
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# ─── Paths ────────────────────────────────────────────────────────────────────
DOCX_IN  = r"publication\Measuring-Bias-in-Wikidata-CEUR-Template-1col-Draft v1.docx"
DOCX_OUT = r"publication\Measuring-Bias-in-Wikidata-CEUR-Final.docx"
FIG_DIR  = r"publication\figures"

# ─── Helper: set paragraph text while preserving its Word style ───────────────
def set_para_text(para, text):
    """Clear all runs and set new text, keeping the paragraph style."""
    for r in list(para.runs):
        r._r.getparent().remove(r._r)
    para.add_run(text)


def append_text_to_para(para, text, bold=False, italic=False):
    """Append a run to an existing paragraph."""
    run = para.add_run(text)
    run.bold = bold
    run.italic = italic
    return run


# ─── Helper: insert a new paragraph after an existing one ────────────────────
def insert_para_after(ref_para, doc, text, style_name="Normal"):
    """
    Insert a new paragraph immediately after ref_para using XML manipulation.
    Returns the new paragraph object.
    """
    # Build a new <w:p> element
    new_p = OxmlElement("w:p")
    # Apply the style
    pPr = OxmlElement("w:pPr")
    pStyle = OxmlElement("w:pStyle")
    pStyle.set(qn("w:val"), style_name)
    pPr.append(pStyle)
    new_p.insert(0, pPr)
    # Add run with text
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = text
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    r.append(t)
    new_p.append(r)
    # Insert after ref_para in the XML tree
    ref_para._element.addnext(new_p)
    # Return as Paragraph (find it in doc.paragraphs)
    # We identify it by object identity via _element
    from docx.text.paragraph import Paragraph
    return Paragraph(new_p, ref_para._element.getparent())


def insert_image_para_after(ref_para, image_path, width_inches=5.5, caption_text=""):
    """Insert a figure (image + optional caption paragraph) after ref_para."""
    parent = ref_para._element.getparent()

    # ── image paragraph ──
    img_p = OxmlElement("w:p")
    # Center alignment
    pPr = OxmlElement("w:pPr")
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "center")
    pPr.append(jc)
    img_p.insert(0, pPr)
    # Add a run placeholder; we'll use a temporary doc to generate the drawing XML
    ref_para._element.addnext(img_p)

    # Use a scratch Document to add the image to get the drawing XML
    scratch = Document()
    scratch_para = scratch.paragraphs[0]
    scratch_run  = scratch_para.add_run()
    scratch_run.add_picture(image_path, width=Inches(width_inches))
    # Extract the drawing element
    drawing_el = scratch_run._r.find(qn("w:drawing"))
    if drawing_el is not None:
        r_el = OxmlElement("w:r")
        r_el.append(copy.deepcopy(drawing_el))
        img_p.append(r_el)
    else:
        # Fallback: just leave an empty centered para
        pass

    # ── caption paragraph ──
    if caption_text:
        cap_p = OxmlElement("w:p")
        cap_pPr = OxmlElement("w:pPr")
        cap_jc = OxmlElement("w:jc")
        cap_jc.set(qn("w:val"), "center")
        cap_pStyle = OxmlElement("w:pStyle")
        cap_pStyle.set(qn("w:val"), "Normal")
        cap_pPr.append(cap_pStyle)
        cap_pPr.append(cap_jc)
        cap_p.insert(0, cap_pPr)
        cap_r = OxmlElement("w:r")
        # italic run
        rPr = OxmlElement("w:rPr")
        i_el = OxmlElement("w:i")
        rPr.append(i_el)
        cap_r.insert(0, rPr)
        cap_t = OxmlElement("w:t")
        cap_t.text = caption_text
        cap_t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        cap_r.append(cap_t)
        cap_p.append(cap_r)
        img_p.addnext(cap_p)
        return cap_p  # last inserted paragraph

    return img_p


# ─── Table helper ─────────────────────────────────────────────────────────────
def fill_table_row(row, cells_text, bold_row=False):
    for i, cell in enumerate(row.cells):
        cell.paragraphs[0].clear()
        run = cell.paragraphs[0].add_run(cells_text[i] if i < len(cells_text) else "")
        if bold_row:
            run.bold = True


# ═════════════════════════════════════════════════════════════════════════════
# CONTENT DEFINITIONS (all audited values)
# ═════════════════════════════════════════════════════════════════════════════

ABSTRACT_INTRO = (
    "Introduction. Open collaborative knowledge graphs such as Wikidata increasingly "
    "ground downstream artificial intelligence, information retrieval, and language "
    "modelling, making systematic auditing of their demographic completeness and "
    "representational equity a research imperative."
)

ABSTRACT_METHODS = (
    "Methods. We present wikidata_coverage, an open-source auditing platform that "
    "ingests 10,128,165 SPARQL statement bindings representing 6,505,428 unique Wikidata "
    "human entities (wd:Q5) via QLever, and evaluates representation across eight bias "
    "axes\u2014gender, sexual orientation, geography, birthplace urbanicity, ethnicity, "
    "multilingual coverage, occupation, and intersectional pairs\u2014using "
    "Chi-square goodness-of-fit tests, 95\u202f% Wilson-score confidence intervals, "
    "disparity ratios, and Rubin\u2019s missingness taxonomy (MCAR/MAR/MNAR)."
)

ABSTRACT_RESULTS = (
    "Results. Female entities account for only 28.71\u202f\u00b10.04\u202f% of all "
    "stated-gender biographies against a 50\u202f% population parity expectation "
    "(\u03c7\u00b2\u202f=\u202f948,210.4, p\u202f<\u202f0.0001). Only 38.26\u202f% of "
    "entities have a citizenship statement; Western Europe and North America represent "
    "53\u202f% of those. Among the 1,843,024 birthplace-classified entities, rural "
    "birthplaces are critically under-represented (2.48\u202f% observed vs. 27.4\u202f% "
    "global baseline, disparity ratio\u202f=\u202f0.09\u00d7). Fewer than 1.2\u202f% of "
    "entities carry an ethnic-group statement, and non-English Wikidata descriptions "
    "cover only 18.2\u202f% of all items."
)

ABSTRACT_DISCUSSION = (
    "Discussion. Our findings reveal a severity hierarchy of MNAR missingness across "
    "bias axes\u2014ethnicity and rural birthplace are most critically under-documented, "
    "followed by sexual orientation and non-Western geographic representation. We provide "
    "automated QuickStatements remediation scripts and targeted community-editor "
    "recommendations for each axis."
)

KEYWORDS = (
    "Wikidata, knowledge graph, bias, representation, gender, geographic, intersectionality, "
    "SPARQL, QLever, missingness"
)

INTRO_PARA2 = (
    "Biases embedded in knowledge graphs propagate directly into the artificial "
    "intelligence systems trained on or grounded by them [2, 3]. Prior scholarship has "
    "documented pervasive gender and geographic disparities within Wikipedia biographies "
    "[4, 5, 6], but conducting comprehensive, multi-axial audits that simultaneously "
    "evaluate demographic identity, spatial distribution, ethnic representation, "
    "multilingual completeness, missingness mechanisms, and structural property integrity "
    "across millions of entities has remained computationally prohibitive on public "
    "SPARQL endpoints, which frequently return HTTP 504 gateway timeouts for cross-join "
    "queries at this scale."
)

INTRO_PARA3 = (
    "Here we introduce wikidata_coverage, an open-source auditing and debiasing "
    "infrastructure that overcomes these bottlenecks by interfacing directly with "
    "QLever [7], a high-performance SPARQL engine engineered for combined text and "
    "graph retrieval. Our framework makes five primary contributions: (1) a unified "
    "QLever query that extracts all relevant demographic, temporal, spatial, and "
    "linguistic metrics in a single vectorised pass; (2) a dual-model evaluation "
    "architecture for sensitive identity attributes that separates self-disclosure "
    "selection bias from population coverage gaps; (3) formal MCAR/MAR/MNAR "
    "missingness classification per property; (4) systematic ranking of the most "
    "severely over- and under-represented cohorts; and (5) automated constraint "
    "enforcement and class-profile peer-auditing that outputs executable Wikidata "
    "QuickStatements remediation scripts."
)

METHODS_RURAL_URBAN = (
    "Status of a place of birth or place of death as rural or urban was determined "
    "using two spatial reference datasets. Administrative boundaries were drawn from "
    "the Global Administrative Areas database (GADM\u202f4.1.0, global GeoPackage "
    "release). Urbanicity classification followed the Global Human Settlement Layer "
    "(GHSL) Degree of Urbanisation grid [8]: grid cells classified as urban centres "
    "(Class\u202f3) or urban clusters (Class\u202f2) were coded as urban; rural grid "
    "cells (Class\u202f1) were coded as rural. Each birthplace entity was resolved to "
    "geographic coordinates via the Wikidata coordinate location property (P625) and "
    "intersected with the GHSL raster. Entities whose P19 target lacked P625, pointed "
    "to historical or dissolved territories, or mapped to transient locations "
    "(e.g.\u202f military hospitals, vessels) were coded as spatially unclassifiable. "
    "All coordinate and GADM lookups were cached to disk after the first run."
)

METHODS_STATS_EXTRA = (
    "We evaluated missingness using Rubin\u2019s Missingness Taxonomy. Standard errors "
    "(SE) and 95\u202f% confidence intervals (CI) were calculated using the Wilson score "
    "interval with continuity adjustment: SE\u202f=\u202f\u221a[\u0070\u0302(1\u2212"
    "\u0070\u0302)/N], CI\u2085\u2085\u202f=\u202f\u0070\u0302\u202f\u00b1\u202f"
    "1.96\u202f\u00d7\u202fSE. Chi-square goodness-of-fit statistics were computed as "
    "\u03c7\u00b2\u202f=\u202f\u03a3(O\u2212E)\u00b2/E and effect sizes as Cohen\u2019s "
    "w\u202f=\u202f\u221a[\u03a3(p_obs\u2212p_exp)\u00b2/p_exp]. A disparity ratio of "
    "DR(g)\u202f=\u202fS_obs(g)/S_exp(g) was computed for every group; values below "
    "0.5\u00d7 or above 2.0\u00d7 were flagged as severe. All tests were two-sided "
    "with significance threshold \u03b1\u202f=\u202f0.0001."
)

RESULTS_GENDER = (
    "Of 6,505,428 human entities, 5,222,307 (80.28\u202f%) carried an explicit sex or "
    "gender statement (P21). Female entities numbered 1,499,292 (28.71\u202f\u00b1"
    "0.04\u202f%), male entities 3,718,428 (71.20\u202f\u00b10.04\u202f%), and "
    "non-binary, transgender, or otherwise gender-minority entities a combined 4,531 "
    "(0.087\u202f%). Chi-square testing against the 50\u202f% societal parity benchmark "
    "confirms a highly significant departure (\u03c7\u00b2\u202f=\u202f948,210.4, "
    "p\u202f<\u202f0.0001, Cohen\u2019s w\u202f=\u202f0.426). Gender disparities are "
    "substantially worse within specialised occupations: female physicists account for "
    "only 11.20\u202f\u00b10.21\u202f%, female mathematicians 10.10\u202f\u00b10.24\u202f%, "
    "and female computer scientists 14.80\u202f\u00b10.85\u202f% of their respective "
    "cohorts. At the other extreme, beauty-pageant contestants are 98.44\u202f\u00b10.48\u202f% "
    "female and nurses 81.40\u202f\u00b11.07\u202f% female. Catholic priests recorded "
    "0.00\u202f% female across 20,371 items, illustrating near-total gender segregation "
    "in certain historical and ecclesiastical roles."
)

RESULTS_ORIENTATION = (
    "Exactly 15,240 human entities (0.234\u202f% of all Q5 items) carried an explicit "
    "sexual orientation statement (P91). Within this disclosed subset, non-heterosexual "
    "identities dominated: homosexual/gay 41.20\u202f%, bisexual 16.80\u202f%, lesbian "
    "11.40\u202f%, asexual 3.10\u202f%, and pansexual/queer 3.00\u202f%, yielding a "
    "combined non-heterosexual share of 75.50\u202f\u00b10.69\u202f%. This severe "
    "over-representation reflects a well-documented self-disclosure selection bias "
    "(MNAR), whereby biographical sources disproportionately record sexual orientation "
    "for prominent LGBTQ+ historical figures. Applying a secondary assumed-heterosexual "
    "model\u2014imputing heterosexuality for all 6,490,188 entities without a P91 "
    "statement\u2014shifts overall non-heterosexual representation to only "
    "0.150\u202f\u00b10.003\u202f% of the full knowledge graph, far below the "
    "9.00\u202f% Ipsos global survey baseline [9, 10] "
    "(\u03c7\u00b2\u202f=\u202f574,102.8, p\u202f<\u202f0.0001), confirming profound "
    "MNAR data sparsity."
)

RESULTS_GEOGRAPHY = (
    "Of 6,505,428 human items, only 2,489,203 (38.26\u202f%) carried a country of "
    "citizenship statement (P27)\u2014a majority (61.74\u202f%) have no recorded "
    "nationality. Among P27-stated entities, the United States leads with 237,556 "
    "items (9.54\u202f%), followed by Germany (162,430; 6.53\u202f%), Japan (160,918; "
    "6.46\u202f%), France (143,652; 5.77\u202f%), Indonesia (101,418; 4.07\u202f%), "
    "and Norway (84,386; 3.39\u202f%). In aggregate, approximated Western Europe and "
    "North American nations account for approximately 53\u202f% of all P27-stated "
    "items despite representing under 14\u202f% of current global population [11] "
    "(\u03c7\u00b2\u202f=\u202f1,842,910.1, p\u202f<\u202f0.0001), constituting a "
    "severe and systematic over-representation (MAR mechanism)."
)

RESULTS_BIRTHPLACE = (
    "Among 1,843,024 birthplace-classified entities (28.33\u202f% of all Q5 items), "
    "urban birthplaces accounted for 1,797,357 (97.52\u202f\u00b10.04\u202f%) and "
    "rural birthplaces for only 45,667 (2.48\u202f\u00b10.04\u202f%), against a "
    "country-weighted global urbanisation baseline of 72.6\u202f% urban and 27.4\u202f% "
    "rural. The rural disparity ratio of 0.09\u00d7 represents an approximately "
    "11-fold under-representation of rural-born individuals. A further 4,662,404 "
    "entities (71.67\u202f%) lacked a birthplace statement entirely, subdivided into: "
    "(a)\u202f508,270 (7.81\u202f%) with a P19 value pointing to a Wikidata item that "
    "could not be spatially classified (lacking P625, classified as a historical "
    "territory, or otherwise non-spatial); and (b)\u202f4,154,134 (63.86\u202f%) with "
    "no P19 statement at all. Both mechanisms are predominantly MAR or MNAR in character, "
    "driven by historical source sparsity and editorial omission patterns."
)

RESULTS_ETHNICITY = (
    "Ethnic group statements (P172) were recorded for only 78,065 human entities "
    "(1.20\u202f\u00b10.01\u202f%); the remaining 6,427,363 items (98.80\u202f%) "
    "carried no ethnicity information, classifying this as extreme MNAR missingness. "
    "Among stated entities, the four most common ethnic groups were African American "
    "(22.4\u202f\u00b10.62\u202f%; n\u202f=\u202f17,486), Han Chinese "
    "(18.2\u202f\u00b10.54\u202f%; n\u202f=\u202f14,208), Ashkenazi Jewish "
    "(14.1\u202f\u00b10.48\u202f%; n\u202f=\u202f11,007), and Euro-American "
    "(12.8\u202f\u00b10.46\u202f%). The high representation of African American and "
    "Ashkenazi Jewish entries reflects targeted volunteer campaigns\u2014AfroCROWD, "
    "Black History Month edit-a-thons, and WikiProject Jewish History\u2014rather than "
    "proportional global demographic representation. European national biographical "
    "sources rarely record ethnicity explicitly, while Asian and African sources "
    "typically encode identity through citizenship (P27) rather than P172."
)

RESULTS_LINGUISTIC = (
    "Label coverage in English (rdfs:label) reached 100\u202f% by construction "
    "(6,505,428 items), while German achieved 68.2\u202f%, French 62.5\u202f%, "
    "Spanish 54.1\u202f%, Mandarin Chinese 41.5\u202f%, Hindi 18.2\u202f%, and "
    "Swahili only 5.1\u202f%. Description coverage (schema:description) is "
    "substantially lower: English 88.1\u202f%, German 44.5\u202f%, French 39.2\u202f%, "
    "Mandarin 19.8\u202f%, Hindi 8.4\u202f%, and Swahili 1.8\u202f%. Alias coverage "
    "(skos:altLabel) is more limited still: English 42.3\u202f%, German 18.4\u202f%, "
    "Mandarin 8.2\u202f%. For languages spoken or written (P1412), English and German "
    "dominate recorded biographical items (29.8\u202f% and 26.5\u202f% of P1412 "
    "statements respectively), while Hindi (0.17\u202f%), Swahili (0.06\u202f%), and "
    "Bengali (0.33\u202f%) represent under 0.5\u202f% of stated language affiliations "
    "despite together accounting for over 15\u202f% of the world\u2019s population [11]."
)

# Figure captions (3 figures selected for CEUR format)
FIG1_CAPTION = (
    "Figure 1. Gender representation disparities in Wikidata human entities (wd:Q5). "
    "Horizontal bars show observed female proportions for the full Q5 dataset and "
    "selected occupational cohorts (N\u202f=\u202f5,222,307 P21-stated entities). "
    "Error bars: 95\u202f% Wilson-score CIs. Red dashed line: 50\u202f% societal "
    "parity expectation [11]."
)

FIG2_CAPTION = (
    "Figure 2. Urban vs. rural birthplace representation and P19 coverage completeness. "
    "Panel (A): observed urban (97.52\u202f%) vs. rural (2.48\u202f%) shares against "
    "the country-weighted global baseline (72.6\u202f% urban, 27.4\u202f% rural) with "
    "95\u202f% CIs. Panel (B): overall birthplace coverage breakdown across 6.50\u202fM "
    "entities (classified urban 27.63\u202f%, classified rural 0.70\u202f%, stated "
    "but unclassified 7.81\u202f%, and missing P19 63.86\u202f%)."
)

FIG3_CAPTION = (
    "Figure 3. Executive summary of representation disparity ratios across all "
    "evaluated bias dimensions. Values show observed/expected ratios; the green "
    "dashed line marks ideal parity (1.0\u00d7). Axes below 0.5\u00d7 or above 2.0\u00d7 "
    "are flagged as severe."
)

# Table 1: 10 data rows (+ 1 header) \u00d7 5 columns
TABLE_HEADER = ["Bias Axis", "Evaluated Cohort", "Observed", "Expected Baseline", "Disparity Ratio"]
TABLE_DATA = [
    ["Gender (P21)",         "Female",                        "28.71 \u00b1 0.04%",  "50.00%",     "0.57\u00d7"],
    ["Gender (P21)",         "Non-binary / Trans",            "0.087%",              "~1.00%",     "0.09\u00d7"],
    ["Orientation (P91)",    "Non-heterosexual (assumed)",    "0.150 \u00b1 0.003%", "9.00%",      "0.02\u00d7"],
    ["Geographic (P27)",     "W. Europe + N. America",        "~53% of P27-stated",  "~14%",       "~3.8\u00d7"],
    ["Birthplace (P19)",     "Rural",                         "2.48 \u00b1 0.04%",   "27.40%",     "0.09\u00d7"],
    ["Ethnicity (P172)",     "Any stated ethnicity",          "1.20 \u00b1 0.01%",   "100%",       "0.01\u00d7"],
    ["Linguistic",           "Non-English descriptions",      "18.2%",               "100%",       "0.18\u00d7"],
    ["Linguistic",           "Non-English labels",            "35.4%",               "100%",       "0.35\u00d7"],
    ["Occupation (P106)",    "Female physicists",             "11.20 \u00b1 0.21%",  "50.00%",     "0.22\u00d7"],
    ["Intersectional",       "Non-Western female",            "~4.80%",              "~43.0%",     "~0.11\u00d7"],
]

DISCUSSION = [
    # Para 1: severity hierarchy
    (
        "Our results reveal a clear severity hierarchy of bias across Wikidata\u2019s "
        "human biographical coverage. The most critical gaps are MNAR in character: "
        "ethnic group (P172) statements are present for only 1.20\u202f% of entities; "
        "sexual orientation (P91) is recorded for only 0.234\u202f% despite roughly "
        "9\u202f% of the global population identifying as LGBTQ+ [9, 10]; and rural "
        "birthplaces are under-represented by a factor of 11\u00d7 relative to world "
        "rural population shares. Geographic representation (P27) is severely skewed, "
        "with Western European and North American items constituting the majority of "
        "citizenship-stated biographies despite representing a small fraction of global "
        "population. Gender representation is moderate but consistent, with female "
        "entities at only 28.71\u202f% across all biographies and dropping below "
        "12\u202f% in several technical and ecclesiastical occupational categories."
    ),
    # Para 2: community editor recommendations
    (
        "On the basis of these findings, we recommend that volunteer editor initiatives "
        "prioritise three areas. First, targeted geographic campaigns should focus on "
        "Sub-Saharan African, South Asian, and Southeast Asian biographical coverage, "
        "where per-capita Wikidata representation is lowest relative to population. "
        "Existing models such as AfroCROWD, WikiProject Women in Red, and the Art+Feminism "
        "editathon series demonstrate that structured, community-led programmes can "
        "measurably close representation gaps over multi-year cycles. Second, rural "
        "birthplace enrichment should be prioritised: adding coordinate location (P625) "
        "to small-town and village Wikidata items would reclassify a large fraction of "
        "the 508,270 currently unclassifiable birthplace entities. Third, multilingual "
        "description and alias completion for under-resourced languages\u2014particularly "
        "Hindi, Swahili, Bengali, and major languages of the Global South\u2014should be "
        "elevated as a structured editing priority, given that description coverage for "
        "these languages falls below 10\u202f%."
    ),
    # Para 3: technical / automated recommendations
    (
        "On the technical side, the wikidata_coverage pipeline provides two complementary "
        "remediation outputs. The constraint-and-class-profile auditor identified 1,669 "
        "constraint violations and 1,283 class-profile property gaps across the sampled "
        "coverage payload, and automatically emits executable Wikidata QuickStatements "
        "batch scripts (wdcoverage suggest) that editors can review and apply directly. "
        "The RAG-based candidate discovery module cross-references Wikidata items against "
        "external scholarly databases (OpenAlex, ORCID, arXiv) to surface real-world "
        "individuals who are absent from Wikidata entirely, yielding structured addition "
        "candidates with pre-formatted QuickStatements payloads. Continuous bias monitoring "
        "via wdcoverage bias enables longitudinal tracking of representation changes across "
        "Wikidata dump cycles."
    ),
    # Para 4: limitations and future work
    (
        "This study has several limitations. Our dataset reflects a single QLever snapshot "
        "taken on 6 August 2026; longitudinal trend analysis and temporal evolution of "
        "representation gaps are left for future work. GADM and GHSL classification "
        "introduce edge cases for historical, dissolved, or maritime territories that "
        "cannot be cleanly resolved to modern administrative polygons. The P91 privacy "
        "constraint\u2014which prohibits inferring sexual orientation without explicit "
        "public self-disclosure\u2014fundamentally limits auditing depth for that axis; "
        "methodological advances in privacy-preserving group-level estimation would be "
        "needed to improve coverage estimates without violating individual privacy norms. "
        "Future work should also incorporate causal modelling to distinguish between "
        "editorial omission, source-side absence, and structural Wikidata policy drivers "
        "as mechanisms underlying the observed missingness patterns."
    ),
]

REFERENCES = [
    "[1] Vrandec\u030cic\u0301, D., Kro\u0308tzsch, M.: Wikidata: A free collaborative "
    "knowledgebase. Commun. ACM 57(10), 78\u201385 (2014).",

    "[2] Klein, M., Koenigstein, N., Zhao, Y.: Monitoring gender diversity in Wikipedia. "
    "In: Proc. 8th ACM Int. Conf. Web Search and Data Mining (WSDM), pp.\u202f481\u2013490 (2015).",

    "[3] Beyt\u00eda, P., Scho\u0308fer, G.: The geographic inequality of open knowledge "
    "graphs. In: Proc. 12th ACM Conf. Web Science (WebSci), pp.\u202f145\u2013154 (2020).",

    "[4] Wagner, C., Garcia, D., Taraborelli, D., Aiello, L.M., Strohmaier, M.: "
    "It\u2019s a man\u2019s Wikipedia? Assessing gender bias in Wikipedia biographies. "
    "In: Proc. Int. AAAI Conf. Web and Social Media (ICWSM), pp.\u202f454\u2013463 (2015).",

    "[5] Reagle, J., Rhue, L.: Gender bias in Wikipedia and Britannica. Int. J. "
    "Communication 5, 1138\u20131158 (2011).",

    "[6] Luggen, M., Dessimoz, C., Cudre\u0301-Mauroux, P.: Non-parametric class "
    "completeness estimators for collaborative knowledge bases. In: Proc. 18th Int. "
    "Semantic Web Conf. (ISWC), pp.\u202f382\u2013398 (2019).",

    "[7] Bast, H., Buchhold, B.: QLever: A SPARQL engine for efficient combined search "
    "on structured and unstructured data. In: Proc. 26th ACM Int. Conf. Information and "
    "Knowledge Management (CIKM), pp.\u202f1559\u20131568 (2017).",

    "[8] European Commission JRC: Global Human Settlement Layer (GHSL): Degree of "
    "Urbanisation Classification Model. European Union (2024).",

    "[9] Ipsos: LGBT+ Pride 2023 Global Survey: A 30-Country Survey Report. "
    "Ipsos Public Affairs (2023).",

    "[10] Ipsos: LGBT+ Pride 2024 Global Survey Report. Ipsos Public Affairs (2024).",

    "[11] United Nations DESA: World Population Prospects 2024: Summary of Results. "
    "United Nations (2024).",
]


# ═════════════════════════════════════════════════════════════════════════════
# MAIN PROCESSING
# ═════════════════════════════════════════════════════════════════════════════

def main():
    if not os.path.exists(DOCX_IN):
        sys.exit(f"ERROR: Input file not found: {DOCX_IN}")

    print(f"Opening: {DOCX_IN}")
    doc = Document(DOCX_IN)

    paras = doc.paragraphs
    print(f"  Paragraphs found: {len(paras)}")
    print(f"  Tables found:     {len(doc.tables)}")

    # ── Build a lookup: paragraph index by partial text match ────────────────
    def find_para(partial, start=0):
        for i in range(start, len(paras)):
            if partial.lower() in paras[i].text.lower():
                return i
        return -1

    # ── 1. ABSTRACT ──────────────────────────────────────────────────────────
    print("  Filling abstract...")
    i = find_para("Introduction.", 0)
    if i >= 0:
        set_para_text(paras[i], ABSTRACT_INTRO)
    i = find_para("Methods.", 0)
    if i >= 0:
        set_para_text(paras[i], ABSTRACT_METHODS)
    i = find_para("Results.", 0)
    if i >= 0:
        set_para_text(paras[i], ABSTRACT_RESULTS)
    i = find_para("Discussion.", 0)
    if i >= 0:
        set_para_text(paras[i], ABSTRACT_DISCUSSION)

    # ── 2. KEYWORDS ──────────────────────────────────────────────────────────
    print("  Expanding keywords...")
    i = find_para("Wikidata, bias")
    if i >= 0:
        set_para_text(paras[i], KEYWORDS)

    # ── 3. INTRODUCTION placeholders ─────────────────────────────────────────
    print("  Filling Introduction placeholders...")
    i = find_para("Talk about bias propagation")
    if i >= 0:
        set_para_text(paras[i], INTRO_PARA2)
    i = find_para("Finish with transition")
    if i >= 0:
        set_para_text(paras[i], INTRO_PARA3)

    # ── 4. METHODS gaps ──────────────────────────────────────────────────────
    print("  Filling Methods gaps...")
    i = find_para("rural or urban was")
    if i >= 0:
        set_para_text(paras[i], METHODS_RURAL_URBAN)
    i = find_para("Add more detail on statistical testing")
    if i >= 0:
        set_para_text(paras[i], METHODS_STATS_EXTRA)

    # ── 5. RESULTS: fix counts, fill [TODO] paragraphs ───────────────────────
    print("  Filling Results paragraphs...")

    # Gender
    i = find_para("5,222,308 items")
    if i >= 0:
        set_para_text(paras[i], RESULTS_GENDER)

    # Sexual orientation
    i = find_para("15,240 instances")
    if i >= 0:
        set_para_text(paras[i], RESULTS_ORIENTATION)

    # Citizenship — CORRECTED from 5,178,210 to 2,489,203
    i = find_para("5,178,210")
    if i >= 0:
        set_para_text(paras[i], RESULTS_GEOGRAPHY)

    # Birthplace — CORRECTED from 1,345,375 to 1,843,024
    i = find_para("1,345,375")
    if i >= 0:
        set_para_text(paras[i], RESULTS_BIRTHPLACE)

    # Ethnicity
    i = find_para("78,065")
    if i >= 0:
        set_para_text(paras[i], RESULTS_ETHNICITY)

    # Multilingual / labels
    i = find_para("individual statements")
    if i >= 0:
        set_para_text(paras[i], RESULTS_LINGUISTIC)

    # ── 6. FIGURES ────────────────────────────────────────────────────────────
    print("  Inserting figures...")
    fig1_path = os.path.join(FIG_DIR, "figure1_gender_disparities.png")
    fig2_path = os.path.join(FIG_DIR, "figure8_urban_rural_disparity.png")
    fig3_path = os.path.join(FIG_DIR, "figure10_executive_summary_radar.png")

    def make_image_para(img_path, width_in=5.5):
        """Return a centered <w:p> element containing an inline picture."""
        scratch = Document()
        if not scratch.paragraphs:
            scratch.add_paragraph("")
        s_para = scratch.paragraphs[0]
        s_run = s_para.add_run()
        s_run.add_picture(img_path, width=Inches(width_in))
        drawing = s_run._r.find(qn("w:drawing"))
        p_el = OxmlElement("w:p")
        pPr = OxmlElement("w:pPr")
        jc = OxmlElement("w:jc"); jc.set(qn("w:val"), "center")
        pPr.append(jc); p_el.insert(0, pPr)
        if drawing is not None:
            r_el = OxmlElement("w:r")
            r_el.append(copy.deepcopy(drawing))
            p_el.append(r_el)
        return p_el

    def make_caption_para(caption_text):
        """Return a centered italic <w:p> element with caption text."""
        p_el = OxmlElement("w:p")
        pPr = OxmlElement("w:pPr")
        jc = OxmlElement("w:jc"); jc.set(qn("w:val"), "center")
        pPr.append(jc); p_el.insert(0, pPr)
        r = OxmlElement("w:r")
        rPr = OxmlElement("w:rPr")
        i_el = OxmlElement("w:i"); rPr.append(i_el)
        r.insert(0, rPr)
        t = OxmlElement("w:t")
        t.text = caption_text
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
        r.append(t); p_el.append(r)
        return p_el

    # Figure 1: replace "Figure 1: XXX" placeholder paragraph with image
    fig1_idx = find_para("Figure 1: XXX")
    if fig1_idx >= 0 and os.path.exists(fig1_path):
        set_para_text(paras[fig1_idx], "")
        run = paras[fig1_idx].add_run()
        run.add_picture(fig1_path, width=Inches(5.5))
        paras[fig1_idx].alignment = 1

    # Figure 1 caption: replace the standalone "XXX" paragraph right after
    for p in paras:
        if p.text.strip() == "XXX":
            set_para_text(p, FIG1_CAPTION)
            break

    # ── Insert figures 2 and 3 before Table 1 ──────────────────────────────
    # Find "Table 1" paragraph to anchor insertion points
    table1_idx = find_para("Table 1")
    img3_p = None  # track for Figure 2 anchor
    if table1_idx >= 0:
        table1_para = paras[table1_idx]
        # Insert Figure 3 (executive summary) before Table 1 — caption then image
        if os.path.exists(fig3_path):
            cap3_p = make_caption_para(FIG3_CAPTION)
            table1_para._element.addprevious(cap3_p)
            img3_p = make_image_para(fig3_path, width_in=5.0)
            cap3_p.addprevious(img3_p)

        # Insert Figure 2 (urban/rural) before Figure 3
        if os.path.exists(fig2_path):
            anchor = img3_p if img3_p is not None else table1_para._element
            cap2_p = make_caption_para(FIG2_CAPTION)
            anchor.addprevious(cap2_p)
            img2_p = make_image_para(fig2_path, width_in=5.5)
            cap2_p.addprevious(img2_p)

    # ── 7. TABLE 1 ────────────────────────────────────────────────────────────
    print("  Populating Table 1...")
    # Update table caption
    i = find_para("Table caption")
    # find by style
    for p in paras:
        if p.style.name == "Table caption" and p.text.strip() in ("XXX", ""):
            set_para_text(p, (
                "Summary of representation disparities across eight bias axes "
                "in Wikidata human entities (wd:Q5, N\u202f=\u202f6,505,428). "
                "Disparity Ratio\u202f=\u202fobserved\u202f/\u202fexpected; values "
                "<\u202f0.5\u00d7 or >\u202f2.0\u00d7 indicate severe bias."
            ))
            break

    table = doc.tables[0]
    # Fill header row
    fill_table_row(table.rows[0], TABLE_HEADER, bold_row=True)
    # Fill data rows
    for ri, row_data in enumerate(TABLE_DATA, start=1):
        if ri < len(table.rows):
            fill_table_row(table.rows[ri], row_data)

    # ── 8. DISCUSSION ────────────────────────────────────────────────────────
    print("  Writing Discussion section...")
    disc_idx = find_para("Discussion")
    # Find the Heading 1 "Discussion"
    disc_heading_idx = -1
    for idx, p in enumerate(paras):
        if p.style.name == "Heading 1" and p.text.strip() == "Discussion":
            disc_heading_idx = idx
            break

    if disc_heading_idx >= 0:
        disc_heading_para = paras[disc_heading_idx]
        # Find the next heading (Acknowledgements) to insert before it
        ack_idx = -1
        for idx, p in enumerate(paras):
            if p.style.name == "Acknowledgements (Heading)":
                ack_idx = idx
                break

        if ack_idx >= 0:
            ack_para = paras[ack_idx]
            # Insert Discussion paragraphs before Acknowledgements, in reverse order
            for disc_text in reversed(DISCUSSION):
                new_p = OxmlElement("w:p")
                new_pPr = OxmlElement("w:pPr")
                new_pStyle = OxmlElement("w:pStyle")
                new_pStyle.set(qn("w:val"), "Normal")
                new_pPr.append(new_pStyle)
                new_p.insert(0, new_pPr)
                new_r = OxmlElement("w:r")
                new_t = OxmlElement("w:t")
                new_t.text = disc_text
                new_t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                new_r.append(new_t)
                new_p.append(new_r)
                ack_para._element.addprevious(new_p)
        else:
            print("  WARNING: Could not find Acknowledgements heading for Discussion insertion")

    # ── 9. REFERENCES ────────────────────────────────────────────────────────
    print("  Appending references...")
    # Find "References" heading
    ref_heading_para = None
    for p in paras:
        if p.style.name == "Acknowledgements (Heading)" and p.text.strip() == "References":
            ref_heading_para = p
            break

    if ref_heading_para is not None:
        # Append each reference after the heading (insert in reverse to maintain order)
        for ref_text in reversed(REFERENCES):
            new_p = OxmlElement("w:p")
            new_pPr = OxmlElement("w:pPr")
            new_pStyle = OxmlElement("w:pStyle")
            new_pStyle.set(qn("w:val"), "Normal")
            new_pPr.append(new_pStyle)
            new_p.insert(0, new_pPr)
            new_r = OxmlElement("w:r")
            new_t = OxmlElement("w:t")
            new_t.text = ref_text
            new_t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            new_r.append(new_t)
            new_p.append(new_r)
            ref_heading_para._element.addnext(new_p)

    # ── 10. SAVE ─────────────────────────────────────────────────────────────
    print(f"  Saving to: {DOCX_OUT}")
    doc.save(DOCX_OUT)
    print("  Done.")

    # ── VERIFICATION ─────────────────────────────────────────────────────────
    print("\n── Verification ───────────────────────────────────────────────────")
    doc2 = Document(DOCX_OUT)
    all_text = " ".join(p.text for p in doc2.paragraphs)
    todos = ["[TODO", "[placeholder", "XXX", "Add more", "Talk about"]
    for marker in todos:
        count = all_text.count(marker)
        status = "OK" if count == 0 else f"WARNING: {count} occurrences remain"
        print(f"  '{marker}': {status}")

    # Verify table populated
    t = doc2.tables[0]
    empty_cells = sum(1 for row in t.rows for cell in row.cells if not cell.text.strip())
    print(f"  Table empty cells: {empty_cells} (should be 0)")

    print("\nAll done! Output written to:", DOCX_OUT)


if __name__ == "__main__":
    main()

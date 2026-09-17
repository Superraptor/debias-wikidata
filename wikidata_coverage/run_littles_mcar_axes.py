"""Multi-Axial Runner for Little's (1988) MCAR Test Across All Non-Intersectional Axes.

This script executes Little's MCAR test on the Wikidata human entity dataset (Q5)
across each non-intersectional axis:
  1. Sex or Gender (P21)
  2. Sexual Orientation (P91 - Explicit vs Assumed)
  3. Country of Citizenship / Geographic Distribution (P27)
  4. Ethnic Group (P172)
  5. Rural vs. Urban Birthplace (P19)
  6. Languages Spoken or Written (P1412) & Multilingual Completeness
  7. Occupational Categorization (P106)
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rich.console import Console
from rich.table import Table

from wikidata_coverage.detectors.littles_mcar import extract_qid, extract_year, littles_mcar_test

console = Console()

# Classification QID mappings
GENDER_MAP = {
    "Q6581072": "Female",
    "Q6581097": "Male",
    "Q1052281": "Transgender Female",
    "Q2449503": "Transgender Male",
    "Q48270": "Non-binary",
    "Q1097630": "Intersex",
    "Q189125": "Transgender Person",
}

SEXUAL_ORIENTATION_MAP = {
    "Q1035954": "Heterosexual",
    "Q6636": "Homosexual / Gay",
    "Q6649": "Bisexual",
    "Q44748": "Lesbian",
    "Q18116794": "Asexual",
    "Q271534": "Pansexual / Queer",
}

ETHNICITY_MAP = {
    "Q2207288": "African American",
    "Q42740": "Han Chinese",
    "Q34069": "Ashkenazi Jewish",
    "Q79": "Egyptians",
    "Q49088": "African / Black",
    "Q200": "White / European American",
    "Q726": "Romani",
    "Q161652": "Tamils",
    "Q9610": "Bengalis",
    "Q8498": "Arabs",
    "Q1065": "Indigenous Americans",
}

# Major country mappings for geographic grouping
WESTERN_COUNTRIES = {
    "Q30", "Q145", "Q183", "Q142", "Q38", "Q29", "Q16", "Q55", "Q31", "Q39",
    "Q27", "Q36", "Q35", "Q40", "Q34", "Q20", "Q33", "Q28", "Q45", "Q218",
    "Q219", "Q224", "Q227", "Q211", "Q212", "Q213", "Q214", "Q215",
}

LANGUAGE_MAP = {
    "Q1860": "English",
    "Q188": "German",
    "Q150": "French",
    "Q1321": "Spanish",
    "Q9056": "Czech",
    "Q652": "Italian",
    "Q7737": "Russian",
    "Q9186": "Mandarin Chinese",
    "Q1568": "Hindi",
    "Q13955": "Arabic",
    "Q9610": "Bengali",
    "Q7838": "Swahili",
}

OCCUPATION_MAP = {
    # Sports
    "Q10833314": "Athletes / Sports", "Q937857": "Athletes / Sports", "Q11513337": "Athletes / Sports",
    # Politics / Law
    "Q82955": "Politics & Government", "Q40348": "Law & Judiciary",
    # Science & Academia
    "Q1650915": "Science & Research", "Q170790": "Science & Research", "Q901": "Science & Research",
    # Arts & Performance
    "Q33999": "Arts & Performance", "Q177220": "Arts & Performance", "Q483501": "Arts & Performance",
    # Military
    "Q47064": "Military & Defense", "Q189290": "Military & Defense",
    # Religious
    "Q250872": "Clergy & Religion", "Q42603": "Clergy & Religion",
}


def load_dataset_records(tsv_path: Path, max_rows: int | None = None) -> list[dict[str, Any]]:
    """Loads and aggregates multi-valued statement rows into unique entity records."""
    console.print(f"[cyan]Streaming TSV records from {tsv_path.name}...[/cyan]")
    t0 = time.time()
    
    entities: dict[str, dict[str, Any]] = {}
    with open(tsv_path, "r", encoding="utf-8", errors="replace") as f:
        header_line = f.readline()
        if not header_line:
            return []
        headers = [h.strip().lstrip("?") for h in header_line.rstrip("\r\n").split("\t")]
        
        idx_map = {h: i for i, h in enumerate(headers)}
        item_idx = idx_map.get("item", 0)
        label_idx = idx_map.get("itemLabel", -1)
        gender_idx = idx_map.get("gender", -1)
        citizenship_idx = idx_map.get("citizenship", -1)
        occupation_idx = idx_map.get("occupation", -1)
        birth_place_idx = idx_map.get("birth_place", -1)
        death_place_idx = idx_map.get("death_place", -1)
        birth_date_idx = idx_map.get("birth_date", -1)
        death_date_idx = idx_map.get("death_date", -1)
        given_name_idx = idx_map.get("given_name", -1)
        language_idx = idx_map.get("language", -1)
        sitelinks_idx = idx_map.get("sitelinks_count", -1)
        orientation_idx = idx_map.get("sexual_orientation", -1)
        ethnicity_idx = idx_map.get("ethnicity", -1)

        row_count = 0
        for line in f:
            row_count += 1
            if max_rows and row_count > max_rows:
                break
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) <= item_idx:
                continue
            qid = extract_qid(parts[item_idx])
            if not qid:
                continue

            if qid not in entities:
                entities[qid] = {
                    "qid": qid,
                    "gender": set(),
                    "citizenship": set(),
                    "occupation": set(),
                    "birth_place": None,
                    "death_place": None,
                    "birth_year": np.nan,
                    "death_year": np.nan,
                    "given_name": False,
                    "language": set(),
                    "sitelinks": 0,
                    "orientation": set(),
                    "ethnicity": set(),
                }

            e = entities[qid]

            if gender_idx != -1 and gender_idx < len(parts):
                g_qid = extract_qid(parts[gender_idx])
                if g_qid:
                    e["gender"].add(g_qid)

            if citizenship_idx != -1 and citizenship_idx < len(parts):
                c_qid = extract_qid(parts[citizenship_idx])
                if c_qid:
                    e["citizenship"].add(c_qid)

            if occupation_idx != -1 and occupation_idx < len(parts):
                o_qid = extract_qid(parts[occupation_idx])
                if o_qid:
                    e["occupation"].add(o_qid)

            if birth_place_idx != -1 and birth_place_idx < len(parts) and parts[birth_place_idx]:
                bp = extract_qid(parts[birth_place_idx])
                if bp:
                    e["birth_place"] = bp

            if death_place_idx != -1 and death_place_idx < len(parts) and parts[death_place_idx]:
                dp = extract_qid(parts[death_place_idx])
                if dp:
                    e["death_place"] = dp

            if birth_date_idx != -1 and birth_date_idx < len(parts) and np.isnan(e["birth_year"]):
                e["birth_year"] = extract_year(parts[birth_date_idx])

            if death_date_idx != -1 and death_date_idx < len(parts) and np.isnan(e["death_year"]):
                e["death_year"] = extract_year(parts[death_date_idx])

            if given_name_idx != -1 and given_name_idx < len(parts) and parts[given_name_idx]:
                e["given_name"] = True

            if language_idx != -1 and language_idx < len(parts):
                l_qid = extract_qid(parts[language_idx])
                if l_qid:
                    e["language"].add(l_qid)

            if sitelinks_idx != -1 and sitelinks_idx < len(parts) and parts[sitelinks_idx]:
                try:
                    e["sitelinks"] = max(e["sitelinks"], int(parts[sitelinks_idx]))
                except ValueError:
                    pass

            if orientation_idx != -1 and orientation_idx < len(parts):
                so_qid = extract_qid(parts[orientation_idx])
                if so_qid:
                    e["orientation"].add(so_qid)

            if ethnicity_idx != -1 and ethnicity_idx < len(parts):
                eth_qid = extract_qid(parts[ethnicity_idx])
                if eth_qid:
                    e["ethnicity"].add(eth_qid)

    t1 = time.time()
    console.print(f"[green]Parsed {len(entities):,} unique entities from {row_count:,} rows in {t1 - t0:.2f}s.[/green]")
    return list(entities.values())


def extract_entity_feature_matrix(entities: list[dict[str, Any]]) -> tuple[np.ndarray, list[str]]:
    """
    Constructs an (N, P) continuous/missing data matrix for Little's MCAR test.
    Variables include continuous attributes and indicator presence/missing metrics.
    """
    feature_names = [
        "birth_year",
        "death_year",
        "sitelinks_count",
        "has_birth_place",
        "has_death_place",
        "has_citizenship",
        "has_occupation",
        "has_given_name",
        "has_language",
    ]

    matrix = np.empty((len(entities), len(feature_names)), dtype=float)

    for i, e in enumerate(entities):
        matrix[i, 0] = e["birth_year"]
        matrix[i, 1] = e["death_year"]
        matrix[i, 2] = float(e["sitelinks"])
        # For presence properties, if missing we encode as nan for completeness missingness testing
        # or as 1.0 vs nan
        matrix[i, 3] = 1.0 if e["birth_place"] else np.nan
        matrix[i, 4] = 1.0 if e["death_place"] else np.nan
        matrix[i, 5] = 1.0 if len(e["citizenship"]) > 0 else np.nan
        matrix[i, 6] = 1.0 if len(e["occupation"]) > 0 else np.nan
        matrix[i, 7] = 1.0 if e["given_name"] else np.nan
        matrix[i, 8] = 1.0 if len(e["language"]) > 0 else np.nan

    return matrix, feature_names


def run_all_axes_mcar_tests(tsv_path: Path | str = "data/q5_qlever_results.tsv", sample_limit: int | None = None) -> dict[str, Any]:
    tsv_file = Path(tsv_path)
    if not tsv_file.exists():
        raise FileNotFoundError(f"TSV dataset {tsv_file} not found.")

    entities = load_dataset_records(tsv_file, max_rows=sample_limit)
    total_n = len(entities)

    results: dict[str, Any] = {
        "metadata": {
            "total_entities": total_n,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
            "methodology": "Little's (1988) MCAR Chi-square Test via EM Algorithm",
        },
        "overall": {},
        "axes": {},
    }

    # 0. Global Population MCAR Test
    console.print("\n[bold cyan]1. Running Little's MCAR Test on Full Knowledge Graph Population...[/bold cyan]")
    full_mat, feat_names = extract_entity_feature_matrix(entities)
    # If full dataset is very large, evaluate on representative stratified batch for numerical speed
    sub_indices = np.random.RandomState(42).choice(total_n, size=min(100000, total_n), replace=False) if total_n > 100000 else np.arange(total_n)
    res_global = littles_mcar_test(full_mat[sub_indices], feature_names=feat_names)
    results["overall"] = res_global

    # 1. Gender Axis (P21)
    console.print("\n[bold cyan]2. Running Little's MCAR Test on Sex or Gender Axis (P21)...[/bold cyan]")
    gender_groups: dict[str, list[int]] = {
        "Female (Q6581072)": [],
        "Male (Q6581097)": [],
        "Nonbinary / Minoritized Genders": [],
        "Unstated / Missing Gender": [],
    }
    for idx, e in enumerate(entities):
        g_set = e["gender"]
        if "Q6581072" in g_set:
            gender_groups["Female (Q6581072)"].append(idx)
        elif "Q6581097" in g_set:
            gender_groups["Male (Q6581097)"].append(idx)
        elif len(g_set) > 0:
            gender_groups["Nonbinary / Minoritized Genders"].append(idx)
        else:
            gender_groups["Unstated / Missing Gender"].append(idx)

    axis_gender_res = {}
    for g_label, idxs in gender_groups.items():
        if len(idxs) > 10:
            sample_sub = idxs if len(idxs) <= 50000 else np.random.RandomState(42).choice(idxs, size=50000, replace=False).tolist()
            res = littles_mcar_test(full_mat[sample_sub], feature_names=feat_names)
            res["total_in_stratum"] = len(idxs)
            axis_gender_res[g_label] = res
    results["axes"]["gender"] = axis_gender_res

    # 2. Sexual Orientation Axis (P91)
    console.print("\n[bold cyan]3. Running Little's MCAR Test on Sexual Orientation Axis (P91)...[/bold cyan]")
    orientation_groups: dict[str, list[int]] = {
        "Explicit Non-Heterosexual": [],
        "Explicit Heterosexual (Q1035954)": [],
        "Assumed Heterosexual (Unstated P91)": [],
    }
    for idx, e in enumerate(entities):
        so_set = e["orientation"]
        if "Q1035954" in so_set:
            orientation_groups["Explicit Heterosexual (Q1035954)"].append(idx)
        elif len(so_set) > 0:
            orientation_groups["Explicit Non-Heterosexual"].append(idx)
        else:
            orientation_groups["Assumed Heterosexual (Unstated P91)"].append(idx)

    axis_orientation_res = {}
    for o_label, idxs in orientation_groups.items():
        if len(idxs) > 10:
            sample_sub = idxs if len(idxs) <= 50000 else np.random.RandomState(42).choice(idxs, size=50000, replace=False).tolist()
            res = littles_mcar_test(full_mat[sample_sub], feature_names=feat_names)
            res["total_in_stratum"] = len(idxs)
            axis_orientation_res[o_label] = res
    results["axes"]["sexual_orientation"] = axis_orientation_res

    # 3. Geographic Axis (P27 Country of Citizenship)
    console.print("\n[bold cyan]4. Running Little's MCAR Test on Geographic Axis (P27)...[/bold cyan]")
    geo_groups: dict[str, list[int]] = {
        "Global North (Europe & North America)": [],
        "Global South (Asia, Africa, Latin America)": [],
        "Unstated / Missing Citizenship": [],
    }
    for idx, e in enumerate(entities):
        c_set = e["citizenship"]
        if not c_set:
            geo_groups["Unstated / Missing Citizenship"].append(idx)
        elif any(c in WESTERN_COUNTRIES for c in c_set):
            geo_groups["Global North (Europe & North America)"].append(idx)
        else:
            geo_groups["Global South (Asia, Africa, Latin America)"].append(idx)

    axis_geo_res = {}
    for geo_label, idxs in geo_groups.items():
        if len(idxs) > 10:
            sample_sub = idxs if len(idxs) <= 50000 else np.random.RandomState(42).choice(idxs, size=50000, replace=False).tolist()
            res = littles_mcar_test(full_mat[sample_sub], feature_names=feat_names)
            res["total_in_stratum"] = len(idxs)
            axis_geo_res[geo_label] = res
    results["axes"]["geographic"] = axis_geo_res

    # 4. Ethnicity Axis (P172)
    console.print("\n[bold cyan]5. Running Little's MCAR Test on Ethnicity Axis (P172)...[/bold cyan]")
    eth_groups: dict[str, list[int]] = {
        "Explicitly Stated Ethnic Group": [],
        "Unstated / Missing Ethnicity": [],
    }
    for idx, e in enumerate(entities):
        eth_set = e["ethnicity"]
        if eth_set:
            eth_groups["Explicitly Stated Ethnic Group"].append(idx)
        else:
            eth_groups["Unstated / Missing Ethnicity"].append(idx)

    axis_eth_res = {}
    for eth_label, idxs in eth_groups.items():
        if len(idxs) > 10:
            sample_sub = idxs if len(idxs) <= 50000 else np.random.RandomState(42).choice(idxs, size=50000, replace=False).tolist()
            res = littles_mcar_test(full_mat[sample_sub], feature_names=feat_names)
            res["total_in_stratum"] = len(idxs)
            axis_eth_res[eth_label] = res
    results["axes"]["ethnicity"] = axis_eth_res

    # 5. Rural vs. Urban Birthplace Axis (P19)
    console.print("\n[bold cyan]6. Running Little's MCAR Test on Rural-Urban Birthplace Axis (P19)...[/bold cyan]")
    bp_groups: dict[str, list[int]] = {
        "Documented Birthplace (P19 Stated)": [],
        "Unstated / Missing Birthplace (P19 Missing)": [],
    }
    for idx, e in enumerate(entities):
        if e["birth_place"]:
            bp_groups["Documented Birthplace (P19 Stated)"].append(idx)
        else:
            bp_groups["Unstated / Missing Birthplace (P19 Missing)"].append(idx)

    axis_bp_res = {}
    for bp_label, idxs in bp_groups.items():
        if len(idxs) > 10:
            sample_sub = idxs if len(idxs) <= 50000 else np.random.RandomState(42).choice(idxs, size=50000, replace=False).tolist()
            res = littles_mcar_test(full_mat[sample_sub], feature_names=feat_names)
            res["total_in_stratum"] = len(idxs)
            axis_bp_res[bp_label] = res
    results["axes"]["rural_urban_birthplace"] = axis_bp_res

    # 6. Linguistic Axis (P1412 / Language)
    console.print("\n[bold cyan]7. Running Little's MCAR Test on Linguistic Axis (P1412)...[/bold cyan]")
    lang_groups: dict[str, list[int]] = {
        "English Spoken/Written (Q1860)": [],
        "Non-English Major Language": [],
        "Unstated / Missing Language (P1412)": [],
    }
    for idx, e in enumerate(entities):
        l_set = e["language"]
        if "Q1860" in l_set:
            lang_groups["English Spoken/Written (Q1860)"].append(idx)
        elif len(l_set) > 0:
            lang_groups["Non-English Major Language"].append(idx)
        else:
            lang_groups["Unstated / Missing Language (P1412)"].append(idx)

    axis_lang_res = {}
    for lang_label, idxs in lang_groups.items():
        if len(idxs) > 10:
            sample_sub = idxs if len(idxs) <= 50000 else np.random.RandomState(42).choice(idxs, size=50000, replace=False).tolist()
            res = littles_mcar_test(full_mat[sample_sub], feature_names=feat_names)
            res["total_in_stratum"] = len(idxs)
            axis_lang_res[lang_label] = res
    results["axes"]["linguistic"] = axis_lang_res

    # 7. Occupational Axis (P106)
    console.print("\n[bold cyan]8. Running Little's MCAR Test on Occupational Axis (P106)...[/bold cyan]")
    occ_groups: dict[str, list[int]] = {
        "Stated Occupation (P106 Documented)": [],
        "Unstated / Missing Occupation": [],
    }
    for idx, e in enumerate(entities):
        if e["occupation"]:
            occ_groups["Stated Occupation (P106 Documented)"].append(idx)
        else:
            occ_groups["Unstated / Missing Occupation"].append(idx)

    axis_occ_res = {}
    for occ_label, idxs in occ_groups.items():
        if len(idxs) > 10:
            sample_sub = idxs if len(idxs) <= 50000 else np.random.RandomState(42).choice(idxs, size=50000, replace=False).tolist()
            res = littles_mcar_test(full_mat[sample_sub], feature_names=feat_names)
            res["total_in_stratum"] = len(idxs)
            axis_occ_res[occ_label] = res
    results["axes"]["occupational"] = axis_occ_res

    # Display Rich Table Output
    table = Table(title="Little's MCAR Test Results Across All Non-Intersectional Axes in Wikidata (Q5)")
    table.add_column("Axis", style="bold cyan")
    table.add_column("Stratum / Subgroup", style="white")
    table.add_column("Cohort Size (N)", justify="right")
    table.add_column("Little's d² (Chi²)", justify="right", style="magenta")
    table.add_column("Degrees of Freedom (df)", justify="right")
    table.add_column("P-Value", justify="right", style="bold red")
    table.add_column("Missingness Status", style="bold yellow")

    for axis_name, strata in results["axes"].items():
        for s_label, r in strata.items():
            p_val_str = f"{r['p_value']:.4e}" if r['p_value'] < 0.0001 else f"{r['p_value']:.4f}"
            status_str = "[green]MCAR (p >= 0.05)[/green]" if r["is_mcar"] else "[red]MAR / MNAR (p < 0.0001)[/red]"
            table.add_row(
                axis_name.capitalize(),
                s_label,
                f"{r.get('total_in_stratum', r['n_samples']):,}",
                f"{r['d2']:,.2f}",
                f"{r['df']:,}",
                p_val_str,
                status_str,
            )

    console.print("\n", table)

    # Save results JSON
    out_json = Path("data/littles_mcar_results.json")
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    console.print(f"\n[green]Saved Little's MCAR test results to {out_json}[/green]")

    return results


if __name__ == "__main__":
    tsv_p = Path("data/q5_qlever_results.tsv")
    run_all_axes_mcar_tests(tsv_p)

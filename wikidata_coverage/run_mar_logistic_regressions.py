"""Logistic Regression Testing for Missing at Random (MAR) Mechanisms Across All 10 Wikidata Axes.

Includes:
  1. Birth Date (P569)
  2. Birth Place (P19)
  3. Death Place (P20)
  4. Country of Citizenship (P27)
  5. Sex or Gender (P21)
  6. Sexual Orientation (P91)
  7. Ethnic Group (P172)
  8. Occupation (P106)
  9. Language Spoken/Written (P1412)
  10. Given Name (P735)
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
import scipy.stats as stats
import statsmodels.api as sm
from rich.console import Console
from rich.table import Table

from wikidata_coverage.access.qlever import QLeverClient

console = Console()

WESTERN_COUNTRIES = {
    "Q30", "Q145", "Q183", "Q142", "Q38", "Q29", "Q16", "Q55", "Q31", "Q39",
    "Q27", "Q36", "Q35", "Q40", "Q34", "Q20", "Q33", "Q28", "Q45", "Q218",
    "Q219", "Q224", "Q227", "Q211", "Q212", "Q213", "Q214", "Q215",
}


def extract_qid(val: str | None) -> str | None:
    if not val:
        return None
    val_str = str(val).strip()
    match = re.search(r"Q\d+", val_str)
    return match.group(0) if match else None


def extract_year(date_str: str | None) -> float:
    if not date_str or not isinstance(date_str, str):
        return np.nan
    match = re.search(r"([+-]?\d{1,4})", date_str)
    if match:
        try:
            val = float(match.group(1))
            if -4000 <= val <= 2026:
                return val
        except ValueError:
            pass
    return np.nan


def fetch_sensitive_property_qids() -> tuple[set[str], set[str]]:
    """Fetches entity QIDs with explicit P91 (orientation) and P172 (ethnicity) claims."""
    console.print("[cyan]Fetching live P91 (orientation) & P172 (ethnicity) entity claims via QLever...[/cyan]")
    ql = QLeverClient()
    p91_qids = set()
    p172_qids = set()

    try:
        q_p91 = "PREFIX wdt: <http://www.wikidata.org/prop/direct/> PREFIX wd: <http://www.wikidata.org/entity/> SELECT DISTINCT ?item WHERE { ?item wdt:P31 wd:Q5 ; wdt:P91 ?o . }"
        rows_p91 = ql.query(q_p91)
        for r in rows_p91:
            qid = extract_qid(r.get("item"))
            if qid:
                p91_qids.add(qid)
        console.print(f"[green]Fetched {len(p91_qids):,} unique P91 entities.[/green]")
    except Exception as exc:
        console.print(f"[yellow]Could not query live P91 claims: {exc}[/yellow]")

    try:
        q_p172 = "PREFIX wdt: <http://www.wikidata.org/prop/direct/> PREFIX wd: <http://www.wikidata.org/entity/> SELECT DISTINCT ?item WHERE { ?item wdt:P31 wd:Q5 ; wdt:P172 ?e . }"
        rows_p172 = ql.query(q_p172)
        for r in rows_p172:
            qid = extract_qid(r.get("item"))
            if qid:
                p172_qids.add(qid)
        console.print(f"[green]Fetched {len(p172_qids):,} unique P172 entities.[/green]")
    except Exception as exc:
        console.print(f"[yellow]Could not query live P172 claims: {exc}[/yellow]")

    return p91_qids, p172_qids


def load_dataset_for_mar(tsv_path: Path, max_rows: int | None = None) -> pd.DataFrame:
    """Loads and constructs tabular DataFrame of entity features and missingness flags."""
    p91_qids, p172_qids = fetch_sensitive_property_qids()

    console.print(f"[cyan]Streaming TSV records from {tsv_path.name} for MAR analysis...[/cyan]")
    t0 = time.time()

    entities: dict[str, dict[str, Any]] = {}
    with open(tsv_path, "r", encoding="utf-8", errors="replace") as f:
        header_line = f.readline()
        if not header_line:
            return pd.DataFrame()
        headers = [h.strip().lstrip("?") for h in header_line.rstrip("\r\n").split("\t")]

        idx_map = {h: i for i, h in enumerate(headers)}
        item_idx = idx_map.get("item", 0)
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
                    "birth_place": False,
                    "death_place": False,
                    "birth_year": np.nan,
                    "death_year": np.nan,
                    "given_name": False,
                    "language": set(),
                    "sitelinks": 0,
                    "has_p91": qid in p91_qids,
                    "has_p172": qid in p172_qids,
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
                if extract_qid(parts[birth_place_idx]):
                    e["birth_place"] = True

            if death_place_idx != -1 and death_place_idx < len(parts) and parts[death_place_idx]:
                if extract_qid(parts[death_place_idx]):
                    e["death_place"] = True

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

    t1 = time.time()
    console.print(f"[green]Parsed {len(entities):,} entities in {t1 - t0:.2f}s.[/green]")

    # Build features dataframe
    records = []
    for e in entities.values():
        c_set = e["citizenship"]
        g_set = e["gender"]
        records.append({
            "qid": e["qid"],
            # Missingness targets (1 = Missing, 0 = Observed)
            "missing_birth_date": 1 if np.isnan(e["birth_year"]) else 0,
            "missing_birth_place": 0 if e["birth_place"] else 1,
            "missing_death_place": 0 if e["death_place"] else 1,
            "missing_citizenship": 0 if len(c_set) > 0 else 1,
            "missing_gender": 0 if len(g_set) > 0 else 1,
            "missing_sexual_orientation": 0 if e["has_p91"] else 1,
            "missing_ethnicity": 0 if e["has_p172"] else 1,
            "missing_occupation": 0 if len(e["occupation"]) > 0 else 1,
            "missing_given_name": 0 if e["given_name"] else 1,
            "missing_language": 0 if len(e["language"]) > 0 else 1,
            # Predictors
            "sitelinks_log": np.log1p(e["sitelinks"]),
            "is_female": 1 if "Q6581072" in g_set else 0,
            "is_male": 1 if "Q6581097" in g_set else 0,
            "is_global_north": 1 if any(c in WESTERN_COUNTRIES for c in c_set) else 0,
            "is_global_south": 1 if (len(c_set) > 0 and not any(c in WESTERN_COUNTRIES for c in c_set)) else 0,
            "has_occupation": 1 if len(e["occupation"]) > 0 else 0,
            "has_birth_place": 1 if e["birth_place"] else 0,
            "has_given_name": 1 if e["given_name"] else 0,
            "has_language": 1 if len(e["language"]) > 0 else 0,
            "is_modern_era": 1 if (not np.isnan(e["birth_year"]) and e["birth_year"] >= 1900) else 0,
            "is_historical_era": 1 if (not np.isnan(e["birth_year"]) and e["birth_year"] < 1900) else 0,
        })

    return pd.DataFrame(records)


def run_mar_logistic_regressions(
    df: pd.DataFrame,
    sample_size: int = 200000,
    random_seed: int = 42,
) -> dict[str, Any]:
    """
    Fits multivariable logistic regressions for all 10 missingness targets
    against other observed biographical characteristics.
    """
    # For highly sparse targets (P91, P172), stratify or oversample observed rows to ensure robust variance estimation
    if len(df) > sample_size:
        # Include all observed P91 and P172 items in the sample plus random sample of remainder
        stated_mask = (df["missing_sexual_orientation"] == 0) | (df["missing_ethnicity"] == 0)
        stated_df = df[stated_mask]
        remaining_needed = max(0, sample_size - len(stated_df))
        unstated_df = df[~stated_mask].sample(n=min(remaining_needed, len(df[~stated_mask])), random_state=random_seed)
        sample_df = pd.concat([stated_df, unstated_df]).sample(frac=1.0, random_state=random_seed).copy()
    else:
        sample_df = df.copy()

    targets = [
        ("Birth Date (P569)", "missing_birth_date", ["sitelinks_log", "is_female", "is_male", "is_global_north", "is_global_south", "has_occupation", "has_birth_place", "has_given_name", "has_language"]),
        ("Birth Place (P19)", "missing_birth_place", ["sitelinks_log", "is_female", "is_male", "is_global_north", "is_global_south", "has_occupation", "has_given_name", "has_language", "is_modern_era"]),
        ("Death Place (P20)", "missing_death_place", ["sitelinks_log", "is_female", "is_male", "is_global_north", "is_global_south", "has_occupation", "has_birth_place", "has_given_name", "is_modern_era"]),
        ("Country of Citizenship (P27)", "missing_citizenship", ["sitelinks_log", "is_female", "is_male", "has_occupation", "has_birth_place", "has_given_name", "has_language", "is_modern_era"]),
        ("Sex or Gender (P21)", "missing_gender", ["sitelinks_log", "is_global_north", "is_global_south", "has_occupation", "has_birth_place", "has_given_name", "has_language", "is_modern_era"]),
        ("Sexual Orientation (P91)", "missing_sexual_orientation", ["sitelinks_log", "is_female", "is_male", "is_global_north", "is_global_south", "has_occupation", "has_birth_place", "is_modern_era"]),
        ("Ethnic Group (P172)", "missing_ethnicity", ["sitelinks_log", "is_female", "is_male", "is_global_north", "is_global_south", "has_occupation", "has_birth_place", "is_modern_era"]),
        ("Occupation (P106)", "missing_occupation", ["sitelinks_log", "is_female", "is_male", "is_global_north", "is_global_south", "has_birth_place", "has_given_name", "has_language", "is_modern_era"]),
        ("Language (P1412)", "missing_language", ["sitelinks_log", "is_female", "is_male", "is_global_north", "is_global_south", "has_occupation", "has_birth_place", "has_given_name", "is_modern_era"]),
        ("Given Name (P735)", "missing_given_name", ["sitelinks_log", "is_female", "is_male", "is_global_north", "is_global_south", "has_occupation", "has_birth_place", "has_language", "is_modern_era"]),
    ]

    all_results: dict[str, Any] = {
        "metadata": {
            "sample_size": len(sample_df),
            "total_population": len(df),
            "model_type": "Binary Logistic Regression (Logit)",
            "formulation": "logit(P(Missing = 1)) = beta_0 + sum(beta_m * X_m)",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
        },
        "models": {},
    }

    console.print(f"\n[bold cyan]Running Logistic Regressions for MAR Testing on {len(sample_df):,} Entities Across All 10 Targets...[/bold cyan]\n")

    for target_name, target_col, predictor_cols in targets:
        y = sample_df[target_col]
        # True population missing rate
        pop_missing_rate = float(df[target_col].mean())

        X = sample_df[predictor_cols].astype(float)
        X = sm.add_constant(X)

        try:
            logit_model = sm.Logit(y, X)
            fit_res = logit_model.fit(disp=False, maxiter=100)

            ll_null = fit_res.llnull
            ll_model = fit_res.llf
            lr_chi2 = fit_res.llr
            lr_pvalue = fit_res.llr_pvalue
            prsquared = fit_res.prsquared

            coef_table = []
            for var_name in X.columns:
                coef = float(fit_res.params[var_name])
                se = float(fit_res.bse[var_name])
                z = float(fit_res.tvalues[var_name])
                pval = float(fit_res.pvalues[var_name])
                odds_ratio = float(np.exp(coef)) if abs(coef) < 700 else float("inf")
                ci_lower = float(np.exp(coef - 1.96 * se)) if abs(coef - 1.96 * se) < 700 else 0.0
                ci_upper = float(np.exp(coef + 1.96 * se)) if abs(coef + 1.96 * se) < 700 else float("inf")

                coef_table.append({
                    "variable": var_name,
                    "coef": coef,
                    "odds_ratio": odds_ratio,
                    "se": se,
                    "z_stat": z,
                    "p_value": pval,
                    "ci_95": [ci_lower, ci_upper],
                    "significant": pval < 0.05,
                })

            all_results["models"][target_name] = {
                "target_variable": target_col,
                "missing_rate": pop_missing_rate,
                "n_obs": int(fit_res.nobs),
                "mcfadden_pseudo_r2": float(prsquared),
                "lr_chi2": float(lr_chi2),
                "lr_pvalue": float(lr_pvalue),
                "supports_mar": bool(lr_pvalue < 0.001),
                "coefficients": coef_table,
            }

            console.print(f"[bold green][OK] Model for {target_name}: Missing Rate={pop_missing_rate:.2%}, Pseudo R²={prsquared:.4f}, LR Chi²={lr_chi2:,.1f}, p={lr_pvalue:.4e}[/bold green]")

        except Exception as exc:
            console.print(f"[red][ERROR] Fitting model for {target_name}: {exc}[/red]")

    return all_results


def print_mar_summary_tables(results: dict[str, Any]) -> None:
    overview_table = Table(title="Multivariable Logistic Regression Overview: Testing MAR Missingness Across All 10 Non-Intersectional Axes")
    overview_table.add_column("Biographical Property Target", style="bold cyan")
    overview_table.add_column("Missing Rate", justify="right")
    overview_table.add_column("Sample (N)", justify="right")
    overview_table.add_column("McFadden Pseudo R²", justify="right", style="magenta")
    overview_table.add_column("Likelihood Ratio Chi²", justify="right", style="yellow")
    overview_table.add_column("Model p-Value", justify="right", style="bold red")
    overview_table.add_column("Missingness Status", style="bold green")

    for model_name, m in results["models"].items():
        p_str = f"{m['lr_pvalue']:.4e}" if m['lr_pvalue'] < 0.0001 else f"{m['lr_pvalue']:.4f}"
        status = "[bold green]Strong MAR Evidence (p < 0.0001)[/bold green]" if m["supports_mar"] else "[yellow]Weak Evidence[/yellow]"
        overview_table.add_row(
            model_name,
            f"{m['missing_rate']:.2%}",
            f"{m['n_obs']:,}",
            f"{m['mcfadden_pseudo_r2']:.4f}",
            f"{m['lr_chi2']:,.1f}",
            p_str,
            status,
        )

    console.print("\n", overview_table)

    out_file = Path("data/mar_logistic_regression_results.json")
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    console.print(f"\n[green]Saved MAR logistic regression results to {out_file}[/green]")


if __name__ == "__main__":
    tsv_p = Path("data/q5_qlever_results.tsv")
    df = load_dataset_for_mar(tsv_p)
    results = run_mar_logistic_regressions(df, sample_size=200000)
    print_mar_summary_tables(results)

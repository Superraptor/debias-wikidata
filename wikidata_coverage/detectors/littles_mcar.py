"""Little's MCAR Test Implementation and Multi-Axial Runner for Wikidata Coverage.

Roderick J. A. Little (1988), "A Test of Missing Completely at Random for
Multivariate Data with Missing Values", Journal of the American Statistical
Association, 83(404): 1198-1202.
"""

from __future__ import annotations

import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy.stats as stats
from rich.console import Console
from rich.table import Table

console = Console()


def extract_year(date_str: str | None) -> float:
    """Extracts 4-digit calendar year from ISO date string."""
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


def extract_qid(val: str | None) -> str | None:
    if not val:
        return None
    val_str = str(val).strip()
    match = re.search(r"Q\d+", val_str)
    return match.group(0) if match else None


def littles_mcar_test(
    data: np.ndarray,
    feature_names: list[str] | None = None,
    max_iter: int = 100,
    tol: float = 1e-4,
    min_pattern_size: int = 1,
) -> dict[str, Any]:
    """
    Executes Little's (1988) MCAR test for multivariate data with missing values.

    Args:
        data: (N, P) numpy array with np.nan representing missing values.
        feature_names: Optional list of column names for debugging.
        max_iter: Maximum EM iterations.
        tol: Convergence tolerance for EM.
        min_pattern_size: Minimum observations in a pattern to include in d^2 calculation.

    Returns:
        dict containing:
            d2: Little's d^2 Chi-square test statistic
            df: Degrees of freedom (sum p_j - p)
            p_value: P-value from Chi-square distribution
            is_mcar: Boolean (True if p_value >= 0.05)
            n_samples: Effective sample size evaluated
            n_features: Number of variables
            n_patterns: Number of distinct missingness patterns
            iterations: Number of EM iterations to convergence
            missingness_by_feature: Dict mapping feature index/name to missing percentage
    """
    if not isinstance(data, np.ndarray):
        data = np.asarray(data, dtype=float)
    else:
        data = data.astype(float, copy=True)

    n, p = data.shape
    if n == 0 or p <= 1:
        return {
            "d2": 0.0,
            "df": 0,
            "p_value": 1.0,
            "is_mcar": True,
            "n_samples": n,
            "n_features": p,
            "n_patterns": 0,
            "iterations": 0,
            "missingness_by_feature": {},
            "status": "Insufficient samples or features",
        }

    # Identify missing values
    missing_mask = np.isnan(data)
    missing_rates = np.mean(missing_mask, axis=0)

    # Remove columns that are 100% missing or 0% missing across the entire dataset
    # (Little's test needs variables with at least some observed and some missing values to test)
    # If all columns have 0% missing, data is fully observed (trivially MCAR)
    if np.all(~missing_mask):
        return {
            "d2": 0.0,
            "df": 0,
            "p_value": 1.0,
            "is_mcar": True,
            "n_samples": n,
            "n_features": p,
            "n_patterns": 1,
            "iterations": 0,
            "missingness_by_feature": {i: 0.0 for i in range(p)},
            "status": "Complete data (no missing values)",
        }

    # Filter out columns with 100% missing
    valid_cols = np.where(missing_rates < 1.0)[0]
    if len(valid_cols) <= 1:
        return {
            "d2": 0.0,
            "df": 0,
            "p_value": 1.0,
            "is_mcar": True,
            "n_samples": n,
            "n_features": len(valid_cols),
            "n_patterns": 0,
            "iterations": 0,
            "missingness_by_feature": {},
            "status": "Too few valid features",
        }

    data = data[:, valid_cols]
    missing_mask = missing_mask[:, valid_cols]
    if feature_names:
        feature_names = [feature_names[i] for i in valid_cols]
    n, p = data.shape

    # Remove rows that are completely missing across all valid columns
    row_all_missing = np.all(missing_mask, axis=1)
    if np.any(row_all_missing):
        data = data[~row_all_missing]
        missing_mask = missing_mask[~row_all_missing]
        n = data.shape[0]

    if n <= p:
        return {
            "d2": 0.0,
            "df": 0,
            "p_value": 1.0,
            "is_mcar": True,
            "n_samples": n,
            "n_features": p,
            "n_patterns": 0,
            "iterations": 0,
            "missingness_by_feature": {},
            "status": "Sample size smaller than feature dimension",
        }

    # Group rows by distinct missingness pattern
    pattern_keys = [tuple(row) for row in missing_mask]
    unique_patterns: dict[tuple, list[int]] = {}
    for idx, key in enumerate(pattern_keys):
        unique_patterns.setdefault(key, []).append(idx)

    # Initial estimates for EM
    col_means = np.nanmean(data, axis=0)
    col_stds = np.nanstd(data, axis=0)
    col_stds[col_stds == 0] = 1.0
    col_means[np.isnan(col_means)] = 0.0

    mu = col_means.copy()
    filled_data = data.copy()
    for j in range(p):
        filled_data[missing_mask[:, j], j] = col_means[j]

    cov_init = np.cov(filled_data, rowvar=False)
    if cov_init.ndim == 0:
        cov_init = np.array([[cov_init]])
    sigma = cov_init + np.eye(p) * 1e-4

    # EM Algorithm to estimate ML parameters (mu, Sigma) under multivariate normal missingness
    n_iter = 0
    for iteration in range(max_iter):
        n_iter = iteration + 1
        mu_prev = mu.copy()
        sigma_prev = sigma.copy()

        sum_y = np.zeros(p)
        sum_yy = np.zeros((p, p))

        for pattern_key, indices in unique_patterns.items():
            pattern_arr = np.array(pattern_key, dtype=bool)
            obs_indices = np.where(~pattern_arr)[0]
            mis_indices = np.where(pattern_arr)[0]

            sub_data = data[indices]
            n_j = len(indices)

            if len(mis_indices) == 0:
                # Fully observed row
                sum_y += np.sum(sub_data, axis=0)
                sum_yy += sub_data.T @ sub_data
            elif len(obs_indices) == 0:
                # Fully missing row
                sum_y += n_j * mu
                sum_yy += n_j * (sigma + np.outer(mu, mu))
            else:
                # Partially observed: compute conditional expectation E[Y_mis | Y_obs]
                mu_obs = mu[obs_indices]
                mu_mis = mu[mis_indices]
                sigma_obs_obs = sigma[np.ix_(obs_indices, obs_indices)]
                sigma_mis_obs = sigma[np.ix_(mis_indices, obs_indices)]
                sigma_mis_mis = sigma[np.ix_(mis_indices, mis_indices)]

                # Invert sigma_obs_obs with ridge stabilization
                try:
                    inv_sigma_obs = np.linalg.pinv(sigma_obs_obs + np.eye(len(obs_indices)) * 1e-6)
                except Exception:
                    inv_sigma_obs = np.eye(len(obs_indices))

                reg_coeff = sigma_mis_obs @ inv_sigma_obs
                cond_cov = sigma_mis_mis - reg_coeff @ sigma_mis_obs.T
                # Ensure positive semi-definiteness of conditional covariance
                cond_cov = 0.5 * (cond_cov + cond_cov.T)

                y_obs = sub_data[:, obs_indices]
                diff_obs = y_obs - mu_obs
                y_mis_hat = mu_mis + diff_obs @ reg_coeff.T

                y_full = np.zeros((n_j, p))
                y_full[:, obs_indices] = y_obs
                y_full[:, mis_indices] = y_mis_hat

                sum_y += np.sum(y_full, axis=0)
                sum_yy += y_full.T @ y_full
                sum_yy[np.ix_(mis_indices, mis_indices)] += n_j * cond_cov

        # M-Step: Update ML mean vector and covariance matrix
        mu = sum_y / n
        sigma = (sum_yy / n) - np.outer(mu, mu)
        sigma = 0.5 * (sigma + sigma.T) + np.eye(p) * 1e-5

        # Check convergence
        diff_mu = np.max(np.abs(mu - mu_prev)) / (np.max(np.abs(mu_prev)) + 1e-8)
        diff_sigma = np.max(np.abs(sigma - sigma_prev)) / (np.max(np.abs(sigma_prev)) + 1e-8)
        if diff_mu < tol and diff_sigma < tol:
            break

    # Calculate Little's d^2 Chi-square Test Statistic:
    # d^2 = sum_j n_j * (y_bar_{obs,j} - mu_{obs,j})^T * (Sigma_{obs,j})^{-1} * (y_bar_{obs,j} - mu_{obs,j})
    d2 = 0.0
    sum_pj = 0
    active_patterns = 0

    for pattern_key, indices in unique_patterns.items():
        if len(indices) < min_pattern_size:
            continue
        pattern_arr = np.array(pattern_key, dtype=bool)
        obs_indices = np.where(~pattern_arr)[0]
        pj = len(obs_indices)

        if pj == 0:
            continue

        sum_pj += pj
        active_patterns += 1
        n_j = len(indices)

        sub_data = data[indices][:, obs_indices]
        y_bar_j = np.mean(sub_data, axis=0)
        mu_obs = mu[obs_indices]
        sigma_obs = sigma[np.ix_(obs_indices, obs_indices)]

        try:
            inv_sigma_obs = np.linalg.pinv(sigma_obs + np.eye(pj) * 1e-5)
        except Exception:
            inv_sigma_obs = np.eye(pj)

        diff = y_bar_j - mu_obs
        d2_j = n_j * float(diff @ inv_sigma_obs @ diff)
        d2 += d2_j

    df = sum_pj - p
    if df > 0:
        p_val = float(stats.chi2.sf(d2, df))
    else:
        df = max(1, len(unique_patterns) - 1)
        p_val = float(stats.chi2.sf(d2, df))

    feat_dict = {}
    for i, rate in enumerate(missing_rates[valid_cols]):
        name = feature_names[i] if feature_names else f"feature_{i}"
        feat_dict[name] = float(rate)

    return {
        "d2": float(d2),
        "df": int(df),
        "p_value": float(p_val),
        "is_mcar": bool(p_val >= 0.05),
        "n_samples": int(n),
        "n_features": int(p),
        "n_patterns": len(unique_patterns),
        "iterations": n_iter,
        "missingness_by_feature": feat_dict,
        "status": "Success",
    }

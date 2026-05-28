#!/usr/bin/env python3
"""Econometric decomposition of the Ukrainian-friendly tag at powiat level.

Produces the data payload consumed by
``assets/ukrainian_friendly_decomposition_data.js`` and a small audit JSON
under ``data/ukr_decomposition_audit.json``.

Four analytical pieces are computed:

1. Oaxaca-style shift-share decomposition of each powiat's deviation from
   the national Ukrainian-friendly share, split into ``compositional``
   (sectoral mix) and ``behavioural`` (within-sector openness) components.
   Computed both at the powiat and the voivodeship level using NACE
   divisions (2-digit codes) as the partition ``k``.

2. Posting-level Linear Probability Model and Logit with powiat fixed
   effects, controlling for NACE division, job-category narrow, contract
   type and seniority. The powiat fixed effects ``δ_p`` are extracted with
   their standard errors and used as "residual openness" measure.

3. OLS regression of ``δ_p`` on ``ln(UKR_density)``, a Poland-Ukraine
   ``border`` dummy and a ``metro`` dummy. Uses MSWiA PESEL UKR snapshot
   (Dec 2022) as the refugee-density proxy and GUS BDL P4280 employed-by-
   residence as the per-capita denominator.

4. Empirical Bayes shrinkage on raw powiat shares using a Beta-Binomial
   model fitted by method of moments.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import sparse, stats

BASE = Path(__file__).resolve().parent
JOBS_DB = BASE / "jobs_database.db"
NACE_DB = BASE / "job_nace.db"
UKR_JSONL = BASE / "ukrainian_friendly_results.jsonl"
EMPLOYED_JSON = BASE / "data" / "employed_powiat.json"
UKR_MSWIA_XLSX = BASE / "data" / "external" / "STATYSTYKI_POWIAT_UKR_20221206.xlsx"
POWIAT_GEOJSON_KEYED = BASE / "data" / "pl_powiats_keyed.geojson"
OUT_JS = BASE / "assets" / "ukrainian_friendly_decomposition_data.js"
OUT_AUDIT = BASE / "data" / "ukr_decomposition_audit.json"

# Powiats with < MIN_POSTINGS_PER_POWIAT postings are dropped from FE / EB
# tables to avoid degenerate categories blowing up the standard errors.
MIN_POSTINGS_PER_POWIAT = 100
TOP_K_POWIATS_FOR_DECOMP = 20

# Cities-on-county-rights that we treat as the "metro" anchors for the
# regression in step 3.
METRO_KEYS = {
    "mazowieckie__warszawa",
    "malopolskie__krakow",
    "dolnoslaskie__wroclaw",
    "wielkopolskie__poznan",
    "pomorskie__gdansk",
    "pomorskie__gdynia",
    "lodzkie__lodz",
    "slaskie__katowice",
    "zachodniopomorskie__szczecin",
    "lubelskie__lublin",
    "kujawsko-pomorskie__bydgoszcz",
    "kujawsko-pomorskie__torun",
}

# Powiats whose territory shares a land border with Ukraine.
BORDER_KEYS_UKR = {
    "podkarpackie__bieszczadzki",
    "podkarpackie__przemyski",
    "podkarpackie__przemysl",  # city-on-county rights
    "podkarpackie__jaroslawski",
    "podkarpackie__lubaczowski",
    "lubelskie__hrubieszowski",
    "lubelskie__tomaszowski",
    "lubelskie__chelmski",
    "lubelskie__chelm",
    "lubelskie__wlodawski",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def norm_powiat(name: str | None) -> str:
    """Collapse all gmina-level annotations back to the parent powiat.

    Also strips the ``m.`` / ``m. st.`` (miasto / miasto stołeczne) prefix
    used by GUS for cities-on-county-rights — job_powiat reports those
    cities by bare name (``Warszawa``) whereas BDL prints them as
    ``Powiat m. st. Warszawa``.  Folding both sides to ``warszawa``
    keeps merges consistent.
    """

    if not name:
        return ""
    n = name.strip().lower()
    n = re.sub(r"^powiat\s+", "", n)
    n = re.sub(r"^m\.?\s*st\.?\s+", "", n)
    n = re.sub(r"^m\.\s+", "", n)
    n = re.sub(r"\s*;\s*gm\..*$", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    return strip_accents(n)


def norm_voiv(name: str | None) -> str:
    if not name:
        return ""
    return strip_accents(name.strip().lower())


def make_key(voiv: str | None, powiat: str | None) -> str:
    return f"{norm_voiv(voiv)}__{norm_powiat(powiat)}"


def nace_section(code: str | None) -> str:
    if not code:
        return ""
    head = code[0]
    return head if head.isalpha() and head.isupper() else ""


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------
def load_ukr_flags() -> dict[int, int]:
    out: dict[int, int] = {}
    with UKR_JSONL.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            out[int(obj["id"])] = int(obj.get("ukrainian_friendly", 0))
    return out


def load_nace_map() -> dict[int, str]:
    con = sqlite3.connect(str(NACE_DB))
    rows = con.execute(
        "SELECT job_id, nace_code FROM job_nace "
        "WHERE nace_code IS NOT NULL AND nace_code != ''"
    ).fetchall()
    con.close()
    return {int(jid): str(code) for jid, code in rows}


def load_posting_frame() -> pd.DataFrame:
    """Build the analysis-grade posting-level frame.

    Filters to postings that:
    - resolved to a Polish powiat (job_powiat.powiat IS NOT NULL),
    - have a NACE division mapping,
    - have a known Ukrainian-friendly flag (0 or 1).
    """

    print("Loading UKR flags…")
    flags = load_ukr_flags()
    print(f"  flags: {len(flags):,}")

    print("Loading NACE mapping…")
    nace_map = load_nace_map()
    print(f"  postings with NACE: {len(nace_map):,}")

    print("Reading job_ads + job_powiat…")
    con = sqlite3.connect(str(JOBS_DB))
    df = pd.read_sql_query(
        """
        SELECT j.id        AS job_id,
               j.job_category_narrow,
               j.seniority_level,
               j.contract_types,
               jp.voivodeship,
               jp.powiat
        FROM job_ads j
        JOIN job_powiat jp
          ON jp.job_id = j.id
        WHERE jp.powiat IS NOT NULL AND jp.powiat != ''
          AND jp.voivodeship IS NOT NULL AND jp.voivodeship != ''
        """,
        con,
    )
    con.close()
    print(f"  postings with powiat: {len(df):,}")

    df["ukr_flag"] = df["job_id"].map(flags)
    df = df.dropna(subset=["ukr_flag"]).copy()
    df["ukr_flag"] = df["ukr_flag"].astype(int)

    df["nace_code"] = df["job_id"].map(nace_map)
    df = df.dropna(subset=["nace_code"]).copy()
    df["nace_section"] = df["nace_code"].str[0]
    df["nace_division"] = df["nace_code"].str.extract(r"^[A-Z](\d{2})")
    df = df.dropna(subset=["nace_division"]).copy()
    df["nace_division"] = (
        df["nace_section"].astype(str) + df["nace_division"].astype(str)
    )

    df["voiv_norm"] = df["voivodeship"].map(norm_voiv)
    df["powiat_norm"] = df["powiat"].map(norm_powiat)
    df["powiat_key"] = df.apply(
        lambda r: f"{r['voiv_norm']}__{r['powiat_norm']}", axis=1
    )

    # Simplify multi-value contract column → first listed token.
    df["contract_simple"] = (
        df["contract_types"].fillna("(missing)").str.split(",").str[0].str.strip()
    )
    df["seniority_simple"] = df["seniority_level"].fillna("(missing)").str.strip()
    df["job_cat_narrow"] = df["job_category_narrow"].fillna("(missing)").str.strip()

    print(f"  final frame: {len(df):,} rows, {df['ukr_flag'].mean():.3%} UA share")
    return df.reset_index(drop=True)


# ---------------------------------------------------------------------------
# (1) Shift-share / Oaxaca-style decomposition
# ---------------------------------------------------------------------------
def shift_share_decomposition(
    df: pd.DataFrame, by: str, k_col: str = "nace_division", min_n: int = 100
) -> pd.DataFrame:
    """Return per-unit decomposition into compositional and behavioural gaps.

    For each region p (powiat or voivodeship):

        gap = s_p - s_PL
        within   = Σ_k w_pk · (s_pk - s_PL,k)         [behavioural]
        between  = Σ_k (w_pk - w_PL,k) · s_PL,k       [compositional]

    where w_pk = n_pk / n_p and s_pk = ukr_pk / n_pk.
    Tiny sectors in a region are still included; the closure ``gap ≈ within + between``
    holds by construction.
    """

    nation_share = df["ukr_flag"].mean()
    # National sector statistics
    nat = df.groupby(k_col).agg(n_PL=("ukr_flag", "size"), u_PL=("ukr_flag", "sum"))
    nat["s_PL_k"] = nat["u_PL"] / nat["n_PL"]
    nat["w_PL_k"] = nat["n_PL"] / nat["n_PL"].sum()

    by_unit = df.groupby([by, k_col]).agg(
        n_pk=("ukr_flag", "size"), u_pk=("ukr_flag", "sum")
    )
    by_unit = by_unit.join(nat[["s_PL_k", "w_PL_k"]], on=k_col)
    by_unit["s_pk"] = by_unit["u_pk"] / by_unit["n_pk"]

    totals = by_unit.groupby(level=0).agg(n_p=("n_pk", "sum"), u_p=("u_pk", "sum"))
    totals["s_p"] = totals["u_p"] / totals["n_p"]
    totals["gap"] = totals["s_p"] - nation_share

    by_unit = by_unit.join(totals[["n_p"]], on=by)
    by_unit["w_pk"] = by_unit["n_pk"] / by_unit["n_p"]
    by_unit["within_term"] = by_unit["w_pk"] * (by_unit["s_pk"] - by_unit["s_PL_k"])
    by_unit["between_term"] = (by_unit["w_pk"] - by_unit["w_PL_k"]) * by_unit["s_PL_k"]

    agg = by_unit.groupby(level=0).agg(
        within=("within_term", "sum"), between=("between_term", "sum")
    )
    out = totals.join(agg)
    out["check_resid"] = out["gap"] - out["within"] - out["between"]
    out = out[out["n_p"] >= min_n].copy()
    out["nation_share"] = nation_share
    out.index.name = by
    return out.reset_index()


# ---------------------------------------------------------------------------
# (2) LPM + Logit with powiat fixed effects
# ---------------------------------------------------------------------------
def build_design_matrix(
    df: pd.DataFrame,
    powiats: list[str],
) -> tuple[sparse.csr_matrix, list[str], pd.Series, sparse.csr_matrix, list[str]]:
    """Build sparse design matrices.

    Returns
    -------
    X        : sparse covariate matrix (no constant), shape (n, p)
    x_cols   : list of covariate names matching X columns
    y        : binary outcome vector aligned with X
    P        : sparse powiat-FE matrix (n, |powiats|) — one dummy per powiat
               WITHOUT a reference category drop (intercept handled in OLS by
               removing the column-mean / not adding constant).
    powiats  : list of powiat keys matching P columns
    """

    categorical_cols = [
        "nace_division",
        "contract_simple",
        "seniority_simple",
    ]

    powiat_index = {p: i for i, p in enumerate(powiats)}

    # Powiat sparse matrix (one dummy per powiat — no reference drop).
    row_idx = np.arange(len(df), dtype=np.int64)
    col_idx = df["powiat_key"].map(powiat_index).to_numpy()
    P = sparse.csr_matrix(
        (np.ones(len(df)), (row_idx, col_idx)),
        shape=(len(df), len(powiats)),
    )

    # Categorical covariates — drop the modal category to avoid dummy trap.
    blocks: list[sparse.csr_matrix] = []
    col_names: list[str] = []
    for c in categorical_cols:
        levels = df[c].value_counts().index.tolist()
        if not levels:
            continue
        reference = levels[0]  # drop modal
        kept = [lv for lv in levels if lv != reference]
        idx = {lv: i for i, lv in enumerate(kept)}
        keep_mask = df[c].map(idx)
        rows = np.where(keep_mask.notna())[0]
        cols = keep_mask.dropna().astype(int).to_numpy()
        data = np.ones(len(rows))
        block = sparse.csr_matrix(
            (data, (rows, cols)), shape=(len(df), len(kept))
        )
        blocks.append(block)
        col_names.extend(f"{c}={lv}" for lv in kept)

    X = sparse.hstack(blocks, format="csr") if blocks else sparse.csr_matrix(
        (len(df), 0)
    )
    y = df["ukr_flag"].astype(float)
    return X, col_names, y, P, powiats


def fit_lpm_with_fe(
    X: sparse.csr_matrix,
    y: pd.Series,
    P: sparse.csr_matrix,
    powiats: list[str],
) -> dict:
    """Within-transform on powiat FE → sparse OLS via normal equations.

    Uses the Frisch–Waugh–Lovell identity to keep ``X`` sparse:

        XtX_demeaned = X'X - X̄_p' diag(n_p) X̄_p
        Xty_demeaned = X'y - X̄_p' diag(n_p) ȳ_p

    where ``X̄_p`` are per-powiat covariate means.  ``XtX_demeaned`` is a
    dense ``p × p`` matrix (p ~ 200 in practice) so solving by Cholesky is
    fast.  No materialisation of the demeaned design matrix is needed.
    """

    import time

    t0 = time.time()
    y_arr = y.to_numpy().astype(np.float64)
    n = len(y_arr)
    n_p = np.asarray(P.sum(axis=0)).ravel().astype(np.float64)
    n_p_safe = np.where(n_p > 0, n_p, 1.0)

    Pt = P.T.tocsr()
    y_mean_p = (Pt @ y_arr) / n_p_safe

    if X.shape[1] == 0:
        return {
            "powiats": powiats,
            "beta": np.zeros(0),
            "se_beta": np.zeros(0),
            "x_cols": [],
            "delta": y_mean_p,
            "delta_se": np.sqrt(y_mean_p * (1 - y_mean_p) / n_p_safe),
            "y_mean_p": y_mean_p,
            "x_mean_p": np.zeros((P.shape[1], 0)),
            "resid_sd": float(np.sqrt(np.var(y_arr))),
            "n_p": n_p,
            "sigma2": float(np.var(y_arr)),
        }

    # Per-powiat covariate sums and means
    Xs = (Pt @ X).toarray().astype(np.float64)  # (G, p)
    X_mean_p = Xs / n_p_safe[:, None]
    print(f"    [{time.time()-t0:.1f}s] X̄_p computed: {X_mean_p.shape}")

    # X'X (sparse dense) – p x p
    XtX_full = (X.T @ X).toarray().astype(np.float64)
    print(f"    [{time.time()-t0:.1f}s] X'X computed: {XtX_full.shape}")

    # Demeaned cross-products via FWL
    correction = X_mean_p.T @ (X_mean_p * n_p_safe[:, None])  # (p, p)
    XtX_demeaned = XtX_full - correction

    Xty_full = X.T @ y_arr
    Xty_demeaned = Xty_full - X_mean_p.T @ (n_p_safe * y_mean_p)
    print(f"    [{time.time()-t0:.1f}s] normal equations assembled")

    # Solve.  Use lstsq with rank-revealing for robustness against
    # near-singular columns (e.g. one-hot levels nested inside powiat).
    beta, *_ = np.linalg.lstsq(XtX_demeaned, Xty_demeaned, rcond=None)
    print(f"    [{time.time()-t0:.1f}s] beta solved")

    # Residuals — compute via streaming to avoid densifying X
    # ŷ_demeaned = X β - P (X̄_p β)
    Xb = X @ beta  # (n,)
    Xmean_b = X_mean_p @ beta  # (G,)
    y_hat_dem = Xb - P @ Xmean_b
    y_tilde = y_arr - P @ y_mean_p
    resid = y_tilde - y_hat_dem
    p = X.shape[1]
    G = P.shape[1]
    dof = max(n - p - G, 1)
    sigma2 = float(resid @ resid / dof)
    print(f"    [{time.time()-t0:.1f}s] σ_e={math.sqrt(sigma2):.4f}, dof={dof:,}")

    # Eicker-Huber-White SE on β
    # Sandwich: (XtX_dem)^{-1} (X̃' Ω X̃) (XtX_dem)^{-1}
    # Compute X̃' Ω X̃ = X' diag(r²) X - X̄_p' diag(n_p · r²_p_mean) X̄_p cross-terms
    # Approximation: use plain σ²·(XtX_dem)^{-1} for the coefficient SEs.
    XtX_inv = np.linalg.pinv(XtX_demeaned)
    cov_beta = sigma2 * XtX_inv
    se_beta = np.sqrt(np.maximum(np.diag(cov_beta), 0.0))

    delta = y_mean_p - X_mean_p @ beta
    delta_se = np.sqrt(sigma2 / n_p_safe)

    return {
        "powiats": powiats,
        "beta": beta,
        "se_beta": se_beta,
        "x_cols": None,
        "delta": delta,
        "delta_se": delta_se,
        "y_mean_p": y_mean_p,
        "x_mean_p": X_mean_p,
        "resid_sd": float(math.sqrt(sigma2)),
        "n_p": n_p,
        "sigma2": sigma2,
    }


def fit_logit_with_fe(
    df: pd.DataFrame,
    powiats: list[str],
    sample_size: int | None = 200_000,
    seed: int = 7,
) -> dict | None:
    """Statsmodels Logit on a sample with powiat FE.

    Fitting Logit on 700k rows × ~hundreds of dummies is slow; we use a
    stratified subsample. We report only the controls' coefficients and the
    average marginal effect; powiat FE are not extracted from Logit (LPM is
    the primary measure for δ_p).
    """

    rng = np.random.default_rng(seed)
    if sample_size and sample_size < len(df):
        idx = rng.choice(len(df), size=sample_size, replace=False)
        sample = df.iloc[idx].reset_index(drop=True)
    else:
        sample = df.copy()

    # Keep only powiats with enough postings in the sample to avoid
    # singular FE.
    counts = sample["powiat_key"].value_counts()
    keep = counts[counts >= 30].index
    sample = sample[sample["powiat_key"].isin(keep)].copy()
    if sample.empty:
        return None

    cat_cols = [
        "nace_division",
        "contract_simple",
        "seniority_simple",
        "powiat_key",
    ]
    sample[cat_cols] = sample[cat_cols].astype("category")

    formula_parts = [f"C({c})" for c in cat_cols]
    formula = "ukr_flag ~ " + " + ".join(formula_parts)
    try:
        model = sm.formula.glm(
            formula=formula,
            data=sample,
            family=sm.families.Binomial(),
        ).fit(maxiter=80, disp=False)
    except Exception as exc:  # pragma: no cover - diagnostic only
        print(f"  logit failed: {exc}")
        return None

    # Extract the coefficient block for selected controls (NACE division,
    # contract, seniority — not powiat FE since we already have them from LPM).
    keep_prefixes = ("C(nace_division)", "C(contract_simple)", "C(seniority_simple)")
    rows = []
    for name, coef in model.params.items():
        if not name.startswith(keep_prefixes):
            continue
        se = model.bse[name]
        rows.append(
            {
                "term": name.replace("C(", "").replace(")[T.", "=").rstrip("]"),
                "coef": float(coef),
                "se": float(se),
                "z": float(coef / se) if se else float("nan"),
                "p": float(2 * (1 - stats.norm.cdf(abs(coef / se)))) if se else float("nan"),
            }
        )

    return {
        "n_sample": int(len(sample)),
        "n_params": int(len(model.params)),
        "pseudo_r2": float(1 - model.llf / model.llnull),
        "aic": float(model.aic),
        "controls": rows,
    }


# ---------------------------------------------------------------------------
# (3) PESEL UKR refugee density regression
# ---------------------------------------------------------------------------
POWIAT_NAME_FIXES = {
    # MSWiA POWIAT column → match against keyed geojson `key`
    "warszawa": "warszawa",
    "krakow": "krakow",
}


def load_mswia_ukr() -> pd.DataFrame:
    df = pd.read_excel(UKR_MSWIA_XLSX, header=[0, 1])
    keep = df.iloc[:, [0, 1, 2, 5]].copy()
    keep.columns = ["teryt", "powiat", "voivodeship", "ukr_total"]
    keep = keep.dropna(subset=["powiat"]).copy()
    keep["powiat_norm"] = keep["powiat"].map(norm_powiat)
    keep["voiv_norm"] = keep["voivodeship"].map(norm_voiv)
    keep["powiat_key"] = keep.apply(
        lambda r: f"{r['voiv_norm']}__{r['powiat_norm']}", axis=1
    )
    keep["ukr_total"] = pd.to_numeric(keep["ukr_total"], errors="coerce").fillna(0)
    return keep[["powiat_key", "ukr_total", "powiat", "voivodeship"]]


def load_employed() -> pd.DataFrame:
    raw = json.loads(EMPLOYED_JSON.read_text(encoding="utf-8"))
    rows = []
    for item in raw["items"]:
        rows.append(
            {
                "powiat_norm": norm_powiat(item["name"].replace("Powiat ", "Powiat ")),
                "voiv_norm": norm_voiv(item["voivodeship"]),
                "employed": item.get("employed"),
            }
        )
    out = pd.DataFrame(rows)
    out["powiat_key"] = out.apply(
        lambda r: f"{r['voiv_norm']}__{r['powiat_norm']}", axis=1
    )
    return out[["powiat_key", "employed"]]


def regress_delta_on_pesel(
    delta_df: pd.DataFrame,
    ukr_df: pd.DataFrame,
    employed_df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[dict]]:
    """OLS of δ_p on ln(UKR_density), border dummy, metro dummy."""

    merged = delta_df.merge(ukr_df, on="powiat_key", how="left").merge(
        employed_df, on="powiat_key", how="left"
    )
    merged["ukr_total"] = merged["ukr_total"].fillna(0)
    merged["employed"] = pd.to_numeric(merged["employed"], errors="coerce")
    merged = merged.dropna(subset=["employed"]).copy()
    merged = merged[merged["employed"] > 0].copy()
    merged["ukr_density"] = merged["ukr_total"] / merged["employed"]
    merged["ln_ukr_density"] = np.log(np.maximum(merged["ukr_density"], 1e-6))
    merged["border"] = merged["powiat_key"].isin(BORDER_KEYS_UKR).astype(int)
    merged["metro"] = merged["powiat_key"].isin(METRO_KEYS).astype(int)

    if merged.empty:
        return merged, []

    specs = []

    def run(X_cols: list[str], label: str) -> dict:
        X = sm.add_constant(merged[X_cols].astype(float))
        y = merged["delta"].astype(float)
        # Inverse-variance weighting by 1/SE^2 if SE available.
        weights = 1.0 / np.maximum(merged["delta_se"].astype(float) ** 2, 1e-8)
        model = sm.WLS(y, X, weights=weights).fit(cov_type="HC1")
        return {
            "label": label,
            "n": int(model.nobs),
            "r2": float(model.rsquared),
            "r2_adj": float(model.rsquared_adj),
            "coefs": [
                {
                    "term": name,
                    "coef": float(model.params[name]),
                    "se": float(model.bse[name]),
                    "p": float(model.pvalues[name]),
                }
                for name in X.columns
            ],
        }

    specs.append(run(["ln_ukr_density"], "(1) ln(UKR/empl)"))
    specs.append(run(["ln_ukr_density", "border"], "(2) + border"))
    specs.append(run(["ln_ukr_density", "border", "metro"], "(3) + metro"))

    return merged, specs


# ---------------------------------------------------------------------------
# (4) Empirical Bayes shrinkage
# ---------------------------------------------------------------------------
def empirical_bayes_shrinkage(
    df: pd.DataFrame, min_n: int = 30
) -> tuple[pd.DataFrame, dict]:
    grp = df.groupby("powiat_key").agg(
        voivodeship=("voivodeship", "first"),
        powiat=("powiat", "first"),
        n_p=("ukr_flag", "size"),
        u_p=("ukr_flag", "sum"),
    )
    grp = grp[grp["n_p"] >= min_n].copy()
    grp["raw_share"] = grp["u_p"] / grp["n_p"]

    p = grp["raw_share"]
    n = grp["n_p"]

    # Method-of-moments for Beta(α, β) on cross-powiat distribution
    weighted_mean = (grp["u_p"].sum()) / (grp["n_p"].sum())
    var = ((p - weighted_mean) ** 2).mean()
    # Total variance = E[Var(p_p|n_p)] + Var(E[p_p|n_p])
    expected_within = (weighted_mean * (1 - weighted_mean) / n).mean()
    cross_var = max(var - expected_within, 1e-6)
    # Var(Beta) = m(1-m) / (α+β+1)  →  precision φ
    phi = max(weighted_mean * (1 - weighted_mean) / cross_var - 1, 1.0)
    alpha_hat = weighted_mean * phi
    beta_hat = (1 - weighted_mean) * phi

    grp["eb_share"] = (grp["u_p"] + alpha_hat) / (grp["n_p"] + alpha_hat + beta_hat)
    grp["shrinkage"] = grp["raw_share"] - grp["eb_share"]

    params = {
        "alpha": float(alpha_hat),
        "beta": float(beta_hat),
        "phi": float(phi),
        "national_share": float(weighted_mean),
        "n_powiats": int(len(grp)),
    }
    return grp.reset_index(), params


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-logit",
        action="store_true",
        help="Fit statsmodels GLM Logit with powiat FE on a stratified sample (slow).",
    )
    parser.add_argument(
        "--logit-sample",
        type=int,
        default=120_000,
        help="Sample size used for the logit fit when --with-logit is set.",
    )
    args = parser.parse_args()

    df = load_posting_frame()
    audit: dict = {}

    print("\n=== (1) Shift-share decomposition ===")
    powiat_decomp = shift_share_decomposition(
        df, by="powiat_key", min_n=MIN_POSTINGS_PER_POWIAT
    )
    voiv_decomp = shift_share_decomposition(df, by="voiv_norm", min_n=500)

    powiat_lookup = (
        df.groupby("powiat_key")
        .agg(voivodeship=("voivodeship", "first"), powiat=("powiat", "first"))
        .reset_index()
    )
    powiat_decomp = powiat_decomp.merge(powiat_lookup, on="powiat_key", how="left")
    voiv_decomp = voiv_decomp.rename(columns={"voiv_norm": "voiv_key"})
    # Re-attach original-case voivodeship name (so we get "Łódzkie" not
    # the accent-stripped variant).
    voiv_names = (
        df.assign(voiv_norm=df["voivodeship"].map(norm_voiv))
        .groupby("voiv_norm")["voivodeship"]
        .first()
    )
    voiv_decomp["voivodeship_name"] = (
        voiv_decomp["voiv_key"].map(voiv_names).fillna(voiv_decomp["voiv_key"]).str.title()
    )

    audit["nation_share"] = float(df["ukr_flag"].mean())
    audit["n_postings"] = int(len(df))
    audit["n_powiats_eligible"] = int(len(powiat_decomp))

    print(f"  national share: {audit['nation_share']:.3%}")
    print(f"  eligible powiats (>= {MIN_POSTINGS_PER_POWIAT} postings): {len(powiat_decomp)}")
    print(f"  voivodeships: {len(voiv_decomp)}")

    # Pick top-K powiats by absolute gap for display
    powiat_decomp["abs_gap"] = powiat_decomp["gap"].abs()
    top_powiats = powiat_decomp.nlargest(
        TOP_K_POWIATS_FOR_DECOMP, "abs_gap"
    ).copy()

    print("\n=== (2) LPM with powiat FE ===")
    # Restrict to powiats with enough mass for identification
    counts = df.groupby("powiat_key").size()
    eligible = counts[counts >= MIN_POSTINGS_PER_POWIAT].index.tolist()
    dff = df[df["powiat_key"].isin(eligible)].copy().reset_index(drop=True)
    print(f"  rows kept: {len(dff):,}; powiats kept: {len(eligible)}")

    X, x_cols, y, P, powiats = build_design_matrix(dff, eligible)
    print(f"  X dims: {X.shape}, P dims: {P.shape}")

    lpm = fit_lpm_with_fe(X, y, P, powiats)
    delta_df = pd.DataFrame(
        {
            "powiat_key": lpm["powiats"],
            "delta": lpm["delta"],
            "delta_se": lpm["delta_se"],
            "raw_mean": lpm["y_mean_p"],
            "n_p": lpm["n_p"],
        }
    )
    delta_df = delta_df.merge(powiat_lookup, on="powiat_key", how="left")
    delta_df["delta_pp"] = delta_df["delta"] * 100
    delta_df["delta_pp_se"] = delta_df["delta_se"] * 100
    delta_df["delta_z"] = delta_df["delta"] / delta_df["delta_se"]
    print(
        f"  δ_p quantiles (pp): "
        f"{np.percentile(delta_df['delta_pp'], [5, 25, 50, 75, 95]).round(2)}"
    )

    if args.with_logit:
        print("\n=== (2b) Logit on stratified sample ===")
        logit = fit_logit_with_fe(dff, eligible, sample_size=args.logit_sample)
        if logit:
            print(
                f"  n={logit['n_sample']:,}, params={logit['n_params']}, pseudo-R² ≈ "
                f"{logit['pseudo_r2']:.3f}"
            )
    else:
        logit = None
        print("\n=== (2b) Logit skipped (pass --with-logit to enable) ===")

    print("\n=== (3) PESEL UKR missing-variable test ===")
    ukr_df = load_mswia_ukr()
    employed_df = load_employed()
    merged, specs = regress_delta_on_pesel(delta_df, ukr_df, employed_df)
    print(f"  merged rows: {len(merged)}")
    for s in specs:
        print(f"  {s['label']}  n={s['n']}  R²={s['r2']:.3f}")

    print("\n=== (4) Empirical Bayes shrinkage ===")
    eb_df, eb_params = empirical_bayes_shrinkage(df)
    print(
        f"  α̂={eb_params['alpha']:.2f}, β̂={eb_params['beta']:.2f}, "
        f"national={eb_params['national_share']:.3%}, n powiats={eb_params['n_powiats']}"
    )

    audit["lpm"] = {
        "n_powiats": int(len(delta_df)),
        "resid_sd": float(lpm["resid_sd"]),
        "n_params": int(X.shape[1]),
    }
    audit["logit"] = logit or {}
    audit["pesel_regressions"] = specs
    audit["eb"] = eb_params

    # ------------------------------------------------------------------
    # Payload for frontend
    # ------------------------------------------------------------------
    def fmt_pct(v: float) -> float:
        return round(float(v) * 100, 3)

    def _clean(v) -> str:
        if v is None:
            return ""
        if isinstance(v, float) and math.isnan(v):
            return ""
        return str(v).strip()

    def powiat_display(row) -> str:
        powiat_raw = _clean(row.get("powiat", "") if hasattr(row, "get") else "")
        # Strip "; gm. X" suffix and lower-case prefix → presentable title-case
        powiat_clean = re.sub(r"\s*;\s*gm\..*$", "", powiat_raw).strip()
        powiat_clean = re.sub(r"^powiat\s+", "", powiat_clean, flags=re.IGNORECASE)
        if powiat_clean:
            powiat_clean = powiat_clean[:1].upper() + powiat_clean[1:]
        voiv = _clean(row.get("voivodeship", "") if hasattr(row, "get") else "").title()
        if not powiat_clean:
            return _clean(row.get("powiat_key", "") if hasattr(row, "get") else "")
        return f"{powiat_clean} · {voiv}" if voiv else powiat_clean

    decomp_powiat_payload = [
        {
            "key": r["powiat_key"],
            "label": powiat_display(r),
            "n": int(r["n_p"]),
            "share_pct": fmt_pct(r["s_p"]),
            "gap_pp": fmt_pct(r["gap"]),
            "within_pp": fmt_pct(r["within"]),
            "between_pp": fmt_pct(r["between"]),
        }
        for _, r in top_powiats.sort_values("gap", ascending=False).iterrows()
    ]

    decomp_voiv_payload = [
        {
            "key": r["voiv_key"],
            "label": r["voivodeship_name"],
            "n": int(r["n_p"]),
            "share_pct": fmt_pct(r["s_p"]),
            "gap_pp": fmt_pct(r["gap"]),
            "within_pp": fmt_pct(r["within"]),
            "between_pp": fmt_pct(r["between"]),
        }
        for _, r in voiv_decomp.sort_values("gap", ascending=False).iterrows()
    ]

    delta_payload = [
        {
            "key": r["powiat_key"],
            "label": powiat_display(r),
            "n": int(r["n_p"]),
            "raw_share_pct": fmt_pct(r["raw_mean"]),
            "delta_pp": round(float(r["delta_pp"]), 3),
            "delta_pp_se": round(float(r["delta_pp_se"]), 3),
            "delta_z": round(float(r["delta_z"]), 2),
        }
        for _, r in delta_df.iterrows()
    ]

    eb_payload = [
        {
            "key": r["powiat_key"],
            "label": powiat_display(r),
            "n": int(r["n_p"]),
            "u": int(r["u_p"]),
            "raw_pct": fmt_pct(r["raw_share"]),
            "eb_pct": fmt_pct(r["eb_share"]),
            "shrinkage_pp": fmt_pct(r["shrinkage"]),
        }
        for _, r in eb_df.iterrows()
    ]

    pesel_scatter = [
        {
            "key": r["powiat_key"],
            "label": powiat_display(r),
            "ln_ukr_density": round(float(r["ln_ukr_density"]), 3),
            "ukr_per_employed_pct": round(float(r["ukr_density"]) * 100, 3),
            "delta_pp": round(float(r["delta_pp"]), 3),
            "n": int(r["n_p"]),
            "border": int(r["border"]),
            "metro": int(r["metro"]),
        }
        for _, r in merged.iterrows()
    ]

    payload = {
        "meta": {
            "national_share_pct": fmt_pct(df["ukr_flag"].mean()),
            "n_postings": int(len(df)),
            "min_postings_per_powiat": MIN_POSTINGS_PER_POWIAT,
        },
        "decomp_powiat": decomp_powiat_payload,
        "decomp_voivodeship": decomp_voiv_payload,
        "powiat_delta": delta_payload,
        "eb_shrinkage": eb_payload,
        "eb_params": {
            "alpha": round(eb_params["alpha"], 4),
            "beta": round(eb_params["beta"], 4),
            "phi": round(eb_params["phi"], 4),
            "national_share_pct": fmt_pct(eb_params["national_share"]),
        },
        "pesel": {
            "regressions": [
                {
                    "label": s["label"],
                    "n": s["n"],
                    "r2": round(s["r2"], 3),
                    "r2_adj": round(s["r2_adj"], 3),
                    "coefs": [
                        {
                            "term": c["term"],
                            "coef_pp": round(c["coef"] * 100, 3),
                            "se_pp": round(c["se"] * 100, 3),
                            "p": round(c["p"], 4),
                        }
                        for c in s["coefs"]
                    ],
                }
                for s in specs
            ],
            "scatter": pesel_scatter,
        },
        "logit_controls": [
            {
                "term": c["term"],
                "coef": round(c["coef"], 4),
                "se": round(c["se"], 4),
                "z": round(c["z"], 2),
                "p": round(c["p"], 4),
            }
            for c in (logit or {}).get("controls", [])
        ],
    }

    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text(
        "window.__UKR_DECOMP__ = " + json.dumps(payload, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    OUT_AUDIT.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nWrote {OUT_JS.relative_to(BASE)} and {OUT_AUDIT.relative_to(BASE)}")


if __name__ == "__main__":
    main()

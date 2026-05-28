#!/usr/bin/env python3
"""Export data for presentation charts in the Quarto report."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from chart_label_translations import (
    bur_category_en,
    bur_modality_en,
    kzis_occupation_en,
    region_display_en,
    skill_label_en,
    voivodeship_en,
)

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "assets" / "results_extended_data.js"
PRES = ROOT / "presentation"
YEARLY_DIR = ROOT / "trainings" / "data" / "yearly"
L1 = PRES / "skills_mismatch_l1_2025.csv"
L1_FULL_SUPPLY = PRES / "skills_mismatch_l1.csv"  # languages: 2025-only BUR has almost no L-tags
L2 = PRES / "skills_mismatch_l2.csv"
SKILL_CODES = [f"S{i}" for i in range(1, 9)]

def _pillar_row(row, d_total: int, s_total: int) -> dict:
    """Shares renormalised to 100% within the pillar (matches build_skills_mismatch charts)."""
    d_share = (row.mentions_offers / d_total) if d_total else 0.0
    s_share = (row.trainings_with_group / s_total) if s_total else 0.0
    return {
        "code": str(row.code),
        "title": str(row.title),
        "label": str(row.title),
        "demand_pct": round(d_share * 100, 2),
        "supply_pct": round(s_share * 100, 2),
        "gap_pp": round((d_share - s_share) * 100, 2),
    }


def load_mismatch_pillar_renorm(
    df: pd.DataFrame,
    family: str,
    *,
    code_re: str | None = None,
    order: list[str] | None = None,
    exclude_codes: set[str] | None = None,
) -> list[dict]:
    sub = df[df["family"] == family].copy()
    if code_re:
        sub = sub[sub["code"].astype(str).str.match(code_re)]
    if exclude_codes:
        sub = sub[~sub["code"].astype(str).isin(exclude_codes)]
    if order:
        by_code = {str(r.code): r for r in sub.itertuples(index=False)}
        ordered = [by_code[c] for c in order if c in by_code]
    else:
        ordered = list(sub.sort_values("mentions_offers", ascending=False).itertuples(index=False))
    d_total = int(sum(r.mentions_offers for r in ordered))
    s_total = int(sum(r.trainings_with_group for r in ordered))
    return [_pillar_row(r, d_total, s_total) for r in ordered]


def load_languages_pillar(df: pd.DataFrame) -> list[dict]:
    """Top languages + Other bucket; exclude L1 (rollup) and L42 (Polish); renorm within L."""
    top_n = 9
    excluded = {"L", "L1", "L42"}
    universe = df[
        (df["family"] == "Languages (L)")
        & df["code"].astype(str).str.match(r"^L")
        & ~df["code"].astype(str).isin(excluded)
    ].copy()
    universe = universe.sort_values("mentions_offers", ascending=False)
    top = list(universe.head(top_n).itertuples(index=False))
    others = list(universe.iloc[top_n:].itertuples(index=False))
    rows = list(top)
    if others:
        from types import SimpleNamespace

        rows.append(
            SimpleNamespace(
                code="Other",
                title=f"Other ({len(others)} languages)",
                mentions_offers=sum(r.mentions_offers for r in others),
                trainings_with_group=sum(r.trainings_with_group for r in others),
            )
        )
    d_total = int(sum(r.mentions_offers for r in rows))
    s_total = int(sum(r.trainings_with_group for r in rows))
    return [_pillar_row(r, d_total, s_total) for r in rows]


def load_l2_top(n: int = 8) -> dict:
    df = pd.read_csv(L2)
    df = df[df["family"].isin(["Skills (S)", "Knowledge (ISCED)", "Transversal (T)"])].copy()
    under = df.nlargest(n, "gap_pp")
    over = df.nsmallest(n, "gap_pp")

    def rows(sub):
        return [
            {"title": f"{r.title} ({r.code})", "gap_pp": round(r.gap_pp, 2)}
            for r in sub.itertuples(index=False)
        ]

    return {"under_supplied": rows(under), "over_supplied": rows(over)}


def mismatch_by_family(l1: pd.DataFrame) -> list[dict]:
    order = ["Skills (S)", "Transversal (T)", "Knowledge (ISCED)", "Languages (L)"]
    labels = {
        "Skills (S)": "ESCO skills (S1–S8)",
        "Transversal (T)": "Transversal (T1–T6)",
        "Knowledge (ISCED)": "Knowledge (ISCED)",
        "Languages (L)": "Languages (L)",
    }
    rows = []
    for fam in order:
        sub = l1[l1["family"] == fam]
        rows.append(
            {
                "family": labels[fam],
                "demand_pct": round(sub["demand_share"].sum() * 100, 2),
                "supply_pct": round(sub["supply_share"].sum() * 100, 2),
            }
        )
    return rows


def training_duration_yearly() -> list[dict]:
    rows = []
    for year in range(2016, 2026):
        p = YEARLY_DIR / f"bur_{year}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p, columns=["liczba_godzin", "rodzaj_uslugi"])
        df = df[df["rodzaj_uslugi"] == "Usługa szkoleniowa"]
        h = pd.to_numeric(df["liczba_godzin"], errors="coerce").dropna()
        if h.empty:
            continue
        rows.append(
            {
                "year": year,
                "mean": round(float(h.mean()), 1),
                "median": round(float(h.median()), 1),
                "p90": round(float(h.quantile(0.9)), 1),
            }
        )
    return rows


def training_duration_2025_by_category() -> list[dict]:
    df = pd.read_parquet(
        YEARLY_DIR / "bur_2025.parquet",
        columns=["liczba_godzin", "rodzaj_uslugi", "kategoria_uslugi"],
    )
    df = df[df["rodzaj_uslugi"] == "Usługa szkoleniowa"].copy()
    df["liczba_godzin"] = pd.to_numeric(df["liczba_godzin"], errors="coerce")
    df = df.dropna(subset=["liczba_godzin", "kategoria_uslugi"])
    g = (
        df.groupby("kategoria_uslugi")["liczba_godzin"]
        .agg(n="count", median="median", mean="mean", p90=lambda s: s.quantile(0.9))
        .reset_index()
        .sort_values("n", ascending=False)
        .head(10)
    )
    return [
        {
            "category": bur_category_en(row.kategoria_uslugi),
            "n": int(row.n),
            "median": round(float(row.median), 1),
            "mean": round(float(row.mean), 1),
            "p90": round(float(row.p90), 1),
        }
        for row in g.itertuples(index=False)
    ]


def training_duration_2025_buckets() -> list[dict]:
    df = pd.read_parquet(
        YEARLY_DIR / "bur_2025.parquet",
        columns=["liczba_godzin", "rodzaj_uslugi"],
    )
    df = df[df["rodzaj_uslugi"] == "Usługa szkoleniowa"]
    df["h"] = pd.to_numeric(df["liczba_godzin"], errors="coerce")
    df = df[df["h"] > 0]
    bins = [0, 1, 4, 8, 16, 24, 40, 80, 160, 320, 800, np.inf]
    labels = [
        "≤1h", "2–4h", "5–8h", "9–16h", "17–24h", "25–40h",
        "41–80h", "81–160h", "161–320h", "321–800h", ">800h",
    ]
    df["bucket"] = pd.cut(df["h"], bins=bins, labels=labels, right=True, include_lowest=True)
    counts = df.groupby("bucket", observed=True).size()
    total = int(counts.sum())
    return [
        {"bucket": lbl, "count": int(counts.get(lbl, 0)), "pct": round(counts.get(lbl, 0) / total * 100, 1)}
        for lbl in labels
    ]


def training_duration_2025_summary() -> dict:
    df = pd.read_parquet(
        YEARLY_DIR / "bur_2025.parquet",
        columns=["liczba_godzin", "rodzaj_uslugi"],
    )
    df = df[df["rodzaj_uslugi"] == "Usługa szkoleniowa"]
    h = pd.to_numeric(df["liczba_godzin"], errors="coerce").dropna()
    return {
        "median": round(float(h.median()), 1),
        "mean": round(float(h.mean()), 1),
        "p25": round(float(h.quantile(0.25)), 1),
        "p75": round(float(h.quantile(0.75)), 1),
        "p90": round(float(h.quantile(0.9)), 1),
        "p95": round(float(h.quantile(0.95)), 1),
        "p99": round(float(h.quantile(0.99)), 1),
    }


def training_change_2019_2025() -> list[dict]:
    def counts(year: int) -> pd.Series:
        df = pd.read_parquet(
            YEARLY_DIR / f"bur_{year}.parquet",
            columns=["wojewodztwo", "rodzaj_uslugi"],
        )
        df = df[df["rodzaj_uslugi"] == "Usługa szkoleniowa"].copy()
        df["voiv"] = df["wojewodztwo"].astype(str).str.strip().str.lower()
        df = df[df["voiv"].notna() & (df["voiv"] != "nan")]
        return df.groupby("voiv").size()

    c19, c25 = counts(2019), counts(2025)
    voivs = sorted(set(c19.index) | set(c25.index))
    rows = []
    for v in voivs:
        n19, n25 = int(c19.get(v, 0)), int(c25.get(v, 0))
        if n19 == 0 and n25 == 0:
            continue
        pct = round((n25 - n19) / n19 * 100, 1) if n19 else None
        rows.append(
            {
                "voivodeship": v,
                "label": voivodeship_en(v),
                "n_2019": n19,
                "n_2025": n25,
                "change_pct": pct,
            }
        )
    rows.sort(key=lambda r: r["change_pct"] if r["change_pct"] is not None else 999)
    return rows


def digital_examples_by_level() -> dict:
    df = pd.read_csv(PRES / "chinen_digital_skill_mapping.csv")
    df = df[df["mapping_status"] == "mapped"].copy()
    out: dict[str, list[str]] = {}
    for level in ["basic", "intermediate", "advanced"]:
        sub = df[df["level"] == level]
        skills = (
            sub.groupby("esco_skill_label_en")
            .size()
            .sort_values(ascending=False)
            .head(6)
            .index.tolist()
        )
        out[level] = skills
    return out


def care_s1s8_compare() -> list[dict]:
    df = pd.read_csv(PRES / "care_services_vs_nace_health_s1_s8.csv")
    care = df[df["segment"].str.contains("Our care services", na=False)]
    health = df[df["segment"].str.contains("NACE R86 healthcare only", na=False)]
    rows = []
    for code in SKILL_CODES:
        c = care[care["pillar"] == code]
        h = health[health["pillar"] == code]
        if c.empty:
            continue
        crow, hrow = c.iloc[0], h.iloc[0]
        rows.append(
            {
                "code": code,
                "title": crow.pillar_label,
                "care_share_pct": round(float(crow.share_of_segment_offers_pct), 1),
                "health_share_pct": round(float(hrow.share_of_segment_offers_pct), 1),
            }
        )
    return rows


def load_simple_csv(
    path: Path,
    label: str,
    value: str,
    pct: str | None = None,
    top: int = 15,
    *,
    label_fn=None,
) -> list[dict]:
    df = pd.read_csv(path).head(top)
    out = []
    for row in df.itertuples(index=False):
        raw = str(getattr(row, label))[:80]
        display = label_fn(raw) if label_fn else raw
        item = {"label": display, "value": int(getattr(row, value))}
        if pct:
            item["pct"] = round(float(getattr(row, pct)), 2)
        out.append(item)
    return out


def main() -> None:
    l1 = pd.read_csv(L1)
    l1_full = pd.read_csv(L1_FULL_SUPPLY)
    s1s8 = l1[l1["code"].isin(SKILL_CODES)].copy()

    payload = {
        "mismatch": {
            "meta": {
                "demand_mentions_m": 5.36,
                "demand_offers": 748922,
                "supply_tags": 410868,
                "supply_trainings": 719265,
                "jsd_l1": 0.161,
                "jsd_l2": 0.296,
            },
            "by_family": mismatch_by_family(l1),
            "skills_s1_s8": [
                {
                    "code": row.code,
                    "title": row.title,
                    "demand_pct": round(row.demand_share * 100, 2),
                    "supply_pct": round(row.supply_share * 100, 2),
                    "gap_pp": round(row.gap_pp, 2),
                }
                for row in s1s8.sort_values("demand_share", ascending=False).itertuples(index=False)
            ],
            "transversal": load_mismatch_pillar_renorm(
                l1,
                "Transversal (T)",
                code_re=r"^T\d$",
                order=["T1", "T2", "T3", "T4", "T5", "T6"],
            ),
            "knowledge": load_mismatch_pillar_renorm(
                l1,
                "Knowledge (ISCED)",
                code_re=r"^\d{2}$",
                order=[f"{i:02d}" for i in range(11)],
            ),
            "languages": load_languages_pillar(l1_full),
            "l2_top": load_l2_top(8),
        },
        "duration": {
            "yearly": training_duration_yearly(),
            "summary_2025": training_duration_2025_summary(),
            "buckets_2025": training_duration_2025_buckets(),
            "by_category_2025": training_duration_2025_by_category(),
        },
        "training_change_2019_2025": training_change_2019_2025(),
        "digital_examples": digital_examples_by_level(),
        "ai_nace_sections": load_simple_csv(
            PRES / "ai_nace_sections.csv", "nace_section_label", "ai_offers", "share_of_ai_offers_pct", 12
        ),
        "ai_nace_divisions": [
            {
                "label": f"{row.nace_div} — {row.label_en}",
                "value": int(row.ai_offers),
                "pct": round(float(row.share_of_ai_offers_pct), 2),
            }
            for row in pd.read_csv(PRES / "ai_nace_divisions_top15.csv").itertuples(index=False)
        ],
        "ai_transversal_groups": [
            {
                "label": row.group,
                "pct": round(float(row.share_of_transversal_offers_pct), 1),
                "offers": int(row.offers),
            }
            for row in pd.read_csv(PRES / "ai_offers_transversal_groups.csv").itertuples(index=False)
        ],
        "green_nace_sections": [
            {
                "label": row.section_label,
                "value": int(row.offers_with_green),
                "pct": round(float(row.share_within_section_pct), 2),
            }
            for row in pd.read_csv(PRES / "green_skills_by_nace_section.csv")
            .sort_values("share_within_section_pct", ascending=False)
            .head(12)
            .itertuples(index=False)
        ],
        "ukr_nace_sections": [
            {
                "code": row.nace_section,
                "label": row.nace_section_label,
                "chart_label": f"{row.nace_section}  ·  {row.nace_section_label}",
                "ukr_pct": round(float(row.ukrainian_friendly_share_pct), 2),
                "other_pct": round(float(row.non_ukrainian_friendly_share_pct), 2),
                "diff_pp": round(float(row.diff_pp), 2),
            }
            for row in pd.read_csv(PRES / "ukr_nace_sections_en.csv")
            .loc[
                lambda d: (d["ukrainian_friendly_share_pct"] >= 0.2)
                | (d["non_ukrainian_friendly_share_pct"] >= 0.2)
            ]
            .sort_values("diff_pp", ascending=False)
            .itertuples(index=False)
        ],
        "care": {
            "offers_kzis": 1095,
            "offers_refined": int(
                float(
                    pd.read_csv(PRES / "care_services_job_offers_refined_summary.csv")
                    .loc[lambda d: d.metric == "total_care_services_offers_refined", "value"]
                    .iloc[0]
                )
            ),
            "top_occupations": load_simple_csv(
                PRES / "care_services_kzis_top.csv",
                "kzis_occupation_name",
                "offer_count",
                top=15,
                label_fn=kzis_occupation_en,
            ),
            "top_skills": load_simple_csv(
                PRES / "care_services_top_esco_skills.csv",
                "skill",
                "offers",
                "share_of_care_offers_pct",
                12,
                label_fn=skill_label_en,
            ),
            "top_knowledge": load_simple_csv(
                PRES / "care_services_top_esco_knowledge.csv",
                "knowledge",
                "offers",
                "share_of_care_offers_pct",
                10,
                label_fn=skill_label_en,
            ),
            "top_transversal": load_simple_csv(
                PRES / "care_services_top_esco_transversal.csv",
                "transversal",
                "offers",
                "share_of_care_offers_pct",
                10,
                label_fn=skill_label_en,
            ),
            "s1s8_vs_health": care_s1s8_compare(),
            "employer_stats": [
                {
                    "segment": row.segment.replace(" (filtered KZiS set)", ""),
                    "unique_employers": int(row.unique_employers),
                    "mean_offers": round(float(row.mean_offers_per_employer), 2),
                    "top10_share_pct": round(float(row.share_offers_from_top_10_employers_pct), 1),
                }
                for row in pd.read_csv(PRES / "care_services_vs_health_nace_employer_stats.csv").itertuples(index=False)
            ],
            "bur_public_health_share": [
                {
                    "year": int(row.year),
                    "share_pct": round(float(row.public_health_share_pct), 2),
                    "trainings": int(row.public_health_trainings),
                }
                for row in pd.read_csv(PRES / "bur_public_health_share_by_year.csv").itertuples(index=False)
            ],
            "public_health_s1s8": [
                {
                    "code": row.pillar,
                    "title": row.label_en,
                    "share_pct": round(float(row.share_within_S1_S8_pct), 1),
                }
                for row in pd.read_csv(PRES / "bur_2025_zdrowie_publiczne_s1_s8_distribution.csv").itertuples(index=False)
                if row.pillar != "S7"
            ],
            "public_health_regions": load_simple_csv(
                PRES / "bur_2025_zdrowie_publiczne_regions.csv",
                "region",
                "n",
                "share_pct",
                12,
                label_fn=region_display_en,
            ),
            "public_health_modality": load_simple_csv(
                PRES / "bur_2025_zdrowie_publiczne_modality.csv",
                "delivery_modality",
                "n",
                "share_pct",
                8,
                label_fn=bur_modality_en,
            ),
            "public_health_duration": load_simple_csv(
                PRES / "bur_2025_zdrowie_publiczne_duration.csv", "duration", "n", "share_pct", 10
            ),
            "public_health_top_skills": load_simple_csv(
                PRES / "bur_2025_zdrowie_publiczne_top_skills.csv",
                "skill",
                "training_skill_tags",
                "share_of_skills_pct",
                10,
                label_fn=skill_label_en,
            ),
            "public_health_top_knowledge": load_simple_csv(
                PRES / "bur_2025_zdrowie_publiczne_top_knowledge.csv",
                "knowledge",
                "training_skill_tags",
                "share_of_knowledge_pct",
                8,
                label_fn=skill_label_en,
            ),
            "public_health_top_transversal": load_simple_csv(
                PRES / "bur_2025_zdrowie_publiczne_top_transversal_skills.csv",
                "transversal_skill",
                "training_skill_tags",
                "share_pct",
                8,
                label_fn=skill_label_en,
            ),
        },
    }

    OUT.write_text(
        "window.__RESULTS_EXTENDED__ = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

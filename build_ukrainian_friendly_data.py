#!/usr/bin/env python3
"""Aggregate Ukrainian-friendly job offers and emit assets/ukrainian_friendly_data.js.

Inputs
------
- ukrainian_friendly_results.jsonl  : per-offer flag scraped from pracuj.pl
- jobs_database.db / job_ads        : location, categories, seniority, contracts
- job_nace.db / job_nace            : NACE industry mapping per offer

Outputs (JS payload consumed by assets/ukrainian_friendly.js):
- meta            (totals, share)
- voivodeships    [{voivodeship, total_offers, ukr_offers, ukr_pct}]
- top_industries  (NACE divisions, ranked by share inside top-share groups)
- top_industries_by_count
- categories_general / categories_narrow
- seniority
- contract_types
"""

from __future__ import annotations

import csv
import json
import math
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

from build_ai_regional_map import (
    VOIV_ORDER,
    build_location_matchers,
    infer_voivodeship,
)
from chart_label_translations import (
    contract_type_en,
    job_category_en,
    nace_title_en,
    seniority_en,
    voivodeship_en,
)

BASE = Path(__file__).resolve().parent
JOBS_DB = BASE / "jobs_database.db"
NACE_DB = BASE / "job_nace.db"
UKR_JSONL = BASE / "ukrainian_friendly_results.jsonl"
REGIONAL_METRICS_CSV = BASE / "data" / "regional_metrics.csv"
OUT_JS = BASE / "assets" / "ukrainian_friendly_data.js"

MIN_OFFERS_FOR_RANKING = 500  # avoid noisy small groups in top-share charts

# Normalize EN labels back to canonical Polish so PL/EN duplicates aggregate together.
SENIORITY_NORM = {
    "specialist (mid / regular)": "specjalista (Mid / Regular)",
    "specjalista (mid / regular)": "specjalista (Mid / Regular)",
    "junior specialist (junior)": "młodszy specjalista (Junior)",
    "młodszy specjalista (junior)": "młodszy specjalista (Junior)",
    "senior specialist (senior)": "starszy specjalista (Senior)",
    "starszy specjalista (senior)": "starszy specjalista (Senior)",
    "expert": "ekspert",
    "ekspert": "ekspert",
    "manager": "menedżer",
    "menedżer": "menedżer",
    "team manager": "kierownik / koordynator",
    "kierownik / koordynator": "kierownik / koordynator",
    "director": "dyrektor",
    "dyrektor": "dyrektor",
    "manual worker": "pracownik fizyczny",
    "pracownik fizyczny": "pracownik fizyczny",
    "trainee": "praktykant / stażysta",
    "praktykant / stażysta": "praktykant / stażysta",
    "assistant": "asystent",
    "asystent": "asystent",
}

CONTRACT_NORM = {
    "contract of employment": "umowa o pracę",
    "umowa o pracę": "umowa o pracę",
    "b2b contract": "kontrakt B2B",
    "kontrakt b2b": "kontrakt B2B",
    "mandate contract": "umowa zlecenie",
    "umowa zlecenie": "umowa zlecenie",
    "contract of mandate": "umowa zlecenie",
    "specific-task contract": "umowa o dzieło",
    "umowa o dzieło": "umowa o dzieło",
    "internship / apprenticeship contract": "umowa o staż / praktyki",
    "umowa o staż / praktyki": "umowa o staż / praktyki",
    "umowa na zastępstwo": "umowa na zastępstwo",
    "replacement contract": "umowa na zastępstwo",
    "umowa agencyjna": "umowa agencyjna",
    "agency agreement": "umowa agencyjna",
}


def normalize_token(value: str, mapping: dict[str, str]) -> str:
    key = value.strip().lower()
    return mapping.get(key, value.strip())


def split_multi(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def load_ukr_flags() -> dict[int, int]:
    flags: dict[int, int] = {}
    with UKR_JSONL.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            flags[int(obj["id"])] = int(obj.get("ukrainian_friendly", 0))
    return flags


def load_nace_map() -> dict[int, tuple[str, str]]:
    con = sqlite3.connect(str(NACE_DB))
    cur = con.cursor()
    cur.execute(
        "SELECT job_id, nace_code, nace_title FROM job_nace "
        "WHERE nace_code IS NOT NULL AND nace_code != ''"
    )
    out = {int(jid): (code, title) for jid, code, title in cur.fetchall()}
    con.close()
    return out


def nace_section(code: str) -> str:
    """Return top-level NACE section letter (A..U) from a detailed code."""
    if not code:
        return ""
    head = code[0]
    if head.isalpha() and head.isupper():
        return head
    return ""


NACE_SECTION_TITLES = {
    "A": "Agriculture, forestry and fishing",
    "B": "Mining and quarrying",
    "C": "Manufacturing",
    "D": "Electricity, gas, steam supply",
    "E": "Water supply, waste management",
    "F": "Construction",
    "G": "Wholesale and retail trade",
    "H": "Transportation and storage",
    "I": "Accommodation and food service",
    "J": "Publishing, broadcasting and content",
    "K": "Telecommunications, IT and information services",
    "L": "Financial and insurance activities",
    "M": "Real estate activities",
    "N": "Professional, scientific, technical",
    "O": "Administrative and support service",
    "P": "Public administration and defence",
    "Q": "Education",
    "R": "Human health and social work",
    "S": "Arts, entertainment and recreation",
    "T": "Other service activities",
    "U": "Activities of households as employers",
    "V": "Extraterritorial organisations",
}


def main() -> None:
    print("Loading Ukrainian-friendly flags…")
    flags = load_ukr_flags()
    print(f"  rows: {len(flags):,}")

    print("Loading NACE mapping…")
    nace_map = load_nace_map()
    print(f"  rows with NACE: {len(nace_map):,}")

    print("Reading job_ads…")
    con = sqlite3.connect(str(JOBS_DB))
    cur = con.cursor()
    cur.execute(
        """
        SELECT id, location, job_category_general, job_category_narrow,
               seniority_level, contract_types
        FROM job_ads
        """
    )
    rows = cur.fetchall()
    con.close()
    print(f"  job_ads rows: {len(rows):,}")

    alias_patterns, city_patterns = build_location_matchers()

    voiv_total = Counter()
    voiv_ukr = Counter()

    nace_section_total = Counter()
    nace_section_ukr = Counter()
    nace_division_total = Counter()
    nace_division_ukr = Counter()
    nace_division_title: dict[str, str] = {}

    cat_general_total = Counter()
    cat_general_ukr = Counter()
    cat_narrow_total = Counter()
    cat_narrow_ukr = Counter()

    seniority_total = Counter()
    seniority_ukr = Counter()
    contract_total = Counter()
    contract_ukr = Counter()

    matched = 0
    ukr_total = 0

    for jid, location, cat_g, cat_n, seniority, contracts in rows:
        ukr = flags.get(int(jid))
        if ukr is None:
            continue
        matched += 1
        ukr_total += ukr

        voiv = infer_voivodeship(location, alias_patterns, city_patterns)
        if voiv:
            voiv_total[voiv] += 1
            voiv_ukr[voiv] += ukr

        nace = nace_map.get(int(jid))
        if nace:
            code, title = nace
            section = nace_section(code)
            if section:
                nace_section_total[section] += 1
                nace_section_ukr[section] += ukr
            nace_division_total[code] += 1
            nace_division_ukr[code] += ukr
            nace_division_title[code] = title

        if cat_g:
            cat_general_total[cat_g] += 1
            cat_general_ukr[cat_g] += ukr
        if cat_n:
            cat_narrow_total[cat_n] += 1
            cat_narrow_ukr[cat_n] += ukr

        for s in split_multi(seniority):
            s_norm = normalize_token(s, SENIORITY_NORM)
            seniority_total[s_norm] += 1
            seniority_ukr[s_norm] += ukr

        for c in split_multi(contracts):
            c_norm = normalize_token(c, CONTRACT_NORM)
            contract_total[c_norm] += 1
            contract_ukr[c_norm] += ukr

    print(f"  matched flag↔job_ads: {matched:,}")
    print(f"  ukrainian-friendly: {ukr_total:,}")

    def _pct(num: int, denom: int) -> float:
        return round(num / denom * 100, 2) if denom else 0.0

    # Labour-force baseline for per-100k normalisation.
    lf_by_voiv: dict[str, float] = {}
    with REGIONAL_METRICS_CSV.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            lf_by_voiv[row["voivodeship"]] = float(row["labour_force_2025_avg"])

    voivodeships = []
    for v in VOIV_ORDER:
        tot = voiv_total[v]
        ukr = voiv_ukr[v]
        lf = lf_by_voiv.get(v)
        offers_per_100k = round(tot * 100000 / lf, 1) if lf else None
        ukr_per_100k = round(ukr * 100000 / lf, 1) if lf else None
        voivodeships.append(
            {
                "voivodeship": v,
                "voivodeship_en": voivodeship_en(v),
                "total_offers": tot,
                "ukr_offers": ukr,
                "ukr_pct": _pct(ukr, tot),
                "labour_force_2025_avg": int(lf) if lf else None,
                "offers_per_100k_lf": offers_per_100k,
                "ukr_per_100k_lf": ukr_per_100k,
            }
        )

    # Correlation between regional offer density and Ukrainian-friendly share.
    # X = total offers per 100k labour force (intensity)
    # Y = ukr_offers / total_offers  (within-region share, %)
    xs = [r["offers_per_100k_lf"] for r in voivodeships if r["offers_per_100k_lf"] is not None]
    ys = [r["ukr_pct"] for r in voivodeships if r["offers_per_100k_lf"] is not None]

    def _pearson(a, b):
        ma, mb = mean(a), mean(b)
        num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        da = math.sqrt(sum((x - ma) ** 2 for x in a))
        db = math.sqrt(sum((y - mb) ** 2 for y in b))
        return num / (da * db) if da and db else float("nan")

    def _ranks(z):
        s = sorted((v, i) for i, v in enumerate(z))
        r = [0.0] * len(z)
        i = 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and s[j + 1][0] == s[i][0]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[s[k][1]] = avg
            i = j + 1
        return r

    pearson_r = _pearson(xs, ys)
    spearman_rho = _pearson(_ranks(xs), _ranks(ys))

    mx = mean(xs)
    my = mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot

    industries_section = []
    for code, total in nace_section_total.items():
        ukr = nace_section_ukr[code]
        industries_section.append(
            {
                "nace_section": code,
                "nace_section_title": NACE_SECTION_TITLES.get(code, code),
                "total_offers": total,
                "ukr_offers": ukr,
                "ukr_pct": _pct(ukr, total),
            }
        )
    industries_section.sort(key=lambda r: -r["ukr_offers"])

    industries_division = []
    for code, total in nace_division_total.items():
        if total < MIN_OFFERS_FOR_RANKING:
            continue
        ukr = nace_division_ukr[code]
        industries_division.append(
            {
                "nace_code": code,
                "nace_title": nace_title_en(code, nace_division_title.get(code, code)),
                "total_offers": total,
                "ukr_offers": ukr,
                "ukr_pct": _pct(ukr, total),
            }
        )
    top_industries_by_share = sorted(
        industries_division, key=lambda r: -r["ukr_pct"]
    )[:20]
    top_industries_by_count = sorted(
        industries_division, key=lambda r: -r["ukr_offers"]
    )[:20]

    def _build_group(total_c: Counter, ukr_c: Counter, min_n: int = 200, label_fn=None):
        out = []
        for key, total in total_c.items():
            if total < min_n:
                continue
            ukr = ukr_c[key]
            display = label_fn(key) if label_fn else key
            out.append(
                {
                    "label": display,
                    "total_offers": total,
                    "ukr_offers": ukr,
                    "ukr_pct": _pct(ukr, total),
                }
            )
        return out

    cat_general = _build_group(cat_general_total, cat_general_ukr, min_n=500, label_fn=job_category_en)
    cat_general_share = sorted(cat_general, key=lambda r: -r["ukr_pct"])[:15]
    cat_general_count = sorted(cat_general, key=lambda r: -r["ukr_offers"])[:15]

    cat_narrow = _build_group(cat_narrow_total, cat_narrow_ukr, min_n=500, label_fn=job_category_en)
    cat_narrow_share = sorted(cat_narrow, key=lambda r: -r["ukr_pct"])[:20]
    cat_narrow_count = sorted(cat_narrow, key=lambda r: -r["ukr_offers"])[:20]

    seniority_rows = sorted(
        _build_group(seniority_total, seniority_ukr, min_n=500, label_fn=seniority_en),
        key=lambda r: -r["total_offers"],
    )
    contract_rows = sorted(
        _build_group(contract_total, contract_ukr, min_n=500, label_fn=contract_type_en),
        key=lambda r: -r["total_offers"],
    )

    payload = {
        "meta": {
            "scraped_offers": len(flags),
            "matched_offers": matched,
            "ukr_offers": ukr_total,
            "ukr_pct_national": _pct(ukr_total, matched),
            "density_correlation": {
                "pearson_r": round(pearson_r, 3),
                "spearman_rho": round(spearman_rho, 3),
                "r_squared": round(r2, 3),
                "slope": round(slope, 4),
                "intercept": round(intercept, 2),
                "x_mean": round(mx, 2),
                "y_mean": round(my, 2),
            },
        },
        "voivodeships": voivodeships,
        "industries_section": industries_section,
        "top_industries_by_share": top_industries_by_share,
        "top_industries_by_count": top_industries_by_count,
        "categories_general_by_share": cat_general_share,
        "categories_general_by_count": cat_general_count,
        "categories_narrow_by_share": cat_narrow_share,
        "categories_narrow_by_count": cat_narrow_count,
        "seniority": seniority_rows,
        "contract_types": contract_rows,
    }

    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text(
        "window.__UKRAINIAN_FRIENDLY__ = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT_JS}")


if __name__ == "__main__":
    main()

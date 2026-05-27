#!/usr/bin/env python3
"""Export presentation chart series for interactive Plotly charts in index.qmd."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "presentation"))

from build_monthly_volumes import (  # noqa: E402
    BUR_PQ,
    JOBS_PQ,
    MONTHS,
    monthly_counts,
    monthly_vacancies,
)

OUT = ROOT / "assets" / "data_overview_data.js"
QUARTERLY_CSV = ROOT / "presentation" / "data" / "quarterly_vacancies_vs_gus_2025.csv"
BUR_YEARLY_CSV = ROOT / "presentation" / "data" / "bur_yearly_2016_2025.csv"


def series_to_records(s: pd.Series) -> list[dict]:
    out = []
    prev = None
    for label, value in s.items():
        mom = None
        if prev is not None and prev > 0:
            mom = round((float(value) - prev) / prev * 100.0, 1)
        out.append({"month": str(label), "value": int(value), "mom_pct": mom})
        prev = float(value)
    return out


def main() -> None:
    offers = monthly_counts(JOBS_PQ, "posted_date")
    vacancies = monthly_vacancies(JOBS_PQ)
    bur = monthly_counts(BUR_PQ, "data_rozpoczecia_uslugi")

    quarterly = pd.read_csv(QUARTERLY_CSV)
    bur_yearly = pd.read_csv(BUR_YEARLY_CSV)

    payload = {
        "meta": {
            "offers_total_2025": int(offers.sum()),
            "vacancies_total_2025": int(vacancies.sum()),
            "bur_total_2025": int(bur.sum()),
        },
        "monthly": {
            "offers": series_to_records(offers),
            "vacancies": series_to_records(vacancies),
            "bur": series_to_records(bur),
        },
        "quarterly_gus": [
            {
                "quarter": row.quarter,
                "pracuj_flow": int(row.pracuj_flow),
                "gus_stock_eoq": int(row.gus_stock_eoq),
                "ratio": float(row.ratio_pracuj_to_gus),
            }
            for row in quarterly.itertuples(index=False)
        ],
        "bur_yearly": [
            {
                "year": int(row.year),
                "services": int(row.services),
                "yoy_pct": None
                if pd.isna(row.yoy_pct)
                else round(float(row.yoy_pct), 1),
            }
            for row in bur_yearly.itertuples(index=False)
        ],
    }

    OUT.write_text(
        "window.__DATA_OVERVIEW__ = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

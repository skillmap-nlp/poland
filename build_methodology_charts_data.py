#!/usr/bin/env python3
"""Export aggregated series for methodology charts (slides 6–15) in index.qmd."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from check_bur_certificates import YEARS, load_year, parse_flags  # noqa: E402

OUT = ROOT / "assets" / "methodology_charts_data.js"
KZIS_CSV = ROOT / "presentation" / "kzis_vacancies_pup_vs_pracuj.csv"
BUR_2025 = ROOT / "trainings" / "data" / "yearly" / "bur_2025.parquet"


def modality_2025() -> list[dict]:
    df = pd.read_parquet(BUR_2025, columns=["forma_swiadczenia", "rodzaj_uslugi"])
    df = df[df["rodzaj_uslugi"] == "Usługa szkoleniowa"]

    def bucket(v: object) -> str:
        if not isinstance(v, str):
            return "Unknown"
        s = v.lower()
        if "mieszana" in s or ("zdal" in s and "stacjon" in s):
            return "Hybrid / mixed"
        if "zdal" in s:
            return "Online only"
        if "stacjon" in s:
            return "In-person only"
        return "Other"

    counts = df["forma_swiadczenia"].map(bucket).value_counts()
    total = int(counts.sum())
    order = ["In-person only", "Online only", "Hybrid / mixed", "Other"]
    out = []
    for label in order:
        n = int(counts.get(label, 0))
        if n:
            out.append({"label": label, "n": n, "share_pct": round(n / total * 100, 1)})
    return out


def certificates() -> dict:
    parts = [load_year(y) for y in YEARS]
    df = pd.concat(parts, ignore_index=True)
    df = df[df["rodzaj_uslugi"] == "Usługa szkoleniowa"].copy()
    flags = df["inne_kwalifikacje"].map(parse_flags)
    parsed = pd.DataFrame(list(flags.dropna()))
    parsed["year"] = df.loc[flags.notna(), "year"].values

    by_year = []
    for year, g in parsed.groupby("year"):
        n = len(g)
        by_year.append(
            {
                "year": int(year),
                "n": n,
                "q1_pct": round(g["kwal_q1_zawod"].mean() * 100, 1),
                "q2_pct": round(g["kwal_q2_panstwo"].mean() * 100, 1),
                "q3_pct": round(g["kwal_q3_uprawnienia"].mean() * 100, 1),
                "q4_pct": round(g["kwal_q4_intl_cert"].mean() * 100, 1),
                "any_q14_pct": round(g["any_recognized_qualification"].mean() * 100, 1),
                "competence_pct": round(g["recognized_competence"].mean() * 100, 1),
                "any_formal_pct": round(g["any_formal_document"].mean() * 100, 1),
            }
        )
    by_year.sort(key=lambda r: r["year"])

    g25 = parsed[parsed["year"] == 2025]
    n25 = len(g25)
    docs_2025 = [
        {
            "label": "Recognised competence certificate (Q17–Q19)",
            "n": int(g25["recognized_competence"].sum()),
            "share_pct": round(g25["recognized_competence"].mean() * 100, 1),
        },
        {
            "label": "Informal / attendance certificate only",
            "n": int((~g25["any_formal_document"]).sum()),
            "share_pct": round((~g25["any_formal_document"]).mean() * 100, 1),
        },
    ]
    return {"by_year": by_year, "documents_2025": docs_2025, "n_2025": n25}


def recurrence() -> dict:
    dist = [
        {"years": 1, "courses": 231_532, "postings": 448_167},
        {"years": 2, "courses": 32_252, "postings": 228_713},
        {"years": 3, "courses": 6_658, "postings": 95_542},
        {"years": 4, "courses": 2_047, "postings": 41_808},
        {"years": 5, "courses": 790, "postings": 19_086},
        {"years": 6, "courses": 429, "postings": 14_362},
        {"years": 7, "courses": 209, "postings": 8_082},
        {"years": 8, "courses": 112, "postings": 6_379},
        {"years": 9, "courses": 46, "postings": 4_022},
        {"years": 10, "courses": 6, "postings": 791},
    ]
    return {
        "meta": {
            "postings_total": 866_952,
            "unique_courses": 274_081,
            "recurring_courses": 42_549,
            "recurring_courses_pct": 15.5,
            "recurring_postings": 418_785,
            "recurring_postings_pct": 48.3,
            "postings_2025_recurring": 38_130,
            "postings_2025_recurring_pct": 29.1,
        },
        "years_distribution": dist,
    }


def provider_types() -> list[dict]:
    return [
        {
            "bucket": "Private companies",
            "trainings": 118_693,
            "trainings_pct": 90.6,
            "providers": 2_663,
            "providers_pct": 86.5,
        },
        {
            "bucket": "NGOs",
            "trainings": 4_100,
            "trainings_pct": 3.1,
            "providers": 152,
            "providers_pct": 4.9,
        },
        {
            "bucket": "Public education",
            "trainings": 8_042,
            "trainings_pct": 6.1,
            "providers": 254,
            "providers_pct": 8.2,
        },
        {
            "bucket": "Public finance sector",
            "trainings": 118,
            "trainings_pct": 0.1,
            "providers": 10,
            "providers_pct": 0.3,
        },
    ]


def kzis_comparison() -> list[dict]:
    df = pd.read_csv(KZIS_CSV)
    rows = []
    for row in df.itertuples(index=False):
        rows.append(
            {
                "group": row.label,
                "pup_share_pct": float(row.pup_share_pct),
                "pracuj_share_pct": float(row.pracuj_share_pct),
                "diff_pp": float(row.diff_pp_pracuj_minus_pup),
            }
        )
    return rows


def main() -> None:
    payload = {
        "esco_samples": [
            "principles of artificial intelligence",
            "natural language processing",
            "utilise machine learning",
            "ICT system integration",
            "interact through digital technologies",
            "design user interface",
            "analyse business requirements",
            "identify process improvements",
            "lead technology development of an organisation",
            "manage ICT change request process",
            "report analysis results",
            "provide training on technological business developments",
            "information confidentiality",
        ],
        "kzis_comparison": kzis_comparison(),
        "provider_types": provider_types(),
        "recurrence": recurrence(),
        "certificates": certificates(),
        "modality_2025": modality_2025(),
    }
    OUT.write_text(
        "window.__METHODOLOGY_CHARTS__ = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

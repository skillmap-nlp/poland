#!/usr/bin/env python3
"""Refresh data/regional_metrics.csv (and the meta JSON) using only
training-service records dated to 2025.

Input
-----
- jobs_database.db            : 2025 job-ad totals per voivodeship (from the
                                existing build pipeline; we keep what's
                                already there).
- trainings/data/yearly/bur_2025.parquet : 2025-only BUR training services.
- data/regional_metrics.csv   : current values (we overwrite the trainings
                                columns and recompute per-100k LF).
- data/regional_metrics_meta.json : updated total + source notes.
"""
from __future__ import annotations

import csv
import json

from chart_label_translations import voivodeship_en
import unicodedata
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
TRAININGS_PARQ = BASE / "trainings" / "data" / "yearly" / "bur_2025.parquet"
CSV = BASE / "data" / "regional_metrics.csv"
META = BASE / "data" / "regional_metrics_meta.json"
GEOJSON = BASE / "data" / "pl_voivodeships.geojson"
JS_OUT = BASE / "assets" / "regional_map_data.js"

# Polish 16 voivodeships canonical (lower-case, with diacritics) — to map both
# 'Małopolskie' and 'Mazowieckie regionalny' (BUR sub-region) to canonical PL.
VOIV_CANONICAL = {
    "dolnośląskie",
    "kujawsko-pomorskie",
    "lubelskie",
    "lubuskie",
    "łódzkie",
    "małopolskie",
    "mazowieckie",
    "opolskie",
    "podkarpackie",
    "podlaskie",
    "pomorskie",
    "śląskie",
    "świętokrzyskie",
    "warmińsko-mazurskie",
    "wielkopolskie",
    "zachodniopomorskie",
}


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def normalise_voiv(raw: str) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    s = raw.strip().lower()
    # 'Mazowieckie regionalny' / 'Mazowieckie stołeczny' → 'mazowieckie'
    s = s.replace("regionalny", "").replace("stołeczny", "").strip()
    if s in VOIV_CANONICAL:
        return s
    # diacritic-insensitive fallback
    bare = _strip_accents(s)
    for v in VOIV_CANONICAL:
        if _strip_accents(v) == bare:
            return v
    return None


def main() -> None:
    print("Loading 2025 BUR trainings…")
    df = pd.read_parquet(TRAININGS_PARQ, columns=["wojewodztwo"])
    print(f"  rows: {len(df):,}")

    df["voiv"] = df["wojewodztwo"].map(normalise_voiv)
    mapped = df["voiv"].notna().sum()
    print(
        f"  mapped to a voivodeship: {mapped:,} "
        f"({mapped / len(df):.1%}); rest are remote / no region"
    )

    counts = df["voiv"].value_counts().to_dict()
    total_mapped = int(sum(counts.values()))
    print(f"  total trainings with voivodeship (2025): {total_mapped:,}")

    print("Updating regional_metrics.csv…")
    rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
    fieldnames = list(rows[0].keys())

    new_rows = []
    for r in rows:
        v = r["voivodeship"]
        n_train = int(counts.get(v, 0))
        lf = float(r["labour_force_2025_avg"])
        offers = int(r["offers"])
        train_per_100k = round(n_train / lf * 100_000, 2) if lf else 0.0
        train_share = round(n_train / total_mapped * 100, 2) if total_mapped else 0.0

        r["trainings"] = n_train
        r["trainings_per_100k_lf"] = train_per_100k
        r["training_share_pct"] = train_share
        # Recompute offer_share_pct against existing offers total to stay
        # consistent with what the report already shows.
        new_rows.append(r)

    with CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(new_rows)
    print(f"  wrote {CSV}")

    print("Updating regional_metrics_meta.json…")
    meta = json.loads(META.read_text(encoding="utf-8"))
    meta["trainings_total_with_voivodeship"] = total_mapped
    meta["trainings_year"] = 2025
    meta["trainings_source"] = (
        "trainings/data/yearly/bur_2025.parquet — Baza Usług Rozwojowych "
        "(BUR), services with a Polish voivodeship assigned in 2025."
    )
    META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  wrote {META}")

    print("Updating assets/regional_map_data.js…")
    geojson = json.loads(GEOJSON.read_text(encoding="utf-8"))
    typed_rows = []
    for r in new_rows:
        typed_rows.append({
            "voivodeship": r["voivodeship"],
            "voivodeship_en": voivodeship_en(r["voivodeship"]),
            "population": int(r["population"]),
            "labour_force_2025_avg": int(float(r["labour_force_2025_avg"])),
            "offers": int(r["offers"]),
            "trainings": int(r["trainings"]),
            "offers_per_100k_lf": float(r["offers_per_100k_lf"]),
            "trainings_per_100k_lf": float(r["trainings_per_100k_lf"]),
            "offer_share_pct": float(r["offer_share_pct"]),
            "training_share_pct": float(r["training_share_pct"]),
            "lf_q1_thousands": float(r["lf_q1_thousands"]),
            "lf_q2_thousands": float(r["lf_q2_thousands"]),
            "lf_q3_thousands": float(r["lf_q3_thousands"]),
            "lf_q4_thousands": float(r["lf_q4_thousands"]),
        })
    payload = {"rows": typed_rows, "meta": meta, "geojson": geojson}
    JS_OUT.write_text(
        "window.__REGIONAL_REPORT__ = " + json.dumps(payload, ensure_ascii=False) + ";",
        encoding="utf-8",
    )
    print(f"  wrote {JS_OUT}")

    print("\nFinal training counts (2025):")
    for r in sorted(new_rows, key=lambda r: -int(r["trainings"])):
        print(
            f"  {r['voivodeship']:<22} "
            f"{int(r['trainings']):>7,} "
            f"({float(r['trainings_per_100k_lf']):>7.0f} / 100k LF)"
        )


if __name__ == "__main__":
    main()

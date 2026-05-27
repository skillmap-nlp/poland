#!/usr/bin/env python3
"""Build ESCO digital skills regional map data.

For each voivodeship, computes:
- total job offers with regional assignment (via job_powiat)
- offers with >=1 ESCO digital skill (digitalSkillsCollection_pl.csv)
- digital_offer_share_pct  (% of offers with at least one digital skill)
- top 10 most-mentioned digital skills

Outputs assets/digital_regional_map_data.js as window.__DIGITAL_REGIONAL_REPORT__.
"""
from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent

from chart_label_translations import skill_label_en, voivodeship_en
DIGITAL_CSV = BASE / "digitalSkillsCollection_pl.csv"
REGIONAL_METRICS_CSV = BASE / "data" / "regional_metrics.csv"
JOBS_DB = BASE / "jobs_database.db"
OUTPUT_JS = BASE / "assets" / "digital_regional_map_data.js"

VOIV_ORDER = [
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
]


def _norm(s: str) -> str:
    return s.strip().lower()


def load_digital_labels() -> set[str]:
    labels: set[str] = set()
    with open(DIGITAL_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            label = row.get("preferredLabel", "")
            if label:
                labels.add(_norm(label))
            for a in (row.get("altLabels", "") or "").split("|"):
                a = a.strip()
                if a:
                    labels.add(_norm(a))
    return labels


def load_regional_base() -> dict[str, dict]:
    with open(REGIONAL_METRICS_CSV, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    return {
        row["voivodeship"]: {
            "voivodeship": row["voivodeship"],
            "labour_force_2025_avg": int(float(row["labour_force_2025_avg"])),
            "offers": int(float(row["offers"])),
        }
        for row in rows
    }


def compute_payload() -> dict:
    digital_labels = load_digital_labels()
    print(f"Digital skill labels loaded (preferred + altLabels): {len(digital_labels):,}")

    regional_base = load_regional_base()

    conn = sqlite3.connect(str(JOBS_DB))
    conn.row_factory = sqlite3.Row

    cur = conn.execute(
        """
        SELECT jp.voivodeship, ja.skills_esco_contextual
        FROM job_powiat jp
        JOIN job_ads ja ON ja.id = jp.job_id
        WHERE jp.voivodeship IS NOT NULL
        """
    )

    total_by_voiv: Counter[str] = Counter()
    digital_by_voiv: Counter[str] = Counter()
    skill_counts: dict[str, Counter] = defaultdict(Counter)

    for row in cur:
        voiv = _norm(row["voivodeship"])
        if voiv not in VOIV_ORDER:
            continue
        total_by_voiv[voiv] += 1

        raw = row["skills_esco_contextual"]
        if not raw or raw == "[]":
            continue
        try:
            arr = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            continue

        matched: set[str] = set()
        for item in arr:
            label = item.get("esco")
            if label and _norm(label) in digital_labels:
                matched.add(_norm(label))

        if matched:
            digital_by_voiv[voiv] += 1
            for lbl in matched:
                skill_counts[voiv][lbl] += 1

    conn.close()

    rows = []
    for voiv in VOIV_ORDER:
        base = regional_base.get(voiv, {})
        total = total_by_voiv[voiv]
        digital = digital_by_voiv[voiv]
        lf = base.get("labour_force_2025_avg", 1) or 1
        base_offers = base.get("offers", total) or total

        top_skills = [
            {"label": skill_label_en(lbl), "count": cnt}
            for lbl, cnt in skill_counts[voiv].most_common(10)
        ]

        rows.append(
            {
                "voivodeship": voiv,
                "voivodeship_en": voivodeship_en(voiv),
                "offers": base_offers,
                "labour_force_2025_avg": lf,
                "digital_offers": digital,
                "total_mapped": total,
                "digital_pct": round(digital * 100 / total, 2) if total else 0.0,
                "top_skills": top_skills,
            }
        )

    rows.sort(key=lambda r: r["digital_pct"], reverse=True)

    total_offers = sum(r["total_mapped"] for r in rows)
    total_digital = sum(r["digital_offers"] for r in rows)

    return {
        "rows": rows,
        "meta": {
            "total_mapped_offers": total_offers,
            "total_digital_offers": total_digital,
            "national_digital_pct": round(total_digital * 100 / total_offers, 2) if total_offers else 0.0,
            "top_voivodeship": rows[0]["voivodeship"],
            "top_digital_pct": rows[0]["digital_pct"],
        },
    }


def main() -> None:
    payload = compute_payload()
    OUTPUT_JS.write_text(
        "window.__DIGITAL_REGIONAL_REPORT__ = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    meta = payload["meta"]
    print(f"Wrote {OUTPUT_JS}")
    print(f"Total mapped offers:  {meta['total_mapped_offers']:,}")
    print(f"Digital offers:       {meta['total_digital_offers']:,}")
    print(f"National digital %:   {meta['national_digital_pct']:.2f}%")
    print(f"Top voivodeship:      {meta['top_voivodeship']} ({meta['top_digital_pct']:.2f}%)")
    print()
    print(f"{'Voivodeship':<25} {'Total':>8} {'Digital':>8} {'%':>7}")
    print("-" * 52)
    for r in payload["rows"]:
        print(f"{r['voivodeship']:<25} {r['total_mapped']:>8,} {r['digital_offers']:>8,} {r['digital_pct']:>6.2f}%")


if __name__ == "__main__":
    main()

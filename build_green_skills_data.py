"""Generate assets/green_skills_data.js from CSV analysis outputs."""

import csv
import json
import sqlite3

from chart_label_translations import kzis_occupation_en, voivodeship_en

VOIV_CSV = "presentation/green_by_voivodeship.csv"
TOP_SKILLS_CSV = "presentation/green_top_skills.csv"
KZIS_CSV = "presentation/green_by_kzis.csv"
FALSE_POS_CSV = "presentation/green_false_positives.csv"
FLAGGED_CSV = "green_skills_matched_flagged.csv"
DB_PATH = "jobs_database.db"
OUT = "assets/green_skills_data.js"


def read_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def main():
    voiv_rows = read_csv(VOIV_CSV)
    top_skills = read_csv(TOP_SKILLS_CSV)
    kzis_rows = read_csv(KZIS_CSV)
    false_pos = read_csv(FALSE_POS_CSV)
    flagged = read_csv(FLAGGED_CSV)

    genuine = [r for r in flagged if r["flag"] == "genuine_green"]
    false_positive = [r for r in flagged if r["flag"] == "false_positive"]

    total_green_offers = sum(int(r["green_offers"]) for r in voiv_rows)
    total_offers = sum(int(r["total_offers"]) for r in voiv_rows)
    green_pct_national = round(total_green_offers / total_offers * 100, 1) if total_offers else 0

    total_green_skills_genuine = len(genuine)
    total_false_positive = len(false_positive)

    for r in voiv_rows:
        r["total_offers"] = int(r["total_offers"])
        r["green_offers"] = int(r["green_offers"])
        r["green_pct"] = float(r["green_pct"])
        if "voivodeship_en" not in r:
            r["voivodeship_en"] = voivodeship_en(r["voivodeship"])

    for r in top_skills:
        r["offer_count"] = int(r["offer_count"])

    for r in kzis_rows:
        r["green_offers"] = int(r["green_offers"])
        r["green_skill_mentions"] = int(r["green_skill_mentions"])
        r["avg_green_skills"] = float(r["avg_green_skills"])
        r["kzis_occupation_en"] = kzis_occupation_en(r["kzis_occupation"])

    for r in false_pos:
        r["offer_count"] = int(r["offer_count"])

    payload = {
        "meta": {
            "total_offers": total_offers,
            "total_green_offers": total_green_offers,
            "green_pct_national": green_pct_national,
            "genuine_green_count": total_green_skills_genuine,
            "false_positive_count": total_false_positive,
        },
        "voivodeships": voiv_rows,
        "top_skills": top_skills[:30],
        "top_occupations": kzis_rows[:20],
        "false_positives": false_pos,
    }

    js = f"window.__GREEN_SKILLS__ = {json.dumps(payload, ensure_ascii=False)};\n"
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(js)
    print(f"Wrote {OUT} ({len(js):,} chars)")


if __name__ == "__main__":
    main()

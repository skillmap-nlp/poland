#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
REGIONAL_METRICS_CSV = BASE / "data" / "regional_metrics.csv"
LIGHTCAST_XLSX = BASE / "ai_skills_2026_lightcast_scraped.xlsx"
MATCH_SCORES_NPZ = BASE / "lightcast_aiml" / "ai_skill_match_scores.npz"
EMBEDDINGS_NPZ = BASE / "lightcast_aiml" / "lightcast_ai_skills_voyage4.npz"
JOBS_DB = BASE / "jobs_database.db"
OUTPUT_JS = BASE / "assets" / "ai_regional_map_data.js"
MATCH_THRESHOLD = 0.55

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

VOIV_ALIASES = {
    "dolnośląskie": ["dolnośląskie", "lower silesia", "lower-silesia"],
    "kujawsko-pomorskie": [
        "kujawsko-pomorskie",
        "kujawsko pomorskie",
        "kuyavian-pomeranian",
        "kuyavian pomeranian",
    ],
    "lubelskie": ["lubelskie", "lublin voivodeship"],
    "lubuskie": ["lubuskie", "lubusz"],
    "łódzkie": ["łódzkie", "lodzkie", "lodz voivodeship"],
    "małopolskie": ["małopolskie", "malopolskie", "lesser poland", "lesser-poland"],
    "mazowieckie": ["mazowieckie", "masovian", "mazovia"],
    "opolskie": ["opolskie", "opole voivodeship"],
    "podkarpackie": ["podkarpackie", "subcarpathian"],
    "podlaskie": ["podlaskie", "podlasie"],
    "pomorskie": ["pomorskie", "pomeranian"],
    "śląskie": ["śląskie", "slaskie", "silesian"],
    "świętokrzyskie": ["świętokrzyskie", "swietokrzyskie", "holy cross"],
    "warmińsko-mazurskie": [
        "warmińsko-mazurskie",
        "warminsko-mazurskie",
        "warmian-masurian",
        "warmian masurian",
    ],
    "wielkopolskie": ["wielkopolskie", "greater poland", "greater-poland"],
    "zachodniopomorskie": [
        "zachodniopomorskie",
        "west pomeranian",
        "western pomeranian",
    ],
}

CITY_TO_VOIV = {
    r"warszaw": "mazowieckie",
    r"radom": "mazowieckie",
    r"płock": "mazowieckie",
    r"plock": "mazowieckie",
    r"siedlc": "mazowieckie",
    r"pruszk[óo]w": "mazowieckie",
    r"krak[óo]w": "małopolskie",
    r"tarn[óo]w": "małopolskie",
    r"nowy sącz": "małopolskie",
    r"nowy sacz": "małopolskie",
    r"wroc[łl]aw": "dolnośląskie",
    r"legnic": "dolnośląskie",
    r"wałbrzych": "dolnośląskie",
    r"walbrzych": "dolnośląskie",
    r"jelenia g[óo]ra": "dolnośląskie",
    r"pozna[nń]": "wielkopolskie",
    r"kalisz": "wielkopolskie",
    r"konin": "wielkopolskie",
    r"pi[łl]a": "wielkopolskie",
    r"gda[nń]sk": "pomorskie",
    r"gdyni": "pomorskie",
    r"sopot": "pomorskie",
    r"słupsk": "pomorskie",
    r"slupsk": "pomorskie",
    r"[łl][óo]d[zź]": "łódzkie",
    r"piotrk[óo]w": "łódzkie",
    r"skierniewic": "łódzkie",
    r"katowic": "śląskie",
    r"gliwic": "śląskie",
    r"sosnowiec": "śląskie",
    r"tychy": "śląskie",
    r"dąbrowa g[óo]rnicza": "śląskie",
    r"dabrowa gornicza": "śląskie",
    r"częstochow": "śląskie",
    r"czestochow": "śląskie",
    r"bielsko": "śląskie",
    r"zabrze": "śląskie",
    r"bytom": "śląskie",
    r"rybnik": "śląskie",
    r"szczecin": "zachodniopomorskie",
    r"koszalin": "zachodniopomorskie",
    r"świnoujście": "zachodniopomorskie",
    r"swinoujscie": "zachodniopomorskie",
    r"lublin": "lubelskie",
    r"zamość": "lubelskie",
    r"zamosc": "lubelskie",
    r"chełm": "lubelskie",
    r"chelm": "lubelskie",
    r"bydgoszcz": "kujawsko-pomorskie",
    r"toru[nń]": "kujawsko-pomorskie",
    r"włocławek": "kujawsko-pomorskie",
    r"wloclawek": "kujawsko-pomorskie",
    r"grudziądz": "kujawsko-pomorskie",
    r"grudziadz": "kujawsko-pomorskie",
    r"rzesz[óo]w": "podkarpackie",
    r"krosno": "podkarpackie",
    r"mielec": "podkarpackie",
    r"przemyśl": "podkarpackie",
    r"przemysl": "podkarpackie",
    r"tarnobrzeg": "podkarpackie",
    r"bia[łl]ystok": "podlaskie",
    r"łomża": "podlaskie",
    r"lomza": "podlaskie",
    r"suwałk": "podlaskie",
    r"suwalk": "podlaskie",
    r"kielc": "świętokrzyskie",
    r"ostrowiec": "świętokrzyskie",
    r"starachowic": "świętokrzyskie",
    r"olsztyn": "warmińsko-mazurskie",
    r"elbląg": "warmińsko-mazurskie",
    r"elblag": "warmińsko-mazurskie",
    r"ełk": "warmińsko-mazurskie",
    r"elk": "warmińsko-mazurskie",
    r"opol": "opolskie",
    r"kędzierzyn": "opolskie",
    r"kedzierzyn": "opolskie",
    r"nysa": "opolskie",
    r"zielona g[óo]ra": "lubuskie",
    r"gorz[óo]w": "lubuskie",
}

FOREIGN_MARKERS = [
    "zagranica",
    "niemcy",
    "germany",
    "netherlands",
    "holand",
    "belgia",
    "belgium",
    "france",
    "francja",
    "austria",
    "norweg",
    "denmark",
    "dania",
    "sweden",
    "szwec",
    "wielka brytania",
    "united kingdom",
    "usa",
    "united states",
]


def load_regional_base() -> dict[str, dict]:
    with REGIONAL_METRICS_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    out = {}
    for row in rows:
        voiv = row["voivodeship"]
        out[voiv] = {
            "voivodeship": voiv,
            "labour_force_2025_avg": int(float(row["labour_force_2025_avg"])),
            "offers": int(float(row["offers"])),
        }
    return out


def load_lightcast_skill_meta() -> list[dict]:
    workbook = pd.read_excel(LIGHTCAST_XLSX, sheet_name="all_skills")
    workbook = workbook[workbook["retrieve_status"] == "ok"].copy()
    workbook["skill_id"] = workbook["skill_id"].astype(str)

    excel_meta = {
        row["skill_id"]: {
            "label": str(row.get("lightcast_name") or row.get("excel_skill_name") or row["skill_id"]).strip(),
            "cluster": str(row.get("excel_ai_skill_cluster") or "").strip(),
            "cluster_source": str(row.get("cluster_source") or "").strip(),
        }
        for _, row in workbook.iterrows()
    }

    embeddings = np.load(EMBEDDINGS_NPZ, allow_pickle=True)
    skill_ids = [str(skill_id) for skill_id in embeddings["skill_ids"]]
    skill_names = [str(name) for name in embeddings["names"]]
    wb_flags = [int(flag) for flag in embeddings["worldbank_ai_skill"]]

    ordered_meta = []
    for skill_id, skill_name, wb_flag in zip(skill_ids, skill_names, wb_flags):
        row = excel_meta.get(skill_id, {})
        cluster_source = row.get("cluster_source") or (
            "Lightcast" if wb_flag else "embedding classification"
        )
        ordered_meta.append(
            {
                "skill_id": skill_id,
                "label": row.get("label") or skill_name,
                "cluster": row.get("cluster") or "",
                "cluster_source": cluster_source,
            }
        )
    return ordered_meta


def build_location_matchers():
    alias_patterns = []
    for voiv, aliases in VOIV_ALIASES.items():
        for alias in aliases:
            alias_patterns.append((voiv, re.compile(re.escape(alias), re.IGNORECASE)))
    city_patterns = [
        (voiv, re.compile(pattern, re.IGNORECASE))
        for pattern, voiv in CITY_TO_VOIV.items()
    ]
    return alias_patterns, city_patterns


def infer_voivodeship(
    location: str | None,
    alias_patterns: list[tuple[str, re.Pattern]],
    city_patterns: list[tuple[str, re.Pattern]],
) -> str | None:
    if not location:
        return None
    text = str(location).strip().lower()
    if not text:
        return None
    if any(marker in text for marker in FOREIGN_MARKERS):
        return None

    matches: list[tuple[int, str]] = []
    for voiv, pattern in alias_patterns:
        match = pattern.search(text)
        if match:
            matches.append((match.start(), voiv))
    if matches:
        matches.sort(key=lambda item: item[0])
        return matches[0][1]

    city_matches: list[tuple[int, str]] = []
    for voiv, pattern in city_patterns:
        match = pattern.search(text)
        if match:
            city_matches.append((match.start(), voiv))
    if city_matches:
        city_matches.sort(key=lambda item: item[0])
        return city_matches[0][1]

    return None


def log_likelihood_g2(k11: int, k12: int, k21: int, k22: int) -> float:
    total = k11 + k12 + k21 + k22
    if total == 0:
        return 0.0

    row1 = k11 + k12
    row2 = k21 + k22
    col1 = k11 + k21
    col2 = k12 + k22
    if row1 == 0 or row2 == 0 or col1 == 0 or col2 == 0:
        return 0.0

    expected = (
        row1 * col1 / total,
        row1 * col2 / total,
        row2 * col1 / total,
        row2 * col2 / total,
    )
    observed = (k11, k12, k21, k22)

    g2 = 0.0
    for obs, exp in zip(observed, expected):
        if obs > 0 and exp > 0:
            g2 += obs * math.log(obs / exp)
    g2 *= 2.0

    # Keep only positively characteristic concepts for the focal voivodeship.
    return g2 if k11 > expected[0] else -g2


def compute_payload() -> dict:
    regional_base = load_regional_base()
    lightcast_meta = load_lightcast_skill_meta()
    lightcast_meta_by_id = {
        row["skill_id"]: row for row in lightcast_meta
    }
    alias_patterns, city_patterns = build_location_matchers()

    ai_offer_counts = Counter()
    skill_counts = defaultdict(Counter)
    cluster_counts = defaultdict(Counter)
    total_ai_offers = 0
    mapped_ai_offers = 0
    unmapped_ai_offers = 0

    match_scores = np.load(MATCH_SCORES_NPZ, allow_pickle=True)
    scores_all = match_scores["scores_all"]
    indices_all = match_scores["indices_all"]
    job_ids = match_scores["job_ids"]

    conn = sqlite3.connect(str(JOBS_DB))
    cur = conn.cursor()
    cur.execute("SELECT id, location FROM job_ads WHERE location IS NOT NULL")
    location_map = {int(job_id): location for job_id, location in cur.fetchall()}

    conn.close()

    for job_id, score, skill_idx in zip(job_ids, scores_all, indices_all):
        if float(score) < MATCH_THRESHOLD:
            continue

        total_ai_offers += 1
        voiv = infer_voivodeship(location_map.get(int(job_id)), alias_patterns, city_patterns)
        if not voiv:
            unmapped_ai_offers += 1
            continue

        mapped_ai_offers += 1
        ai_offer_counts[voiv] += 1
        skill_meta = lightcast_meta[int(skill_idx)]
        skill_counts[voiv][skill_meta["skill_id"]] += 1
        if skill_meta["cluster"]:
            cluster_counts[voiv][skill_meta["cluster"]] += 1

    global_skill_counts = Counter()
    for voiv in VOIV_ORDER:
        global_skill_counts.update(skill_counts[voiv])

    mapped_total_ai_offers = sum(ai_offer_counts.values())

    rows = []
    for voiv in VOIV_ORDER:
        base = regional_base[voiv]
        region_ai_offers = ai_offer_counts[voiv]
        outside_ai_offers = mapped_total_ai_offers - region_ai_offers
        scored = []
        for skill_id, count in skill_counts[voiv].items():
            outside_count = global_skill_counts[skill_id] - count
            absent_in_region = max(region_ai_offers - count, 0)
            absent_outside_region = max(outside_ai_offers - outside_count, 0)
            g2 = log_likelihood_g2(
                count,
                absent_in_region,
                outside_count,
                absent_outside_region,
            )
            skill_meta = lightcast_meta_by_id[skill_id]
            scored.append(
                {
                    "skill_id": skill_id,
                    "label": skill_meta["label"],
                    "cluster": skill_meta["cluster"],
                    "cluster_source": skill_meta["cluster_source"],
                    "count": count,
                    "g2": round(g2, 6),
                }
            )
        scored = [item for item in scored if item["g2"] > 0]
        scored.sort(key=lambda item: (-item["g2"], -item["count"], item["label"]))
        top_skills = scored[:3]
        top_skills_text = ", ".join(item["label"] for item in top_skills) if top_skills else "No AI skills detected"
        top_clusters = [
            {
                "cluster": cluster,
                "count": count,
                "share_of_regional_ai_pct": round(count * 100 / region_ai_offers, 1)
                if region_ai_offers
                else 0.0,
            }
            for cluster, count in sorted(
                cluster_counts[voiv].items(),
                key=lambda item: (-item[1], item[0]),
            )[:5]
        ]

        ai_offers = ai_offer_counts[voiv]
        rows.append(
            {
                "voivodeship": voiv,
                "offers": base["offers"],
                "labour_force_2025_avg": base["labour_force_2025_avg"],
                "ai_offers": ai_offers,
                "ai_offers_per_100k_lf": round(ai_offers * 100000 / base["labour_force_2025_avg"], 2),
                "ai_offer_share_pct": round(ai_offers * 100 / base["offers"], 2) if base["offers"] else 0.0,
                "top_characteristic_skills": top_skills,
                "top_clusters": top_clusters,
                "top_characteristic_skills_text": top_skills_text,
            }
        )

    rows.sort(key=lambda item: item["ai_offers_per_100k_lf"], reverse=True)
    top_row = rows[0]

    return {
        "rows": rows,
        "meta": {
            "ai_offers_total": total_ai_offers,
            "ai_offers_total_mapped": mapped_ai_offers,
            "ai_offers_total_unmapped": unmapped_ai_offers,
            "match_threshold": MATCH_THRESHOLD,
            "top_voivodeship": top_row["voivodeship"],
            "top_ai_offers_per_100k_lf": top_row["ai_offers_per_100k_lf"],
        },
    }


def main() -> None:
    payload = compute_payload()
    OUTPUT_JS.write_text(
        "window.__AI_REGIONAL_REPORT__ = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUTPUT_JS}")
    print(
        "Mapped AI offers:",
        payload["meta"]["ai_offers_total_mapped"],
        "/",
        payload["meta"]["ai_offers_total"],
    )


if __name__ == "__main__":
    main()

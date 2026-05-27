#!/usr/bin/env python3
"""Aggregate Ukrainian-friendly job offers per powiat and emit the assets
consumed by the powiat-level map + correlation chart.

Outputs
-------
- data/pl_powiats_keyed.geojson : powiat polygons annotated with voivodeship
                                  and a stable (voiv, powiat) key
- assets/ukrainian_friendly_powiat_data.js : payload for the chart layer
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter
from pathlib import Path
from statistics import mean

from shapely.geometry import shape

BASE = Path(__file__).resolve().parent
JOBS_DB = BASE / "jobs_database.db"
UKR_JSONL = BASE / "ukrainian_friendly_results.jsonl"
POWIAT_GEOJSON_IN = BASE / "data" / "pl_powiats.geojson"
POWIAT_GEOJSON_OUT = BASE / "data" / "pl_powiats_keyed.geojson"
VOIV_GEOJSON = BASE / "data" / "pl_voivodeships.geojson"
WIKI_MD = BASE / "data" / "powiat_wikipedia.md"
EMPLOYED_JSON = BASE / "data" / "employed_powiat.json"
OUT_JS = BASE / "assets" / "ukrainian_friendly_powiat_data.js"

# How many offers are required for a powiat to enter the correlation regression.
# Tiny powiats with a handful of postings produce noise that dominates the fit.
MIN_OFFERS_FOR_CORR = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def norm_powiat(name: str) -> str:
    """Lower-case, accent-stripped, 'powiat ' prefix removed."""
    if not name:
        return ""
    n = name.strip().lower()
    n = re.sub(r"^powiat\s+", "", n)
    return strip_accents(n)


def make_key(voiv: str, powiat: str) -> str:
    return f"{voiv}__{norm_powiat(powiat)}"


# ---------------------------------------------------------------------------
# 1. Annotate the powiat geojson with voivodeship via centroid → PIP
# ---------------------------------------------------------------------------
def build_keyed_geojson() -> dict:
    powiats = json.loads(POWIAT_GEOJSON_IN.read_text(encoding="utf-8"))
    voivs = json.loads(VOIV_GEOJSON.read_text(encoding="utf-8"))

    voiv_polys = []
    for f in voivs["features"]:
        props = f["properties"]
        # try common name keys
        name = (
            props.get("nazwa")
            or props.get("name")
            or props.get("NAZWA")
            or props.get("JPT_NAZWA_")
            or ""
        ).lower()
        voiv_polys.append((name, shape(f["geometry"])))

    matched = 0
    for f in powiats["features"]:
        geom = shape(f["geometry"])
        c = geom.representative_point()  # always inside even for concave shapes
        voiv_name = None
        for name, poly in voiv_polys:
            if poly.contains(c):
                voiv_name = name
                break
        if voiv_name is None:
            # Fallback: nearest polygon centroid
            voiv_name = min(
                voiv_polys, key=lambda kv: kv[1].centroid.distance(c)
            )[0]
        f["properties"]["voiv"] = voiv_name
        f["properties"]["key"] = make_key(voiv_name, f["properties"]["nazwa"])
        if voiv_name:
            matched += 1
    print(
        f"  geojson features: {len(powiats['features'])}, "
        f"with voivodeship: {matched}"
    )
    POWIAT_GEOJSON_OUT.write_text(
        json.dumps(powiats, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  wrote {POWIAT_GEOJSON_OUT}")
    return powiats


# ---------------------------------------------------------------------------
# 2. Parse the Wikipedia table for population per (voivodeship, powiat name)
# ---------------------------------------------------------------------------
def _strip_md_link(s: str) -> str:
    """Replace [label](url) with label, where url may contain parens."""
    # Greedy nested-paren handling: walk chars.
    out = []
    i = 0
    while i < len(s):
        if s[i] == "[":
            close = s.find("]", i + 1)
            if close == -1:
                out.append(s[i])
                i += 1
                continue
            label = s[i + 1 : close]
            j = close + 1
            if j < len(s) and s[j] == "(":
                depth = 1
                j += 1
                while j < len(s) and depth > 0:
                    if s[j] == "(":
                        depth += 1
                    elif s[j] == ")":
                        depth -= 1
                    j += 1
            out.append(label)
            i = j
        else:
            out.append(s[i])
            i += 1
    return "".join(out)


def load_employed() -> tuple[dict[str, int], str]:
    """Return (key→employed, year) where key = make_key(voiv, name).
    Names from BDL come prefixed: 'Powiat m. Kraków' / 'Powiat bocheński'.
    """
    payload = json.loads(EMPLOYED_JSON.read_text(encoding="utf-8"))
    out: dict[str, int] = {}
    for r in payload["items"]:
        nm = re.sub(r"^Powiat\s+(m\.\s+(st\.\s+)?)?", "", r["name"])
        # Trim historical-period suffixes like "od 2013".
        nm = re.sub(r"\s+od\s+\d{4}.*$", "", nm).strip()
        out[make_key(r["voivodeship"], nm)] = r["employed"]
    return out, payload["year"]


def parse_wiki_population() -> dict[str, int]:
    """Wikipedia table layout:
    | powiat | seat | plates | województwo | area | population | density | growth |
    """
    pops: dict[str, int] = {}
    text = WIKI_MD.read_text(encoding="utf-8")
    for line in text.splitlines():
        if not line.startswith("| ") or "---" in line:
            continue
        cells = [c.strip() for c in _strip_md_link(line).strip("|").split("|")]
        if len(cells) < 6:
            continue
        powiat_raw = cells[0]
        voiv = cells[3].lower()
        pop_str = cells[5].replace("\u00a0", "").replace(" ", "")
        if not pop_str.isdigit():
            continue
        if voiv not in {
            "dolnośląskie", "kujawsko-pomorskie", "lubelskie", "lubuskie",
            "łódzkie", "małopolskie", "mazowieckie", "opolskie",
            "podkarpackie", "podlaskie", "pomorskie", "śląskie",
            "świętokrzyskie", "warmińsko-mazurskie", "wielkopolskie",
            "zachodniopomorskie",
        }:
            continue
        pops[make_key(voiv, powiat_raw)] = int(pop_str)
    print(f"  parsed populations for {len(pops)} powiats")
    return pops


# ---------------------------------------------------------------------------
# 3. Aggregate UA-friendly counts by (voivodeship, powiat)
# ---------------------------------------------------------------------------
def load_ukr_flags() -> dict[int, int]:
    flags: dict[int, int] = {}
    with UKR_JSONL.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            obj = json.loads(line)
            flags[int(obj["id"])] = int(obj.get("ukrainian_friendly", 0))
    return flags


def aggregate(flags: dict[int, int]) -> tuple[Counter, Counter, dict[str, dict]]:
    """Return (total_by_key, ukr_by_key, meta_by_key)."""
    con = sqlite3.connect(str(JOBS_DB))
    cur = con.cursor()
    cur.execute(
        "SELECT job_id, voivodeship, powiat FROM job_powiat "
        "WHERE voivodeship IS NOT NULL AND powiat IS NOT NULL"
    )
    rows = cur.fetchall()
    con.close()
    print(f"  job_powiat rows with (voiv, powiat): {len(rows):,}")

    total = Counter()
    ukr = Counter()
    meta: dict[str, dict] = {}

    for jid, voiv, powiat in rows:
        ukr_flag = flags.get(int(jid))
        if ukr_flag is None:
            continue
        key = make_key(voiv, powiat)
        total[key] += 1
        ukr[key] += ukr_flag
        if key not in meta:
            meta[key] = {"voivodeship": voiv, "powiat": powiat}
    return total, ukr, meta


# ---------------------------------------------------------------------------
# 4. Pearson / Spearman / OLS
# ---------------------------------------------------------------------------
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


def main() -> None:
    print("Annotating powiat geojson with voivodeship…")
    geo = build_keyed_geojson()
    geo_keys = {f["properties"]["key"] for f in geo["features"]}
    geo_meta = {
        f["properties"]["key"]: {
            "voiv": f["properties"]["voiv"],
            "nazwa": f["properties"]["nazwa"],
        }
        for f in geo["features"]
    }

    print("Parsing Wikipedia population table…")
    pops = parse_wiki_population()

    matched_pop = sum(1 for k in geo_keys if k in pops)
    print(
        f"  matched population for {matched_pop}/{len(geo_keys)} powiats "
        f"({matched_pop / len(geo_keys):.1%})"
    )
    missing_pop = [geo_meta[k]["nazwa"] for k in geo_keys if k not in pops]
    if missing_pop:
        print(f"  missing population (sample): {missing_pop[:5]}")

    print("Loading GUS BDL employed-by-residence per powiat…")
    employed, employed_year = load_employed()
    matched_emp = sum(1 for k in geo_keys if k in employed)
    print(
        f"  matched employed for {matched_emp}/{len(geo_keys)} powiats "
        f"({matched_emp / len(geo_keys):.1%}); year={employed_year}"
    )
    missing_emp = [geo_meta[k]["nazwa"] for k in geo_keys if k not in employed]
    if missing_emp:
        print(f"  missing employed (sample): {missing_emp[:5]}")

    print("Loading UA-friendly flags…")
    flags = load_ukr_flags()
    print(f"  flags: {len(flags):,}")

    print("Aggregating by (voivodeship, powiat)…")
    total, ukr, meta = aggregate(flags)
    print(f"  unique (voiv, powiat) buckets: {len(total):,}")

    matched_to_geo = sum(1 for k in total if k in geo_keys)
    print(
        f"  buckets matched to geojson: {matched_to_geo}/{len(total)} "
        f"({matched_to_geo / len(total):.1%})"
    )

    rows = []
    for key, tot in total.items():
        if key not in geo_keys:
            continue
        u = ukr[key]
        pop = pops.get(key)
        emp = employed.get(key)
        rows.append(
            {
                "key": key,
                "voivodeship": meta[key]["voivodeship"],
                "powiat": meta[key]["powiat"],
                "powiat_label": geo_meta[key]["nazwa"],
                "population": pop,
                "employed_2025": emp,
                "total_offers": tot,
                "ukr_offers": u,
                "ukr_pct": round(u / tot * 100, 2),
                "offers_per_100k_pop": (
                    round(tot / pop * 100_000, 1) if pop else None
                ),
                "offers_per_100k_emp": (
                    round(tot / emp * 100_000, 1) if emp else None
                ),
            }
        )

    # Correlation: X = offers per 100k employed (LF proxy), Y = UA share %
    corr_rows = [
        r
        for r in rows
        if r["offers_per_100k_emp"] is not None
        and r["total_offers"] >= MIN_OFFERS_FOR_CORR
    ]
    xs = [r["offers_per_100k_emp"] for r in corr_rows]
    ys = [r["ukr_pct"] for r in corr_rows]

    if len(xs) >= 3:
        pearson_r = _pearson(xs, ys)
        spearman_rho = _pearson(_ranks(xs), _ranks(ys))
        mx, my = mean(xs), mean(ys)
        sxx = sum((x - mx) ** 2 for x in xs)
        sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        slope = sxy / sxx if sxx else 0.0
        intercept = my - slope * mx
        ss_res = sum((y - (intercept + slope * x)) ** 2 for x, y in zip(xs, ys))
        ss_tot = sum((y - my) ** 2 for y in ys)
        r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    else:
        pearson_r = spearman_rho = r2 = slope = intercept = mx = my = float("nan")

    # Embed the keyed geojson in the data payload so the front-end doesn't
    # need a separate fetch (matches the pattern used for voivodeships).
    payload = {
        "geojson": geo,
        "meta": {
            "min_offers_for_corr": MIN_OFFERS_FOR_CORR,
            "n_powiats_total": len(rows),
            "n_powiats_for_corr": len(corr_rows),
            "employed_year": employed_year,
            "employed_source": (
                "GUS BDL P4280 (Pracujący w gospodarce narodowej "
                "wg miejsca zamieszkania, dane miesięczne, styczeń)"
            ),
            "pearson_r": round(pearson_r, 3) if not math.isnan(pearson_r) else None,
            "spearman_rho": (
                round(spearman_rho, 3) if not math.isnan(spearman_rho) else None
            ),
            "r_squared": round(r2, 3) if not math.isnan(r2) else None,
            "slope": round(slope, 4) if not math.isnan(slope) else None,
            "intercept": round(intercept, 2) if not math.isnan(intercept) else None,
            "x_mean": round(mx, 2) if not math.isnan(mx) else None,
            "y_mean": round(my, 2) if not math.isnan(my) else None,
        },
        "powiats": rows,
    }

    OUT_JS.parent.mkdir(parents=True, exist_ok=True)
    OUT_JS.write_text(
        "window.__UKRAINIAN_FRIENDLY_POWIAT__ = "
        + json.dumps(payload, ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT_JS} ({len(rows)} powiats)")
    print(
        f"Correlation (n={len(corr_rows)}): "
        f"r={pearson_r:.3f}, rho={spearman_rho:.3f}, R²={r2:.3f}"
    )


if __name__ == "__main__":
    main()

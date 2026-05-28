#!/usr/bin/env python3
"""Sensitivity check on the ESCO-mismatch weighting scheme.

The headline mismatch figures use **mention-mass** weighting:

    s_g^MM = Σ_i  count_i(g) / Σ_i |S_i|

where ``S_i`` is the (multiset of) ESCO skill mentions in posting / training
``i`` and ``count_i(g)`` is the number of mentions in posting ``i`` that
fall into ESCO L1 group ``g``.  A 20-mention CTO posting contributes 20
units; a 3-mention assistant posting contributes 3.

The robust alternative is the **per-posting** scheme:

    s_g^PP = (1/N) Σ_i  count_i(g) / |S_i|

Every posting (or training) carries the same total weight regardless of
how verbose its description is.

This script computes both vectors **separately for demand and supply**,
then reports:

    L1 distance      = Σ_g |s_g^MM - s_g^PP|
    cosine similarity = <s^MM, s^PP> / (||s^MM|| · ||s^PP||)

Decision rule (per the user's brief):

    L1 < 0.02 → re-normalisation is cosmetic; the headline figures are
                robust to the choice and we mention this in the
                methodology / sensitivity notes.

Outputs
-------
- presentation/skills_mismatch_sensitivity_l1.csv
- data/skills_mismatch_sensitivity_audit.json
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
ESCO_DICT = ROOT / "app_deploy" / "esco_dictionary.json"
JOBS_DB = ROOT / "jobs_database.db"
BUR_ESCO = ROOT / "trainings" / "data" / "bur_to_esco_kalm_top1.parquet"
BUR_2025 = ROOT / "trainings" / "data" / "yearly" / "bur_2025.parquet"
OUT_CSV = ROOT / "presentation" / "skills_mismatch_sensitivity_l1.csv"
OUT_JSON = ROOT / "data" / "skills_mismatch_sensitivity_audit.json"


# ---------------------------------------------------------------------------
# ESCO label → L1 code lookup
# ---------------------------------------------------------------------------
def load_label_to_l1(use_uri: bool = False) -> dict[str, str]:
    """Map each ESCO entry to its L1 group code.

    Parameters
    ----------
    use_uri : bool
        When True, the dictionary is keyed by ESCO conceptUri (used for the
        supply side).  When False, keyed by the label (used for the demand
        side ``skills_esco_contextual.esco`` field).
    """

    raw = json.loads(ESCO_DICT.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for key, info in raw.items():
        h = info.get("hierarchy") or []
        if len(h) < 2:
            continue
        l1 = h[-2].get("code")
        if not l1:
            continue
        if use_uri:
            uri = info.get("uri")
            if uri:
                out[uri] = l1
        else:
            out[key] = l1
    return out


# ---------------------------------------------------------------------------
# Demand-side counts (Pracuj.pl 2025 offers)
# ---------------------------------------------------------------------------
def demand_vectors() -> tuple[dict[str, float], dict[str, float], dict]:
    label_to_l1 = load_label_to_l1(use_uri=False)
    print(f"  ESCO label→L1 map size: {len(label_to_l1):,}")

    con = sqlite3.connect(str(JOBS_DB))
    cur = con.cursor()
    cur.execute(
        "SELECT skills_esco_contextual "
        "FROM job_ads WHERE is_pl = 1 "
        "AND skills_esco_contextual IS NOT NULL "
        "AND skills_esco_contextual != ''"
    )

    n_offers = 0
    n_offers_with_skills = 0
    total_mentions = 0
    mm_counts: dict[str, int] = defaultdict(int)
    pp_counts: dict[str, float] = defaultdict(float)

    batch = 0
    while True:
        rows = cur.fetchmany(20_000)
        if not rows:
            break
        for (js,) in rows:
            n_offers += 1
            try:
                skills = json.loads(js) if js else []
            except Exception:
                skills = []
            if not skills:
                continue
            l1_counts: dict[str, int] = defaultdict(int)
            for s in skills:
                lbl = s.get("esco")
                if not lbl:
                    continue
                l1 = label_to_l1.get(lbl)
                if l1 is None:
                    continue
                l1_counts[l1] += 1
            if not l1_counts:
                continue
            n_offers_with_skills += 1
            n_mentions_i = sum(l1_counts.values())
            total_mentions += n_mentions_i
            inv = 1.0 / n_mentions_i
            for g, c in l1_counts.items():
                mm_counts[g] += c
                pp_counts[g] += c * inv
        batch += 1
        if batch % 5 == 0:
            print(
                f"    scanned offers ≈ {n_offers:,}  mentions matched ≈ {total_mentions:,}"
            )
    con.close()

    mm = {g: v / total_mentions for g, v in mm_counts.items()}
    pp = {g: v / n_offers_with_skills for g, v in pp_counts.items()}
    audit = {
        "side": "demand",
        "n_offers_scanned": n_offers,
        "n_offers_with_l1_skills": n_offers_with_skills,
        "total_matched_mentions": total_mentions,
    }
    return mm, pp, audit


# ---------------------------------------------------------------------------
# Supply-side counts (BUR trainings)
# ---------------------------------------------------------------------------
def supply_vectors(year_filter_2025: bool = True) -> tuple[
    dict[str, float], dict[str, float], dict
]:
    uri_to_l1 = load_label_to_l1(use_uri=True)
    print(f"  ESCO URI→L1 map size: {len(uri_to_l1):,}")

    bur_esco = pd.read_parquet(
        BUR_ESCO, columns=["bur_bur_ids_json", "esco_conceptUri"]
    )

    ids_2025: set[int] | None = None
    if year_filter_2025 and BUR_2025.exists():
        ids_2025 = {
            int(x)
            for x in pd.read_parquet(BUR_2025, columns=["id"])["id"].dropna()
        }
        print(f"  filter: BUR 2025 trainings = {len(ids_2025):,}")

    training_to_l1: dict[int, dict[str, int]] = defaultdict(
        lambda: defaultdict(int)
    )

    for js, uri in zip(bur_esco["bur_bur_ids_json"], bur_esco["esco_conceptUri"]):
        l1 = uri_to_l1.get(uri)
        if l1 is None:
            continue
        try:
            ids = json.loads(js) if isinstance(js, str) else list(js or [])
        except Exception:
            ids = []
        for tid in ids:
            try:
                tid_int = int(tid)
            except Exception:
                continue
            if ids_2025 is not None and tid_int not in ids_2025:
                continue
            training_to_l1[tid_int][l1] += 1

    n_trainings = len(training_to_l1)
    total_pairs = 0
    mm_counts: dict[str, int] = defaultdict(int)
    pp_counts: dict[str, float] = defaultdict(float)

    for _, l1_counts in training_to_l1.items():
        n_pairs = sum(l1_counts.values())
        total_pairs += n_pairs
        inv = 1.0 / n_pairs if n_pairs else 0.0
        for g, c in l1_counts.items():
            mm_counts[g] += c
            pp_counts[g] += c * inv

    mm = {g: v / total_pairs for g, v in mm_counts.items()} if total_pairs else {}
    pp = {g: v / n_trainings for g, v in pp_counts.items()} if n_trainings else {}
    audit = {
        "side": "supply",
        "year_filter_2025": bool(year_filter_2025),
        "n_trainings_with_skills": n_trainings,
        "total_training_skill_pairs": total_pairs,
    }
    return mm, pp, audit


# ---------------------------------------------------------------------------
# Comparison metrics
# ---------------------------------------------------------------------------
def compare(mm: dict[str, float], pp: dict[str, float]) -> dict:
    keys = sorted(set(mm) | set(pp))
    diffs = []
    dot = 0.0
    norm_mm = 0.0
    norm_pp = 0.0
    for k in keys:
        a = mm.get(k, 0.0)
        b = pp.get(k, 0.0)
        diffs.append((k, a, b))
        dot += a * b
        norm_mm += a * a
        norm_pp += b * b
    l1 = sum(abs(a - b) for _, a, b in diffs)
    tvd = 0.5 * l1
    cos = dot / (norm_mm**0.5 * norm_pp**0.5) if norm_mm and norm_pp else 0.0
    max_abs_pp = max(abs(a - b) for _, a, b in diffs) if diffs else 0.0
    top_movers = sorted(
        diffs, key=lambda r: -abs(r[1] - r[2])
    )[:8]
    return {
        "l1": l1,
        "tvd": tvd,
        "cosine": cos,
        "max_abs_diff_pp": max_abs_pp * 100,
        "n_groups": len(keys),
        "top_movers": [
            {
                "code": k,
                "mm_pct": round(a * 100, 3),
                "pp_pct": round(b * 100, 3),
                "diff_pp": round((b - a) * 100, 3),
            }
            for k, a, b in top_movers
        ],
    }


def write_csv(mm_d, pp_d, mm_s, pp_s, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    keys = sorted(set(mm_d) | set(pp_d) | set(mm_s) | set(pp_s))
    import csv

    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "code",
                "demand_mm_pct",
                "demand_pp_pct",
                "demand_diff_pp",
                "supply_mm_pct",
                "supply_pp_pct",
                "supply_diff_pp",
            ]
        )
        for k in keys:
            dmm = mm_d.get(k, 0.0) * 100
            dpp = pp_d.get(k, 0.0) * 100
            smm = mm_s.get(k, 0.0) * 100
            spp = pp_s.get(k, 0.0) * 100
            w.writerow(
                [
                    k,
                    f"{dmm:.3f}",
                    f"{dpp:.3f}",
                    f"{dpp - dmm:+.3f}",
                    f"{smm:.3f}",
                    f"{spp:.3f}",
                    f"{spp - smm:+.3f}",
                ]
            )


def gap_vectors(d: dict[str, float], s: dict[str, float]) -> dict[str, float]:
    """Return gap_pp[g] = demand_share - supply_share in percentage points."""
    keys = set(d) | set(s)
    return {k: (d.get(k, 0.0) - s.get(k, 0.0)) * 100 for k in keys}


def gap_rank_overlap(
    g_mm: dict[str, float], g_pp: dict[str, float], k: int = 10
) -> dict:
    """How stable are the top-k under-/over-supplied rankings across schemes?"""
    keys = sorted(set(g_mm) | set(g_pp))
    if not keys:
        return {"top_under_overlap": 0, "top_over_overlap": 0}
    top_under_mm = {kk for kk, _ in sorted(
        g_mm.items(), key=lambda r: -r[1])[:k]}
    top_under_pp = {kk for kk, _ in sorted(
        g_pp.items(), key=lambda r: -r[1])[:k]}
    top_over_mm = {kk for kk, _ in sorted(g_mm.items(), key=lambda r: r[1])[:k]}
    top_over_pp = {kk for kk, _ in sorted(g_pp.items(), key=lambda r: r[1])[:k]}
    # Pearson correlation across all groups
    import statistics

    common = sorted(keys)
    xs = [g_mm.get(c, 0.0) for c in common]
    ys = [g_pp.get(c, 0.0) for c in common]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = sum((x - mx) ** 2 for x in xs) ** 0.5
    den_y = sum((y - my) ** 2 for y in ys) ** 0.5
    corr = num / (den_x * den_y) if den_x and den_y else 0.0
    max_dev = max(abs(a - b) for a, b in zip(xs, ys))
    return {
        "top_under_overlap": len(top_under_mm & top_under_pp),
        "top_over_overlap": len(top_over_mm & top_over_pp),
        "pearson_gap_corr": round(corr, 5),
        "max_abs_gap_diff_pp": round(max_dev, 3),
        "top_under_mm": sorted(top_under_mm),
        "top_under_pp": sorted(top_under_pp),
        "top_over_mm": sorted(top_over_mm),
        "top_over_pp": sorted(top_over_pp),
    }


def main() -> None:
    print("=== DEMAND ===")
    mm_d, pp_d, audit_d = demand_vectors()
    cmp_d = compare(mm_d, pp_d)
    print(f"  L1 distance      : {cmp_d['l1']:.4f}")
    print(f"  TVD              : {cmp_d['tvd']:.4f}")
    print(f"  cosine similarity: {cmp_d['cosine']:.5f}")
    print(f"  max |Δ|          : {cmp_d['max_abs_diff_pp']:.2f} pp")
    print(f"  top movers       :")
    for r in cmp_d["top_movers"]:
        print(
            f"    {r['code']:<6} MM={r['mm_pct']:6.2f}%  "
            f"PP={r['pp_pct']:6.2f}%  Δ={r['diff_pp']:+.2f} pp"
        )

    print("\n=== SUPPLY (2025-only) ===")
    mm_s, pp_s, audit_s = supply_vectors(year_filter_2025=True)
    cmp_s = compare(mm_s, pp_s)
    print(f"  L1 distance      : {cmp_s['l1']:.4f}")
    print(f"  TVD              : {cmp_s['tvd']:.4f}")
    print(f"  cosine similarity: {cmp_s['cosine']:.5f}")
    print(f"  max |Δ|          : {cmp_s['max_abs_diff_pp']:.2f} pp")
    print(f"  top movers       :")
    for r in cmp_s["top_movers"]:
        print(
            f"    {r['code']:<6} MM={r['mm_pct']:6.2f}%  "
            f"PP={r['pp_pct']:6.2f}%  Δ={r['diff_pp']:+.2f} pp"
        )

    # Decision rule from the user's brief
    def verdict(l1: float) -> str:
        return "COSMETIC (L1 < 0.02)" if l1 < 0.02 else "SUBSTANTIVE (L1 ≥ 0.02)"

    print("\n=== VERDICT ===")
    print(f"  demand : {verdict(cmp_d['l1'])}")
    print(f"  supply : {verdict(cmp_s['l1'])}")

    # Gap-vector comparison: does the mismatch story change?
    g_mm = gap_vectors(mm_d, mm_s)
    g_pp = gap_vectors(pp_d, pp_s)
    gap_cmp = gap_rank_overlap(g_mm, g_pp, k=10)
    print("\n=== GAP VECTOR (demand − supply) ===")
    print(
        f"  Pearson r between MM- and PP-derived gaps: {gap_cmp['pearson_gap_corr']}"
    )
    print(
        f"  max |Δ gap_pp|: {gap_cmp['max_abs_gap_diff_pp']:.2f} pp"
    )
    print(
        f"  top-10 under-supplied overlap: "
        f"{gap_cmp['top_under_overlap']} / 10"
    )
    print(
        f"  top-10 over-supplied overlap : "
        f"{gap_cmp['top_over_overlap']} / 10"
    )

    write_csv(mm_d, pp_d, mm_s, pp_s, OUT_CSV)
    print(f"\nwrote {OUT_CSV.relative_to(ROOT)}")

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(
            {
                "demand": {"audit": audit_d, "metrics": cmp_d},
                "supply": {"audit": audit_s, "metrics": cmp_s},
                "gap": gap_cmp,
                "decision_rule": "L1 < 0.02 → cosmetic; report in methodology note.",
                "verdict": {
                    "demand": verdict(cmp_d["l1"]),
                    "supply": verdict(cmp_s["l1"]),
                },
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

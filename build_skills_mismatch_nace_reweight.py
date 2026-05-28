#!/usr/bin/env python3
"""Robustness check: NACE-section post-stratification of online job postings.

Pracuj.pl over-represents some sectors (ICT, professional services,
finance) and under-represents others (agriculture, public administration,
education, health, mining). The headline ESCO-mismatch figures therefore
partly reflect the sectoral skew of online vacancies, not just labour-market
demand structure.

Standard post-stratification fixes this. For each NACE section *k*:

    w_k = p_k^target / p_k^pracuj

where
    p_k^target  = share of NACE section k in total Polish employment
                  (Eurostat LFS 2024, ``lfsa_egan2`` — closest direct
                  equivalent of "Pracujący w gospodarce narodowej wg sekcji
                  PKD" published by GUS in BAEL/LFS)
    p_k^pracuj  = share of NACE section k in Pracuj.pl 2025 postings used
                  in the analysis

Each posting in sector *k* is then weighted by w_k and aggregate skill
shares are recomputed on the weighted sample.

The script produces, for ESCO L1 (the same 25 group taxonomy used in the
headline figures):

* the **unweighted** demand share vector ``s_g^MM`` — the headline
* the **NACE-reweighted** demand share vector ``s_g^MM,rw``
* a comparison: L1 distance, cosine similarity, max single-group shift
* the change in the **gap vector** ``demand − supply`` and whether the
  top-10 under-/over-supplied groups are stable

Inputs
------
* ``data/external/eurostat_lfsa_egan2_pl_2024.json`` — Eurostat LFS payload
  (cached locally so the build is reproducible offline)
* ``jobs_database.db``                  — Pracuj.pl ESCO mentions
* ``job_nace.db``                       — posting → NACE 4-digit code
* ``app_deploy/esco_dictionary.json``   — ESCO → L1 group
* ``trainings/data/bur_to_esco_kalm_top1.parquet`` + ``bur_2025.parquet``
                                        — supply side (mention-mass)

Outputs
-------
* ``data/skills_mismatch_nace_reweight_audit.json`` — full audit payload
* ``presentation/skills_mismatch_nace_reweight.csv`` — group-level table
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
ESCO_DICT = ROOT / "app_deploy" / "esco_dictionary.json"
JOBS_DB = ROOT / "jobs_database.db"
NACE_DB = ROOT / "job_nace.db"
EUROSTAT_JSON = ROOT / "data" / "external" / "eurostat_lfsa_egan2_pl_2024.json"
BUR_ESCO = ROOT / "trainings" / "data" / "bur_to_esco_kalm_top1.parquet"
BUR_2025 = ROOT / "trainings" / "data" / "yearly" / "bur_2025.parquet"

OUT_CSV = ROOT / "presentation" / "skills_mismatch_nace_reweight.csv"
OUT_JSON = ROOT / "data" / "skills_mismatch_nace_reweight_audit.json"


# ---------------------------------------------------------------------------
# Target distribution: PL employment by NACE section (Eurostat LFS 2024)
# ---------------------------------------------------------------------------
# NACE sections kept in the post-stratification universe.  We drop:
#   T = "Activities of households as employers" (tiny, never appears in OJP)
#   U = "Extraterritorial organisations and bodies" (not reported for PL)
#   NRP / TOTAL = aggregate / no-response buckets
NACE_KEEP: tuple[str, ...] = (
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
    "K", "L", "M", "N", "O", "P", "Q", "R", "S",
)


def load_eurostat_target() -> tuple[dict[str, float], dict]:
    """Return the renormalised PL NACE-section employment shares."""

    raw = json.loads(EUROSTAT_JSON.read_text(encoding="utf-8"))
    nace = raw["dimension"]["nace_r2"]["category"]
    idx = nace["index"]
    inv = {v: k for k, v in idx.items()}
    values = raw["value"]

    rows: dict[str, float] = {}
    for pos, code in inv.items():
        v = values.get(str(pos))
        if v is None or code not in NACE_KEEP:
            continue
        rows[code] = float(v)

    total = sum(rows.values())
    if total <= 0:
        raise RuntimeError("Eurostat payload contains no usable values.")
    shares = {k: v / total for k, v in rows.items()}

    audit = {
        "source": "Eurostat lfsa_egan2",
        "geo": "PL",
        "sex": "T",
        "age": "Y_GE15",
        "year": 2024,
        "raw_thousands": rows,
        "renorm_total_thousands": round(total, 1),
        "shares_pct": {k: round(v * 100, 3) for k, v in shares.items()},
        "kept_sections": list(NACE_KEEP),
    }
    return shares, audit


# ---------------------------------------------------------------------------
# ESCO label → L1 code lookup (same logic as the sensitivity script)
# ---------------------------------------------------------------------------
def load_label_to_l1(use_uri: bool = False) -> dict[str, str]:
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
# Posting → NACE section lookup
# ---------------------------------------------------------------------------
def load_nace_section_map() -> dict[int, str]:
    con = sqlite3.connect(str(NACE_DB))
    rows = con.execute(
        "SELECT job_id, nace_code FROM job_nace "
        "WHERE nace_code IS NOT NULL AND nace_code != ''"
    ).fetchall()
    con.close()
    out: dict[int, str] = {}
    for jid, code in rows:
        if not code:
            continue
        head = code[0]
        if head.isalpha() and head.isupper():
            out[int(jid)] = head
    return out


# ---------------------------------------------------------------------------
# Demand-side: stream ESCO mentions, keyed by NACE section
# ---------------------------------------------------------------------------
def demand_by_nace() -> tuple[
    dict[str, dict[str, int]],  # mentions[k][g]
    dict[str, int],             # total_mentions_by_nace[k]
    dict[str, int],             # n_postings_by_nace[k]
    dict[str, int],             # all_mm_counts[g]    (unweighted baseline)
    int,                        # total mentions
    int,                        # postings scanned with NACE + skills
]:
    label_to_l1 = load_label_to_l1(use_uri=False)
    nace_map = load_nace_section_map()
    print(f"  ESCO label→L1 map size : {len(label_to_l1):,}")
    print(f"  posting→NACE section   : {len(nace_map):,}")

    con = sqlite3.connect(str(JOBS_DB))
    cur = con.cursor()
    cur.execute(
        "SELECT id, skills_esco_contextual "
        "FROM job_ads WHERE is_pl = 1 "
        "AND skills_esco_contextual IS NOT NULL "
        "AND skills_esco_contextual != ''"
    )

    mentions: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    tot_mentions_k: dict[str, int] = defaultdict(int)
    n_post_k: dict[str, int] = defaultdict(int)
    all_mm_counts: dict[str, int] = defaultdict(int)

    n_scanned = 0
    n_used = 0
    n_missing_nace = 0
    grand_mentions = 0

    while True:
        rows = cur.fetchmany(20_000)
        if not rows:
            break
        for jid, js in rows:
            n_scanned += 1
            k = nace_map.get(int(jid))
            if k is None or k not in NACE_KEEP:
                n_missing_nace += 1
                continue
            try:
                skills = json.loads(js) if js else []
            except Exception:
                skills = []
            l1_counts: dict[str, int] = defaultdict(int)
            for s in skills:
                lbl = s.get("esco") if isinstance(s, dict) else None
                if not lbl:
                    continue
                l1 = label_to_l1.get(lbl)
                if l1 is None:
                    continue
                l1_counts[l1] += 1
            if not l1_counts:
                continue
            n_mentions_i = sum(l1_counts.values())
            tot_mentions_k[k] += n_mentions_i
            n_post_k[k] += 1
            grand_mentions += n_mentions_i
            n_used += 1
            for g, c in l1_counts.items():
                mentions[k][g] += c
                all_mm_counts[g] += c
        if n_scanned % 100_000 == 0:
            print(
                f"    scanned ≈ {n_scanned:,}  used ≈ {n_used:,}  "
                f"missing-NACE ≈ {n_missing_nace:,}"
            )
    con.close()

    print(
        f"  postings scanned: {n_scanned:,}  used: {n_used:,}  "
        f"missing NACE / out-of-scope section: {n_missing_nace:,}"
    )
    print(f"  matched ESCO L1 mentions: {grand_mentions:,}")

    return (
        {k: dict(v) for k, v in mentions.items()},
        dict(tot_mentions_k),
        dict(n_post_k),
        dict(all_mm_counts),
        grand_mentions,
        n_used,
    )


# ---------------------------------------------------------------------------
# Supply-side mention-mass (BUR 2025), reused from the sensitivity script
# ---------------------------------------------------------------------------
def supply_mm() -> tuple[dict[str, float], dict]:
    uri_to_l1 = load_label_to_l1(use_uri=True)
    bur_esco = pd.read_parquet(
        BUR_ESCO, columns=["bur_bur_ids_json", "esco_conceptUri"]
    )
    ids_2025 = {
        int(x) for x in pd.read_parquet(BUR_2025, columns=["id"])["id"].dropna()
    }

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
            if tid_int not in ids_2025:
                continue
            training_to_l1[tid_int][l1] += 1

    total_pairs = 0
    mm_counts: dict[str, int] = defaultdict(int)
    for _, l1_counts in training_to_l1.items():
        n_pairs = sum(l1_counts.values())
        total_pairs += n_pairs
        for g, c in l1_counts.items():
            mm_counts[g] += c
    mm = {g: v / total_pairs for g, v in mm_counts.items()} if total_pairs else {}
    audit = {
        "n_trainings_with_skills": len(training_to_l1),
        "total_training_skill_pairs": total_pairs,
        "year_filter": 2025,
    }
    return mm, audit


# ---------------------------------------------------------------------------
# Weighting + aggregation
# ---------------------------------------------------------------------------
def compute_weights(
    target_share: dict[str, float], n_post_k: dict[str, int]
) -> tuple[dict[str, float], dict[str, float], dict[str, float]]:
    """Return (p_pracuj, w_k, target_renorm) over the *intersection* of
    NACE sections present in both Pracuj and the target.

    ``target_renorm`` is the target distribution renormalised over the
    same intersection (so weighted MM totals can be compared against an
    apples-to-apples target).
    """

    common = sorted(k for k in NACE_KEEP if n_post_k.get(k, 0) > 0)
    tot_post = sum(n_post_k[k] for k in common)
    p_pracuj = {k: n_post_k[k] / tot_post for k in common}

    tot_target = sum(target_share.get(k, 0.0) for k in common)
    target_renorm = {k: target_share.get(k, 0.0) / tot_target for k in common}

    w_k = {
        k: target_renorm[k] / p_pracuj[k]
        for k in common
        if p_pracuj[k] > 0
    }
    return p_pracuj, w_k, target_renorm


def reweighted_demand_mm(
    mentions: dict[str, dict[str, int]],
    tot_mentions_k: dict[str, int],
    w_k: dict[str, float],
) -> dict[str, float]:
    """Mention-mass demand shares with per-posting weight w_k absorbed
    into the section level (constant within section, so the section is
    the unit of reweighting).
    """

    num: dict[str, float] = defaultdict(float)
    denom = 0.0
    for k, w in w_k.items():
        denom += w * tot_mentions_k.get(k, 0)
        section_mentions = mentions.get(k, {})
        for g, c in section_mentions.items():
            num[g] += w * c
    if denom <= 0:
        return {}
    return {g: v / denom for g, v in num.items()}


# ---------------------------------------------------------------------------
# Comparison metrics
# ---------------------------------------------------------------------------
def compare(a: dict[str, float], b: dict[str, float]) -> dict:
    keys = sorted(set(a) | set(b))
    diffs = []
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for k in keys:
        x = a.get(k, 0.0)
        y = b.get(k, 0.0)
        diffs.append((k, x, y))
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    l1 = sum(abs(x - y) for _, x, y in diffs)
    cos = dot / (math.sqrt(norm_a) * math.sqrt(norm_b)) if norm_a and norm_b else 0.0
    max_abs = max(abs(x - y) for _, x, y in diffs) if diffs else 0.0
    movers = sorted(diffs, key=lambda r: -abs(r[1] - r[2]))[:10]
    return {
        "l1": round(l1, 5),
        "tvd": round(0.5 * l1, 5),
        "cosine": round(cos, 6),
        "max_abs_diff_pp": round(max_abs * 100, 3),
        "n_groups": len(keys),
        "top_movers": [
            {
                "code": k,
                "headline_pct": round(x * 100, 3),
                "reweighted_pct": round(y * 100, 3),
                "diff_pp": round((y - x) * 100, 3),
            }
            for k, x, y in movers
        ],
    }


def gap_vector(d: dict[str, float], s: dict[str, float]) -> dict[str, float]:
    keys = set(d) | set(s)
    return {k: (d.get(k, 0.0) - s.get(k, 0.0)) * 100 for k in keys}


def rank_stability(g_base: dict[str, float], g_rw: dict[str, float], k: int = 10) -> dict:
    keys = sorted(set(g_base) | set(g_rw))
    if not keys:
        return {}
    top_under_b = [kk for kk, _ in sorted(g_base.items(), key=lambda r: -r[1])[:k]]
    top_under_r = [kk for kk, _ in sorted(g_rw.items(), key=lambda r: -r[1])[:k]]
    top_over_b = [kk for kk, _ in sorted(g_base.items(), key=lambda r: r[1])[:k]]
    top_over_r = [kk for kk, _ in sorted(g_rw.items(), key=lambda r: r[1])[:k]]

    import statistics

    xs = [g_base.get(c, 0.0) for c in keys]
    ys = [g_rw.get(c, 0.0) for c in keys]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    num_ = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den_x = math.sqrt(sum((x - mx) ** 2 for x in xs))
    den_y = math.sqrt(sum((y - my) ** 2 for y in ys))
    corr = num_ / (den_x * den_y) if den_x and den_y else 0.0
    max_dev = max(abs(x - y) for x, y in zip(xs, ys))
    return {
        "pearson_gap_corr": round(corr, 5),
        "max_abs_gap_diff_pp": round(max_dev, 3),
        "top_under_overlap": len(set(top_under_b) & set(top_under_r)),
        "top_over_overlap": len(set(top_over_b) & set(top_over_r)),
        "top_under_headline": top_under_b,
        "top_under_reweighted": top_under_r,
        "top_over_headline": top_over_b,
        "top_over_reweighted": top_over_r,
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------
def write_csv(
    head_d: dict[str, float],
    rw_d: dict[str, float],
    supply: dict[str, float],
    out: Path,
) -> None:
    keys = sorted(set(head_d) | set(rw_d) | set(supply))
    import csv

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "code",
                "demand_headline_pct",
                "demand_nace_reweighted_pct",
                "demand_diff_pp",
                "supply_pct",
                "gap_headline_pp",
                "gap_reweighted_pp",
                "gap_change_pp",
            ]
        )
        for k in keys:
            dh = head_d.get(k, 0.0) * 100
            dr = rw_d.get(k, 0.0) * 100
            sp = supply.get(k, 0.0) * 100
            gh = dh - sp
            gr = dr - sp
            w.writerow(
                [
                    k,
                    f"{dh:.3f}",
                    f"{dr:.3f}",
                    f"{dr - dh:+.3f}",
                    f"{sp:.3f}",
                    f"{gh:+.3f}",
                    f"{gr:+.3f}",
                    f"{gr - gh:+.3f}",
                ]
            )


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
def main() -> None:
    print("=== Eurostat LFS 2024 target ===")
    target_share, target_audit = load_eurostat_target()
    for k in NACE_KEEP:
        if k in target_share:
            print(f"  {k}: {target_share[k] * 100:5.2f}%  "
                  f"({target_audit['raw_thousands'][k]:.0f}k employed)")

    print("\n=== Demand by NACE section (Pracuj.pl 2025) ===")
    mentions, tot_k, n_k, all_mm, grand_mentions, n_used = demand_by_nace()

    p_pracuj, w_k, target_renorm = compute_weights(target_share, n_k)

    print("\n=== Sectoral weights (target / pracuj) ===")
    print(f"  {'k':<3} {'n_post':>9} {'p_pracuj_%':>11} "
          f"{'p_target_%':>11} {'w_k':>8}")
    for k in NACE_KEEP:
        if k not in p_pracuj:
            continue
        print(
            f"  {k:<3} {n_k.get(k, 0):>9,d} "
            f"{p_pracuj[k] * 100:>10.2f}% "
            f"{target_renorm.get(k, 0.0) * 100:>10.2f}% "
            f"{w_k.get(k, 0.0):>8.3f}"
        )

    print("\n=== Skill shares: headline vs NACE-reweighted (MM) ===")
    headline_mm = {g: v / grand_mentions for g, v in all_mm.items()} if grand_mentions else {}
    rw_mm = reweighted_demand_mm(mentions, tot_k, w_k)
    diag = compare(headline_mm, rw_mm)
    print(f"  L1 distance      : {diag['l1']:.4f}")
    print(f"  TVD              : {diag['tvd']:.4f}")
    print(f"  cosine similarity: {diag['cosine']:.5f}")
    print(f"  max |Δ|          : {diag['max_abs_diff_pp']:.2f} pp")
    print("  top movers (reweighted − headline, pp):")
    for r in diag["top_movers"]:
        print(
            f"    {r['code']:<6} headline={r['headline_pct']:6.2f}%  "
            f"rw={r['reweighted_pct']:6.2f}%  Δ={r['diff_pp']:+.2f}"
        )

    print("\n=== Supply (BUR 2025, MM) ===")
    supply, supply_audit = supply_mm()
    print(f"  groups: {len(supply):,}  trainings: "
          f"{supply_audit['n_trainings_with_skills']:,}  pairs: "
          f"{supply_audit['total_training_skill_pairs']:,}")

    print("\n=== Gap vector: headline vs reweighted ===")
    gap_head = gap_vector(headline_mm, supply)
    gap_rw = gap_vector(rw_mm, supply)
    rank = rank_stability(gap_head, gap_rw, k=10)
    print(f"  Pearson r gap_pp : {rank['pearson_gap_corr']}")
    print(f"  max |Δ gap_pp|   : {rank['max_abs_gap_diff_pp']:.2f} pp")
    print(f"  top-10 under-supplied overlap : {rank['top_under_overlap']}/10")
    print(f"  top-10 over-supplied overlap  : {rank['top_over_overlap']}/10")

    write_csv(headline_mm, rw_mm, supply, OUT_CSV)
    print(f"\nwrote {OUT_CSV.relative_to(ROOT)}")

    audit = {
        "target": target_audit,
        "pracuj": {
            "postings_used": n_used,
            "matched_l1_mentions": grand_mentions,
            "n_post_by_nace": n_k,
            "tot_mentions_by_nace": tot_k,
            "p_pracuj_pct": {k: round(v * 100, 4) for k, v in p_pracuj.items()},
        },
        "weights": {
            "target_renorm_pct": {
                k: round(v * 100, 4) for k, v in target_renorm.items()
            },
            "w_k": {k: round(v, 5) for k, v in w_k.items()},
            "min_w": round(min(w_k.values()), 5) if w_k else None,
            "max_w": round(max(w_k.values()), 5) if w_k else None,
        },
        "demand_headline_mm_pct": {
            g: round(v * 100, 4) for g, v in headline_mm.items()
        },
        "demand_reweighted_mm_pct": {
            g: round(v * 100, 4) for g, v in rw_mm.items()
        },
        "diagnostics": diag,
        "supply_mm_pct": {g: round(v * 100, 4) for g, v in supply.items()},
        "supply_audit": supply_audit,
        "gap_stability": rank,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

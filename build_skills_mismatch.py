"""Skills demand–supply mismatch (ESCO L1 + L2): job offers vs BUR trainings.

Inputs
------
- app_deploy/skills_stats_cache.json          (demand : Pracuj.pl 2025 offers)
- app_deploy/trainings_regional_cache.json    (supply : BUR trainings, ESCO-tagged)

For both sides we compute the *skill mix* — share of the total ESCO mentions
(or training-skill tags) that fall into each ESCO concept group:

    demand_share[g] = mentions_in_offers[g]   / Σ mentions_in_offers
    supply_share[g] = trainings_with_group[g] / Σ trainings_with_group

The mismatch in percentage points is

    gap_pp[g] = demand_share[g] − supply_share[g]

    gap > 0 → group is under-supplied (more demand than training response)
    gap < 0 → group is over-supplied (training response exceeds demand)

Outputs
-------
- presentation/skills_mismatch_l1.csv
- presentation/skills_mismatch_l2.csv
- presentation/skills_mismatch_l1_overview.png   (paired bars, sorted by demand)
- presentation/skills_mismatch_l1_gap.png        (diverging gap bars)
- presentation/skills_mismatch_l2_top.png        (top under- and over-supplied L2)
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

ROOT = Path(__file__).resolve().parent
DEMAND_PATH = ROOT / "app_deploy" / "skills_stats_cache.json"
SUPPLY_PATH = ROOT / "app_deploy" / "trainings_regional_cache.json"
OUT_DIR = ROOT / "presentation"

NAVY = "#15314B"
RED = "#c1272d"      # under-supplied (demand > supply)
GREEN = "#1f8b4c"    # over-supplied  (supply > demand)
LIGHT_BLUE = "#5C9DCE"
SAND = "#D4A24C"


# ───────────────────────── load + normalise ───────────────────────── #


def load_demand() -> dict[str, dict[str, Any]]:
    """Return tree node → {title, count, l2_children:{code: (title, count)}}."""
    raw = json.loads(DEMAND_PATH.read_text(encoding="utf-8"))
    tree = raw["tree"]
    meta = raw["meta"]
    out: dict[str, dict[str, Any]] = {}
    for k, v in tree.items():
        l2 = {
            ck: {"title": cv.get("title", ck), "count": int(cv.get("count", 0))}
            for ck, cv in v.get("children", {}).items()
        }
        out[k] = {
            "title": v.get("title", k),
            "count": int(v.get("count", 0)),
            "l2": l2,
        }
    return {"meta": meta, "groups": out}


def load_supply() -> dict[str, dict[str, Any]]:
    raw = json.loads(SUPPLY_PATH.read_text(encoding="utf-8"))
    meta = raw["meta"]
    return {
        "meta": meta,
        "L1": {k: {"n_with_group": int(v["national_n_with_group"]),
                   "n_uris": int(v["n_uris_in_group"])}
               for k, v in raw["L1"].items()},
        "L2": {k: {"n_with_group": int(v["national_n_with_group"]),
                   "n_uris": int(v["n_uris_in_group"])}
               for k, v in raw["L2"].items()},
    }


def load_supply_2025() -> dict[str, dict[str, Any]]:
    """Compute supply (training-skill tag) counts using *only* trainings whose
    `id` appears in `trainings/data/yearly/bur_2025.parquet`.

    For each (BUR competency → ESCO skill) row in `bur_to_esco_kalm_top1.parquet`
    we intersect `bur_bur_ids_json` with the set of 2025 IDs and add that count
    to the L1 group of the ESCO skill.
    """
    import pandas as pd

    esco_dict = json.loads((ROOT / "app_deploy" / "esco_dictionary.json")
                           .read_text(encoding="utf-8"))
    uri2l1: dict[str, str] = {}
    for _, info in esco_dict.items():
        h = info.get("hierarchy") or []
        if len(h) >= 2:
            uri2l1[info["uri"]] = h[-2]["code"]

    bur_2025 = pd.read_parquet(
        ROOT / "trainings" / "data" / "yearly" / "bur_2025.parquet",
        columns=["id"],
    )
    ids_2025: set[int] = {int(x) for x in bur_2025["id"].dropna().tolist()}

    bur_esco = pd.read_parquet(
        ROOT / "trainings" / "data" / "bur_to_esco_kalm_top1.parquet",
        columns=["bur_bur_ids_json", "esco_conceptUri"],
    )

    l1_count: dict[str, int] = {}
    n_total_pairs = 0          # (training_2025, ESCO-skill) pairs
    n_trainings_in_2025 = len(ids_2025)

    for js, uri in zip(bur_esco["bur_bur_ids_json"], bur_esco["esco_conceptUri"]):
        l1 = uri2l1.get(uri)
        if l1 is None:
            continue
        try:
            ids = json.loads(js) if isinstance(js, str) else list(js or [])
        except Exception:
            ids = []
        n_match = sum(1 for x in ids if int(x) in ids_2025)
        if n_match == 0:
            continue
        l1_count[l1] = l1_count.get(l1, 0) + n_match
        n_total_pairs += n_match

    meta = {
        "year": 2025,
        "n_trainings_in_2025_parquet": n_trainings_in_2025,
        "n_training_skill_pairs_2025": n_total_pairs,
        "source": "trainings/data/yearly/bur_2025.parquet (id) ∩ "
                  "trainings/data/bur_to_esco_kalm_top1.parquet",
    }
    return {
        "meta": meta,
        "L1": {k: {"n_with_group": v, "n_uris": 0} for k, v in l1_count.items()},
        "L2": {},   # L2 not built here — slide focuses on S1–S8
    }


# ───────────────────────── classification ───────────────────────── #


def family_of(code: str) -> str:
    """ESCO concept family used for colour coding."""
    if code.startswith("S"):
        return "Skills (S)"
    if code.startswith("T"):
        return "Transversal (T)"
    if code.startswith("L"):
        return "Languages (L)"
    return "Knowledge (ISCED)"


FAMILY_COLORS = {
    "Skills (S)":         "#1d4e89",
    "Transversal (T)":    "#5c9dce",
    "Knowledge (ISCED)":  "#d4a24c",
    "Languages (L)":      "#7f7f7f",
}


# ───────────────────────── core computation ───────────────────────── #


def build_l1(demand: dict, supply: dict) -> list[dict]:
    """Per-L1 row with demand share, supply share, gap (pp)."""
    d_groups = demand["groups"]
    sup_l1 = supply["L1"]

    # union of keys
    keys = sorted(set(d_groups) | set(sup_l1))
    d_total = sum(d_groups[k]["count"] for k in d_groups if k in keys)
    s_total = sum(sup_l1[k]["n_with_group"] for k in sup_l1 if k in keys)

    rows = []
    for k in keys:
        d_count = d_groups.get(k, {}).get("count", 0)
        s_count = sup_l1.get(k, {}).get("n_with_group", 0)
        title = d_groups.get(k, {}).get("title") or k
        d_share = d_count / d_total if d_total else 0.0
        s_share = s_count / s_total if s_total else 0.0
        rows.append({
            "code": k,
            "title": title,
            "family": family_of(k),
            "mentions_offers": d_count,
            "trainings_with_group": s_count,
            "demand_share": d_share,
            "supply_share": s_share,
            "gap_pp": (d_share - s_share) * 100,
        })
    rows.sort(key=lambda r: -r["demand_share"])
    return rows


def build_l2(demand: dict, supply: dict) -> list[dict]:
    """Per-L2 row using the same shape."""
    sup_l2 = supply["L2"]
    # flatten demand L2
    d_l2: dict[str, dict] = {}
    for l1k, l1v in demand["groups"].items():
        for ck, cv in l1v["l2"].items():
            d_l2[ck] = {"title": cv["title"], "count": cv["count"], "parent": l1k,
                        "parent_title": l1v["title"]}

    keys = sorted(set(d_l2) | set(sup_l2))
    d_total = sum(d_l2[k]["count"] for k in d_l2 if k in keys)
    s_total = sum(sup_l2[k]["n_with_group"] for k in sup_l2 if k in keys)

    rows = []
    for k in keys:
        d_count = d_l2.get(k, {}).get("count", 0)
        s_count = sup_l2.get(k, {}).get("n_with_group", 0)
        title = (d_l2.get(k) or {}).get("title") or k
        parent = (d_l2.get(k) or {}).get("parent", "")
        parent_title = (d_l2.get(k) or {}).get("parent_title", "")
        d_share = d_count / d_total if d_total else 0.0
        s_share = s_count / s_total if s_total else 0.0
        rows.append({
            "code": k,
            "title": title,
            "parent_code": parent,
            "parent_title": parent_title,
            "family": family_of(k or parent),
            "mentions_offers": d_count,
            "trainings_with_group": s_count,
            "demand_share": d_share,
            "supply_share": s_share,
            "gap_pp": (d_share - s_share) * 100,
        })
    return rows


# ───────────────────────── output csv ───────────────────────── #


def write_csv(rows: list[dict], out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


# ───────────────────────── chart 1: L1 paired bars ───────────────────────── #


def chart_l1_overview(rows: list[dict], out: Path) -> None:
    """Paired horizontal bars (demand vs supply) for top L1 groups."""
    rows = [r for r in rows if r["demand_share"] >= 0.005 or r["supply_share"] >= 0.005]
    rows = sorted(rows, key=lambda r: -r["demand_share"])

    n = len(rows)
    fig, ax = plt.subplots(figsize=(12.5, 0.42 * n + 1.6), dpi=200)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    y = list(range(n))
    h = 0.40
    d_vals = [r["demand_share"] * 100 for r in rows]
    s_vals = [r["supply_share"] * 100 for r in rows]
    labels = [f"{r['code']} · {r['title']}" for r in rows]

    ax.barh([yi + h / 2 for yi in y], d_vals, height=h,
            color=LIGHT_BLUE, edgecolor="white", label="Demand (job offers)")
    ax.barh([yi - h / 2 for yi in y], s_vals, height=h,
            color=SAND, edgecolor="white", label="Supply (BUR trainings)")

    for yi, dv, sv in zip(y, d_vals, s_vals):
        ax.text(dv + 0.2, yi + h / 2, f"{dv:.1f}%", va="center", ha="left",
                fontsize=8.5, color=NAVY)
        ax.text(sv + 0.2, yi - h / 2, f"{sv:.1f}%", va="center", ha="left",
                fontsize=8.5, color=NAVY)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9.5, color=NAVY)
    ax.invert_yaxis()
    ax.set_xlabel("Share of all ESCO mentions / training-skill tags (%)",
                  fontsize=10, color=NAVY)
    ax.xaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f%%"))
    ax.tick_params(axis="x", colors=NAVY, labelsize=9)
    ax.grid(axis="x", linestyle=":", color="#cbd5e1", linewidth=0.7, zorder=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#94a3b8")

    ax.legend(loc="lower right", frameon=False, fontsize=10)
    fig.suptitle("Skill mix: demand (job offers) vs supply (BUR trainings)",
                 x=0.02, y=0.985, ha="left", fontsize=14, color=NAVY,
                 fontweight="bold")
    fig.text(0.02, 0.955, "ESCO Level-1 concept groups · 2025",
             ha="left", fontsize=10.5, color="#64748b")
    fig.text(0.02, 0.01,
             "Demand: 5.36 M ESCO skill mentions across 748,922 Pracuj.pl offers · "
             "Supply: 719,265 BUR training services tagged with ESCO skills (KALM top-1, sim ≥ 0.7).",
             ha="left", fontsize=8.2, color="#64748b", style="italic")

    fig.tight_layout(rect=(0.0, 0.025, 1.0, 0.94))
    fig.savefig(out, dpi=200, facecolor="white")
    plt.close(fig)


# ───────────────────────── chart 2: L1 diverging gap ───────────────────────── #


def chart_l1_gap(rows: list[dict], out: Path) -> None:
    rows = [r for r in rows if r["demand_share"] >= 0.005 or r["supply_share"] >= 0.005]
    rows = sorted(rows, key=lambda r: r["gap_pp"])

    n = len(rows)
    fig, ax = plt.subplots(figsize=(12.5, 0.42 * n + 1.6), dpi=200)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    y = list(range(n))
    gaps = [r["gap_pp"] for r in rows]
    labels = [f"{r['code']} · {r['title']}" for r in rows]
    colors = [RED if g > 0 else GREEN for g in gaps]

    ax.barh(y, gaps, color=colors, edgecolor="white", height=0.7)

    span = max(abs(min(gaps)), abs(max(gaps))) if gaps else 1
    for yi, g in zip(y, gaps):
        # always put the label *outside* the bar, away from the y-axis labels
        if g >= 0:
            ax.text(g + span * 0.015, yi, f"{g:+.1f} pp", va="center", ha="left",
                    fontsize=8.8, color=NAVY, fontweight="bold")
        else:
            ax.text(g - span * 0.015, yi, f"{g:+.1f} pp", va="center", ha="right",
                    fontsize=8.8, color=NAVY, fontweight="bold")
    ax.set_xlim(-span * 1.18, span * 1.18)

    ax.axvline(0, color="#475569", linewidth=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=9.5, color=NAVY)
    ax.set_xlabel("Demand share − Supply share  (percentage points)",
                  fontsize=10, color=NAVY)
    ax.tick_params(axis="x", colors=NAVY, labelsize=9)
    ax.grid(axis="x", linestyle=":", color="#cbd5e1", linewidth=0.7, zorder=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#94a3b8")

    fig.suptitle("Where supply lags demand — ESCO Level-1 mismatch",
                 x=0.02, y=0.985, ha="left", fontsize=14, color=NAVY,
                 fontweight="bold")
    fig.text(0.02, 0.955,
             "Red = under-supplied (more demand than training response) · "
             "Green = over-supplied (training response exceeds demand)",
             ha="left", fontsize=10.5, color="#64748b")
    fig.text(0.02, 0.01,
             "Pracuj.pl 2025 offers vs BUR 2024–2025 training services · "
             "ESCO L1 concept groups, KALM top-1 mapping (sim ≥ 0.7).",
             ha="left", fontsize=8.2, color="#64748b", style="italic")

    fig.tight_layout(rect=(0.0, 0.025, 1.0, 0.94))
    fig.savefig(out, dpi=200, facecolor="white")
    plt.close(fig)


# ───────────────────────── chart S1–S8 only (renormalised) ───────────────────────── #


def chart_skills_only(rows: list[dict], out_overview: Path, out_gap: Path,
                      supply_label: str = "BUR 2024–2025 training services",
                      order: list[str] | None = None,
                      pillar_name: str = "Skills",
                      pillar_xlabel: str = "Skills pillar",
                      sort_by_demand: bool = False) -> None:
    """Restrict to a chosen ESCO L1 sub-pillar, renormalise each side to 100 %,
    and render in the specified `order`.

    Defaults reproduce the original S1–S8 chart. Pass:
      - `order=["00",...,"10"]`, `pillar_name="Knowledge"`,
        `pillar_xlabel="Knowledge pillar (ISCED-F)"`
      - `order=["T1",...,"T6"]`, `pillar_name="Transversal"`,
        `pillar_xlabel="Transversal pillar"`
    to render the K and T variants.

    If `sort_by_demand=True`, the rows in `order` are re-sorted by descending
    demand share before rendering (used for the Languages pillar where the
    natural code order is meaningless).
    """
    if order is None:
        order = ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"]
    by_code = {r["code"]: r for r in rows}
    sub = [by_code[c] for c in order if c in by_code]
    if sort_by_demand:
        sub = sorted(sub, key=lambda r: -r["mentions_offers"])
        order = [r["code"] for r in sub]

    d_total = sum(r["mentions_offers"] for r in sub)
    s_total = sum(r["trainings_with_group"] for r in sub)

    renorm = []
    for r in sub:
        d_share = r["mentions_offers"] / d_total if d_total else 0.0
        s_share = r["trainings_with_group"] / s_total if s_total else 0.0
        renorm.append({
            **r,
            "demand_share": d_share,
            "supply_share": s_share,
            "gap_pp": (d_share - s_share) * 100,
        })

    # ─── overview (paired bars), fixed S1→S8 order ───
    n = len(renorm)
    fig, ax = plt.subplots(figsize=(12.5, 0.78 * n + 1.6), dpi=200)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    y = list(range(n))
    h = 0.40
    d_vals = [r["demand_share"] * 100 for r in renorm]
    s_vals = [r["supply_share"] * 100 for r in renorm]
    labels = [f"{r['code']} · {r['title']}" for r in renorm]

    ax.barh([yi + h / 2 for yi in y], d_vals, height=h,
            color=LIGHT_BLUE, edgecolor="white", label="Demand (job offers)")
    ax.barh([yi - h / 2 for yi in y], s_vals, height=h,
            color=SAND, edgecolor="white", label="Supply (BUR trainings)")

    for yi, dv, sv in zip(y, d_vals, s_vals):
        ax.text(dv + 0.4, yi + h / 2, f"{dv:.1f}%", va="center", ha="left",
                fontsize=9.5, color=NAVY, fontweight="bold")
        ax.text(sv + 0.4, yi - h / 2, f"{sv:.1f}%", va="center", ha="left",
                fontsize=9.5, color=NAVY, fontweight="bold")

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10.5, color=NAVY)
    ax.invert_yaxis()
    ax.set_xlabel(f"Share within ESCO {pillar_xlabel} (%, each side sums to 100 %)",
                  fontsize=10, color=NAVY)
    ax.xaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f%%"))
    ax.tick_params(axis="x", colors=NAVY, labelsize=9)
    ax.grid(axis="x", linestyle=":", color="#cbd5e1", linewidth=0.7, zorder=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#94a3b8")
    ax.legend(loc="lower right", frameon=False, fontsize=10)

    code_range = f"{order[0]}–{order[-1]}" if len(order) > 1 else order[0]
    fig.suptitle(f"Skill mix within the ESCO {pillar_name} pillar — demand vs supply",
                 x=0.02, y=0.985, ha="left", fontsize=14, color=NAVY,
                 fontweight="bold")
    fig.text(0.02, 0.955,
             f"ESCO L1 groups {code_range} · shares renormalised to 100 % within the pillar · 2025",
             ha="left", fontsize=10.5, color="#64748b")
    fig.text(0.02, 0.012,
             f"Demand: ESCO mentions in {code_range} · Pracuj.pl 2025 offers · "
             f"Supply: {supply_label}, KALM top-1 (sim ≥ 0.7).",
             ha="left", fontsize=8.2, color="#64748b", style="italic")
    fig.tight_layout(rect=(0.0, 0.025, 1.0, 0.94))
    fig.savefig(out_overview, dpi=200, facecolor="white")
    plt.close(fig)

    # ─── diverging gap (also S1→S8 order) ───
    fig, ax = plt.subplots(figsize=(12.5, 0.78 * n + 1.6), dpi=200)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#ffffff")

    gaps = [r["gap_pp"] for r in renorm]
    colors = [RED if g > 0 else GREEN for g in gaps]
    ax.barh(y, gaps, color=colors, edgecolor="white", height=0.62)

    span = max(abs(min(gaps)), abs(max(gaps))) if gaps else 1
    for yi, g in zip(y, gaps):
        if g >= 0:
            ax.text(g + span * 0.02, yi, f"{g:+.1f} pp", va="center", ha="left",
                    fontsize=10, color=NAVY, fontweight="bold")
        else:
            ax.text(g - span * 0.02, yi, f"{g:+.1f} pp", va="center", ha="right",
                    fontsize=10, color=NAVY, fontweight="bold")

    ax.axvline(0, color="#475569", linewidth=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10.5, color=NAVY)
    ax.invert_yaxis()
    ax.set_xlim(-span * 1.22, span * 1.22)
    ax.set_xlabel(f"Demand share − Supply share  (percentage points, within {code_range})",
                  fontsize=10, color=NAVY)
    ax.tick_params(axis="x", colors=NAVY, labelsize=9)
    ax.grid(axis="x", linestyle=":", color="#cbd5e1", linewidth=0.7, zorder=0)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#94a3b8")

    fig.suptitle(f"Where supply lags demand within the ESCO {pillar_name} pillar",
                 x=0.02, y=0.985, ha="left", fontsize=14, color=NAVY,
                 fontweight="bold")
    fig.text(0.02, 0.955,
             f"Red = under-supplied (more demand than training response) · "
             f"Green = over-supplied · {code_range} only · shares renormalised to 100 %",
             ha="left", fontsize=10.2, color="#64748b")
    fig.text(0.02, 0.012,
             f"Pracuj.pl 2025 offers vs {supply_label} · "
             f"ESCO {pillar_name} pillar ({code_range}) · KALM top-1 mapping (sim ≥ 0.7).",
             ha="left", fontsize=8.2, color="#64748b", style="italic")
    fig.tight_layout(rect=(0.0, 0.025, 1.0, 0.94))
    fig.savefig(out_gap, dpi=200, facecolor="white")
    plt.close(fig)

    print()
    print(f"{code_range} only — renormalised to 100 % within the pillar:")
    print(f"  {'code':<6}{'demand%':>10}{'supply%':>10}{'gap pp':>10}  title")
    for r in renorm:
        print(f"  {r['code']:<6}{r['demand_share']*100:>9.2f}%"
              f"{r['supply_share']*100:>9.2f}%{r['gap_pp']:>10.2f}  {r['title']}")


# ───────────────────────── chart 3: L2 top mismatches ───────────────────────── #


def chart_l2_top(rows: list[dict], out: Path, k_each: int = 12) -> None:
    """Two side-by-side panels: top under- and over-supplied L2 groups.

    Both panels show *absolute* gap so bar direction is consistent and labels
    sit cleanly to the left of the bars on both sides.
    """
    eligible = [r for r in rows
                if (r["demand_share"] + r["supply_share"]) >= 0.005]

    under = sorted(eligible, key=lambda r: -r["gap_pp"])[:k_each]   # demand >> supply
    over = sorted(eligible, key=lambda r: r["gap_pp"])[:k_each]     # supply >> demand

    fig = plt.figure(figsize=(16.4, 7.8), dpi=200)
    fig.patch.set_facecolor("#ffffff")
    # explicit axes so y-tick label rooms don't fight with figure margins
    ax_left = fig.add_axes([0.21, 0.090, 0.27, 0.78])
    ax_right = fig.add_axes([0.71, 0.090, 0.27, 0.78])
    axes = [ax_left, ax_right]

    def _panel(ax, data, title, color):
        ax.set_facecolor("#ffffff")
        # largest at top
        data = list(data)
        y = list(range(len(data)))
        gaps = [abs(r["gap_pp"]) for r in data]
        labels = [_short_label(r) for r in data]
        ax.barh(y, gaps, color=color, edgecolor="white", height=0.72)
        x_max = max(gaps) if gaps else 1
        for yi, g, r in zip(y, gaps, data):
            d = r["demand_share"] * 100
            s = r["supply_share"] * 100
            ax.text(g + x_max * 0.012, yi,
                    f"{g:.2f} pp   ({d:.1f}% vs {s:.1f}%)",
                    va="center", ha="left", fontsize=8.4, color=NAVY)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=8.6, color=NAVY)
        ax.invert_yaxis()
        ax.tick_params(axis="x", colors=NAVY, labelsize=9)
        ax.set_xlabel("|Demand − Supply| share (pp)", fontsize=9.5, color=NAVY)
        ax.grid(axis="x", linestyle=":", color="#cbd5e1", linewidth=0.7, zorder=0)
        for spine in ("top", "right", "left"):
            ax.spines[spine].set_visible(False)
        ax.spines["bottom"].set_color("#94a3b8")
        ax.set_title(title, color=NAVY, fontsize=11.5, loc="left",
                     pad=8, fontweight="bold")
        ax.set_xlim(0, x_max * 1.55)

    _panel(axes[0], under,
           "Under-supplied — strong employer demand, thin training offer",
           RED)
    _panel(axes[1], over,
           "Over-supplied — heavy training offer, weaker employer demand",
           GREEN)

    fig.suptitle("Top skill-level mismatches between job offers and BUR trainings",
                 x=0.02, y=0.985, ha="left", fontsize=14, color=NAVY,
                 fontweight="bold")
    fig.text(0.02, 0.955,
             "ESCO Level-2 concept groups · share of all skill mentions / training tags · "
             f"top {k_each} on each side",
             ha="left", fontsize=10.2, color="#64748b")
    fig.text(0.02, 0.012,
             "Demand: 4.91 M matched ESCO mentions across Pracuj.pl 2025 offers · "
             "Supply: BUR services tagged via KALM top-1 (sim ≥ 0.7).",
             ha="left", fontsize=8.0, color="#64748b", style="italic")

    fig.savefig(out, dpi=200, facecolor="white")
    plt.close(fig)


def _short_label(r: dict, max_len: int = 56) -> str:
    title = r["title"] or r["code"]
    if len(title) > max_len:
        title = title[: max_len - 1].rstrip() + "…"
    return f"{r['code']} · {title}"


# ───────────────────────── main ───────────────────────── #


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    demand = load_demand()
    supply = load_supply()

    print("DEMAND meta:", demand["meta"])
    print("SUPPLY meta:",
          {k: v for k, v in supply["meta"].items()
           if k in {"n_trainings_with_voivodeship", "n_esco_source_rows",
                    "similarity_threshold", "external_esco"}})

    l1 = build_l1(demand, supply)
    l2 = build_l2(demand, supply)

    # totals for headers
    print("\nL1 — sum demand_share:",
          round(sum(r["demand_share"] for r in l1), 4),
          " sum supply_share:", round(sum(r["supply_share"] for r in l1), 4))

    print("\nTop 10 L1 groups by demand share:")
    print(f"  {'code':<6}{'demand%':>10}{'supply%':>10}{'gap pp':>10}  title")
    for r in sorted(l1, key=lambda r: -r["demand_share"])[:10]:
        print(f"  {r['code']:<6}{r['demand_share']*100:>9.2f}%"
              f"{r['supply_share']*100:>9.2f}%{r['gap_pp']:>10.2f}  {r['title']}")

    print("\nTop 10 L1 mismatches — under-supplied (demand >> supply):")
    print(f"  {'code':<6}{'demand%':>10}{'supply%':>10}{'gap pp':>10}  title")
    for r in sorted(l1, key=lambda r: -r["gap_pp"])[:10]:
        print(f"  {r['code']:<6}{r['demand_share']*100:>9.2f}%"
              f"{r['supply_share']*100:>9.2f}%{r['gap_pp']:>10.2f}  {r['title']}")

    print("\nTop 10 L1 mismatches — over-supplied (supply >> demand):")
    print(f"  {'code':<6}{'demand%':>10}{'supply%':>10}{'gap pp':>10}  title")
    for r in sorted(l1, key=lambda r: r["gap_pp"])[:10]:
        print(f"  {r['code']:<6}{r['demand_share']*100:>9.2f}%"
              f"{r['supply_share']*100:>9.2f}%{r['gap_pp']:>10.2f}  {r['title']}")

    print("\nTop 12 L2 mismatches — under-supplied:")
    print(f"  {'code':<8}{'demand%':>10}{'supply%':>10}{'gap pp':>10}  title")
    for r in sorted([r for r in l2
                     if r["demand_share"] + r["supply_share"] >= 0.005],
                    key=lambda r: -r["gap_pp"])[:12]:
        print(f"  {r['code']:<8}{r['demand_share']*100:>9.2f}%"
              f"{r['supply_share']*100:>9.2f}%{r['gap_pp']:>10.2f}  {r['title']}")

    print("\nTop 12 L2 mismatches — over-supplied:")
    print(f"  {'code':<8}{'demand%':>10}{'supply%':>10}{'gap pp':>10}  title")
    for r in sorted([r for r in l2
                     if r["demand_share"] + r["supply_share"] >= 0.005],
                    key=lambda r: r["gap_pp"])[:12]:
        print(f"  {r['code']:<8}{r['demand_share']*100:>9.2f}%"
              f"{r['supply_share']*100:>9.2f}%{r['gap_pp']:>10.2f}  {r['title']}")

    # write CSVs
    write_csv(l1, OUT_DIR / "skills_mismatch_l1.csv")
    write_csv(l2, OUT_DIR / "skills_mismatch_l2.csv")
    print("\nwrote", OUT_DIR / "skills_mismatch_l1.csv")
    print("wrote", OUT_DIR / "skills_mismatch_l2.csv")

    # charts
    chart_l1_overview(l1, OUT_DIR / "skills_mismatch_l1_overview.png")
    print("wrote", OUT_DIR / "skills_mismatch_l1_overview.png")
    chart_l1_gap(l1, OUT_DIR / "skills_mismatch_l1_gap.png")
    print("wrote", OUT_DIR / "skills_mismatch_l1_gap.png")
    chart_skills_only(
        l1,
        OUT_DIR / "skills_mismatch_s1_s8_overview.png",
        OUT_DIR / "skills_mismatch_s1_s8_gap.png",
    )
    print("wrote", OUT_DIR / "skills_mismatch_s1_s8_overview.png")
    print("wrote", OUT_DIR / "skills_mismatch_s1_s8_gap.png")

    # ── S1–S8, supply restricted to 2025-only trainings ──
    print("\n── 2025-only supply ──")
    supply_2025 = load_supply_2025()
    print("supply_2025 meta:", supply_2025["meta"])
    l1_2025 = build_l1(demand, supply_2025)
    chart_skills_only(
        l1_2025,
        OUT_DIR / "skills_mismatch_s1_s8_overview_2025.png",
        OUT_DIR / "skills_mismatch_s1_s8_gap_2025.png",
        supply_label="BUR 2025 training services (id ∈ bur_2025.parquet)",
    )
    print("wrote", OUT_DIR / "skills_mismatch_s1_s8_overview_2025.png")
    print("wrote", OUT_DIR / "skills_mismatch_s1_s8_gap_2025.png")
    write_csv(l1_2025, OUT_DIR / "skills_mismatch_l1_2025.csv")
    print("wrote", OUT_DIR / "skills_mismatch_l1_2025.csv")
    chart_l2_top(l2, OUT_DIR / "skills_mismatch_l2_top.png", k_each=12)
    print("wrote", OUT_DIR / "skills_mismatch_l2_top.png")

    # ── Knowledge groups (00–10, ISCED-F) — 2025-only supply ──
    print("\n── Knowledge pillar (00–10), 2025-only supply ──")
    k_order = ["00", "01", "02", "03", "04", "05",
               "06", "07", "08", "09", "10"]
    chart_skills_only(
        l1_2025,
        OUT_DIR / "skills_mismatch_knowledge_overview_2025.png",
        OUT_DIR / "skills_mismatch_knowledge_gap_2025.png",
        supply_label="BUR 2025 training services (id ∈ bur_2025.parquet)",
        order=k_order,
        pillar_name="Knowledge",
        pillar_xlabel="Knowledge pillar (ISCED-F)",
    )
    print("wrote", OUT_DIR / "skills_mismatch_knowledge_overview_2025.png")
    print("wrote", OUT_DIR / "skills_mismatch_knowledge_gap_2025.png")

    # ── Transversal skills (T1–T6) — 2025-only supply ──
    print("\n── Transversal pillar (T1–T6), 2025-only supply ──")
    t_order = ["T1", "T2", "T3", "T4", "T5", "T6"]
    chart_skills_only(
        l1_2025,
        OUT_DIR / "skills_mismatch_transversal_overview_2025.png",
        OUT_DIR / "skills_mismatch_transversal_gap_2025.png",
        supply_label="BUR 2025 training services (id ∈ bur_2025.parquet)",
        order=t_order,
        pillar_name="Transversal",
        pillar_xlabel="Transversal pillar",
    )
    print("wrote", OUT_DIR / "skills_mismatch_transversal_overview_2025.png")
    print("wrote", OUT_DIR / "skills_mismatch_transversal_gap_2025.png")

    # ── Languages pillar (L*) — full supply (BUR 2024–2025) ──
    # 2025-only BUR supply has almost no language tags, so we use the full
    # supply (~720k tagged trainings).
    # Excluded from the chart:
    #   - L1   = generic placeholder (not a language)
    #   - L42  = Polish (almost everyone in the labour market speaks it;
    #            its 'demand' is misleading — usually means 'native speaker
    #            required for non-Poles' rather than a learnable skill)
    # The remaining languages are split into TOP-N + 'Other' bucket so the
    # long tail (Belarusian, Bulgarian, Estonian, ...) is still represented
    # but doesn't crowd the chart.
    print("\n── Languages pillar (L*), full supply ──")
    TOP_N_LANGUAGES = 9
    EXCLUDED = {"L1", "L42"}
    l_universe = [r for r in l1
                  if r["code"].startswith("L") and r["code"] not in EXCLUDED]
    l_universe = sorted(l_universe, key=lambda r: -r["mentions_offers"])
    top_l = l_universe[:TOP_N_LANGUAGES]
    others_l = l_universe[TOP_N_LANGUAGES:]

    # Build synthetic "Other" row aggregating the long tail.
    other_demand = sum(r["mentions_offers"] for r in others_l)
    other_supply = sum(r["trainings_with_group"] for r in others_l)
    other_codes = ", ".join(r["code"] for r in others_l)
    other_titles = ", ".join((r["title"] or r["code"]).split(" ")[0] for r in others_l)
    print(f"  'Other' bucket = {len(others_l)} languages "
          f"({other_demand:,} mentions, {other_supply:,} trainings): {other_titles}")
    other_row = {
        "code": "Other",
        "title": f"Other ({len(others_l)} languages)",
        "family": "Languages (L)",
        "mentions_offers": other_demand,
        "trainings_with_group": other_supply,
        # demand_share/supply_share/gap_pp recomputed by chart_skills_only
        "demand_share": 0.0, "supply_share": 0.0, "gap_pp": 0.0,
    }
    rows_for_chart = top_l + [other_row]
    l_codes = [r["code"] for r in rows_for_chart]
    chart_skills_only(
        rows_for_chart,
        OUT_DIR / "skills_mismatch_languages_overview.png",
        OUT_DIR / "skills_mismatch_languages_gap.png",
        supply_label="BUR 2024–2025 training services",
        order=l_codes,
        pillar_name="Languages",
        pillar_xlabel="Languages pillar (renormalised within L, Polish excluded)",
        sort_by_demand=True,
    )
    print("wrote", OUT_DIR / "skills_mismatch_languages_overview.png")
    print("wrote", OUT_DIR / "skills_mismatch_languages_gap.png")


if __name__ == "__main__":
    main()

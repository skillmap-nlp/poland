"""Build assets/international_comparison_data.js.

Takes baseline international data from the skillmap-nlp/east-asia repo
(macro context, digital-skill levels, ESCO S1-S8 mix) and replaces the Poland
values with the figures produced for this Poland report. The output is a
single JS asset consumed by assets/international_comparison.js.

The east-asia source files are kept under /vendor/east_asia/ to make updates
auditable. If they are missing, the script raises a clear error.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENDOR = ROOT / "vendor" / "east_asia"
OUT = ROOT / "assets" / "international_comparison_data.js"

RESULTS_EXT = ROOT / "assets" / "results_extended_data.js"
DIGITAL_REG = ROOT / "assets" / "digital_regional_map_data.js"


def load_json_asset(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    payload = text.split("=", 1)[1].rstrip(";\n")
    return json.loads(payload)


def load_vendor(name: str) -> dict:
    path = VENDOR / name
    if not path.exists():
        raise FileNotFoundError(
            f"Missing vendor file {path}. Re-run the fetch step that copies the "
            "east-asia JSONs into vendor/east_asia/."
        )
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    macro = load_vendor("macro_context.json")
    digital_levels = load_vendor("digital_skill_offer_shares.json")
    esco_shares = load_vendor("esco_category_shares.json")

    res_ext = load_json_asset(RESULTS_EXT)
    digital_reg = load_json_asset(DIGITAL_REG)

    # Macro context for Poland is left untouched — these are external WB
    # indicators (GDP per capita, demographics) that the Poland report does
    # not recompute. We keep them and the labelling consistent with east-asia.

    # Digital skill levels — Poland values come from the report's Figure 23.
    # 696,092 classified digital skill mentions: 43.45% advanced, 33.13% basic,
    # 23.42% intermediate.
    pl_digital_total = 696_092
    pl_digital_shares = {
        "Basic": 0.3313,
        "Intermediate": 0.2342,
        "Advanced": 0.4345,
    }
    pl_digital_counts = {
        level: int(round(pl_digital_total * share))
        for level, share in pl_digital_shares.items()
    }
    pl_offers = digital_reg.get("meta", {}).get("total_mapped_offers", 734_324)

    for row in digital_levels.get("rows", []):
        if row.get("country") == "Poland":
            row["offers"] = pl_offers
            row["digital_skill_mentions"] = pl_digital_total
            row["counts"] = pl_digital_counts
            row["shares"] = pl_digital_shares
            row["source"] = "Poland 2025 report"

    # ESCO S1-S8 shares — Poland values come from the report's by_family +
    # skills_s1_s8 entries. Demand shares within the S1-S8 family are
    # renormalised to sum to 1.0 (matching the east-asia convention).
    pl_s1_s8_demand = {
        r["code"]: r["demand_pct"] for r in res_ext["mismatch"]["skills_s1_s8"]
    }
    total = sum(pl_s1_s8_demand.values())
    pl_skill_shares = {
        code: round(value / total, 6) for code, value in pl_s1_s8_demand.items()
    }
    pl_skill_counts = {
        code: int(round(share * res_ext["mismatch"]["meta"]["demand_mentions_m"] * 1e6))
        for code, share in pl_skill_shares.items()
    }

    if "Poland" in esco_shares.get("countries", {}):
        pl_country = esco_shares["countries"]["Poland"]
        pl_country["offers"] = res_ext["mismatch"]["meta"]["demand_offers"]
        pl_country["skill_shares"] = pl_skill_shares
        pl_country["skill_counts"] = pl_skill_counts
        pl_country["source"] = "Poland 2025 report"

    # Trim the ESCO payload to what we actually render — keep skill_meta,
    # skill_shares and offer counts. Knowledge categories are not surfaced in
    # the comparison cards (they would need re-aggregation for Poland).
    countries_trim: dict[str, dict] = {}
    for name, payload in esco_shares.get("countries", {}).items():
        countries_trim[name] = {
            "offers": payload.get("offers"),
            "skill_shares": payload.get("skill_shares", {}),
            "source": payload.get("source"),
        }

    out_payload = {
        "macro": macro,
        "digital_levels": digital_levels,
        "esco_skill_shares": {
            "country_order": esco_shares.get("country_order", []),
            "skill_meta": esco_shares.get("skill_meta", {}),
            "countries": countries_trim,
        },
        "highlight_country": "Poland",
        "highlight_iso": "PL",
        "regions": {
            "east_asia": [
                "Japan",
                "South Korea",
                "Taiwan",
                "Thailand",
                "Malaysia",
                "Singapore",
                "Indonesia",
                "Vietnam",
                "Philippines",
            ],
            "benchmark": ["India", "Mexico", "Poland"],
        },
    }

    OUT.write_text(
        f"window.__INTL_COMPARISON__ = {json.dumps(out_payload, ensure_ascii=False)};\n",
        encoding="utf-8",
    )
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()

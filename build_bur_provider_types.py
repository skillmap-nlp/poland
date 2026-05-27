"""Estimate distribution of BUR 2025 training providers across four buckets:

  1. Private companies (incl. sole proprietors)
  2. NGOs (foundations, associations, ...)
  3. Public educational institutions (universities, vocational schools, ...)
  4. Public finance sector entities (ministries, urzędy, public hospitals, ...)

Method: extract `nazwa` from the JSON `dostawca_uslug` field, normalise (UPPER +
strip Polish accents), and apply ordered keyword regexes. First match wins.

Outputs:
  - presentation/data_export/bur_provider_types_2025.xlsx (6 sheets)
  - presentation/bur_provider_types_2025.png
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parent
PARQ = ROOT / "trainings" / "data" / "yearly" / "bur_2025.parquet"
OUT_XLSX = ROOT / "presentation" / "data_export" / "bur_provider_types_2025.xlsx"
OUT_PNG = ROOT / "presentation" / "bur_provider_types_2025.png"

# ── Normalisation ──────────────────────────────────────────────────────
PL_REPLACE = str.maketrans("ŁłŚśŻżŹźĆćŃńÓóĄąĘę", "LlSsZzZzCcNnOoAaEe")


def normalize(name: str) -> str:
    n = name.upper()
    n = "".join(c for c in unicodedata.normalize("NFKD", n) if not unicodedata.combining(c))
    return n.translate(PL_REPLACE)


# ── Keyword rules (priority order) ─────────────────────────────────────
NGO_PAT = [
    r"\bFUNDACJA\b", r"\bSTOWARZYSZENIE\b", r"\bTOWARZYSTWO\b",
    r"\bZWIAZEK\b(?!\s+ZAWODOWY)", r"\bZRZESZENIE\b", r"\bFEDERACJA\b",
    r"\bIZBA RZEMIESLNICZA\b", r"\bIZBA GOSPODARCZA\b", r"\bIZBA HANDLOWA\b",
    r"\bPCK\b", r"\bCARITAS\b", r"\bTPD\b",
    r"\bORGANIZACJA POZYTKU PUBLICZNEGO\b", r"\bSPOLDZIELNIA SOCJALNA\b",
]
EDU_PAT = [
    r"\bUNIWERSYTET\b", r"\bUNIWERSYTECKA\b", r"\bPOLITECHNIKA\b",
    r"\bAKADEMIA\b", r"\bWYZSZA SZKOLA\b", r"\bSZKOLA GLOWNA\b", r"\bSZKOLA WYZSZA\b",
    r"\bUCZELNIA\b", r"\bKOLEGIUM\b", r"\bINSTYTUT BADAWCZY\b",
    r"\bPOLSKA AKADEMIA NAUK\b", r"\bPAN\b",
    r"\bCENTRUM KSZTALCENIA ZAWODOWEGO\b", r"\bCENTRUM KSZTALCENIA USTAWICZNEGO\b",
    r"\bOSRODEK DOSKONALENIA NAUCZYCIELI\b", r"\bODN\b",
    r"\bTECHNIKUM\b", r"\bSZKOLA BRANZOWA\b", r"\bZESPOL SZKOL\b",
    r"\bOHP\b", r"\bOCHOTNICZE HUFCE PRACY\b",
    r"\bCKZ\b", r"\bCKZIU\b", r"\bCKU\b",
]
PF_PAT = [
    r"\bMINISTERSTWO\b",
    r"\bURZAD MIASTA\b", r"\bURZAD GMINY\b", r"\bURZAD MARSZALKOWSKI\b",
    r"\bURZAD WOJEWODZKI\b", r"\bURZAD PRACY\b", r"\bURZAD STATYSTYCZNY\b",
    r"\bURZAD SKARBOWY\b", r"\bSTAROSTWO\b",
    r"\bMIASTO\b", r"\bGMINA\b", r"\bPOWIAT\b", r"\bSAMORZAD\b",
    r"\bAGENCJA RESTRUKTURYZACJI\b", r"\bAGENCJA ROZWOJU\b",
    r"\bPARP\b", r"\bGUS\b", r"\bZUS\b", r"\bKRUS\b", r"\bPFRON\b", r"\bSANEPID\b",
    r"\bWORD\b", r"\bWOJEWODZKI OSRODEK RUCHU DROGOWEGO\b",
    r"\bINSPEKTORAT\b", r"\bKOMENDA\b",
    r"\bPANSTWOWA\b", r"\bPANSTWOWY\b", r"\bPANSTWOWE\b",
    r"\bSPZOZ\b", r"\bSP\s+ZOZ\b", r"\bSAMODZIELNY PUBLICZNY\b",
    r"\bSZPITAL POWIATOWY\b", r"\bSZPITAL WOJEWODZKI\b", r"\bSZPITAL UNIWERSYTECKI\b",
    r"\bPGE\b", r"\bORLEN\b", r"\bPKP\b", r"\bKGHM\b",
]
PRIV_PAT = [
    r"\bSP\s*\.?\s*Z\s*O\.?\s*O\.?",
    r"\bSPOLKA Z OGRANICZONA ODPOWIEDZIALNOSCIA\b",
    r"\bSPOLKA AKCYJNA\b", r"\bSPOLKA JAWNA\b", r"\bSPOLKA KOMANDYTOWA\b",
    r"\bSPOLKA KOMANDYTOWO-AKCYJNA\b", r"\bSPOLKA CYWILNA\b", r"\bSPOLKA Z O\.O\.",
    r"\bSP\.?\s*J\.?", r"\bSP\.?\s*K\.?", r"\bS\.?A\.?", r"\bS\.\s*C\.", r"\bO\.\s*O\.",
    r"\bSPOLKA\b", r"\bPRZEDSIEBIORSTWO\b", r"\bP\.P\.H\.U\b", r"\bP\.H\.U\b",
    r"\bLLC\b", r"\bINC\b", r"\bLTD\b", r"\bGMBH\b",
    r"\bNIEPUBLICZNA PLACOWKA\b", r"\bNIEPUBLICZNY OSRODEK\b",
    r"\bZAKLAD DOSKONALENIA ZAWODOWEGO\b",
]


def classify(name: str) -> str:
    if not name:
        return "unknown"
    n = normalize(name)
    if any(re.search(p, n) for p in NGO_PAT):
        return "ngo"
    if any(re.search(p, n) for p in EDU_PAT):
        return "public_education"
    if any(re.search(p, n) for p in PF_PAT):
        return "public_finance"
    if any(re.search(p, n) for p in PRIV_PAT):
        return "private_company"
    return "private_individual"


def bucket(c: str) -> str:
    if c in ("private_company", "private_individual"):
        return "Private companies"
    if c == "ngo":
        return "NGOs"
    if c == "public_education":
        return "Public educational institutions"
    if c == "public_finance":
        return "Public finance sector entities"
    return "Unknown"


def extract_name(j) -> str:
    if isinstance(j, str):
        try:
            d = json.loads(j)
        except Exception:
            return ""
    elif isinstance(j, dict):
        d = j
    else:
        return ""
    return str(d.get("nazwa", "")).strip()


# ── Build ──────────────────────────────────────────────────────────────
def main() -> None:
    df = pd.read_parquet(PARQ, columns=["dostawca_uslug"])
    df["name"] = df["dostawca_uslug"].apply(extract_name)
    df["category"] = df["name"].apply(classify)
    df["bucket"] = df["category"].apply(bucket)

    total = len(df)
    prov = df.drop_duplicates("name")
    total_p = prov.shape[0]

    LABELS_EN = {
        "private_company": "Private companies (legal forms)",
        "private_individual": "Private — sole proprietors / individual entrepreneurs",
        "ngo": "NGOs (foundations, associations)",
        "public_education": "Public educational institutions (universities, vocational)",
        "public_finance": "Public finance sector entities",
        "unknown": "Unknown",
    }

    detail = df["category"].value_counts().reset_index()
    detail.columns = ["category", "trainings"]
    detail["label_en"] = detail["category"].map(LABELS_EN)
    detail["share_pct"] = (detail["trainings"] / total * 100).round(2)
    detail["unique_providers"] = detail["category"].map(prov["category"].value_counts().to_dict())
    detail = detail[["category", "label_en", "unique_providers", "trainings", "share_pct"]]

    agg = pd.DataFrame([
        {"bucket": b,
         "trainings": int(df[df["bucket"] == b].shape[0]),
         "unique_providers": int(prov[prov["bucket"] == b].shape[0])}
        for b in ["Private companies", "NGOs",
                  "Public educational institutions",
                  "Public finance sector entities"]
    ])
    agg["share_trainings_pct"] = (agg["trainings"] / total * 100).round(2)
    agg["share_providers_pct"] = (agg["unique_providers"] / total_p * 100).round(2)

    prov_list = (df.groupby(["name", "bucket", "category"]).size()
                 .reset_index(name="trainings").sort_values("trainings", ascending=False))

    methodology = pd.DataFrame([
        {"step": "1. Source",
         "description": "Field 'dostawca_uslug' from BUR 2025 parquet (trainings/data/yearly/bur_2025.parquet). The field is a JSON object — we extracted 'nazwa' (provider name)."},
        {"step": "2. Normalisation",
         "description": "Provider names converted to UPPERCASE; accents stripped (NFKD + manual map for Polish-only Ł→L, Ó→O, etc.)."},
        {"step": "3. Priority order",
         "description": "NGO → Public education → Public finance → Private company → Private individual (catch-all). First matching rule wins."},
        {"step": "4. NGO keywords",
         "description": "FUNDACJA, STOWARZYSZENIE, TOWARZYSTWO, ZRZESZENIE, FEDERACJA, IZBA RZEMIEŚLNICZA / GOSPODARCZA / HANDLOWA, PCK, CARITAS, TPD, SPÓŁDZIELNIA SOCJALNA, ORGANIZACJA POŻYTKU PUBLICZNEGO."},
        {"step": "5. Public education keywords",
         "description": "UNIWERSYTET, POLITECHNIKA, AKADEMIA, WYŻSZA SZKOŁA, SZKOŁA GŁÓWNA / WYŻSZA, UCZELNIA, KOLEGIUM, INSTYTUT BADAWCZY, PAN, TECHNIKUM, SZKOŁA BRANŻOWA, ZESPÓŁ SZKÓŁ, OHP, CKZ/CKZIU/CKU, OŚRODEK DOSKONALENIA NAUCZYCIELI."},
        {"step": "6. Public finance keywords",
         "description": "MINISTERSTWO, URZĄD (MIASTA / GMINY / MARSZAŁKOWSKI / WOJEWÓDZKI / PRACY / STATYSTYCZNY / SKARBOWY), STAROSTWO, MIASTO, GMINA, POWIAT, SAMORZĄD, ARiMR, AGENCJA ROZWOJU, PARP, GUS, ZUS, KRUS, PFRON, SANEPID, WORD, INSPEKTORAT, KOMENDA, PAŃSTWOWA/Y/E, SP ZOZ / SAMODZIELNY PUBLICZNY, SZPITAL POWIATOWY/WOJEWÓDZKI/UNIWERSYTECKI, plus large state-owned enterprises (PGE, ORLEN, PKP, KGHM)."},
        {"step": "7. Private company keywords",
         "description": "SP. Z O.O. / SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ, S.A., SP.J., SP.K., S.K.A., S.C., SPÓŁKA, PRZEDSIĘBIORSTWO, PPHU/PHU, LLC/INC/LTD/GMBH, NIEPUBLICZNA PLACÓWKA, ZAKŁAD DOSKONALENIA ZAWODOWEGO."},
        {"step": "8. Private individual",
         "description": "Catch-all — all remaining providers. Typical pattern: business name + a person's first/last name (sole proprietorship / jednoosobowa działalność gospodarcza, JDG)."},
        {"step": "9. Caveats",
         "description": "Heuristic only; designed to be conservative for public/NGO categories. Some legal-form abbreviations may slip through. Manual review of edge cases is recommended."},
    ])
    sources = pd.DataFrame([
        {"source": "BUR (Baza Usług Rozwojowych)",
         "publisher": "Polska Agencja Rozwoju Przedsiębiorczości (PARP)",
         "field": "dostawca_uslug (JSON: id, logo, nazwa)",
         "year": 2025,
         "rows_ingested": total,
         "url": "https://uslugirozwojowe.parp.gov.pl/",
         "local_file": str(PARQ.relative_to(ROOT))},
    ])

    OUT_XLSX.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as w:
        agg.to_excel(w, sheet_name="Distribution (4 buckets)", index=False)
        detail.to_excel(w, sheet_name="Detailed categories", index=False)
        prov_list.head(500).to_excel(w, sheet_name="Top 500 providers", index=False)
        prov_list.to_excel(w, sheet_name="All providers", index=False)
        methodology.to_excel(w, sheet_name="Methodology", index=False)
        sources.to_excel(w, sheet_name="Sources", index=False)

    BLUE, LGREY = "1d6fa8", "EEF2F8"

    def style(ws):
        HDR = PatternFill("solid", fgColor=BLUE)
        ALT = PatternFill("solid", fgColor=LGREY)
        HF = Font(name="Calibri", bold=True, color="FFFFFF", size=10)
        BF = Font(name="Calibri", size=10)
        for cell in ws[1]:
            cell.fill = HDR
            cell.font = HF
            cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="left")
        for ri, row in enumerate(ws.iter_rows(min_row=2), 2):
            for cell in row:
                if ri % 2 == 0:
                    cell.fill = ALT
                cell.font = BF
                cell.alignment = Alignment(wrap_text=True, vertical="top", horizontal="left")
                if isinstance(cell.value, float):
                    cell.number_format = "0.00"
                elif isinstance(cell.value, int):
                    cell.number_format = "#,##0"
        for ci in range(1, ws.max_column + 1):
            cl = get_column_letter(ci)
            mxl = max((len(str(c.value or "")) for c in ws[cl] if c.value), default=8)
            ws.column_dimensions[cl].width = min(max(mxl + 2, 12), 100)
        ws.row_dimensions[1].height = 30
        ws.freeze_panes = "A2"

    wb = load_workbook(OUT_XLSX)
    for s in wb.sheetnames:
        style(wb[s])
    wb.save(OUT_XLSX)
    print(f"✓ Wrote {OUT_XLSX}")

    # ── Chart ──
    NAVY = "#15314B"
    COLOURS = {"Private companies": "#1d6fa8", "NGOs": "#e88c30",
               "Public educational institutions": "#5b8c5a",
               "Public finance sector entities": "#9b3a3a"}
    order = ["Private companies", "Public educational institutions",
             "NGOs", "Public finance sector entities"]
    agg_ord = agg.set_index("bucket").loc[order]

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5))

    ax = axes[0]
    bars = ax.barh(agg_ord.index, agg_ord["trainings"], color=[COLOURS[b] for b in agg_ord.index])
    for bar, v, p in zip(bars, agg_ord["trainings"], agg_ord["share_trainings_pct"]):
        ax.text(v + 1500, bar.get_y() + bar.get_height() / 2, f"{int(v):,}  ({p:.1f}%)",
                va="center", fontsize=10, color=NAVY)
    ax.set_title("Distribution of TRAININGS\nby provider category", fontsize=12, color=NAVY,
                 fontweight="bold", pad=10)
    ax.set_xlabel("Number of trainings (BUR 2025)", color=NAVY, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, agg_ord["trainings"].max() * 1.32)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(colors=NAVY)

    ax = axes[1]
    bars = ax.barh(agg_ord.index, agg_ord["unique_providers"], color=[COLOURS[b] for b in agg_ord.index])
    for bar, v, p in zip(bars, agg_ord["unique_providers"], agg_ord["share_providers_pct"]):
        ax.text(v + 30, bar.get_y() + bar.get_height() / 2, f"{int(v):,}  ({p:.1f}%)",
                va="center", fontsize=10, color=NAVY)
    ax.set_title("Distribution of UNIQUE PROVIDERS\nby provider category", fontsize=12, color=NAVY,
                 fontweight="bold", pad=10)
    ax.set_xlabel("Number of providers (BUR 2025)", color=NAVY, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, agg_ord["unique_providers"].max() * 1.32)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(colors=NAVY)
    ax.set_yticklabels([])

    fig.suptitle("BUR 2025 — providers (dostawca_uslug) classified by keywords",
                 fontsize=13.5, color=NAVY, fontweight="bold", y=1.02)
    fig.text(0.5, -0.02,
             "Source: BUR (PARP) — bur_2025.parquet · keyword classifier "
             "(FUNDACJA/STOWARZYSZENIE → NGO; UNIWERSYTET/POLITECHNIKA/CKZ → public education; "
             "URZĄD/MINISTERSTWO/SP ZOZ → public finance; SP. Z O.O./S.A./SP.K. → private company)",
             ha="center", fontsize=8, color=NAVY, style="italic")
    plt.tight_layout()
    plt.savefig(OUT_PNG, dpi=200, bbox_inches="tight")
    print(f"✓ Wrote {OUT_PNG}")

    print("\n=== FINAL: 4-bucket distribution (BUR 2025, n={:,} trainings, {:,} providers) ===".format(total, total_p))
    for _, row in agg.iterrows():
        print(f"  {row['bucket']:<35} trainings: {row['trainings']:>7,} ({row['share_trainings_pct']:>5.1f}%)   |"
              f"  providers: {row['unique_providers']:>5,} ({row['share_providers_pct']:.1f}%)")


if __name__ == "__main__":
    main()

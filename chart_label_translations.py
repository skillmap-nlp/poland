"""Shared display labels for Plotly charts in the Quarto report."""
from __future__ import annotations

import json
import sqlite3
import unicodedata
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent

VOIVODESHIP_EN: dict[str, str] = {
    "dolnośląskie": "Dolnośląskie",
    "kujawsko-pomorskie": "Kujawsko-pomorskie",
    "lubelskie": "Lubelskie",
    "lubuskie": "Lubuskie",
    "łódzkie": "Łódzkie",
    "małopolskie": "Małopolskie",
    "mazowieckie": "Mazowieckie",
    "mazowieckie regionalny": "Mazowieckie (regional BUR)",
    "opolskie": "Opolskie",
    "podkarpackie": "Podkarpackie",
    "podlaskie": "Podlaskie",
    "pomorskie": "Pomorskie",
    "śląskie": "Śląskie",
    "świętokrzyskie": "Świętokrzyskie",
    "warmińsko-mazurskie": "Warmińsko-mazurskie",
    "wielkopolskie": "Wielkopolskie",
    "zachodniopomorskie": "Zachodniopomorskie",
    "brak": "Brak danych",
}

# BUR region field uses title-case Polish names.
REGION_DISPLAY_EN: dict[str, str] = {
    "Brak": "Brak danych",
    "Dolnośląskie": "Dolnośląskie",
    "Kujawsko-pomorskie": "Kujawsko-pomorskie",
    "Lubelskie": "Lubelskie",
    "Lubuskie": "Lubuskie",
    "Łódzkie": "Łódzkie",
    "Małopolskie": "Małopolskie",
    "Mazowieckie": "Mazowieckie",
    "Mazowieckie regionalny": "Mazowieckie (regional BUR)",
    "Opolskie": "Opolskie",
    "Podkarpackie": "Podkarpackie",
    "Podlaskie": "Podlaskie",
    "Pomorskie": "Pomorskie",
    "Śląskie": "Śląskie",
    "Świętokrzyskie": "Świętokrzyskie",
    "Warmińsko-mazurskie": "Warmińsko-mazurskie",
    "Wielkopolskie": "Wielkopolskie",
    "Zachodniopomorskie": "Zachodniopomorskie",
}

BUR_CATEGORY_EN: dict[str, str] = {
    "Biznes": "Business",
    "Zdrowie i medycyna": "Health and medicine",
    "Informatyka i telekomunikacja": "IT and telecommunications",
    "Prawo jazdy": "Driving licences",
    "Techniczne": "Technical",
    "Języki": "Languages",
    "Finanse i bankowość": "Finance and banking",
    "Prawo i administracja": "Law and administration",
    "Inne": "Other",
    "Styl życia": "Lifestyle",
    "Transport i motoryzacja": "Transport and automotive",
    "Ekologia i rolnictwo": "Ecology and agriculture",
}

BUR_MODALITY_EN: dict[str, str] = {
    "stacjonarna": "In-person only",
    "zdalna": "Online only",
    "zdalna w czasie rzeczywistym": "Live online",
    "mieszana (stacjonarna połączona z usługą zdalną w czasie rzeczywistym)": "Hybrid (in-person + live online)",
    "mieszana (stacjonarna połączona z usługą zdalną)": "Hybrid (in-person + online)",
    "mieszana (zdalna połączona z usługą zdalną w czasie rzeczywistym)": "Hybrid (online + live online)",
}

SENIORITY_EN: dict[str, str] = {
    "specjalista (Mid / Regular)": "Specialist (mid / regular)",
    "młodszy specjalista (Junior)": "Junior specialist",
    "starszy specjalista (Senior)": "Senior specialist",
    "ekspert": "Expert",
    "menedżer": "Manager",
    "manager / supervisor": "Manager / supervisor",
    "kierownik / koordynator": "Team manager / coordinator",
    "dyrektor": "Director",
    "pracownik fizyczny": "Manual worker",
    "praktykant / stażysta": "Trainee / intern",
    "asystent": "Assistant",
}

CONTRACT_TYPE_EN: dict[str, str] = {
    "umowa o pracę": "Employment contract",
    "umowa o pracę tymczasową": "Temporary employment contract",
    "kontrakt B2B": "B2B contract",
    "umowa zlecenie": "Contract of mandate",
    "umowa o dzieło": "Contract for specific work",
    "umowa o staż / praktyki": "Internship / apprenticeship contract",
    "umowa na zastępstwo": "Replacement contract",
    "umowa agencyjna": "Agency agreement",
}

JOB_CATEGORY_EN: dict[str, str] = {
    "Administrowanie bazami danych i storage": "Database and storage administration",
    "Administrowanie systemami": "Systems administration",
    "Artykuły spożywcze": "Food products",
    "Badania i rozwój": "Research and development",
    "Finanse / Ekonomia": "Finance / economics",
    "Franczyza / Własny biznes": "Franchise / own business",
    "Fryzjer / Kosmetyczka": "Hairdresser / beautician",
    "Hotelarstwo / Gastronomia / Turystyka": "Hospitality / catering / tourism",
    "Human Resources / Zasoby ludzkie": "Human resources",
    "IT - Administracja": "IT — administration",
    "IT - Rozwój oprogramowania": "IT — software development",
    "Katering / Restauracje / Gastronomia": "Catering / restaurants",
    "Kurierzy / Dostawcy": "Couriers / delivery",
    "Monterzy / Serwisanci / Elektrycy": "Installers / service technicians / electricians",
    "Obsługa hotelowa": "Hotel operations",
    "Obsługa klienta": "Customer service",
    "Praca fizyczna": "Manual labour",
    "Pracownicy budowlani": "Construction workers",
    "Pracownicy gastronomii": "Hospitality staff",
    "Pracownicy magazynowi": "Warehouse workers",
    "Pracownicy produkcji": "Production workers",
    "Sieci handlowe": "Retail chains",
    "Transport / Spedycja / Logistyka": "Transport / forwarding / logistics",
    "Transport i zarządzanie flotą": "Transport and fleet management",
    "Utrzymanie czystości": "Cleaning and hygiene",
    "Łańcuch dostaw": "Supply chain",
    **SENIORITY_EN,
    **CONTRACT_TYPE_EN,
}

NACE_TITLE_EN: dict[str, str] = {
    "C14": "Manufacture of wearing apparel",
    "C22.11": "Manufacture, retreading and rebuilding of rubber tyres and tubes",
    "C25.93": "Manufacture of wire products, chains and springs",
    "D35.14": "Distribution of electricity",
    "F43.91": "Masonry works",
    "G": "Wholesale and retail trade",
    "G47": "Retail trade",
    "G47.1": "Non-specialised retail trade",
    "G47.11": "Non-specialised retail sale with food, beverages or tobacco predominating",
    "G47.2": "Retail sale of food, beverages and tobacco",
    "G47.22": "Retail sale of meat and meat products",
    "G47.5": "Retail sale of other household goods",
    "G47.63": "Retail sale of sporting equipment",
    "G47.71": "Retail sale of clothing",
    "G47.9": "Retail sale via intermediaries",
    "H49.32": "Other non-scheduled passenger road transport",
    "H49.33": "Passenger transport on demand with driver",
    "H49.41": "Freight transport by road",
    "H52.1": "Warehousing and storage",
    "H53": "Postal and courier activities",
    "I56.1": "Restaurants and mobile food service activities",
    "I56.11": "Restaurants",
    "I56.2": "Event catering and other food service activities",
    "I56.3": "Beverage serving activities",
    "K62.1": "Computer programming activities",
    "K62.2": "Computer consultancy and computer facilities management",
    "N69.2": "Accounting, bookkeeping and tax consultancy",
    "N70.1": "Head-office activities",
    "N70.2": "Management consultancy activities",
    "N71.12": "Engineering activities and related technical consultancy",
    "T95.31": "Repair and maintenance of motor vehicles, excluding motorcycles",
}

KZIS_OCCUPATION_EN: dict[str, str] = {
    "Inżynier inżynierii środowiska – instalacje sanitarne": "Environmental engineering engineer - sanitary installations",
    "Specjalista ochrony środowiska": "Environmental protection specialist",
    "Inżynier sprzedaży": "Sales engineer",
    "Specjalista bezpieczeństwa i higieny pracy": "Occupational health and safety specialist",
    "Regionalny kierownik sprzedaży": "Regional sales manager",
    "Inżynier chłodnictwa i klimatyzacji": "Refrigeration and air-conditioning engineer",
    "Konserwator budynków i stanu technicznego pomieszczeń": "Building and premises maintenance technician",
    "Specjalista do spraw społecznej odpowiedzialności przedsiębiorstw": "Corporate social responsibility specialist",
    "Specjalista do spraw kluczowych klientów (key account manager)": "Key account manager",
    "Inżynier budowy dróg": "Road construction engineer",
    "Inżynier utrzymania ruchu": "Maintenance engineer",
    "Fizjoterapeuta": "Physiotherapist",
    "Specjalista fizjoterapii": "Physiotherapy specialist",
    "Pielęgniarka": "Nurse",
    "Asystentka stomatologiczna": "Dental assistant",
    "Psychoterapeuta": "Psychotherapist",
    "Lekarz dentysta": "Dentist",
    "Opiekun osoby starszej": "Elderly-care worker",
    "Nauczyciel przedszkola": "Preschool teacher",
    "Lekarz dentysta – specjalista ortodoncji": "Orthodontist",
    "Pielęgniarka oddziałowa": "Ward nurse",
    "Opiekun medyczny": "Medical care assistant",
    "Lekarz dentysta – specjalista protetyki stomatologicznej": "Prosthodontist",
    "Psycholog": "Psychologist",
    "Logopeda": "Speech therapist",
    "Technik masażysta": "Massage technician",
    "Lekarz dentysta – specjalista periodontologii": "Periodontist",
    "Psycholog wychowawczy": "Educational psychologist",
    "Lekarz dentysta – specjalista stomatologii zachowawczej z endodoncją": "Restorative dentist (with endodontics)",
    "Lekarz – specjalista okulistyki": "Ophthalmologist",
    "Lekarz – specjalista medycyny rodzinnej": "Family physician",
    "Lekarz – specjalista radiologii i diagnostyki obrazowej": "Radiologist",
    "Lekarz dentysta – specjalista stomatologii dziecięcej": "Paediatric dentist",
    "Lekarz – specjalista otorynolaryngologii": "ENT specialist",
    "Lekarz – specjalista dermatologii i wenerologii": "Dermatologist",
    "Lekarz – specjalista gastroenterologii": "Gastroenterologist",
    "Specjalista w dziedzinie psychologii klinicznej": "Clinical psychologist",
    "Lekarz – specjalista endokrynologii": "Endocrinologist",
    "Lekarz – specjalista położnictwa i ginekologii": "Obstetrician / gynaecologist",
    "Lekarz dentysta – specjalista chirurgii stomatologicznej": "Oral surgeon",
    "Lekarz – specjalista psychiatrii": "Psychiatrist",
}


def voivodeship_en(slug: str) -> str:
    key = (slug or "").strip().lower()
    return VOIVODESHIP_EN.get(key, slug.replace("-", " ").title() if slug else slug)


def region_display_en(name: str) -> str:
    key = (name or "").strip()
    if not key:
        return "Brak danych"
    if key in REGION_DISPLAY_EN:
        return REGION_DISPLAY_EN[key]
    low = key.lower()
    if low in VOIVODESHIP_EN:
        return VOIVODESHIP_EN[low]
    return key


def bur_category_en(name: str) -> str:
    return BUR_CATEGORY_EN.get(name, name)


def bur_modality_en(name: str) -> str:
    return BUR_MODALITY_EN.get(name, name)


def seniority_en(name: str) -> str:
    return SENIORITY_EN.get(name, name)


def contract_type_en(name: str) -> str:
    return CONTRACT_TYPE_EN.get(name, name)


def job_category_en(name: str) -> str:
    return JOB_CATEGORY_EN.get(name, name)


def nace_title_en(code: str, title: str | None = None) -> str:
    return NACE_TITLE_EN.get(code, title or code)


def kzis_occupation_en(name: str) -> str:
    return KZIS_OCCUPATION_EN.get(name, name)


MANUAL_SKILL_EN: dict[str, str] = {
    "stosować podstawowe umiejętności programistyczne": "apply basic programming skills",
    "posługiwać się językami zapytań": "use query languages",
    "programowanie systemowe w zakresie ict": "ICT systems programming",
    "techniki sprzedaży w sektorze ict": "ICT sales techniques",
    "edukacja technologiczna": "technology education",
    "spełniać wymogi ustanowione przez organy zajmujące się refundacją świadczeń z za": "comply with medical-supply reimbursement requirements",
}


def _norm_pl_skill(text: str) -> str:
    return unicodedata.normalize("NFKD", text.strip().lower())


@lru_cache(maxsize=1)
def _skill_pl_to_en() -> dict[str, str]:
    mapping: dict[str, str] = {}

    esco_db = ROOT / "comprehensive_esco.db"
    if esco_db.exists():
        con = sqlite3.connect(esco_db)
        uri_en = dict(con.execute("SELECT uri, title FROM esco_concepts"))
        con.close()
        dict_path = ROOT / "app_deploy" / "esco_dictionary.json"
        if dict_path.exists():
            with dict_path.open(encoding="utf-8") as f:
                for pl, meta in json.load(f).items():
                    uri = meta.get("uri")
                    if uri and uri in uri_en:
                        mapping[_norm_pl_skill(pl)] = uri_en[uri]

    chinen = ROOT / "presentation" / "chinen_digital_skill_mapping.csv"
    if chinen.exists():
        import pandas as pd

        df = pd.read_csv(chinen)
        for row in df.itertuples(index=False):
            en = row.esco_skill_label_en or row.esco_title_en
            if not isinstance(en, str) or not en.strip():
                continue
            for pl in str(row.pl_labels or "").split("|"):
                pl = pl.strip()
                if pl:
                    mapping[_norm_pl_skill(pl)] = en.strip()

    for pl, en in MANUAL_SKILL_EN.items():
        mapping[_norm_pl_skill(pl)] = en

    return mapping


def skill_label_en(label: str) -> str:
    if not label:
        return label
    hit = _skill_pl_to_en().get(_norm_pl_skill(label))
    if hit:
        return hit
    # Title-case Latin tokens (e.g. Devops, SAP R3) — leave as-is if no PL diacritics.
    if not any(c in label for c in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"):
        return label
    return label

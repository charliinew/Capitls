"""
Parseurs des sources de référence — fonctions pures, sans appel réseau.

Entrée : HTML brut (service-public.fr, justETF) → sortie : valeurs normalisées.
Les taux sont renvoyés en fraction décimale (1,7 % → 0.017), les montants en euros.
Une valeur introuvable renvoie None : l'appelant conserve alors la dernière valeur connue.
"""

from __future__ import annotations

import html as html_lib
import re

SERVICE_PUBLIC_BASE = "https://www.service-public.gouv.fr/particuliers/vosdroits/"
JUSTETF_BASE = "https://www.justetf.com/fr/etf-profile.html?isin="

_NUM = r"(\d{1,3}(?:[   ]\d{3})*(?:,\d+)?|\d+(?:,\d+)?)"

# Faits extraits de service-public.fr : clé → (page, regex avec 1 groupe numérique, type)
# type "rate" : pourcentage → fraction ; "amount" : euros ; "int" : entier
SERVICE_PUBLIC_FACTS: dict[str, tuple[str, str, str]] = {
    "livret_a.taux": ("F2365", r"taux d'intérêt annuel du livret A est de " + _NUM + r" ?%", "rate"),
    "livret_a.plafond": ("F2365", r"inscrit sur le livret A est de " + _NUM + r" ?€", "amount"),
    "ldds.taux": (
        "F2368",
        r"taux de rémunération du LDDS \?[^.]{0,20}?taux d'intérêt annuel est de " + _NUM + r" ?%",
        "rate",
    ),
    "ldds.plafond": ("F2368", r"plafond du LDDS est de " + _NUM + r" ?€", "amount"),
    "lep.taux": ("F2367", r"taux d'intérêt du LEP est de " + _NUM + r" ?%", "rate"),
    "lep.plafond": ("F2367", r"plafond des versements sur le LEP est fixé à " + _NUM + r" ?€", "amount"),
    "lep.rfr_1_part": ("F2367", r"Plafond de RFR 1 " + _NUM + r" ?€", "amount"),
    "livret_jeune.plafond": (
        "F2904",
        r"plafond des versements sur le livret jeune est fixé à " + _NUM + r" ?€",
        "amount",
    ),
    "livret_jeune.age_min": ("F2904", r"(?:avoir|entre) " + _NUM + r" (?:ans )?et 25 ans", "int"),
    "livret_jeune.age_max": ("F2904", r"(?:avoir|entre) \d+ (?:ans )?et " + _NUM + r" ans", "int"),
    "pea.plafond": ("F2385", r"plafond des versements sur le PEA bancaire est de " + _NUM + r" ?€", "amount"),
    "pea_pme.plafond": ("F2385", r"plafond du PEA PME-ETI est de " + _NUM + r" ?€", "amount"),
    "pea_jeune.plafond": ("F2385", r"limité à " + _NUM + r" ?€ tant que dure le rattachement", "amount"),
    "fiscalite.pfu_total": ("F21618", r"prélèvement forfaitaire unique au taux de " + _NUM + r" ?%", "rate"),
    "fiscalite.ir_forfaitaire": (
        "F21618",
        r"prélèvement forfaitaire unique au taux de [\d,]+ ?% \( ?" + _NUM + r" ?% d'impôt sur le revenu",
        "rate",
    ),
    "fiscalite.ps_placements": ("F21618", r"% d'impôt sur le revenu et " + _NUM + r" ?%", "rate"),
    "fiscalite.ps_assurance_vie": ("F22414", r"prélèvements sociaux \(CSG, CRDS\) au taux de " + _NUM + r" ?%", "rate"),
    "assurance_vie.ir_apres_8_ans": (
        "F22414",
        r"imposés au taux de " + _NUM + r" ?% s'ils résultent de primes",
        "rate",
    ),
}


def service_public_url(page: str) -> str:
    return SERVICE_PUBLIC_BASE + page


def justetf_url(isin: str) -> str:
    return JUSTETF_BASE + isin


def html_to_text(raw_html: str) -> str:
    """HTML → texte brut sur une ligne (scripts/styles retirés, entités décodées)."""
    without_scripts = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", raw_html, flags=re.S | re.I)
    text = html_lib.unescape(re.sub(r"<[^>]+>", " ", without_scripts))
    text = text.replace(" ", " ").replace(" ", " ").replace("’", "'")
    return re.sub(r"\s+", " ", text).strip()


def parse_french_number(raw: str) -> float:
    """'22 950' → 22950.0 ; '1,7' → 1.7 ; '2,50' → 2.5"""
    cleaned = re.sub(r"[   ]", "", raw).replace(",", ".")
    return float(cleaned)


def _convert(raw: str, kind: str) -> float | int:
    value = parse_french_number(raw)
    if kind == "rate":
        return round(value / 100, 6)
    if kind == "int":
        return int(value)
    return value


def extract_fact(text: str, pattern: str, kind: str) -> float | int | None:
    """Première occurrence du motif dans le texte, convertie selon le type. None si absent."""
    match = re.search(pattern, text, flags=re.I)
    if not match:
        return None
    try:
        return _convert(match.group(1), kind)
    except (ValueError, IndexError):
        return None


def parse_service_public_page(page: str, raw_html: str) -> dict[str, float | int | None]:
    """Extrait tous les faits connus pour une page service-public (ex: 'F2365')."""
    text = html_to_text(raw_html)
    return {
        key: extract_fact(text, pattern, kind)
        for key, (fact_page, pattern, kind) in SERVICE_PUBLIC_FACTS.items()
        if fact_page == page
    }


def service_public_pages() -> list[str]:
    """Liste des pages service-public à récupérer."""
    return sorted({page for page, _, _ in SERVICE_PUBLIC_FACTS.values()})


def parse_justetf_profile(raw_html: str) -> dict:
    """
    Extrait d'une fiche ETF justETF : nom, TER, encours (M€), éligibilité PEA.
    pea_eligible = True si la fiche porte la mention « Éligible au PEA », sinon None
    (absence de mention ≠ preuve d'inéligibilité).
    """
    ter_match = re.search(r"ter-value[^>]*>\s*" + _NUM + r"\s*%", raw_html)
    name_match = re.search(r"<h1[^>]*>(.*?)</h1>", raw_html, flags=re.S)
    text = html_to_text(raw_html)
    size_match = re.search(r"Taille du fonds EUR " + _NUM + r" ?(M|Md)", text)

    fund_size_meur = None
    if size_match:
        fund_size_meur = parse_french_number(size_match.group(1))
        if size_match.group(2) == "Md":
            fund_size_meur *= 1000

    return {
        "name": html_to_text(name_match.group(1)) if name_match else None,
        "ter": _convert(ter_match.group(1), "rate") if ter_match else None,
        "fund_size_meur": fund_size_meur,
        "pea_eligible": True if "Éligible au PEA" in raw_html else None,
    }

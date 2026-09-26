"""
Adapter données de référence → HTML brut.
Sources : service-public.fr (tier_1, taux/plafonds/fiscalité), justETF (tier_1, TER/encours ETF).

Seul fichier qui fait des requêtes HTTP vers ces sources ; le parsing est dans
skills/reference_parsers.py (pur, testable). Si une page change de structure,
les parseurs renvoient None et la dernière valeur connue sert de repli.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import requests

from skills.reference_parsers import (
    justetf_url,
    parse_justetf_profile,
    parse_service_public_page,
    service_public_pages,
    service_public_url,
)

logger = logging.getLogger(__name__)

_HEADERS: dict[str, str | bytes] = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}
_TIMEOUT = 15


class ReferenceAdapter:
    def _get(self, url: str) -> str | None:
        try:
            response = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logger.warning("Échec fetch %s: %s", url, e)
            return None

    def fetch_regulatory_facts(self) -> tuple[dict[str, float | int | None], dict[str, str], list[str]]:
        """
        Récupère et parse toutes les pages service-public.
        Retourne (valeurs par clé, source par clé, erreurs).
        """
        pages = service_public_pages()
        with ThreadPoolExecutor(max_workers=6) as pool:
            htmls = dict(zip(pages, pool.map(lambda p: self._get(service_public_url(p)), pages)))

        values: dict[str, float | int | None] = {}
        sources: dict[str, str] = {}
        errors: list[str] = []
        for page, raw in htmls.items():
            if raw is None:
                errors.append(f"service-public {page} inaccessible")
                continue
            for key, value in parse_service_public_page(page, raw).items():
                values[key] = value
                sources[key] = service_public_url(page)
                if value is None:
                    errors.append(f"{key} introuvable sur {page} (structure de page modifiée ?)")
        return values, sources, errors

    def fetch_etf_profiles(self, isins: list[str]) -> tuple[dict[str, dict], list[str]]:
        """Fiches justETF par ISIN → {isin: {name, ter, fund_size_meur, pea_eligible}}."""
        with ThreadPoolExecutor(max_workers=4) as pool:
            htmls = dict(zip(isins, pool.map(lambda i: self._get(justetf_url(i)), isins)))

        profiles: dict[str, dict] = {}
        errors: list[str] = []
        for isin, raw in htmls.items():
            if raw is None:
                errors.append(f"justETF {isin} inaccessible")
                continue
            profile = parse_justetf_profile(raw)
            if profile["ter"] is None:
                errors.append(f"TER introuvable pour {isin} sur justETF")
            profiles[isin] = profile
        return profiles, errors

    def fetch_etf_profile(self, isin: str) -> dict | None:
        raw = self._get(justetf_url(isin))
        return parse_justetf_profile(raw) if raw else None

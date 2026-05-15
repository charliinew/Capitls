"""
Tool MCP : règles réglementaires françaises.
Source : AMF, Service-public.fr, Banque de France (tier_1 — données statiques 2026).
Ces données sont mises à jour manuellement — vérifier régulièrement.
"""

from __future__ import annotations

PEA_RULES_2026 = {
    "plafond_versements_classique": 150_000,
    "plafond_versements_pea_pme": 225_000,
    "plafond_pea_jeune": 20_000,
    "fiscalite_avant_5_ans": {
        "ir": 0.128,
        "ps": 0.186,
        "total": 0.314,
        "note": "Tout retrait avant 5 ans = clôture automatique du PEA",
    },
    "fiscalite_apres_5_ans": {
        "ir": 0.0,
        "ps": 0.186,
        "total": 0.186,
        "note": "Exonération IR totale — seulement les PS s'appliquent",
    },
    "retraits_partiels_apres_5_ans": True,
    "source": "Service-public.fr + AMF (tier_1)",
    "last_verified": "2026-05",
}

LIVRET_JEUNE_2026 = {
    "taux_minimum": 0.015,
    "taux_maximum_estime": 0.035,
    "plafond": 1_600,
    "age_minimum": 12,
    "age_maximum": 25,
    "fiscalite": "exonéré IR et PS",
    "note": "Fermeture automatique au 31 décembre de l'année des 25 ans",
    "source": "Banque de France + Service-public.fr (tier_1)",
    "last_verified": "2026-05",
}

FLAT_TAX_2026 = {
    "pfu": 0.128,
    "ps": 0.186,
    "total": 0.314,
    "note": "Prélèvement Forfaitaire Unique — s'applique aux CTO, PER, assurance-vie avant 8 ans",
    "source": "AMF (tier_1)",
}


def get_pea_rules() -> dict:
    """Règles complètes du PEA en vigueur (2026)."""
    return {
        "rules": PEA_RULES_2026,
        "source": "AMF + Service-public.fr (tier_1)",
        "label": "[FACTUEL]",
        "warning": "Vérifier sur amf-france.org pour toute modification réglementaire récente",
    }


def get_livret_jeune_rules() -> dict:
    """Règles du Livret Jeune en vigueur (2026)."""
    return {
        "rules": LIVRET_JEUNE_2026,
        "source": "Banque de France (tier_1)",
        "label": "[FACTUEL]",
    }


def get_tax_comparison(gross_gains: float) -> dict:
    """
    Comparaison fiscale : PEA avant 5 ans vs après 5 ans vs flat tax CTO.
    """
    return {
        "gross_gains": gross_gains,
        "pea_before_5y": {
            "tax": round(gross_gains * PEA_RULES_2026["fiscalite_avant_5_ans"]["total"], 2),
            "rate": f"{PEA_RULES_2026['fiscalite_avant_5_ans']['total']*100:.1f}%",
            "net_gains": round(gross_gains * (1 - PEA_RULES_2026["fiscalite_avant_5_ans"]["total"]), 2),
        },
        "pea_after_5y": {
            "tax": round(gross_gains * PEA_RULES_2026["fiscalite_apres_5_ans"]["total"], 2),
            "rate": f"{PEA_RULES_2026['fiscalite_apres_5_ans']['total']*100:.1f}%",
            "net_gains": round(gross_gains * (1 - PEA_RULES_2026["fiscalite_apres_5_ans"]["total"]), 2),
        },
        "cto_flat_tax": {
            "tax": round(gross_gains * FLAT_TAX_2026["total"], 2),
            "rate": f"{FLAT_TAX_2026['total']*100:.1f}%",
            "net_gains": round(gross_gains * (1 - FLAT_TAX_2026["total"]), 2),
        },
        "source": "AMF (tier_1)",
        "label": "[FACTUEL]",
    }


def check_pea_eligibility(isin: str) -> dict:
    """
    Vérifie si un ISIN est éligible PEA (base statique 2026).
    Pour vérification complète, consulter justETF ou l'émetteur.
    """
    eligible_isins = {
        "FR001400U5Q4": {"name": "DCAM", "note": "Éligible PEA — réplication synthétique"},
        "IE0002XZSHO1": {"name": "WPEA", "note": "Éligible PEA — réplication synthétique"},
        "LU1681043599": {"name": "CW8", "note": "Éligible PEA — réplication synthétique"},
        "FR0011869353": {"name": "EWLD", "note": "Éligible PEA — réplication synthétique"},
    }

    if isin in eligible_isins:
        return {
            "isin": isin,
            "eligible_pea": True,
            **eligible_isins[isin],
            "source": "Base interne (à vérifier sur justETF)",
            "label": "[FACTUEL partiel]",
        }

    return {
        "isin": isin,
        "eligible_pea": None,
        "note": "ISIN inconnu — vérifier sur justETF.com ou auprès de l'émetteur",
        "label": "[VÉRIFICATION REQUISE]",
    }

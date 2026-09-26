"""
Tool MCP : règles réglementaires et fiscales françaises.
Toutes les valeurs viennent des données de référence (service-public.fr / justETF, tier_1),
rafraîchies automatiquement toutes les 24h — aucune valeur en dur ici.
"""

from __future__ import annotations

from mcp_server.tools import reference_tool
from skills.reference_data import format_value, stale_facts


def _facts(reference: dict, keys: list[str]) -> dict:
    facts = reference.get("facts", {})
    return {
        key: {
            "label": facts[key].get("label"),
            "value": facts[key].get("value"),
            "display": format_value(facts[key].get("value"), facts[key].get("unit")),
            "verified_at": facts[key].get("verified_at"),
            "source": facts[key].get("source"),
        }
        for key in keys
        if key in facts
    }


def _freshness_warning(reference: dict, keys: list[str]) -> list[dict]:
    subset = {k: v for k, v in reference.get("facts", {}).items() if k in keys}
    return stale_facts(subset, reference_tool._now().date())


def get_pea_rules() -> dict:
    """Règles PEA : plafonds, fiscalité avant/après la durée d'exonération, retraits."""
    reference = reference_tool.get_reference()
    get = lambda k: reference_tool.get_fact(reference, k)  # noqa: E731
    ir, ps, years = (
        get("fiscalite.ir_forfaitaire"),
        get("fiscalite.ps_placements"),
        int(get("pea.duree_exoneration_ans")),
    )
    keys = [
        "pea.plafond",
        "pea_pme.plafond",
        "pea_jeune.plafond",
        "pea.duree_exoneration_ans",
        "fiscalite.ir_forfaitaire",
        "fiscalite.ps_placements",
    ]
    return {
        "facts": _facts(reference, keys),
        "fiscalite_avant_exoneration": {
            "ir": ir,
            "ps": ps,
            "total": round(ir + ps, 4),
            "note": f"Retrait avant {years} ans = clôture du plan (sauf exceptions légales)",
        },
        "fiscalite_apres_exoneration": {
            "ir": 0.0,
            "ps": ps,
            "total": ps,
            "note": "Exonération d'IR — seuls les prélèvements sociaux s'appliquent ; retraits partiels possibles sans clôture",
        },
        "point_de_depart": "Date du premier versement (pas la date d'ouverture)",
        "stale_warnings": _freshness_warning(reference, keys),
        "source": "service-public.fr (tier_1) — rafraîchi automatiquement",
        "label": "[FACTUEL]",
    }


def get_savings_rates() -> dict:
    """Taux et plafonds de l'épargne réglementée (Livret A, LDDS, LEP, Livret Jeune)."""
    reference = reference_tool.get_reference()
    keys = [
        "livret_a.taux",
        "livret_a.plafond",
        "ldds.taux",
        "ldds.plafond",
        "lep.taux",
        "lep.plafond",
        "lep.rfr_1_part",
        "livret_jeune.plafond",
        "livret_jeune.age_min",
        "livret_jeune.age_max",
    ]
    return {
        "facts": _facts(reference, keys),
        "notes": [
            "Livrets réglementés : intérêts exonérés d'IR et de prélèvements sociaux.",
            "Livret Jeune : taux libre fixé par la banque, jamais inférieur au Livret A ; fermeture l'année des âge_max ans.",
            "LEP : sous condition de revenu fiscal de référence (plafond selon le nombre de parts).",
        ],
        "stale_warnings": _freshness_warning(reference, keys),
        "source": "service-public.fr (tier_1) — rafraîchi automatiquement",
        "label": "[FACTUEL]",
    }


def get_tax_comparison(gross_gains: float) -> dict:
    """Imposition d'un même gain : PEA (avant/après exonération), CTO, assurance-vie (avant/après 8 ans)."""
    reference = reference_tool.get_reference()
    get = lambda k: reference_tool.get_fact(reference, k)  # noqa: E731
    ir = get("fiscalite.ir_forfaitaire")
    ps = get("fiscalite.ps_placements")
    pfu = get("fiscalite.pfu_total")
    ps_av = get("fiscalite.ps_assurance_vie")
    ir_av_8 = get("assurance_vie.ir_apres_8_ans")
    pea_years = int(get("pea.duree_exoneration_ans"))
    av_years = int(get("assurance_vie.duree_avantage_ans"))

    def line(rate: float) -> dict:
        return {
            "rate": f"{rate * 100:.1f}%",
            "tax": round(gross_gains * rate, 2),
            "net_gains": round(gross_gains * (1 - rate), 2),
        }

    return {
        "gross_gains": gross_gains,
        f"pea_avant_{pea_years}_ans": line(ir + ps),
        f"pea_apres_{pea_years}_ans": line(ps),
        "cto_flat_tax": line(pfu),
        f"assurance_vie_avant_{av_years}_ans": line(ir + ps_av),
        f"assurance_vie_apres_{av_years}_ans": {
            **line(ir_av_8 + ps_av),
            "note": "Hors abattement annuel sur les gains (montant selon situation familiale, voir la source F22414)",
        },
        "stale_warnings": _freshness_warning(
            reference,
            [
                "fiscalite.ir_forfaitaire",
                "fiscalite.ps_placements",
                "fiscalite.pfu_total",
                "fiscalite.ps_assurance_vie",
                "assurance_vie.ir_apres_8_ans",
            ],
        ),
        "source": "service-public.fr (tier_1) — rafraîchi automatiquement",
        "label": "[FACTUEL]",
    }


def check_pea_eligibility(isin: str) -> dict:
    """Éligibilité PEA d'un ISIN : catalogue de référence, sinon fiche justETF en direct."""
    isin = isin.strip().upper()
    reference = reference_tool.get_reference()
    for ticker, etf in reference.get("etfs", {}).items():
        if etf.get("isin") == isin:
            return {
                "isin": isin,
                "ticker": ticker,
                "name": etf.get("name"),
                "eligible_pea": etf.get("pea_eligible"),
                "ter": etf.get("ter"),
                "verified_at": etf.get("verified_at"),
                "source": "justETF (tier_1) via données de référence",
                "label": "[FACTUEL]",
            }

    from adapters.reference_adapter import ReferenceAdapter

    profile = ReferenceAdapter().fetch_etf_profile(isin)
    if profile is None or profile.get("name") is None:
        return {
            "isin": isin,
            "eligible_pea": None,
            "note": "ISIN introuvable sur justETF — vérifier auprès de l'émetteur",
            "label": "[VÉRIFICATION REQUISE]",
        }
    return {
        "isin": isin,
        "name": profile["name"],
        "eligible_pea": profile["pea_eligible"],
        "ter": profile["ter"],
        "note": None
        if profile["pea_eligible"]
        else "Aucune mention « Éligible au PEA » sur justETF — probablement non éligible, à confirmer",
        "source": "justETF (tier_1) — consultation directe",
        "label": "[FACTUEL]" if profile["pea_eligible"] else "[VÉRIFICATION REQUISE]",
    }

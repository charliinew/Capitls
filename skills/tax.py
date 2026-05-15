"""
Calculs fiscaux France — fonctions pures.
Source: AMF + Service-public.fr (tier_1)
Mise à jour: 2026
"""

from __future__ import annotations


# Taux France 2026
FLAT_TAX_RATE = 0.128       # PFU (Prélèvement Forfaitaire Unique) 12.8%
SOCIAL_CHARGES_RATE = 0.186  # Prélèvements sociaux 17.2% → 18.6% depuis 2026
PEA_TAX_BEFORE_5Y = FLAT_TAX_RATE + SOCIAL_CHARGES_RATE  # 31.4%
PEA_TAX_AFTER_5Y = SOCIAL_CHARGES_RATE  # 18.6% seulement (IR exonéré)


def calculate_pea_tax_advantage(
    gross_gains: float,
    years_held: int,
) -> dict:
    """
    Compare l'imposition PEA vs flat tax 30% (compte-titres ordinaire).

    Retourne: { pea_tax, flat_tax, savings, effective_rate, eligible_for_exemption }
    """
    eligible = years_held >= 5

    if eligible:
        pea_tax = gross_gains * PEA_TAX_AFTER_5Y
        effective_rate = PEA_TAX_AFTER_5Y
    else:
        pea_tax = gross_gains * PEA_TAX_BEFORE_5Y
        effective_rate = PEA_TAX_BEFORE_5Y

    flat_tax = gross_gains * (FLAT_TAX_RATE + SOCIAL_CHARGES_RATE)
    savings = flat_tax - pea_tax

    return {
        "pea_tax": round(pea_tax, 2),
        "flat_tax": round(flat_tax, 2),
        "savings_vs_flat_tax": round(savings, 2),
        "effective_rate": round(effective_rate * 100, 1),
        "eligible_for_exemption": eligible,
        "years_held": years_held,
        "note": (
            "Exonération IR après 5 ans — PS 18.6% toujours dus"
            if eligible
            else f"Encore {5 - years_held} an(s) avant l'exonération IR"
        ),
    }


def calculate_real_return(
    nominal_return: float,
    inflation: float,
    annual_fees: float,
) -> float:
    """
    Rendement net réel après inflation et frais.
    Formule de Fisher: (1 + nominal) / ((1 + inflation) * (1 + fees)) - 1
    """
    real = (1 + nominal_return) / ((1 + inflation) * (1 + annual_fees)) - 1
    return round(real, 4)


def calculate_livret_jeune_vs_pea(
    amount: float,
    livret_rate: float,
    pea_annual_rate: float,
    years: int,
) -> dict:
    """
    Compare le Livret Jeune (exonéré) vs PEA après 5 ans (18.6% PS).
    Utile pour décider où allouer l'épargne disponible.
    """
    # Livret Jeune : intérêts exonérés, pas de PS
    livret_final = amount * ((1 + livret_rate) ** years)
    livret_net_gains = livret_final - amount

    # PEA après 5 ans : 18.6% PS sur les gains
    pea_gross_final = amount * ((1 + pea_annual_rate) ** years)
    pea_gross_gains = pea_gross_final - amount
    pea_tax = pea_gross_gains * PEA_TAX_AFTER_5Y
    pea_net_final = pea_gross_final - pea_tax

    return {
        "livret_jeune": {
            "final_value": round(livret_final, 2),
            "net_gains": round(livret_net_gains, 2),
            "tax": 0,
        },
        "pea_after_5y": {
            "final_value": round(pea_net_final, 2),
            "gross_gains": round(pea_gross_gains, 2),
            "tax_ps": round(pea_tax, 2),
            "net_gains": round(pea_net_final - amount, 2),
        },
        "verdict": "PEA" if pea_net_final > livret_final else "Livret Jeune",
        "difference": round(abs(pea_net_final - livret_final), 2),
        "years": years,
    }

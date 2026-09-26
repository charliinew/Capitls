"""
Calculs fiscaux France — fonctions pures.
Les taux (IR forfaitaire, prélèvements sociaux…) sont passés en paramètres depuis les
données de référence (service-public.fr, rafraîchies automatiquement) — aucun taux en dur.
"""

from __future__ import annotations


def calculate_pea_tax_advantage(
    gross_gains: float,
    years_held: float,
    ir_rate: float,
    ps_rate: float,
    exemption_years: int,
) -> dict:
    """
    Imposition des gains d'un PEA vs compte-titres (PFU = ir_rate + ps_rate).
    Avant `exemption_years` : IR + PS ; après : PS seuls.
    """
    eligible = years_held >= exemption_years
    pea_rate = ps_rate if eligible else ir_rate + ps_rate
    cto_rate = ir_rate + ps_rate
    pea_tax = gross_gains * pea_rate
    cto_tax = gross_gains * cto_rate

    return {
        "pea_tax": round(pea_tax, 2),
        "flat_tax": round(cto_tax, 2),
        "savings_vs_flat_tax": round(cto_tax - pea_tax, 2),
        "effective_rate": round(pea_rate * 100, 1),
        "flat_tax_rate": round(cto_rate * 100, 1),
        "eligible_for_exemption": eligible,
        "years_held": years_held,
        "note": (
            f"Exonération d'IR après {exemption_years} ans — prélèvements sociaux {ps_rate * 100:.1f} % toujours dus"
            if eligible
            else f"Encore {exemption_years - years_held:g} an(s) avant l'exonération d'IR"
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


def calculate_livret_vs_pea(
    amount: float,
    livret_rate: float,
    pea_annual_rate: float,
    years: int,
    ps_rate: float,
) -> dict:
    """
    Livret réglementé (exonéré IR+PS) vs PEA après la durée d'exonération (PS sur les gains).
    Utile pour décider où allouer l'épargne disponible.
    """
    livret_final = amount * ((1 + livret_rate) ** years)

    pea_gross_final = amount * ((1 + pea_annual_rate) ** years)
    pea_gross_gains = pea_gross_final - amount
    pea_tax = pea_gross_gains * ps_rate
    pea_net_final = pea_gross_final - pea_tax

    return {
        "livret": {
            "final_value": round(livret_final, 2),
            "net_gains": round(livret_final - amount, 2),
            "tax": 0,
        },
        "pea_after_exemption": {
            "final_value": round(pea_net_final, 2),
            "gross_gains": round(pea_gross_gains, 2),
            "tax_ps": round(pea_tax, 2),
            "net_gains": round(pea_net_final - amount, 2),
        },
        "verdict": "PEA" if pea_net_final > livret_final else "Livret",
        "difference": round(abs(pea_net_final - livret_final), 2),
        "years": years,
    }

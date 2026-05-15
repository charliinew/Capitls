"""
Projections multi-scénarios — fonctions pures.
Taux historiques MSCI World : pessimiste=4%, neutre=7%, optimiste=10%
"""

from __future__ import annotations

SCENARIOS = {
    "pessimiste": 0.04,
    "neutre": 0.07,
    "optimiste": 0.10,
}


def project_portfolio(
    current_value: float,
    monthly_contribution: float,
    annual_rate: float,
    years: int,
) -> dict:
    """Projection d'un portfolio avec contributions mensuelles régulières."""
    monthly_rate = annual_rate / 12
    value = current_value
    total_invested = current_value
    by_year = []

    for year in range(1, years + 1):
        for _ in range(12):
            value = value * (1 + monthly_rate) + monthly_contribution
            total_invested += monthly_contribution
        by_year.append({
            "year": year,
            "value": round(value, 2),
            "total_invested": round(total_invested, 2),
            "gains": round(value - total_invested, 2),
        })

    return {
        "final_value": round(value, 2),
        "total_invested": round(total_invested, 2),
        "total_gains": round(value - total_invested, 2),
        "by_year": by_year,
    }


def project_portfolio_multi_scenarios(
    current_value: float,
    monthly_contribution: float,
    years: int,
    scenarios: list[str] | None = None,
) -> dict:
    """
    Projections pour plusieurs scénarios de rendement.

    Retourne: { "pessimiste": {...}, "neutre": {...}, "optimiste": {...} }
    """
    if scenarios is None:
        scenarios = list(SCENARIOS.keys())

    results = {}
    for scenario in scenarios:
        if scenario not in SCENARIOS:
            continue
        rate = SCENARIOS[scenario]
        proj = project_portfolio(current_value, monthly_contribution, rate, years)
        proj["annual_rate"] = rate
        proj["scenario"] = scenario
        results[scenario] = proj

    return results


def project_pea_goal(
    target_value: float,
    current_value: float,
    monthly_contribution: float,
    annual_rate: float = SCENARIOS["neutre"],
    max_years: int = 40,
) -> dict:
    """
    Calcule en combien d'années un PEA atteint une valeur cible.
    Utile pour : "Quand aurai-je 50 000€ sur mon PEA ?"
    """
    monthly_rate = annual_rate / 12
    value = current_value
    months = 0

    while value < target_value and months < max_years * 12:
        value = value * (1 + monthly_rate) + monthly_contribution
        months += 1

    if months >= max_years * 12:
        return {
            "reached": False,
            "note": f"Cible {target_value}€ non atteinte en {max_years} ans",
            "value_at_max_years": round(value, 2),
        }

    years = months // 12
    remaining_months = months % 12

    return {
        "reached": True,
        "years": years,
        "months": remaining_months,
        "total_months": months,
        "final_value": round(value, 2),
        "annual_rate_used": annual_rate,
    }

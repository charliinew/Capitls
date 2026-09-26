"""
Capacité d'investissement et budget DCA — fonctions pures.
Adapté aux revenus irréguliers : la recommandation se base sur le mois le plus faible.
"""

from __future__ import annotations

SAFETY_BUFFER_PCT = 0.10  # part du revenu gardée en tampon (hypothèse de prudence)


def calculate_investment_capacity(
    monthly_income: float,
    fixed_expenses: float,
    safety_pct: float = SAFETY_BUFFER_PCT,
    free_order_max: float | None = None,
) -> dict:
    """
    Capacité d'investissement mensuelle.
    fixed_expenses : dépenses fixes mensuelles (loyer, nourriture, abonnements...)
    free_order_max : plafond d'un ordre gratuit chez le courtier (None si inconnu)
    Retourne: {investable_amount, safety_buffer, net_after_expenses, is_free_order, broker_note}
    """
    if monthly_income <= 0:
        return {
            "investable_amount": 0.0,
            "safety_buffer": 0.0,
            "net_after_expenses": 0.0,
            "is_free_order": None,
            "note": "Revenu mensuel non renseigné ou nul",
        }

    net_after_expenses = max(0.0, monthly_income - fixed_expenses)
    safety_buffer = round(monthly_income * safety_pct, 2)
    investable = round(max(0.0, net_after_expenses - safety_buffer), 2)

    result: dict[str, object] = {
        "monthly_income": round(monthly_income, 2),
        "fixed_expenses": round(fixed_expenses, 2),
        "safety_buffer": safety_buffer,
        "net_after_expenses": round(net_after_expenses, 2),
        "investable_amount": investable,
        "is_free_order": None,
    }
    if free_order_max is not None:
        result["is_free_order"] = investable <= free_order_max
        result["broker_note"] = (
            f"Ordre gratuit (≤ {free_order_max:.0f}€)"
            if investable <= free_order_max
            else f"⚠️ Dépasse {free_order_max:.0f}€ — ordre payant ou à réduire"
        )
    return result


def calculate_optimal_dca(
    income_history: list[dict],
    fixed_expenses: float,
    safety_pct: float = SAFETY_BUFFER_PCT,
    free_order_max: float | None = None,
) -> dict:
    """
    DCA recommandé à partir de l'historique des revenus (mois le plus faible = prudent).
    income_history : [{"month": "YYYY-MM", "income": 1200.0, "source": "salaire"}, ...]
    Plusieurs sources le même mois sont additionnées.
    """
    if not income_history:
        return {
            "months_analyzed": 0,
            "recommended_monthly_dca": None,
            "note": "Aucun historique de revenus — enregistrer les revenus avec record_monthly_income()",
        }

    by_month: dict[str, float] = {}
    for entry in income_history:
        if entry.get("income", 0) > 0:
            by_month[entry["month"]] = by_month.get(entry["month"], 0.0) + entry["income"]
    incomes = list(by_month.values())
    if not incomes:
        return {"error": "Historique revenus sans montants valides"}

    avg_income = sum(incomes) / len(incomes)
    min_income = min(incomes)

    capacity_avg = calculate_investment_capacity(avg_income, fixed_expenses, safety_pct, free_order_max)
    capacity_min = calculate_investment_capacity(min_income, fixed_expenses, safety_pct, free_order_max)
    recommended = capacity_min["investable_amount"]

    return {
        "months_analyzed": len(incomes),
        "average_income": round(avg_income, 2),
        "min_income": round(min_income, 2),
        "avg_investable": capacity_avg["investable_amount"],
        "recommended_monthly_dca": recommended,
        "is_free_order": (recommended <= free_order_max) if free_order_max is not None else None,
        "scenarios": {
            "mois_normal": capacity_avg["investable_amount"],
            "mois_difficile": capacity_min["investable_amount"],
        },
        "note": "Recommandation basée sur le mois le plus faible pour éviter de surestimer la capacité",
    }

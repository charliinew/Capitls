"""
Calcul de capacité d'investissement et budget DCA — fonctions pures.
Adapté au profil étudiant avec revenus irréguliers (stage + freelance).
"""

from __future__ import annotations

# Dépenses fixes minimales estimées pour un étudiant parisien
DEFAULT_FIXED_EXPENSES = 600.0  # minimum liquidité de précaution
SAFETY_BUFFER_PCT = 0.10         # 10% du revenu net gardé en buffer


def calculate_investment_capacity(
    monthly_income: float,
    fixed_expenses: float = DEFAULT_FIXED_EXPENSES,
    safety_pct: float = SAFETY_BUFFER_PCT,
    max_fortuneo_free: float = 500.0,
) -> dict:
    """
    Calcule la capacité d'investissement mensuelle disponible.
    fixed_expenses : dépenses fixes mensuelles (loyer, nourriture, abonnements...)
    safety_pct : % du revenu net conservé en buffer de sécurité
    Retourne: {investable_amount, safety_buffer, net_after_expenses, is_free_order, note}
    """
    if monthly_income <= 0:
        return {
            "investable_amount": 0.0,
            "safety_buffer": 0.0,
            "net_after_expenses": 0.0,
            "is_free_order": False,
            "note": "Revenu mensuel non renseigné ou nul",
        }

    net_after_expenses = max(0.0, monthly_income - fixed_expenses)
    safety_buffer = round(monthly_income * safety_pct, 2)
    investable = round(max(0.0, net_after_expenses - safety_buffer), 2)

    return {
        "monthly_income": round(monthly_income, 2),
        "fixed_expenses": round(fixed_expenses, 2),
        "safety_buffer": safety_buffer,
        "net_after_expenses": round(net_after_expenses, 2),
        "investable_amount": investable,
        "is_free_order": investable <= max_fortuneo_free,
        "fortuneo_note": (
            f"Ordre gratuit sur Fortuneo (≤{max_fortuneo_free:.0f}€)"
            if investable <= max_fortuneo_free
            else f"⚠️ Dépasse {max_fortuneo_free:.0f}€ — scinder en 2 ordres ou réduire le montant"
        ),
    }


def calculate_optimal_dca(
    income_history: list[dict],
    fixed_expenses: float = DEFAULT_FIXED_EXPENSES,
    safety_pct: float = SAFETY_BUFFER_PCT,
) -> dict:
    """
    Calcule le DCA optimal basé sur l'historique des revenus.
    income_history : [{"month": "2026-05", "income": 900.0, "source": "stage"}, ...]
    Retourne: {average_income, avg_investable, recommended_monthly_dca, scenarios, months_analyzed}
    """
    if not income_history:
        return {
            "average_income": 0.0,
            "avg_investable": 0.0,
            "recommended_monthly_dca": 200.0,
            "months_analyzed": 0,
            "note": "Aucun historique de revenus — valeur par défaut 200€/mois",
        }

    incomes = [e.get("income", 0.0) for e in income_history if e.get("income", 0) > 0]
    if not incomes:
        return {"error": "Historique revenus sans montants valides"}

    avg_income = sum(incomes) / len(incomes)
    min_income = min(incomes)

    capacity_avg = calculate_investment_capacity(avg_income, fixed_expenses, safety_pct)
    capacity_min = calculate_investment_capacity(min_income, fixed_expenses, safety_pct)

    # Recommandation conservatrice : basée sur le revenu minimum historique
    recommended = capacity_min["investable_amount"]

    return {
        "months_analyzed": len(incomes),
        "average_income": round(avg_income, 2),
        "min_income": round(min_income, 2),
        "avg_investable": capacity_avg["investable_amount"],
        "recommended_monthly_dca": recommended,
        "is_free_order": recommended <= 500.0,
        "scenarios": {
            "mois_normal": capacity_avg["investable_amount"],
            "mois_difficile": capacity_min["investable_amount"],
        },
        "note": "Recommandation basée sur le mois le plus faible pour éviter de surestimer la capacité",
    }

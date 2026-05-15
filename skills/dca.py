"""
Calculs DCA — fonctions pures, sans appel réseau.
Taux historiques MSCI World : pessimiste=4%, neutre=7%, optimiste=10%
"""

from __future__ import annotations

from datetime import date, timedelta


def calculate_dca_projection(
    monthly_amount: float,
    initial_amount: float,
    annual_rate: float,
    years: int,
) -> dict:
    """
    Projection DCA avec intérêts composés mensuels.

    Retourne: { total_invested, final_value, total_gains, gain_pct, by_year }
    """
    monthly_rate = annual_rate / 12
    value = initial_amount
    total_invested = initial_amount
    by_year = []

    for year in range(1, years + 1):
        for _ in range(12):
            value = value * (1 + monthly_rate) + monthly_amount
            total_invested += monthly_amount
        by_year.append({
            "year": year,
            "total_invested": round(total_invested, 2),
            "portfolio_value": round(value, 2),
            "gains": round(value - total_invested, 2),
        })

    gains = value - total_invested
    gain_pct = round((gains / total_invested) * 100, 1) if total_invested > 0 else 0.0
    return {
        "total_invested": round(total_invested, 2),
        "final_value": round(value, 2),
        "total_gains": round(gains, 2),
        "gain_pct": gain_pct,
        "by_year": by_year,
    }


def calculate_optimal_dca_schedule(
    total_amount: float,
    months: int,
    initial_weight: float = 0.25,
) -> list[dict]:
    """
    Calendrier de versements DCA pondéré.
    Le premier mois reçoit initial_weight * total, le reste est réparti uniformément.

    Retourne: [{ month, date, amount, cumulative }]
    """
    if months <= 0 or total_amount <= 0:
        return []

    initial_payment = round(total_amount * initial_weight, 2)
    remaining = total_amount - initial_payment
    monthly_payment = round(remaining / (months - 1), 2) if months > 1 else remaining

    # Ajustement pour éviter les erreurs d'arrondi sur le dernier mois
    total_planned = initial_payment + monthly_payment * (months - 1)
    adjustment = round(total_amount - total_planned, 2)

    schedule = []
    today = date.today()
    cumulative = 0.0

    for i in range(months):
        amount = initial_payment if i == 0 else monthly_payment
        if i == months - 1:
            amount = round(amount + adjustment, 2)
        cumulative += amount
        payment_date = date(today.year, today.month, 1) + timedelta(days=32 * i)
        payment_date = payment_date.replace(day=1)
        schedule.append({
            "month": i + 1,
            "date": payment_date.isoformat(),
            "amount": round(amount, 2),
            "cumulative": round(cumulative, 2),
        })

    return schedule


def calculate_fortuneo_dca_plan(
    monthly_budget: float,
    etf_price: float,
    max_free_order: float = 500.0,
) -> dict:
    """
    Plan DCA adapté à Fortuneo : 1 ordre/mois < max_free_order = gratuit.
    Calcule le nombre de parts à acheter et si l'ordre est gratuit.

    Retourne: { shares, amount, is_free, leftover, note }
    """
    if monthly_budget > max_free_order:
        amount = max_free_order
        note = f"Budget {monthly_budget}€ > {max_free_order}€. Limité à {max_free_order}€ pour ordre gratuit."
    else:
        amount = monthly_budget
        note = "Ordre gratuit sur Fortuneo (< 500€/mois)."

    shares = amount / etf_price if etf_price > 0 else 0
    leftover = monthly_budget - amount

    return {
        "shares_to_buy": round(shares, 4),
        "order_amount": round(amount, 2),
        "is_free_order": amount <= max_free_order,
        "leftover_cash": round(leftover, 2),
        "note": note,
    }

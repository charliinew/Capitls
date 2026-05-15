"""
Suivi PEA Fortuneo — fonctions pures, sans appel réseau.
Gestion du countdown 5 ans, historique des ordres, performance et calendrier.
"""

from __future__ import annotations

from datetime import date, timedelta


def calculate_pea_countdown(opening_date: str | None) -> dict:
    """
    opening_date: ISO string "YYYY-MM-DD" ou None si PEA pas encore actif
    Retourne: {is_active, days_remaining, months_remaining, is_exempt,
               exemption_date, years_held, opening_date}
    5 ans = 1826 jours (365*5+1 pour bissextile)
    """
    if opening_date is None:
        return {
            "is_active": False,
            "days_remaining": None,
            "months_remaining": None,
            "is_exempt": None,
            "exemption_date": None,
            "years_held": None,
            "opening_date": None,
        }

    five_years_days = 1826
    opened = date.fromisoformat(opening_date)
    exemption = opened + timedelta(days=five_years_days)
    today = date.today()

    years_held = round((today - opened).days / 365.25, 2)
    is_exempt = today >= exemption
    days_remaining = max(0, (exemption - today).days)
    months_remaining = round(days_remaining / 30.44, 1)

    return {
        "is_active": True,
        "days_remaining": days_remaining,
        "months_remaining": months_remaining,
        "is_exempt": is_exempt,
        "exemption_date": exemption.isoformat(),
        "years_held": years_held,
        "opening_date": opening_date,
    }


def add_pea_order(order_history: list, date: str, ticker: str, amount: float, price: float) -> list:
    """
    Ajoute un ordre à la liste. amount = montant investi en €, price = prix/part
    Calcule shares = amount / price
    Retourne la liste mise à jour (nouvelle liste, ne mutate pas l'originale)
    Chaque ordre: {date, ticker, amount, price, shares, is_free}
    is_free = amount <= 500 (règle Fortuneo)
    """
    shares = round(amount / price, 6) if price > 0 else 0.0
    new_order = {
        "date": date,
        "ticker": ticker,
        "amount": round(amount, 2),
        "price": round(price, 4),
        "shares": shares,
        "is_free": amount <= 500.0,
    }
    return list(order_history) + [new_order]


def calculate_pea_performance(order_history: list, current_price: float, ticker: str) -> dict:
    """
    Calcule P&L sur les ordres du ticker donné dans l'historique
    Retourne: {total_invested, current_value, gain_eur, gain_pct, avg_buy_price,
               total_shares, order_count}
    Si historique vide ou aucun ordre pour ce ticker: retourne les 0
    """
    orders = [o for o in order_history if o.get("ticker") == ticker]

    if not orders:
        return {
            "total_invested": 0.0,
            "current_value": 0.0,
            "gain_eur": 0.0,
            "gain_pct": 0.0,
            "avg_buy_price": 0.0,
            "total_shares": 0.0,
            "order_count": 0,
        }

    total_invested = sum(o["amount"] for o in orders)
    total_shares = sum(o["shares"] for o in orders)
    current_value = round(total_shares * current_price, 2)
    gain_eur = round(current_value - total_invested, 2)
    gain_pct = round((gain_eur / total_invested) * 100, 2) if total_invested > 0 else 0.0
    avg_buy_price = round(total_invested / total_shares, 4) if total_shares > 0 else 0.0

    return {
        "total_invested": round(total_invested, 2),
        "current_value": current_value,
        "gain_eur": gain_eur,
        "gain_pct": gain_pct,
        "avg_buy_price": avg_buy_price,
        "total_shares": round(total_shares, 6),
        "order_count": len(orders),
    }


def get_next_order_info(order_history: list, monthly_target: float = 200.0) -> dict:
    """
    Détermine quand passer le prochain ordre
    Regarde le dernier ordre dans l'historique, recommande +1 mois
    Si historique vide: recommande aujourd'hui
    Retourne: {next_date, amount, is_free_order, days_until, note}
    """
    today = date.today()

    if not order_history:
        return {
            "next_date": today.isoformat(),
            "amount": round(monthly_target, 2),
            "is_free_order": monthly_target <= 500.0,
            "days_until": 0,
            "note": "Aucun ordre passé — premier ordre recommandé dès aujourd'hui",
        }

    last_order = order_history[-1]
    last_date = date.fromisoformat(last_order["date"])

    next_month = last_date.month + 1
    next_year = last_date.year
    if next_month > 12:
        next_month = 1
        next_year += 1

    last_day_of_next_month = (date(next_year, next_month % 12 + 1, 1) - timedelta(days=1)).day if next_month != 12 else 31
    next_day = min(last_date.day, last_day_of_next_month)
    next_date = date(next_year, next_month, next_day)

    days_until = max(0, (next_date - today).days)

    return {
        "next_date": next_date.isoformat(),
        "amount": round(monthly_target, 2),
        "is_free_order": monthly_target <= 500.0,
        "days_until": days_until,
        "note": f"Dernier ordre le {last_order['date']} ({last_order['ticker']}, {last_order['amount']}€)",
    }

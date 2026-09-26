"""
Suivi PEA — fonctions pures, sans appel réseau.
Compte à rebours fiscal (depuis le 1er versement), historique des ordres, performance, calendrier.
"""

from __future__ import annotations

import calendar
from datetime import date


def _add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:  # 29 février → 28 février
        return d.replace(year=d.year + years, day=28)


def calculate_pea_countdown(first_deposit_date: str | None, exemption_years: int) -> dict:
    """
    first_deposit_date : "YYYY-MM-DD" (date du 1er versement) ou None si PEA non alimenté.
    exemption_years : durée de détention pour l'exonération d'IR (donnée de référence).
    Retourne: {is_active, days_remaining, months_remaining, is_exempt, exemption_date, years_held, first_deposit_date}
    """
    if first_deposit_date is None:
        return {
            "is_active": False,
            "days_remaining": None,
            "months_remaining": None,
            "is_exempt": None,
            "exemption_date": None,
            "years_held": None,
            "first_deposit_date": None,
        }

    opened = date.fromisoformat(first_deposit_date)
    exemption = _add_years(opened, exemption_years)
    today = date.today()
    days_remaining = max(0, (exemption - today).days)

    return {
        "is_active": True,
        "days_remaining": days_remaining,
        "months_remaining": round(days_remaining / 30.44, 1),
        "is_exempt": today >= exemption,
        "exemption_date": exemption.isoformat(),
        "years_held": round((today - opened).days / 365.25, 2),
        "first_deposit_date": first_deposit_date,
    }


def add_pea_order(
    order_history: list,
    date: str,
    ticker: str,
    amount: float,
    price: float,
    free_order_max: float | None = None,
) -> list:
    """
    Ajoute un ordre (nouvelle liste, l'originale n'est pas modifiée).
    shares = amount / price ; is_free = amount ≤ free_order_max (None si plafond inconnu).
    """
    new_order = {
        "date": date,
        "ticker": ticker,
        "amount": round(amount, 2),
        "price": round(price, 4),
        "shares": round(amount / price, 6) if price > 0 else 0.0,
        "is_free": (amount <= free_order_max) if free_order_max is not None else None,
    }
    return list(order_history) + [new_order]


def calculate_pea_performance(order_history: list, current_price: float, ticker: str) -> dict:
    """
    P&L des ordres d'un ticker au prix actuel.
    Retourne: {total_invested, current_value, gain_eur, gain_pct, avg_buy_price, total_shares, order_count}
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

    return {
        "total_invested": round(total_invested, 2),
        "current_value": current_value,
        "current_price": current_price,
        "gain_eur": gain_eur,
        "gain_pct": round((gain_eur / total_invested) * 100, 2) if total_invested > 0 else 0.0,
        "avg_buy_price": round(total_invested / total_shares, 4) if total_shares > 0 else 0.0,
        "total_shares": round(total_shares, 6),
        "order_count": len(orders),
    }


def get_next_order_info(
    order_history: list,
    monthly_target: float | None,
    free_order_max: float | None = None,
) -> dict:
    """
    Prochain ordre : même jour du mois suivant le dernier ordre (aujourd'hui si aucun ordre).
    Retourne: {next_date, amount, is_free_order, days_until, note}
    """
    today = date.today()
    is_free = monthly_target <= free_order_max if monthly_target is not None and free_order_max is not None else None

    if not order_history:
        return {
            "next_date": today.isoformat(),
            "amount": monthly_target,
            "is_free_order": is_free,
            "days_until": 0,
            "note": "Aucun ordre passé — premier ordre possible dès aujourd'hui",
        }

    last_order = max(order_history, key=lambda o: o["date"])
    last_date = date.fromisoformat(last_order["date"])
    next_year = last_date.year + (1 if last_date.month == 12 else 0)
    next_month = 1 if last_date.month == 12 else last_date.month + 1
    next_day = min(last_date.day, calendar.monthrange(next_year, next_month)[1])
    next_date = date(next_year, next_month, next_day)

    return {
        "next_date": next_date.isoformat(),
        "amount": monthly_target,
        "is_free_order": is_free,
        "days_until": max(0, (next_date - today).days),
        "note": f"Dernier ordre le {last_order['date']} ({last_order['ticker']}, {last_order['amount']}€)",
    }

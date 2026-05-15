"""
Benchmark et comparaison DCA vs lump sum — fonctions pures, sans appel réseau.
"""

from __future__ import annotations


def calculate_dca_vs_lumpsum(
    prices: list[float],
    monthly_amount: float = 200.0,
    months: int = 12,
) -> dict:
    """
    Compare DCA mensuel vs lump sum sur les N derniers mois.
    prices: closes du plus ancien au plus récent (besoin d'au moins months+1 points).
    Suppose ~21 jours de trading par mois.
    Retourne: {dca_final, lumpsum_final, dca_wins, outperformance_pct, total_invested, note}
    """
    trading_days_per_month = 21
    required = months * trading_days_per_month + 1

    if len(prices) < required:
        usable_months = max(1, (len(prices) - 1) // trading_days_per_month)
        prices = prices[-(usable_months * trading_days_per_month + 1):]
        months = usable_months

    total_invested = monthly_amount * months
    last_price = prices[-1]

    # Lump sum : on investit tout au départ
    start_price = prices[0]
    lumpsum_shares = total_invested / start_price
    lumpsum_final = lumpsum_shares * last_price

    # DCA : un achat par mois au prix du début du mois
    dca_shares = 0.0
    for m in range(months):
        idx = m * trading_days_per_month
        if idx < len(prices):
            dca_shares += monthly_amount / prices[idx]
    dca_final = dca_shares * last_price

    dca_wins = dca_final > lumpsum_final
    outperformance = ((dca_final - lumpsum_final) / lumpsum_final) * 100 if lumpsum_final > 0 else 0.0

    return {
        "dca_final": round(dca_final, 2),
        "lumpsum_final": round(lumpsum_final, 2),
        "total_invested": round(total_invested, 2),
        "dca_wins": dca_wins,
        "outperformance_pct": round(outperformance, 2),
        "months_compared": months,
        "note": (
            "DCA réduit le risque de timing mais le lump sum surperforme ~67% du temps historiquement"
        ),
    }


def compare_returns(
    prices_a: list[float],
    prices_b: list[float],
    label_a: str = "Portfolio",
    label_b: str = "Benchmark",
) -> dict:
    """
    Compare les rendements de deux séries de prix sur la même période.
    Tronque à la longueur minimale des deux séries.
    Retourne: {return_a_pct, return_b_pct, outperformance_pct, label_a, label_b}
    """
    n = min(len(prices_a), len(prices_b))
    if n < 2:
        return {"error": "Pas assez de données (minimum 2 points par série)"}

    prices_a = prices_a[-n:]
    prices_b = prices_b[-n:]

    return_a = ((prices_a[-1] - prices_a[0]) / prices_a[0]) * 100
    return_b = ((prices_b[-1] - prices_b[0]) / prices_b[0]) * 100
    outperformance = return_a - return_b

    return {
        label_a: {
            "start_price": round(prices_a[0], 4),
            "end_price": round(prices_a[-1], 4),
            "return_pct": round(return_a, 2),
        },
        label_b: {
            "start_price": round(prices_b[0], 4),
            "end_price": round(prices_b[-1], 4),
            "return_pct": round(return_b, 2),
        },
        "outperformance_pct": round(outperformance, 2),
        "winner": label_a if outperformance > 0 else label_b,
        "periods": n,
    }

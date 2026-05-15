"""
Timing d'achat — fonctions pures, sans appel réseau.
Score percentile basé sur le ratio prix/SMA252.
"""

from __future__ import annotations


def calculate_sma(prices: list[float], window: int) -> float | None:
    """Simple Moving Average. Retourne None si pas assez de données."""
    if len(prices) < window:
        return None
    return sum(prices[-window:]) / window


def calculate_timing_score(prices: list[float]) -> dict:
    """
    Score 0-100 basé sur percentile du ratio price/SMA252 dans l'historique
    prices: liste de closes (du plus ancien au plus récent)
    Retourne: {score, current_price, sma_52w, price_to_sma_ratio,
               interpretation, source}
    interpretation: "Bon point d'entrée" si score<=30, "Neutre" si 30<score<=70,
                   "Prix élevé" si score>70
    Si moins de 252 données: utiliser toutes les données disponibles pour la SMA,
    et comparer le ratio sur toutes les données disponibles
    Si moins de 2 données: retourner score=50 (neutre, pas assez de données)
    """
    if len(prices) < 2:
        return {
            "score": 50,
            "current_price": prices[0] if prices else None,
            "sma_52w": None,
            "price_to_sma_ratio": None,
            "interpretation": "Neutre",
            "source": "Pas assez de données",
        }

    # Fenêtre 63 jours (3 mois) : génère ~189 ratios sur 1 an de données
    # Une fenêtre 252 jours (1 an) ne produirait qu'1 ratio avec 1 an de données
    sma_window = min(63, len(prices) // 2)
    if sma_window < 2:
        sma_window = 2
    sma_current = sum(prices[-sma_window:]) / sma_window
    current_price = prices[-1]
    current_ratio = current_price / sma_current if sma_current > 0 else 1.0

    # Construire l'historique des ratios sur toutes les données disponibles
    ratios = []
    for i in range(sma_window, len(prices) + 1):
        window_prices = prices[i - sma_window:i]
        window_sma = sum(window_prices) / len(window_prices)
        if window_sma > 0:
            ratios.append(prices[i - 1] / window_sma)

    if not ratios:
        ratios = [current_ratio]

    below_count = sum(1 for r in ratios if r <= current_ratio)
    score = round((below_count / len(ratios)) * 100)

    if score <= 30:
        interpretation = "Bon point d'entrée"
    elif score <= 70:
        interpretation = "Neutre"
    else:
        interpretation = "Prix élevé"

    return {
        "score": score,
        "current_price": round(current_price, 4),
        "sma_52w": round(sma_current, 4),
        "price_to_sma_ratio": round(current_ratio, 4),
        "interpretation": interpretation,
        "source": f"Calcul sur {len(prices)} points de données",
    }

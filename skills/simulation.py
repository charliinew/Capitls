"""
Simulation d'allocation et alertes diversification — fonctions pures.
"""

from __future__ import annotations

# Modèle de référence pour un étudiant investisseur long terme
MODEL_PORTFOLIO_STUDENT = {
    "world": 0.70,    # ETF MSCI World PEA
    "savings": 0.20,  # Liquidités de précaution
    "crypto": 0.10,   # Crypto (optionnel, risqué)
}

CRYPTO_ALERT_THRESHOLD = 0.15  # 15% max recommandé


def simulate_allocation(
    current_allocation: dict[str, float],
    target_allocation: dict[str, float],
    total_value: float,
) -> dict:
    """
    Simule l'impact d'un changement d'allocation.
    current_allocation et target_allocation : {"world": 0.0, "crypto": 0.35, "savings": 0.65}
    Les valeurs sont des pourcentages décimaux (0.70 = 70%).
    Retourne: {current_amounts, target_amounts, changes_needed, rebalancing_actions}
    """
    current_amounts = {k: round(v * total_value, 2) for k, v in current_allocation.items()}
    target_amounts = {k: round(v * total_value, 2) for k, v in target_allocation.items()}

    # Calcul des mouvements nécessaires
    all_keys = set(current_allocation) | set(target_allocation)
    changes = {}
    for key in all_keys:
        curr = current_amounts.get(key, 0.0)
        tgt = target_amounts.get(key, 0.0)
        delta = round(tgt - curr, 2)
        changes[key] = {
            "current": curr,
            "target": tgt,
            "delta": delta,
            "action": "acheter" if delta > 0 else ("vendre" if delta < 0 else "conserver"),
        }

    actions = [
        f"{v['action'].upper()} {abs(v['delta']):.0f}€ de {k}"
        for k, v in changes.items()
        if abs(v["delta"]) >= 10
    ]

    return {
        "total_value": round(total_value, 2),
        "current_allocation": {k: f"{v*100:.1f}%" for k, v in current_allocation.items()},
        "target_allocation": {k: f"{v*100:.1f}%" for k, v in target_allocation.items()},
        "changes": changes,
        "rebalancing_actions": actions if actions else ["Aucun mouvement significatif requis"],
    }


def compare_vs_model_portfolio(
    current_allocation: dict[str, float],
    model: dict[str, float] | None = None,
) -> dict:
    """
    Compare l'allocation actuelle au modèle étudiant standard.
    current_allocation : {"world": 0.0, "crypto": 0.35, "savings": 0.65}
    Retourne: {gaps, score_ecart, recommendation}
    """
    if model is None:
        model = MODEL_PORTFOLIO_STUDENT

    all_keys = set(current_allocation) | set(model)
    gaps = {}
    total_gap = 0.0

    for key in all_keys:
        curr_pct = current_allocation.get(key, 0.0) * 100
        model_pct = model.get(key, 0.0) * 100
        gap = round(curr_pct - model_pct, 1)
        gaps[key] = {
            "actuel": f"{curr_pct:.1f}%",
            "modele": f"{model_pct:.1f}%",
            "ecart": f"{'+' if gap > 0 else ''}{gap:.1f}%",
        }
        total_gap += abs(gap)

    # Score d'écart : 0 = parfait, 100 = complètement différent
    ecart_score = min(100, round(total_gap / 2))

    if ecart_score <= 15:
        verdict = "Allocation proche du modèle étudiant"
    elif ecart_score <= 40:
        verdict = "Allocation acceptable, quelques ajustements possibles"
    else:
        verdict = "Allocation très éloignée du modèle — rééquilibrage recommandé à terme"

    return {
        "gaps": gaps,
        "ecart_score": ecart_score,
        "verdict": verdict,
        "model_reference": {k: f"{v*100:.0f}%" for k, v in model.items()},
        "note": "Modèle indicatif pour un étudiant investisseur long terme — adapter selon tolérance au risque",
    }


def get_crypto_alert(
    crypto_value: float,
    total_value: float,
    threshold: float = CRYPTO_ALERT_THRESHOLD,
) -> dict:
    """
    Alerte si la part crypto dépasse le seuil recommandé.
    Retourne: {alert, crypto_pct, threshold_pct, excess_eur, recommendation}
    """
    if total_value <= 0:
        return {"alert": False, "error": "Patrimoine total = 0"}

    crypto_pct = (crypto_value / total_value) * 100
    threshold_pct = threshold * 100
    alert = crypto_pct > threshold_pct
    excess_eur = max(0.0, crypto_value - total_value * threshold) if alert else 0.0

    return {
        "alert": alert,
        "crypto_value": round(crypto_value, 2),
        "crypto_pct": round(crypto_pct, 1),
        "threshold_pct": round(threshold_pct, 1),
        "excess_eur": round(excess_eur, 2),
        "recommendation": (
            f"⚠️ Crypto représente {crypto_pct:.1f}% du patrimoine (seuil : {threshold_pct:.0f}%). "
            f"Rééquilibrer en vendant ~{excess_eur:.0f}€ de crypto ou en augmentant les autres actifs."
            if alert
            else f"Crypto à {crypto_pct:.1f}% — dans les limites recommandées ({threshold_pct:.0f}% max)."
        ),
    }

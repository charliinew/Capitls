"""
Analyse de diversification — fonctions pures.
Les seuils personnels (liquidité minimale, part crypto max) viennent du profil utilisateur.
"""

from __future__ import annotations

LIQUID_TYPES = ("checking", "savings", "regulated_savings", "livret")
INVESTED_TYPES = ("pea", "cto", "securities", "life_insurance", "retirement")


def analyze_diversification(
    portfolio: dict,
    liquidity_min: float | None = None,
    crypto_max_pct: float | None = None,
) -> dict:
    """
    Score de diversification du portfolio.

    portfolio : {"accounts": [{"category" | "type": "pea|crypto|savings|...", "balance": 1000.0}]}
    liquidity_min : épargne de précaution minimale (€) — règle ignorée si None
    crypto_max_pct : part crypto max (fraction, ex 0.20) — règle ignorée si None

    Retourne: { score (0-100), repartition, warnings }
    """
    accounts = portfolio.get("accounts", [])
    if not accounts:
        return {"score": 0, "repartition": {}, "warnings": ["Portfolio vide"]}

    total = sum(a.get("balance", 0) for a in accounts)
    if total == 0:
        return {"score": 0, "repartition": {}, "warnings": ["Total portfolio = 0"]}

    repartition: dict[str, float] = {}
    for account in accounts:
        atype = account.get("category") or account.get("type", "other")
        repartition[atype] = repartition.get(atype, 0) + account.get("balance", 0)

    repartition_pct = {k: round(v / total * 100, 1) for k, v in repartition.items()}

    warnings = []
    score = 100

    has_invested = any(repartition.get(t, 0) > 0 for t in INVESTED_TYPES)
    if not has_invested:
        score -= 25

    crypto_pct = repartition_pct.get("crypto", 0)
    if crypto_max_pct is not None and crypto_pct > crypto_max_pct * 100:
        warnings.append(f"Crypto trop élevée : {crypto_pct}% (max défini {crypto_max_pct * 100:.0f}%)")
        score -= min(30, (crypto_pct - crypto_max_pct * 100) * 2)

    liquid = sum(repartition.get(t, 0) for t in LIQUID_TYPES)
    if liquidity_min is not None and liquid < liquidity_min:
        warnings.append(f"Liquidité insuffisante : {liquid:.0f}€ (minimum défini {liquidity_min:.0f}€)")
        score -= 20

    asset_classes = len([v for v in repartition.values() if v > 0])
    if asset_classes >= 3:
        score = min(100, score + 10)
    elif asset_classes == 1:
        warnings.append("Portfolio concentré sur une seule classe d'actifs")
        score -= 15

    max_pct = max(repartition_pct.values())
    if max_pct > 80:
        warnings.append(f"Concentration excessive : {max_pct}% sur un seul type d'actif")
        score -= 20

    if not has_invested:
        warnings.append("⚠️ Aucun actif investi en bourse (PEA, CTO, assurance-vie) — capital non exposé aux marchés")

    return {
        "score": max(0, min(100, score)),
        "total_portfolio": round(total, 2),
        "repartition": repartition_pct,
        "repartition_amounts": {k: round(v, 2) for k, v in repartition.items()},
        "warnings": warnings,
        "asset_classes_count": asset_classes,
    }


def detect_etf_overlap(etf_isins: list[str], isin_to_index: dict[str, str]) -> dict:
    """
    Détecte les ETF qui répliquent le même indice (chevauchement ~100 %).
    isin_to_index : {isin: indice} — issu du catalogue ETF des données de référence.
    """
    indices_held: dict[str, list[str]] = {}
    for isin in etf_isins:
        indices_held.setdefault(isin_to_index.get(isin, "Unknown"), []).append(isin)

    overlaps = [
        {
            "index": index,
            "isins": isins,
            "overlap_pct": 100 if index != "Unknown" else None,
            "warning": f"Chevauchement 100% : {', '.join(isins)} suivent tous {index}",
        }
        for index, isins in indices_held.items()
        if len(isins) > 1
    ]

    return {
        "overlaps_found": len(overlaps) > 0,
        "overlaps": overlaps,
        "recommendation": (
            "Choisir UN SEUL ETF par indice — les doubler ne diversifie pas, ça multiplie les frais."
            if overlaps
            else "Aucun chevauchement détecté."
        ),
        "note": "Analyse par indice répliqué — pour une vérification fine, justETF Portfolio X-Ray (tier_1)",
    }

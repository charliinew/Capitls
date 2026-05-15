"""
Analyse de diversification — fonctions pures.
"""

from __future__ import annotations


def analyze_diversification(portfolio: dict) -> dict:
    """
    Score de diversification du portfolio.

    portfolio format:
    {
        "accounts": [
            {"type": "pea|crypto|savings|livret|checking", "balance": 1000.0}
        ]
    }

    Retourne: { score (0-100), repartition, warnings }
    """
    accounts = portfolio.get("accounts", [])
    if not accounts:
        return {"score": 0, "repartition": {}, "warnings": ["Portfolio vide"]}

    total = sum(a.get("balance", 0) for a in accounts)
    if total == 0:
        return {"score": 0, "repartition": {}, "warnings": ["Total portfolio = 0"]}

    # Répartition par type
    repartition: dict[str, float] = {}
    for account in accounts:
        atype = account.get("type", "other")
        repartition[atype] = repartition.get(atype, 0) + account.get("balance", 0)

    repartition_pct = {k: round(v / total * 100, 1) for k, v in repartition.items()}

    warnings = []
    score = 100

    # Pénalité si aucun compte de type investi (PEA, securities)
    invested_types = {"pea", "securities"}
    has_invested = any(a.get("type") in invested_types for a in accounts)
    if not has_invested:
        score -= 25

    # Règle : crypto max 20%
    crypto_pct = repartition_pct.get("crypto", 0)
    if crypto_pct > 20:
        warnings.append(f"Crypto trop élevée : {crypto_pct}% (max recommandé 20%)")
        score -= min(30, (crypto_pct - 20) * 2)

    # Règle : pas de compte sans liquidité de précaution
    liquid = repartition.get("savings", 0) + repartition.get("checking", 0)
    if liquid < 600:
        warnings.append(f"Liquidité insuffisante : {liquid:.0f}€ (minimum recommandé 600€)")
        score -= 20

    # Bonus : diversification entre asset classes
    asset_classes = len([v for v in repartition.values() if v > 0])
    if asset_classes >= 3:
        score = min(100, score + 10)
    elif asset_classes == 1:
        warnings.append("Portfolio concentré sur une seule classe d'actifs")
        score -= 15

    # Malus : trop concentré sur une seule position (>80%)
    max_pct = max(repartition_pct.values())
    if max_pct > 80:
        warnings.append(f"Concentration excessive : {max_pct}% sur un seul type d'actif")
        score -= 20

    if not has_invested:
        warnings.append("⚠️ Aucun actif investi en bourse (PEA, actions) — capital non exposé aux marchés")

    return {
        "score": max(0, min(100, score)),
        "total_portfolio": round(total, 2),
        "repartition": repartition_pct,
        "repartition_amounts": {k: round(v, 2) for k, v in repartition.items()},
        "warnings": warnings,
        "asset_classes_count": asset_classes,
    }


def detect_etf_overlap(etf_isins: list[str]) -> dict:
    """
    Détecte les chevauchements entre ETF basé sur les indices suivis.
    Utilise une base statique — les ETF MSCI World se chevauchent à ~100%.

    Pour une analyse plus fine, utiliser justETF ou Morningstar X-Ray.
    """
    # Indices suivis par ISIN (base statique simplifiée)
    index_map = {
        "FR001400U5Q4": "MSCI World",    # DCAM
        "IE0002XZSHO1": "MSCI World",    # WPEA
        "LU1681043599": "MSCI World",    # CW8
        "FR0011869353": "MSCI World",    # EWLD
        "IE00B4L5Y983": "MSCI World",    # IWDA (non PEA)
        "LU1437016972": "MSCI World",    # LCUW (non PEA)
    }

    overlaps = []
    indices_held: dict[str, list[str]] = {}

    for isin in etf_isins:
        index = index_map.get(isin, "Unknown")
        if index not in indices_held:
            indices_held[index] = []
        indices_held[index].append(isin)

    for index, isins in indices_held.items():
        if len(isins) > 1:
            overlaps.append({
                "index": index,
                "isins": isins,
                "overlap_pct": 100 if index != "Unknown" else None,
                "warning": f"Chevauchement 100% : {', '.join(isins)} suivent tous {index}",
            })

    return {
        "overlaps_found": len(overlaps) > 0,
        "overlaps": overlaps,
        "recommendation": (
            "Choisir UN SEUL ETF MSCI World — les doubler ne diversifie pas, ça multiplie les frais."
            if overlaps else "Aucun chevauchement détecté."
        ),
        "note": "Analyse statique — pour vérification complète, utiliser justETF Portfolio X-Ray (tier_1)",
    }

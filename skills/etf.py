"""
Comparaison et analyse d'ETF — fonctions pures.
Le catalogue (ISIN, TER, encours, éligibilité PEA) vient des données de référence
(data/reference_data.json, rafraîchi depuis justETF) et est passé en paramètre.
"""

from __future__ import annotations

DEFAULT_GROSS_RETURN = 0.07  # hypothèse de rendement brut pour illustrer l'impact des frais


def get_etf_info(ticker: str, catalog: dict[str, dict]) -> dict:
    """Infos d'un ETF depuis le catalogue."""
    ticker = ticker.upper().replace(".PA", "")
    if ticker not in catalog:
        return {"error": f"ETF '{ticker}' non trouvé. Disponibles: {list(catalog.keys())}"}
    return catalog[ticker]


def compare_etfs(tickers: list[str], catalog: dict[str, dict]) -> list[dict]:
    """Comparaison tabulaire, triée par TER croissant. Tickers inconnus ignorés."""
    results = []
    for ticker in tickers:
        info = get_etf_info(ticker, catalog)
        if "error" not in info:
            results.append({**info, "ticker": ticker.upper().replace(".PA", "")})
    results.sort(key=lambda x: x["ter"] if x.get("ter") is not None else float("inf"))
    return results


def recommend_etf_for_pea(
    catalog: dict[str, dict],
    broker: str | None = None,
    monthly_budget: float | None = None,
    index: str | None = None,
) -> dict:
    """
    Meilleur ETF éligible PEA : TER le plus bas, puis encours le plus élevé (liquidité).
    index : restreint à un indice (ex: "MSCI World").
    """
    eligible = [
        {"ticker": k, **v}
        for k, v in catalog.items()
        if v.get("pea_eligible") and v.get("ter") is not None and (index is None or v.get("index") == index)
    ]
    if not eligible:
        return {"error": "Aucun ETF éligible PEA dans le catalogue"}
    eligible.sort(key=lambda x: (x["ter"], -(x.get("fund_size_meur") or 0)))

    best = eligible[0]
    same_ter = [e["ticker"] for e in eligible if e["ter"] == best["ter"]]
    return {
        "recommended": best,
        "equivalents_same_ter": same_ter,
        "alternatives": eligible[1:3],
        "broker": broker,
        "monthly_budget": monthly_budget,
        "reasoning": (
            f"{', '.join(same_ter)} : TER le plus bas ({best['ter'] * 100:.2f} %) parmi les ETF éligibles PEA du catalogue. "
            + (
                f"Vérifier la disponibilité et les frais chez {broker}."
                if broker
                else "Vérifier la disponibilité chez votre courtier."
            )
        ),
        "source": "justETF (tier_1) via données de référence",
    }


def calculate_ter_impact(
    initial: float,
    monthly: float,
    years: int,
    ter_a: float,
    ter_b: float,
    gross_return: float = DEFAULT_GROSS_RETURN,
) -> dict:
    """Écart de valeur finale entre deux TER sur une période (versements mensuels)."""

    def simulate(ter: float) -> float:
        monthly_rate = (gross_return - ter) / 12
        value = initial
        for _ in range(years * 12):
            value = value * (1 + monthly_rate) + monthly
        return round(value, 2)

    value_a = simulate(ter_a)
    value_b = simulate(ter_b)
    diff = round(abs(value_a - value_b), 2)

    return {
        "ter_a": {"ter": ter_a, "final_value": value_a},
        "ter_b": {"ter": ter_b, "final_value": value_b},
        "difference": diff,
        "years": years,
        "gross_return_assumption": gross_return,
        "note": f"Sur {years} ans, la différence de TER coûte {diff}€",
    }

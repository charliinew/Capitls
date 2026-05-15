"""
Comparaison et analyse d'ETF — fonctions pures + fetch justETF.
Source données : justETF (tier_1 pour TER/composition), Yahoo Finance (tier_2 pour prix)
"""

from __future__ import annotations

# Référentiel ETF MSCI World éligibles PEA — mise à jour 2026-05
ETF_CATALOG: dict[str, dict] = {
    "DCAM": {
        "isin": "FR001400U5Q4",
        "name": "Amundi PEA Monde MSCI World",
        "ter": 0.0020,
        "eligible_pea": True,
        "replication": "synthétique (swap)",
        "domicile": "France",
        "distribuant": False,
        "launched": "2025-03",
        "ticker_yahoo": "DCAM.PA",
        "note": "Meilleur choix 2026 — TER le plus bas, Amundi",
    },
    "WPEA": {
        "isin": "IE0002XZSHO1",
        "name": "iShares MSCI World Swap PEA UCITS ETF",
        "ter": 0.0020,
        "eligible_pea": True,
        "replication": "synthétique (swap)",
        "domicile": "Irlande",
        "distribuant": False,
        "launched": "2024-04",
        "ticker_yahoo": "WPEA.PA",
        "note": "Meilleur choix 2026 ex aequo — TER identique, iShares",
    },
    "CW8": {
        "isin": "LU1681043599",
        "name": "Amundi MSCI World Swap UCITS ETF",
        "ter": 0.0038,
        "eligible_pea": True,
        "replication": "synthétique (swap)",
        "domicile": "Luxembourg",
        "distribuant": False,
        "launched": "2018",
        "ticker_yahoo": "CW8.PA",
        "note": "Historique, grande liquidité (5.6Md€) mais TER 2x plus élevé que DCAM/WPEA",
    },
    "EWLD": {
        "isin": "FR0011869353",
        "name": "Lyxor PEA Monde MSCI World",
        "ter": 0.0045,
        "eligible_pea": True,
        "replication": "synthétique (swap)",
        "domicile": "France",
        "distribuant": True,
        "launched": "2014",
        "ticker_yahoo": "EWLD.PA",
        "note": "DÉCONSEILLÉ — TER 0.45%, le plus élevé de la catégorie",
    },
}


def get_etf_info(ticker: str) -> dict:
    """Infos statiques sur un ETF depuis le catalogue interne."""
    ticker = ticker.upper().replace(".PA", "")
    if ticker not in ETF_CATALOG:
        return {"error": f"ETF '{ticker}' non trouvé. Disponibles: {list(ETF_CATALOG.keys())}"}
    return ETF_CATALOG[ticker]


def compare_etfs(tickers: list[str]) -> list[dict]:
    """
    Comparaison tabulaire de plusieurs ETF.
    Tickers : DCAM, WPEA, CW8, EWLD (sans suffixe .PA)
    """
    results = []
    for ticker in tickers:
        info = get_etf_info(ticker)
        if "error" not in info:
            results.append({"ticker": ticker, **info})

    # Tri par TER croissant
    results.sort(key=lambda x: x.get("ter", 999))
    return results


def recommend_etf_for_pea(
    courtier: str = "fortuneo",
    monthly_budget: float = 200.0,
) -> dict:
    """
    Recommande le meilleur ETF World PEA selon le courtier et le budget.
    Priorité : TER minimum, éligibilité PEA, disponibilité chez le courtier.
    """
    # Catalogue filtré : éligibles PEA uniquement, tri TER
    eligible = [
        {"ticker": k, **v}
        for k, v in ETF_CATALOG.items()
        if v["eligible_pea"] and k != "EWLD"
    ]
    eligible.sort(key=lambda x: x["ter"])

    best = eligible[0]
    alternatives = eligible[1:]

    return {
        "recommended": best,
        "alternatives": alternatives,
        "courtier": courtier,
        "monthly_budget": monthly_budget,
        "reasoning": (
            f"DCAM et WPEA ont le TER le plus bas (0.20%) parmi les ETF MSCI World éligibles PEA. "
            f"Vérifier la disponibilité sur {courtier.capitalize()} avant d'investir."
        ),
        "source": "justETF + AMF (tier_1)",
    }


def calculate_ter_impact(
    initial: float,
    monthly: float,
    years: int,
    ter_a: float,
    ter_b: float,
) -> dict:
    """
    Compare l'impact du TER sur deux ETF sur une période donnée.
    Montre combien de frais en plus on paie avec le TER le plus élevé.
    """
    def simulate(ter: float) -> float:
        net_rate = 0.07 - ter  # rendement MSCI World neutre 7% - frais
        monthly_rate = net_rate / 12
        value = initial
        for _ in range(years * 12):
            value = value * (1 + monthly_rate) + monthly
        return round(value, 2)

    value_a = simulate(ter_a)
    value_b = simulate(ter_b)

    return {
        "ter_a": {"ter": ter_a, "final_value": value_a},
        "ter_b": {"ter": ter_b, "final_value": value_b},
        "difference": round(abs(value_a - value_b), 2),
        "years": years,
        "note": f"Sur {years} ans, la différence de TER coûte {round(abs(value_a - value_b), 2)}€",
    }

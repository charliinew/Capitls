"""
Tool MCP : analyses financières et recommandations.
Orchestre les skills (calculs purs) et les contextualise au profil utilisateur.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from skills.dca import calculate_dca_projection, calculate_fortuneo_dca_plan, calculate_optimal_dca_schedule
from skills.diversification import analyze_diversification, detect_etf_overlap
from skills.etf import compare_etfs, recommend_etf_for_pea
from skills.projection import project_portfolio_multi_scenarios
from skills.tax import calculate_pea_tax_advantage, calculate_livret_jeune_vs_pea

logger = logging.getLogger(__name__)

PROFILE_PATH = Path(__file__).parent.parent / "context" / "user_profile.json"


def _load_profile() -> dict:
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return json.load(f)


def analyze_portfolio(portfolio: dict) -> dict:
    """
    Analyse complète du portfolio : diversification, règles personnelles, points d'attention.
    portfolio : format interne normalisé (sortie de portfolio_tool.get_portfolio)
    """
    profile = _load_profile()
    diversification = analyze_diversification(portfolio)

    accounts = portfolio.get("accounts", [])
    total = sum(a.get("balance", 0) for a in accounts)
    excluded = set(profile.get("regles_personnelles", {}).get("liquidite_comptes_exclus", []))
    liquid = sum(
        a["balance"] for a in accounts
        if a["type"] in ("savings", "checking", "livret") and a.get("institution") not in excluded
    )

    return {
        "total_net_worth": round(total, 2),
        "diversification": diversification,
        "liquidity": {
            "amount": round(liquid, 2),
            "minimum_required": profile["regles_personnelles"]["liquidite_minimale"],
            "status": "ok" if liquid >= profile["regles_personnelles"]["liquidite_minimale"] else "insuffisant",
        },
        "pea_status": profile["patrimoine"]["pea"]["statut"],
        "next_actions": _compute_next_actions(profile, diversification, liquid, total),
    }


def recommend_dca_plan(
    monthly_budget: float | None = None,
    etf_ticker: str = "DCAM",
    etf_price: float | None = None,
    years: int = 10,
) -> dict:
    """
    Plan DCA complet adapté à Fortuneo.
    Si etf_price est None, l'outil retourne la structure sans le calcul d'ordre.
    """
    profile = _load_profile()
    pea = profile["patrimoine"]["pea"]

    budget = monthly_budget or pea["versement_mensuel_cible"]

    # Projections multi-scénarios
    projections = project_portfolio_multi_scenarios(
        current_value=0,
        monthly_contribution=budget,
        years=years,
    )

    # Plan Fortuneo
    fortuneo_plan = None
    if etf_price:
        fortuneo_plan = calculate_fortuneo_dca_plan(
            monthly_budget=budget,
            etf_price=etf_price,
        )

    # ETF recommandé
    etf_recommendation = recommend_etf_for_pea(courtier="fortuneo", monthly_budget=budget)

    # Calendrier d'initialisation (apport initial sur 6 mois)
    initial_schedule = calculate_optimal_dca_schedule(
        total_amount=pea["apport_initial_cible"],
        months=6,
        initial_weight=0.25,
    )

    return {
        "monthly_budget": budget,
        "etf_recommended": etf_ticker,
        "fortuneo_constraint": "1 ordre/mois < 500€ gratuit — ne pas dépasser",
        "fortuneo_order": fortuneo_plan,
        "initial_investment_schedule": initial_schedule,
        "projections": {
            scenario: {
                "final_value": p["final_value"],
                "total_invested": p["total_invested"],
                "gains": p["total_gains"],
                "annual_rate": p["annual_rate"],
            }
            for scenario, p in projections.items()
        },
        "etf_recommendation": etf_recommendation,
        "note": f"Parrainage Fortuneo : {pea['parrainage']['bonus']}€ offerts si {pea['parrainage']['condition']}",
    }


def compare_etf_options(tickers: list[str] | None = None) -> dict:
    """
    Comparaison détaillée des ETF MSCI World PEA disponibles.
    Inclut l'impact du TER sur 10 ans.
    """
    if tickers is None:
        tickers = ["DCAM", "WPEA", "CW8"]

    comparison = compare_etfs(tickers)

    # Impact TER : comparaison DCAM (0.20%) vs CW8 (0.38%) sur 10 ans, 200€/mois
    from skills.etf import calculate_ter_impact
    ter_impact = calculate_ter_impact(
        initial=1000,
        monthly=200,
        years=10,
        ter_a=0.0020,
        ter_b=0.0038,
    )

    return {
        "comparison": comparison,
        "ter_impact_10y": ter_impact,
        "verdict": "DCAM ou WPEA sont les meilleurs choix en 2026 (TER 0.20% vs 0.38% pour CW8)",
        "source": "Données internes basées sur justETF (tier_1)",
    }


def project_wealth(
    years: int = 10,
    monthly_contribution: float | None = None,
) -> dict:
    """
    Projection du patrimoine total sur N ans, multi-scénarios.
    Basé sur le profil utilisateur et les actifs actuels.
    """
    profile = _load_profile()
    pat = profile["patrimoine"]

    current_pea = 0  # PEA pas encore ouvert
    current_crypto = pat["crypto"]["valeur_estimee"]
    current_savings = pat["livret_jeune"]["montant"] + pat["epargne_revolut"]["montant"]
    current_total = current_pea + current_crypto + current_savings

    contrib = monthly_contribution or pat["pea"]["versement_mensuel_cible"]

    projections = project_portfolio_multi_scenarios(
        current_value=current_total,
        monthly_contribution=contrib,
        years=years,
    )

    return {
        "current_snapshot": {
            "total": current_total,
            "pea": current_pea,
            "crypto": current_crypto,
            "savings": current_savings,
        },
        "monthly_contribution": contrib,
        "projections_years": years,
        "scenarios": {
            scenario: {
                "final_value": p["final_value"],
                "total_invested": p["total_invested"],
                "gains": p["total_gains"],
                "annual_rate": f"{p['annual_rate']*100:.0f}%",
            }
            for scenario, p in projections.items()
        },
        "note": "Projection simplifiée — crypto et livret traités comme cash, PEA seul investi",
    }


def get_investment_capacity(monthly_income: float = 0.0, fixed_expenses: float = 600.0) -> dict:
    """
    Calcule la capacité d'investissement DCA mensuelle selon les revenus.
    Si monthly_income=0, utilise le revenu de stage du profil (900€).
    """
    from skills.budget import calculate_investment_capacity, calculate_optimal_dca

    profile = _load_profile()

    if monthly_income <= 0:
        # Utiliser le revenu de stage par défaut du profil
        for src in profile.get("revenus", {}).get("sources", []):
            if src.get("type") == "stage" and src.get("montant_mensuel"):
                monthly_income = src["montant_mensuel"]
                break
        if monthly_income <= 0:
            monthly_income = 900.0

    capacity = calculate_investment_capacity(monthly_income, fixed_expenses)

    income_history = profile.get("revenus", {}).get("historique_mensuel", [])
    optimal = calculate_optimal_dca(income_history, fixed_expenses) if income_history else None

    result = {
        "status": "ok",
        "current_month_capacity": capacity,
        "source": "user_profile.json (tier_2) + calcul (tier_3)",
    }
    if optimal:
        result["historical_analysis"] = optimal

    return result


def compare_vs_benchmark(
    etf_ticker: str = "DCAM.PA",
    benchmark_ticker: str = "EUNL.DE",
    period: str = "1y",
) -> dict:
    """
    Compare la performance d'un ETF vs le benchmark MSCI World (EUNL.DE) sur la période.
    """
    from adapters.market_adapter import MarketAdapter
    from skills.benchmark import compare_returns, calculate_dca_vs_lumpsum

    adapter = MarketAdapter()
    hist_etf = adapter.get_etf_history(etf_ticker, period)
    hist_bench = adapter.get_etf_history(benchmark_ticker, period)

    if "error" in hist_etf:
        return {"status": "error", "error": f"{etf_ticker}: {hist_etf['error']}"}
    if "error" in hist_bench:
        return {"status": "error", "error": f"{benchmark_ticker}: {hist_bench['error']}"}

    prices_etf = [p["close"] for p in hist_etf.get("points", [])]
    prices_bench = [p["close"] for p in hist_bench.get("points", [])]

    if len(prices_etf) < 2 or len(prices_bench) < 2:
        return {"status": "error", "error": "Données insuffisantes pour comparaison"}

    comparison = compare_returns(prices_etf, prices_bench, etf_ticker, benchmark_ticker)
    dca_vs_ls = calculate_dca_vs_lumpsum(prices_etf, monthly_amount=200.0)

    return {
        "status": "ok",
        "period": period,
        "benchmark_comparison": comparison,
        "dca_vs_lumpsum": dca_vs_ls,
        "source": f"Yahoo Finance (tier_2) — {etf_ticker} vs {benchmark_ticker}",
    }


def simulate_portfolio(
    world_pct: float = 70.0,
    crypto_pct: float = 10.0,
    savings_pct: float = 20.0,
) -> dict:
    """
    Simule un changement d'allocation cible et compare au profil actuel.
    Les pourcentages doivent totaliser 100.
    world_pct: % en ETF World PEA, crypto_pct: % crypto, savings_pct: % liquidités.
    """
    from skills.simulation import simulate_allocation, compare_vs_model_portfolio, get_crypto_alert

    total = world_pct + crypto_pct + savings_pct
    if abs(total - 100) > 1:
        return {"status": "error", "error": f"Les % doivent totaliser 100 (actuel: {total})"}

    profile = _load_profile()
    pat = profile["patrimoine"]

    crypto_val = pat["crypto"]["valeur_estimee"]
    savings_val = pat.get("epargne_revolut", {}).get("montant", 0) + pat.get("sg_livret_jeune", {}).get("montant", 0)
    pea_val = pat["pea"].get("valeur_actuelle", 0)
    total_val = crypto_val + savings_val + pea_val

    if total_val <= 0:
        return {"status": "error", "error": "Patrimoine total = 0, impossible de simuler"}

    current_alloc = {
        "world": pea_val / total_val,
        "crypto": crypto_val / total_val,
        "savings": savings_val / total_val,
    }
    target_alloc = {
        "world": world_pct / 100,
        "crypto": crypto_pct / 100,
        "savings": savings_pct / 100,
    }

    simulation = simulate_allocation(current_alloc, target_alloc, total_val)
    model_comparison = compare_vs_model_portfolio(target_alloc)
    crypto_alert = get_crypto_alert(crypto_val, total_val)

    return {
        "status": "ok",
        "simulation": simulation,
        "model_comparison": model_comparison,
        "crypto_alert": crypto_alert,
        "source": "user_profile.json (tier_2) + calcul (tier_3)",
    }


def get_dca_timing(ticker: str) -> dict:
    """
    Score de timing pour un achat DCA sur l'ETF donné.
    Récupère l'historique 1y, calcule le score percentile.
    """
    from adapters.market_adapter import MarketAdapter
    from skills.timing import calculate_timing_score

    adapter = MarketAdapter()
    history = adapter.get_etf_history(ticker, "1y")

    if "error" in history:
        return {"status": "error", "ticker": ticker, "error": history["error"]}

    prices = [p["close"] for p in history.get("points", [])]

    if len(prices) < 2:
        return {"status": "error", "ticker": ticker, "error": "Pas assez de données historiques"}

    score_data = calculate_timing_score(prices)

    if score_data["score"] <= 30:
        advice = "Bon moment pour passer l'ordre mensuel Fortuneo"
    elif score_data["score"] <= 70:
        advice = "Prix dans la moyenne historique — DCA mensuel à maintenir"
    else:
        advice = "Prix élevé vs historique — le DCA mensuel reste pertinent (ne pas timer le marché)"

    return {
        "status": "ok",
        "ticker": ticker,
        "timing": score_data,
        "advice": advice,
        "source": "Yahoo Finance (tier_2) + analyse (tier_3)",
    }


def _compute_next_actions(profile: dict, diversification: dict, liquid: float, total: float) -> list[str]:
    """Génère une liste d'actions prioritaires basée sur le profil."""
    actions = []

    # PEA non ouvert
    if profile["patrimoine"]["pea"]["statut"] == "à ouvrir":
        actions.append(
            f"🎯 Ouvrir le PEA Fortuneo avec {profile['patrimoine']['pea']['apport_initial_cible']}€"
            f" — parrainage: {profile['patrimoine']['pea']['parrainage']['bonus']}€ offerts"
        )

    # Liquidité insuffisante
    liq_min = profile["regles_personnelles"]["liquidite_minimale"]
    if liquid < liq_min:
        actions.append(f"⚠️ Reconstituer la liquidité de précaution : {liquid:.0f}€ → {liq_min}€")

    # Diversification faible
    if diversification["score"] < 60:
        actions.append(f"📊 Améliorer la diversification (score: {diversification['score']}/100)")

    # Warnings diversification
    for warning in diversification.get("warnings", []):
        actions.append(warning)

    return actions

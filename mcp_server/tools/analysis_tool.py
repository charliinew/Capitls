"""
Tool MCP : analyses financières et recommandations.
Orchestre les skills (calculs purs) avec le profil utilisateur (source unique des données
personnelles) et les données de référence (taux, catalogue ETF rafraîchis automatiquement).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from mcp_server.profile import store
from mcp_server.tools import portfolio_tool, reference_tool
from skills.dca import calculate_broker_dca_plan, calculate_optimal_dca_schedule
from skills.diversification import analyze_diversification
from skills.etf import calculate_ter_impact, compare_etfs, recommend_etf_for_pea
from skills.projection import project_portfolio_multi_scenarios
from skills.situation_review import LIQUID_CATEGORIES, liquidity

logger = logging.getLogger(__name__)

INVESTED_CATEGORIES = ("pea", "cto", "life_insurance", "retirement")


def _missing(field: str, question: str) -> dict:
    return {
        "status": "missing_info",
        "field": field,
        "question": question,
        "next_step": "Poser la question puis enregistrer la réponse avec update_situation()",
    }


def _catalog() -> dict:
    return reference_tool.get_reference().get("etfs", {})


def _active_income(profile) -> float:
    current = datetime.now(timezone.utc).strftime("%Y-%m")
    return sum(
        s.monthly_amount or 0.0 for s in profile.income.sources if s.regular and (s.end is None or s.end >= current)
    )


def analyze_portfolio() -> dict:
    """Analyse complète : diversification, liquidité, règles personnelles, actions prioritaires."""
    portfolio = portfolio_tool.get_portfolio()
    if portfolio["status"] != "ok":
        return portfolio
    profile = store.require_profile()
    rules = profile.rules

    diversification = analyze_diversification(
        {"accounts": portfolio["accounts"]}, rules.liquidity_min, rules.crypto_max_pct
    )
    liq = liquidity(portfolio["accounts"])

    actions = []
    if profile.pea.status in ("planned", "opening"):
        broker = f" chez {profile.pea.broker.name}" if profile.pea.broker.name else ""
        actions.append(f"🎯 Finaliser l'ouverture du PEA{broker} — le délai fiscal démarre au 1er versement")
        if profile.pea.referral:
            actions.append(f"🎁 Parrainage en cours : {profile.pea.referral}")
    if rules.liquidity_min is not None and liq["total"] < rules.liquidity_min:
        actions.append(f"⚠️ Reconstituer l'épargne de précaution : {liq['total']:.0f}€ → {rules.liquidity_min:.0f}€")
    if diversification["score"] < 60:
        actions.append(f"📊 Améliorer la diversification (score: {diversification['score']}/100)")
    actions += diversification.get("warnings", [])
    unclassified = [a.name for a in profile.accounts if a.needs_classification]
    if unclassified:
        actions.append(f"🗂️ Comptes à classer : {', '.join(unclassified)}")

    return {
        "status": "ok",
        "total_net_worth": portfolio["total_net_worth"],
        "diversification": diversification,
        "liquidity": {
            **liq,
            "minimum_required": rules.liquidity_min,
            "status": None
            if rules.liquidity_min is None
            else ("ok" if liq["total"] >= rules.liquidity_min else "insuffisant"),
        },
        "pea_status": profile.pea.status,
        "next_actions": actions,
        **({"warning": portfolio["warning"]} if "warning" in portfolio else {}),
        "source": "Finary (tier_2) + profil utilisateur + calcul (tier_3)",
    }


def recommend_dca_plan(
    monthly_budget: float | None = None,
    etf_ticker: str | None = None,
    etf_price: float | None = None,
    years: int = 10,
) -> dict:
    """Plan DCA adapté aux frais du courtier déclaré dans le profil."""
    from mcp_server.tools import market_tool

    profile = store.require_profile()
    pea = profile.pea
    budget = monthly_budget or pea.monthly_target
    if not budget:
        return _missing("pea.monthly_target", "Combien souhaitez-vous investir chaque mois ?")

    catalog = _catalog()
    recommendation = recommend_etf_for_pea(catalog, pea.broker.name, budget)
    ticker = (etf_ticker or pea.target_etf or recommendation.get("recommended", {}).get("ticker") or "").upper()

    price_error = None
    if etf_price is None and ticker:
        quote = market_tool.get_etf_quote(ticker)
        etf_price = quote.get("price")
        price_error = quote.get("error")

    broker = pea.broker
    return {
        "status": "ok",
        "monthly_budget": budget,
        "etf": ticker,
        "broker": broker.model_dump(),
        "order": calculate_broker_dca_plan(budget, etf_price, broker.free_order_max) if etf_price else None,
        "price_error": price_error,
        "broker_constraint": (
            f"{broker.free_orders_per_month or '?'} ordre(s) gratuit(s)/mois ≤ {broker.free_order_max:.0f}€ chez {broker.name}"
            if broker.free_order_max
            else "Conditions de frais du courtier non renseignées — les demander à l'utilisateur"
        ),
        "initial_investment_schedule": (
            calculate_optimal_dca_schedule(pea.initial_deposit_target, months=6, initial_weight=0.25)
            if pea.initial_deposit_target and not pea.orders
            else None
        ),
        "projections": {
            name: {k: p[k] for k in ("final_value", "total_invested", "total_gains", "annual_rate")}
            for name, p in project_portfolio_multi_scenarios(0, budget, years).items()
        },
        "etf_recommendation": recommendation,
        "referral": pea.referral,
    }


def compare_etf_options(tickers: list[str] | None = None) -> dict:
    """Comparaison des ETF du catalogue + impact des frais sur 10 ans (le moins cher vs le plus cher)."""
    catalog = _catalog()
    comparison = compare_etfs(tickers or list(catalog), catalog)
    with_ter = [e for e in comparison if e.get("ter") is not None]
    ter_impact = None
    if len(with_ter) >= 2:
        profile = store.load_profile()
        monthly = (profile.pea.monthly_target if profile else None) or 100.0
        ter_impact = calculate_ter_impact(0, monthly, 10, with_ter[0]["ter"], with_ter[-1]["ter"])
        ter_impact["compared"] = f"{with_ter[0]['ticker']} vs {with_ter[-1]['ticker']}, {monthly:.0f}€/mois"
    return {
        "comparison": comparison,
        "ter_impact_10y": ter_impact,
        "recommendation": recommend_etf_for_pea(catalog),
        "source": "justETF (tier_1) via données de référence",
    }


def project_wealth(years: int = 10, monthly_contribution: float | None = None) -> dict:
    """Projection du patrimoine : la part investie croît selon les scénarios, le reste est constant."""
    portfolio = portfolio_tool.get_portfolio()
    if portfolio["status"] != "ok":
        return portfolio
    profile = store.require_profile()
    accounts = portfolio["accounts"]

    invested = sum(a["balance"] for a in accounts if a["category"] in INVESTED_CATEGORIES)
    crypto = sum(a["balance"] for a in accounts if a["category"] == "crypto")
    liquid = sum(a["balance"] for a in accounts if a["category"] in LIQUID_CATEGORIES)
    other = portfolio["total_net_worth"] - invested - crypto - liquid

    contrib = monthly_contribution if monthly_contribution is not None else profile.pea.monthly_target
    if contrib is None:
        return _missing("pea.monthly_target", "Combien comptez-vous investir chaque mois ?")

    constant = crypto + liquid + other
    scenarios = project_portfolio_multi_scenarios(invested, contrib, years)
    return {
        "status": "ok",
        "current_snapshot": {
            "total": portfolio["total_net_worth"],
            "invested": round(invested, 2),
            "crypto": round(crypto, 2),
            "liquid": round(liquid, 2),
            "other": round(other, 2),
        },
        "monthly_contribution": contrib,
        "projections_years": years,
        "scenarios": {
            name: {
                "invested_final": p["final_value"],
                "total_final": round(p["final_value"] + constant, 2),
                "total_contributed": p["total_invested"],
                "gains": p["total_gains"],
                "annual_rate": f"{p['annual_rate'] * 100:.0f}%",
            }
            for name, p in scenarios.items()
        },
        "note": "Hypothèses de rendement indicatives ; crypto, liquidités et autres actifs supposés constants",
    }


def get_investment_capacity(monthly_income: float = 0.0, fixed_expenses: float | None = None) -> dict:
    """Capacité DCA mensuelle. Sans arguments : revenus actifs et dépenses fixes du profil."""
    from skills.budget import calculate_investment_capacity, calculate_optimal_dca

    profile = store.require_profile()
    income = monthly_income if monthly_income > 0 else _active_income(profile)
    expenses = fixed_expenses if fixed_expenses is not None else profile.income.fixed_expenses
    if income <= 0:
        return _missing("income.sources", "Quels sont vos revenus mensuels actuels (type, montant) ?")
    if expenses is None:
        return _missing("income.fixed_expenses", "À combien estimez-vous vos dépenses fixes mensuelles ?")

    free_max = profile.pea.broker.free_order_max
    history = [h.model_dump() for h in profile.income.history]
    result = {
        "status": "ok",
        "current_month_capacity": calculate_investment_capacity(income, expenses, free_order_max=free_max),
        "source": "profil utilisateur + calcul (tier_3)",
    }
    if history:
        result["historical_analysis"] = calculate_optimal_dca(history, expenses, free_order_max=free_max)
    return result


def compare_vs_benchmark(etf_ticker: str, benchmark_ticker: str = "EUNL.DE", period: str = "1y") -> dict:
    """Performance d'un ETF vs un benchmark (par défaut iShares Core MSCI World, EUNL.DE)."""
    from mcp_server.tools import market_tool
    from skills.benchmark import calculate_dca_vs_lumpsum, compare_returns

    hist_etf = market_tool.get_etf_history(etf_ticker, period)
    hist_bench = market_tool.get_etf_history(benchmark_ticker, period)
    if "error" in hist_etf:
        return {"status": "error", "error": f"{etf_ticker}: {hist_etf['error']}"}
    if "error" in hist_bench:
        return {"status": "error", "error": f"{benchmark_ticker}: {hist_bench['error']}"}

    prices_etf = [p["close"] for p in hist_etf.get("points", [])]
    prices_bench = [p["close"] for p in hist_bench.get("points", [])]
    if len(prices_etf) < 2 or len(prices_bench) < 2:
        return {"status": "error", "error": "Données insuffisantes pour comparaison"}

    profile = store.load_profile()
    monthly = (profile.pea.monthly_target if profile else None) or 100.0
    return {
        "status": "ok",
        "period": period,
        "benchmark_comparison": compare_returns(prices_etf, prices_bench, etf_ticker, benchmark_ticker),
        "dca_vs_lumpsum": calculate_dca_vs_lumpsum(prices_etf, monthly_amount=monthly),
        "source": f"Yahoo Finance (tier_2) — {etf_ticker} vs {benchmark_ticker}",
    }


def simulate_portfolio(world_pct: float, crypto_pct: float, savings_pct: float) -> dict:
    """Simule une allocation cible (investi / crypto / liquidités, en %) vs l'allocation actuelle."""
    from skills.simulation import (
        CRYPTO_ALERT_THRESHOLD,
        compare_vs_model_portfolio,
        get_crypto_alert,
        simulate_allocation,
    )

    total_pct = world_pct + crypto_pct + savings_pct
    if abs(total_pct - 100) > 1:
        return {"status": "error", "error": f"Les % doivent totaliser 100 (actuel: {total_pct})"}

    portfolio = portfolio_tool.get_portfolio()
    if portfolio["status"] != "ok":
        return portfolio
    profile = store.require_profile()
    accounts = portfolio["accounts"]
    invested = sum(a["balance"] for a in accounts if a["category"] in INVESTED_CATEGORIES)
    crypto = sum(a["balance"] for a in accounts if a["category"] == "crypto")
    savings = liquidity(accounts)["total"]
    total = invested + crypto + savings
    if total <= 0:
        return {"status": "error", "error": "Patrimoine total = 0, impossible de simuler"}

    current = {"world": invested / total, "crypto": crypto / total, "savings": savings / total}
    target = {"world": world_pct / 100, "crypto": crypto_pct / 100, "savings": savings_pct / 100}
    threshold = profile.rules.crypto_max_pct or CRYPTO_ALERT_THRESHOLD

    return {
        "status": "ok",
        "simulation": simulate_allocation(current, target, total),
        "model_comparison": compare_vs_model_portfolio(target),
        "crypto_alert": get_crypto_alert(crypto, total, threshold),
        "source": "Finary (tier_2) + profil + calcul (tier_3)",
    }


def get_dca_timing(ticker: str) -> dict:
    """Score de timing (percentile prix / moyenne 3 mois sur 1 an d'historique)."""
    from mcp_server.tools import market_tool
    from skills.timing import calculate_timing_score

    history = market_tool.get_etf_history(ticker, "1y")
    if "error" in history:
        return {"status": "error", "ticker": ticker, "error": history["error"]}
    prices = [p["close"] for p in history.get("points", [])]
    if len(prices) < 2:
        return {"status": "error", "ticker": ticker, "error": "Pas assez de données historiques"}

    score = calculate_timing_score(prices)
    if score["score"] <= 30:
        advice = "Prix sous sa moyenne récente — bon moment pour l'ordre mensuel"
    elif score["score"] <= 70:
        advice = "Prix dans la moyenne — maintenir le DCA mensuel"
    else:
        advice = "Prix au-dessus de sa moyenne récente — le DCA reste pertinent (ne pas chercher à timer le marché)"

    return {
        "status": "ok",
        "ticker": ticker,
        "timing": score,
        "advice": advice,
        "source": "Yahoo Finance (tier_2) + analyse (tier_3)",
    }

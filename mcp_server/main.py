"""
Capitls — Serveur MCP de finance personnelle.
Utilise FastMCP (https://github.com/prefecthq/fastmcp)

Enregistrement Claude Code : .claude/settings.json (déjà configuré)
Enregistrement Claude Desktop : ~/Library/Application Support/Claude/claude_desktop_config.json

Pour lancer en test : uv run python -m mcp_server.main
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.WARNING)

# Assurer que le répertoire racine est dans le path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

from fastmcp import FastMCP

from mcp_server.tools import analysis_tool, market_tool, portfolio_tool, regulation_tool


def _last_sync_date() -> str:
    """Retourne la date du dernier sync Finary depuis user_profile.json."""
    try:
        import json
        profile_path = Path(__file__).parent / "context" / "user_profile.json"
        with open(profile_path, encoding="utf-8") as f:
            profile = json.load(f)
        return profile.get("snapshot_finary", {}).get("date", profile.get("last_updated", "inconnue"))
    except Exception:
        return "inconnue"

mcp = FastMCP(
    name="capitls",
    instructions=(
        "Agent financier personnel expert du marché français. "
        "Accès au portfolio Finary, données de marché ETF/crypto, "
        "règles PEA/fiscalité françaises, et calculs de projections DCA. "
        "RÈGLE IMPÉRATIVE : toujours appeler sync_profile() en premier avant toute analyse "
        "ou recommandation portant sur le portfolio ou les soldes. "
        "Toujours indiquer le tier de la source utilisée dans les réponses."
    ),
)

# --- Tools : Portfolio Finary ---

@mcp.tool
def sync_profile() -> dict:
    """Synchronise user_profile.json avec les soldes Finary en temps réel. À appeler en début de session ou quand les données semblent obsolètes."""
    result = portfolio_tool.sync_profile()
    if result.get("status") == "auth_error":
        last_sync = _last_sync_date()
        raise ValueError(
            f"⚠️ SESSION FINARY EXPIRÉE — données périmées depuis le {last_sync}. "
            f"Les conseils basés sur les soldes ne sont PAS fiables. "
            f"Pour reconnecter : make finary-signin MFA=<code_2fa>"
        )
    return result


@mcp.tool
def get_portfolio() -> dict:
    """Récupère le portfolio complet depuis Finary (comptes, soldes, patrimoine total)."""
    result = portfolio_tool.get_portfolio()
    if result.get("status") == "auth_error":
        last_sync = _last_sync_date()
        raise ValueError(
            f"⚠️ SESSION FINARY EXPIRÉE — données périmées depuis le {last_sync}. "
            f"Pour reconnecter : make finary-signin MFA=<code_2fa>"
        )
    return result


@mcp.tool
def get_accounts_summary() -> dict:
    """Résumé des comptes avec vérification des règles personnelles (liquidité, allocation crypto)."""
    result = portfolio_tool.get_accounts_summary()
    if result.get("status") == "auth_error":
        last_sync = _last_sync_date()
        raise ValueError(
            f"⚠️ SESSION FINARY EXPIRÉE — données périmées depuis le {last_sync}. "
            f"Pour reconnecter : make finary-signin MFA=<code_2fa>"
        )
    return result


@mcp.tool
def record_decision(decision: str, details: str) -> dict:
    """Enregistre une décision financière dans l'historique. decision: description courte, details: JSON ou texte."""
    if len(decision) > 500:
        return {"status": "error", "error": "Champ 'decision' trop long (max 500 chars)"}
    try:
        det = json.loads(details)
    except Exception:
        det = {"note": details[:1000]}
    return portfolio_tool.update_decision_history(decision, det)


# --- Tools : Marché ---

@mcp.tool
def get_etf_price(ticker: str) -> dict:
    """Prix et variation d'un ETF Euronext Paris. ticker: DCAM, WPEA, CW8, CW8.PA, etc."""
    return market_tool.get_etf_quote(ticker)


@mcp.tool
def get_etf_history(ticker: str, period: str = "1y") -> dict:
    """Historique prix d'un ETF. period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y"""
    return market_tool.get_etf_history(ticker, period)


@mcp.tool
def get_world_etfs() -> dict:
    """Snapshot de tous les ETF MSCI World PEA principaux (DCAM, WPEA, CW8, EWLD)."""
    return market_tool.get_world_etfs_snapshot()


@mcp.tool
def get_crypto_prices(symbols: str = "BTC,ETH") -> dict:
    """Prix crypto en EUR. symbols: liste séparée par virgules (ex: BTC,ETH,SOL)"""
    symbol_list = [s.strip() for s in symbols.split(",")]
    return market_tool.get_crypto_prices(symbol_list)


# --- Tools : Réglementation ---

@mcp.tool
def get_pea_rules() -> dict:
    """Règles PEA en vigueur 2026 : plafonds, fiscalité avant/après 5 ans, retraits."""
    return regulation_tool.get_pea_rules()


@mcp.tool
def get_tax_comparison(gross_gains: float) -> dict:
    """Compare l'imposition : PEA avant 5 ans / PEA après 5 ans / flat tax CTO pour un montant de gains."""
    return regulation_tool.get_tax_comparison(gross_gains)


@mcp.tool
def check_etf_pea_eligibility(isin: str) -> dict:
    """Vérifie si un ISIN est éligible PEA (base 2026)."""
    return regulation_tool.check_pea_eligibility(isin)


# --- Tools : Analyse et recommandations ---

@mcp.tool
def analyze_portfolio(portfolio_json: str) -> dict:
    """
    Analyse complète du portfolio : diversification, liquidité, alertes.
    portfolio_json: résultat de get_portfolio() sérialisé en JSON string.
    """
    portfolio = json.loads(portfolio_json)
    return analysis_tool.analyze_portfolio(portfolio)


@mcp.tool
def recommend_dca_plan(
    monthly_budget: float = 200.0,
    etf_ticker: str = "DCAM",
    etf_price: float = 0.0,
    years: int = 10,
) -> dict:
    """
    Plan DCA complet adapté à Fortuneo (1 ordre/mois < 500€ gratuit).
    etf_price: prix actuel de l'ETF (0 pour ignorer le calcul d'ordre).
    """
    price = etf_price if etf_price > 0 else None
    return analysis_tool.recommend_dca_plan(monthly_budget, etf_ticker, price, years)


@mcp.tool
def compare_etfs(tickers: str = "DCAM,WPEA,CW8") -> dict:
    """Comparaison des ETF MSCI World PEA. tickers: liste séparée par virgules."""
    ticker_list = [t.strip() for t in tickers.split(",")]
    return analysis_tool.compare_etf_options(ticker_list)


@mcp.tool
def project_wealth(years: int = 10, monthly_contribution: float = 200.0) -> dict:
    """Projection du patrimoine sur N ans, multi-scénarios (pessimiste/neutre/optimiste)."""
    return analysis_tool.project_wealth(years, monthly_contribution)


@mcp.tool
def get_pea_status() -> dict:
    """Statut complet du PEA : countdown 5 ans, performance, prochain ordre recommandé."""
    return portfolio_tool.get_pea_status()


@mcp.tool
def record_pea_order(date: str, ticker: str, amount: float, price: float) -> dict:
    """Enregistre un ordre PEA exécuté. date: YYYY-MM-DD, ticker: DCAM/WPEA, amount: montant €, price: prix/part."""
    return portfolio_tool.record_pea_order(date, ticker, amount, price)


@mcp.tool
def get_dca_timing(ticker: str = "DCAM") -> dict:
    """Score de timing DCA 0-100 (percentile prix vs moyenne 52 semaines). ticker: DCAM.PA, WPEA.PA, etc."""
    return analysis_tool.get_dca_timing(ticker)


# --- Tools : V4 — Budget, Benchmark, Simulation ---

@mcp.tool
def get_dca_reminder() -> dict:
    """Vérifie si l'ordre DCA mensuel a déjà été passé ce mois. Retourne un rappel si nécessaire."""
    return portfolio_tool.get_dca_reminder()


@mcp.tool
def record_monthly_income(month: str, income: float, source: str = "stage") -> dict:
    """Enregistre un revenu mensuel pour le suivi de capacité DCA. month: YYYY-MM, source: stage/freelance."""
    return portfolio_tool.record_monthly_income(month, income, source)


@mcp.tool
def get_investment_capacity(monthly_income: float = 0.0, fixed_expenses: float = 600.0) -> dict:
    """Calcule la capacité DCA mensuelle selon revenus. monthly_income=0 → utilise le profil (stage 900€)."""
    return analysis_tool.get_investment_capacity(monthly_income, fixed_expenses)


@mcp.tool
def compare_vs_benchmark(
    etf_ticker: str = "DCAM.PA",
    benchmark_ticker: str = "EUNL.DE",
    period: str = "1y",
) -> dict:
    """Compare la performance d'un ETF vs MSCI World (EUNL.DE). period: 1y, 2y, 5y."""
    return analysis_tool.compare_vs_benchmark(etf_ticker, benchmark_ticker, period)


@mcp.tool
def simulate_portfolio(
    world_pct: float = 70.0,
    crypto_pct: float = 10.0,
    savings_pct: float = 20.0,
) -> dict:
    """Simule un changement d'allocation cible (world/crypto/savings en %). Total doit faire 100."""
    return analysis_tool.simulate_portfolio(world_pct, crypto_pct, savings_pct)


if __name__ == "__main__":
    mcp.run()

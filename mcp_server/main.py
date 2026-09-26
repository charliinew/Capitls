"""
Capitls — Serveur MCP de finance personnelle (FastMCP, transport stdio).

Enregistrement Claude Code : .mcp.json (généré par `make setup`, gitignoré)
Lancement manuel : uv run python -m mcp_server.main
"""

from __future__ import annotations

import functools
import json
import logging

from dotenv import load_dotenv
from fastmcp import FastMCP

from mcp_server.profile.store import ProfileMissingError
from mcp_server.tools import (
    analysis_tool,
    market_tool,
    portfolio_tool,
    profile_tool,
    reference_tool,
    regulation_tool,
)

logging.basicConfig(level=logging.WARNING)
load_dotenv()

mcp = FastMCP(
    name="capitls",
    instructions=(
        "Agent financier personnel spécialisé marché français (PEA, ETF, épargne réglementée, DCA). "
        "DÉBUT DE SESSION : appeler start_session() — il met à jour les taux (si > 24h), synchronise "
        "Finary, liste les actualités réglementaires et indique si une revue de situation est due. "
        "Si une revue est due, ou dès que l'utilisateur évoque un changement (revenus, comptes, "
        "projet, PEA…), appeler review_situation(), présenter le résumé point par point, demander "
        "« Votre situation a-t-elle changé depuis le … ? », puis update_situation() ou "
        "confirm_situation_unchanged(). "
        "Ne jamais citer un taux ou un plafond de mémoire : utiliser les tools (données service-public "
        "/ justETF datées). Si un outil renvoie status=missing_info, poser la question à l'utilisateur. "
        "Toujours indiquer le tier de la source."
    ),
)


def _profile_guard(fn):
    """Transforme l'absence de profil en invitation à l'onboarding plutôt qu'en erreur brute."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ProfileMissingError as e:
            return {"status": "onboarding_required", "error": str(e), "next_step": "review_situation()"}

    return wrapper


# --- Session & profil ---


@mcp.tool
def start_session() -> dict:
    """À appeler en début de session : taux à jour, synchro Finary, actualités réglementaires, revue de situation si due."""
    return profile_tool.start_session()


@mcp.tool
def review_situation() -> dict:
    """Résumé point par point de la situation enregistrée + changements probables. Onboarding si aucun profil."""
    return profile_tool.review_situation()


@mcp.tool
def update_situation(changes_json: str) -> dict:
    """
    Met à jour le profil avec un profil partiel JSON. Les listes avec `id` (accounts, income.sources)
    sont fusionnées par id ; {"id": "...", "_delete": true} supprime un élément.
    Ex: {"income": {"sources": [{"id": "salaire_1", "type": "salaire", "monthly_amount": 1800}]}}
    Catégories de compte : checking, savings, regulated_savings, pea, cto, life_insurance, retirement,
    crypto, pro_reserved, other. Statut PEA : none, planned, opening, open, closed.
    """
    return profile_tool.update_situation(changes_json)


@mcp.tool
@_profile_guard
def confirm_situation_unchanged() -> dict:
    """L'utilisateur confirme que sa situation n'a pas changé depuis la dernière revue."""
    return profile_tool.confirm_situation_unchanged()


# --- Données de référence (taux, plafonds, fiscalité, ETF) ---


@mcp.tool
def get_reference_data(force_refresh: bool = False) -> dict:
    """Taux, plafonds, fiscalité et catalogue ETF à jour (service-public.fr, justETF), avec date de vérification."""
    return reference_tool.get_reference_data(force_refresh)


@mcp.tool
def get_regulatory_news(since: str = "") -> dict:
    """Changements de taux / fiscalité / frais ETF depuis la dernière consultation (ou depuis `since`, YYYY-MM-DD)."""
    return reference_tool.get_regulatory_news(since or None)


@mcp.tool
def record_verified_fact(key: str, value: float, source_url: str) -> dict:
    """Enregistre une valeur de référence vérifiée sur une source officielle (si le fetch automatique a échoué)."""
    return reference_tool.record_verified_fact(key, value, source_url)


@mcp.tool
def get_savings_rates() -> dict:
    """Taux et plafonds de l'épargne réglementée : Livret A, LDDS, LEP (+ plafond de revenus), Livret Jeune."""
    return regulation_tool.get_savings_rates()


# --- Portfolio Finary ---


@mcp.tool
def sync_profile() -> dict:
    """Synchronise le profil avec les soldes Finary live. Les nouveaux comptes sont ajoutés « à classer »."""
    result = portfolio_tool.sync_profile()
    if result.get("status") == "auth_error":
        raise ValueError(
            "⚠️ SESSION FINARY EXPIRÉE — les soldes du profil ne sont plus à jour, les conseils basés "
            "sur les soldes ne sont PAS fiables. Pour reconnecter : make finary-signin"
        )
    return result


@mcp.tool
def get_portfolio() -> dict:
    """Portfolio complet (comptes, soldes, crypto). Synchro Finary automatique si la dernière date de plus d'1h."""
    return portfolio_tool.get_portfolio()


@mcp.tool
@_profile_guard
def get_accounts_summary() -> dict:
    """Résumé des comptes + vérification des règles personnelles (liquidité minimale, part crypto)."""
    return portfolio_tool.get_accounts_summary()


@mcp.tool
@_profile_guard
def record_decision(decision: str, details: str) -> dict:
    """Enregistre une décision financière. decision: description courte, details: JSON ou texte."""
    if len(decision) > 500:
        return {"status": "error", "error": "Champ 'decision' trop long (max 500 chars)"}
    try:
        det = json.loads(details)
        if not isinstance(det, dict):
            det = {"value": det}
    except json.JSONDecodeError:
        det = {"note": details[:1000]}
    return portfolio_tool.update_decision_history(decision, det)


@mcp.tool
@_profile_guard
def get_pea_status() -> dict:
    """Statut du PEA : compte à rebours fiscal, performance au prix actuel, prochain ordre recommandé."""
    return portfolio_tool.get_pea_status()


@mcp.tool
@_profile_guard
def record_pea_order(date: str, ticker: str, amount: float, price: float) -> dict:
    """Enregistre un ordre PEA exécuté. date: YYYY-MM-DD, ticker: ex DCAM, amount: montant €, price: prix/part."""
    return portfolio_tool.record_pea_order(date, ticker, amount, price)


@mcp.tool
@_profile_guard
def get_dca_reminder() -> dict:
    """Vérifie si l'ordre PEA du mois a déjà été enregistré."""
    return portfolio_tool.get_dca_reminder()


@mcp.tool
def record_monthly_income(month: str, income: float, source: str) -> dict:
    """Enregistre un revenu mensuel. month: YYYY-MM, source: salaire/stage/freelance/autre."""
    return portfolio_tool.record_monthly_income(month, income, source)


# --- Marché ---


@mcp.tool
def get_etf_price(ticker: str) -> dict:
    """Prix et variation d'un ETF (Euronext Paris par défaut). ticker: DCAM, WPEA, CW8.PA, EUNL.DE…"""
    return market_tool.get_etf_quote(ticker)


@mcp.tool
def get_etf_history(ticker: str, period: str = "1y") -> dict:
    """Historique prix d'un ETF. period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y"""
    return market_tool.get_etf_history(ticker, period)


@mcp.tool
def get_world_etfs() -> dict:
    """Prix de tous les ETF du catalogue de référence (ETF monde éligibles PEA)."""
    return market_tool.get_world_etfs_snapshot()


@mcp.tool
def get_crypto_prices(symbols: str = "BTC,ETH") -> dict:
    """Prix crypto en EUR. symbols: liste séparée par virgules (ex: BTC,ETH,SOL)"""
    return market_tool.get_crypto_prices([s.strip() for s in symbols.split(",") if s.strip()])


# --- Réglementation ---


@mcp.tool
def get_pea_rules() -> dict:
    """Règles PEA à jour : plafonds, fiscalité avant/après la durée d'exonération, retraits."""
    return regulation_tool.get_pea_rules()


@mcp.tool
def get_tax_comparison(gross_gains: float) -> dict:
    """Imposition d'un gain : PEA (avant/après exonération), CTO (flat tax), assurance-vie (avant/après 8 ans)."""
    return regulation_tool.get_tax_comparison(gross_gains)


@mcp.tool
def check_etf_pea_eligibility(isin: str) -> dict:
    """Éligibilité PEA d'un ISIN (catalogue de référence, sinon fiche justETF en direct)."""
    return regulation_tool.check_pea_eligibility(isin)


# --- Analyse et recommandations ---


@mcp.tool
@_profile_guard
def analyze_portfolio() -> dict:
    """Analyse complète : diversification, liquidité, règles personnelles, actions prioritaires."""
    return analysis_tool.analyze_portfolio()


@mcp.tool
@_profile_guard
def recommend_dca_plan(
    monthly_budget: float = 0.0,
    etf_ticker: str = "",
    etf_price: float = 0.0,
    years: int = 10,
) -> dict:
    """
    Plan DCA adapté aux frais du courtier du profil. Paramètres à 0/vide = valeurs du profil
    (objectif mensuel, ETF cible) et prix actuel récupéré automatiquement.
    """
    return analysis_tool.recommend_dca_plan(monthly_budget or None, etf_ticker or None, etf_price or None, years)


@mcp.tool
def compare_etfs(tickers: str = "") -> dict:
    """Comparaison des ETF (TER, encours, éligibilité PEA) + impact des frais sur 10 ans. Vide = tout le catalogue."""
    ticker_list = [t.strip() for t in tickers.split(",") if t.strip()] or None
    return analysis_tool.compare_etf_options(ticker_list)


@mcp.tool
@_profile_guard
def project_wealth(years: int = 10, monthly_contribution: float = -1.0) -> dict:
    """Projection du patrimoine sur N ans (scénarios pessimiste/neutre/optimiste). -1 = objectif mensuel du profil."""
    return analysis_tool.project_wealth(years, None if monthly_contribution < 0 else monthly_contribution)


@mcp.tool
def get_dca_timing(ticker: str) -> dict:
    """Score 0-100 : position du prix actuel vs sa moyenne 3 mois sur 1 an (≤30 bas, >70 haut)."""
    return analysis_tool.get_dca_timing(ticker)


@mcp.tool
@_profile_guard
def get_investment_capacity(monthly_income: float = 0.0, fixed_expenses: float = -1.0) -> dict:
    """Capacité d'investissement mensuelle. 0 / -1 = revenus actifs et dépenses fixes du profil."""
    return analysis_tool.get_investment_capacity(monthly_income, None if fixed_expenses < 0 else fixed_expenses)


@mcp.tool
def compare_vs_benchmark(etf_ticker: str, benchmark_ticker: str = "EUNL.DE", period: str = "1y") -> dict:
    """Performance d'un ETF vs un benchmark (défaut : iShares Core MSCI World, EUNL.DE). period: 1y, 2y, 5y."""
    return analysis_tool.compare_vs_benchmark(etf_ticker, benchmark_ticker, period)


@mcp.tool
@_profile_guard
def simulate_portfolio(world_pct: float = 70.0, crypto_pct: float = 10.0, savings_pct: float = 20.0) -> dict:
    """Simule une allocation cible (investi / crypto / liquidités en %, total 100) vs l'allocation actuelle."""
    return analysis_tool.simulate_portfolio(world_pct, crypto_pct, savings_pct)


if __name__ == "__main__":
    mcp.run()

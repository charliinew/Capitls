"""
Tool MCP : données de marché (ETF, crypto).
Sources : Yahoo Finance (tier_2), CoinGecko (tier_2).
"""

from __future__ import annotations

import logging

from adapters.market_adapter import MarketAdapter

logger = logging.getLogger(__name__)

_adapter = MarketAdapter()


def _etf_tickers() -> dict[str, str]:
    """Ticker court → ticker Yahoo, depuis le catalogue ETF des données de référence."""
    from mcp_server.tools import reference_tool

    catalog = reference_tool.get_reference().get("etfs", {})
    return {t: e.get("ticker_yahoo") or f"{t}.PA" for t, e in catalog.items()}


def _yahoo_ticker(ticker: str) -> str:
    if "." in ticker and not ticker.upper().endswith(".PA"):
        return ticker  # autre place de cotation explicitement demandée (ex: EUNL.DE)
    clean = ticker.upper().replace(".PA", "")
    return _etf_tickers().get(clean, f"{clean}.PA")


# IDs CoinGecko pour les cryptos courantes
CRYPTO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOT": "polkadot",
    "AVAX": "avalanche-2",
    "LINK": "chainlink",
    "POL": "polygon-ecosystem-token",
    "USDC": "usd-coin",
    "USDT": "tether",
}


def get_etf_quote(ticker: str) -> dict:
    """
    Prix et variation d'un ETF (Euronext Paris).
    ticker : DCAM, WPEA, CW8, CW8.PA, etc.
    """
    result = _adapter.get_etf_price(_yahoo_ticker(ticker))
    result["source"] = "Yahoo Finance (tier_2) — données non officielles"
    return result


def get_etf_history(ticker: str, period: str = "1y") -> dict:
    """
    Historique prix d'un ETF.
    period : 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y
    """
    return _adapter.get_etf_history(_yahoo_ticker(ticker), period)


def get_world_etfs_snapshot() -> dict:
    """Snapshot des ETF du catalogue de référence (ETF monde éligibles PEA)."""
    results = {}
    for name, ticker in _etf_tickers().items():
        results[name] = _adapter.get_etf_price(ticker)
    return {
        "etfs": results,
        "note": "Données Yahoo Finance — vérifier sur justETF pour données officielles",
        "source": "Yahoo Finance (tier_2)",
    }


def get_crypto_prices(symbols: list[str] | None = None) -> dict:
    """
    Prix crypto en EUR.
    symbols : ['BTC', 'ETH'] ou None pour BTC+ETH par défaut
    """
    if symbols is None:
        symbols = ["BTC", "ETH"]

    coin_ids = [CRYPTO_IDS.get(s.upper(), s.lower()) for s in symbols]
    return _adapter.get_crypto_price(coin_ids, vs_currency="eur")


def get_crypto_history(symbol: str, days: int = 365) -> dict:
    """Historique prix crypto en EUR sur N jours."""
    coin_id = CRYPTO_IDS.get(symbol.upper(), symbol.lower())
    return _adapter.get_crypto_history(coin_id, days=days)

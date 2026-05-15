"""
Tool MCP : données de marché (ETF, crypto).
Sources : Yahoo Finance (tier_2), CoinGecko (tier_2).
"""

from __future__ import annotations

import logging

from adapters.market_adapter import MarketAdapter

logger = logging.getLogger(__name__)

_adapter = MarketAdapter()

# Tickers Yahoo Finance pour les principaux ETF World PEA
ETF_TICKERS = {
    "DCAM": "DCAM.PA",
    "WPEA": "WPEA.PA",
    "CW8": "CW8.PA",
    "EWLD": "EWLD.PA",
}

# IDs CoinGecko pour les cryptos courantes
CRYPTO_IDS = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
}


def get_etf_quote(ticker: str) -> dict:
    """
    Prix et variation d'un ETF (Euronext Paris).
    ticker : DCAM, WPEA, CW8, CW8.PA, etc.
    """
    # Normaliser le ticker
    clean = ticker.upper().replace(".PA", "")
    yahoo_ticker = ETF_TICKERS.get(clean, f"{clean}.PA")

    result = _adapter.get_etf_price(yahoo_ticker)
    result["source"] = "Yahoo Finance (tier_2) — données non officielles"
    return result


def get_etf_history(ticker: str, period: str = "1y") -> dict:
    """
    Historique prix d'un ETF.
    period : 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y
    """
    clean = ticker.upper().replace(".PA", "")
    yahoo_ticker = ETF_TICKERS.get(clean, f"{clean}.PA")
    return _adapter.get_etf_history(yahoo_ticker, period)


def get_world_etfs_snapshot() -> dict:
    """Snapshot de tous les ETF MSCI World PEA principaux."""
    results = {}
    for name, ticker in ETF_TICKERS.items():
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

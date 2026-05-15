"""
Adapter market data → format interne.
Sources : yfinance (ETF/actions), pycoingecko (crypto).

yfinance : données Euronext Paris via suffixe .PA (ex: DCAM.PA, CW8.PA)
           parfois lacunaire pour les données européennes — vérifier avant usage.
pycoingecko : API publique fiable, 30 req/min avec clé demo gratuite.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class MarketAdapter:
    def __init__(self):
        self._coingecko_key = os.getenv("COINGECKO_API_KEY")

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # --- ETF / Actions (yfinance) ---

    def get_etf_price(self, ticker: str) -> dict:
        """
        Prix et infos d'un ETF.
        Utiliser le ticker Yahoo Finance avec suffixe marché : DCAM.PA, CW8.PA, WPEA.PA
        """
        try:
            import yfinance as yf

            etf = yf.Ticker(ticker)
            info = etf.info
            hist = etf.history(period="5d")

            if hist.empty:
                return {"error": f"Aucune donnée pour {ticker} — vérifier le ticker"}

            last_close = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else last_close
            change_pct = ((last_close - prev_close) / prev_close) * 100

            return {
                "ticker": ticker,
                "name": info.get("longName", ticker),
                "price": round(last_close, 4),
                "change_pct_1d": round(change_pct, 2),
                "currency": info.get("currency", "EUR"),
                "isin": info.get("isin", ""),
                "expense_ratio": info.get("annualReportExpenseRatio", None),
                "last_updated": self._now(),
                "source": "Yahoo Finance (tier_2)",
            }
        except Exception as e:
            logger.error("Erreur yfinance get_etf_price %s: %s", ticker, e)
            return {"ticker": ticker, "error": str(e)}

    def get_etf_history(self, ticker: str, period: str = "1y") -> dict:
        """Historique de prix d'un ETF. period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y"""
        try:
            import yfinance as yf

            hist = yf.Ticker(ticker).history(period=period)
            if hist.empty:
                return {"error": f"Aucune donnée pour {ticker}"}

            return {
                "ticker": ticker,
                "period": period,
                "points": [
                    {"date": str(idx.date()), "close": round(float(row["Close"]), 4)}
                    for idx, row in hist.iterrows()
                ],
                "last_updated": self._now(),
                "source": "Yahoo Finance (tier_2)",
            }
        except Exception as e:
            logger.error("Erreur yfinance history %s: %s", ticker, e)
            return {"ticker": ticker, "error": str(e)}

    # --- Crypto (CoinGecko) ---

    def get_crypto_price(self, coin_ids: list[str], vs_currency: str = "eur") -> dict:
        """
        Prix crypto en temps réel.
        coin_ids : identifiants CoinGecko (ex: ['bitcoin', 'ethereum'])
        """
        try:
            from pycoingecko import CoinGeckoAPI

            cg = CoinGeckoAPI(api_key=self._coingecko_key) if self._coingecko_key else CoinGeckoAPI()
            prices = cg.get_price(ids=",".join(coin_ids), vs_currencies=vs_currency)

            return {
                "prices": {
                    coin: {"price": data[vs_currency], "currency": vs_currency.upper()}
                    for coin, data in prices.items()
                },
                "last_updated": self._now(),
                "source": "CoinGecko (tier_2)",
            }
        except Exception as e:
            logger.error("Erreur CoinGecko get_crypto_price: %s", e)
            return {"error": str(e)}

    def get_crypto_history(self, coin_id: str, days: int = 365) -> dict:
        """Historique prix crypto sur N jours."""
        try:
            from pycoingecko import CoinGeckoAPI

            cg = CoinGeckoAPI(api_key=self._coingecko_key) if self._coingecko_key else CoinGeckoAPI()
            data = cg.get_coin_market_chart_by_id(id=coin_id, vs_currency="eur", days=days)

            return {
                "coin": coin_id,
                "days": days,
                "prices": [
                    {"timestamp": p[0], "price": round(p[1], 2)}
                    for p in data.get("prices", [])
                ],
                "last_updated": self._now(),
                "source": "CoinGecko (tier_2)",
            }
        except Exception as e:
            logger.error("Erreur CoinGecko history %s: %s", coin_id, e)
            return {"error": str(e)}

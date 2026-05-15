"""
Adapter finary_uapi → format interne normalisé.

finary_uapi version : 0.2.3
Endpoints CLI utilisés : holdings_accounts, cryptos, savings_accounts, dashboard

IMPORTANT : finary_uapi est une CLI Python, pas une API Python importable.
Tous les appels passent par subprocess vers `python -m finary_uapi <commande>`.
La session est établie une seule fois via : make finary-signin MFA=<code>
L'utilisateur a la 2FA activée — cette étape manuelle est obligatoire.

Si Finary change son API ou active un bot-detection plus strict, seul ce fichier
est à modifier (pattern Adapter — le reste du code ne change pas).
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from adapters.base_adapter import BasePortfolioAdapter

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent


class FinaryAuthError(Exception):
    """Session Finary expirée, invalide, ou bot détecté par Finary."""


class FinaryAdapter(BasePortfolioAdapter):
    """
    Wrapping de finary_uapi via subprocess.
    Isole tous les appels CLI Finary derrière cette interface stable.
    """

    def _run_command(self, subcommand: str) -> dict | list:
        """
        Exécute `python -m finary_uapi <subcommand>` et retourne le JSON parsé.
        Lève FinaryAuthError si session expirée ou bot détecté.
        """
        cmd = [sys.executable, "-m", "finary_uapi", subcommand]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=PROJECT_ROOT,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Timeout lors de l'appel finary_uapi {subcommand} (>30s)")
        except FileNotFoundError:
            raise RuntimeError(
                "finary_uapi non trouvé. Vérifier que 'uv sync' a été lancé."
            )

        stderr_lower = result.stderr.lower()
        if result.returncode != 0 or "401" in result.stderr or "unauthorized" in stderr_lower:
            if "bot detected" in stderr_lower or "bot_detected" in stderr_lower:
                raise FinaryAuthError(
                    "Finary a détecté un accès bot. "
                    "Attendre quelques heures puis relancer: make finary-signin MFA=<code>"
                )
            raise FinaryAuthError(
                f"Session Finary expirée ou invalide. Relancer: make finary-signin MFA=<code>. "
                f"Détail: {result.stderr[:100]}"
            )

        stdout = result.stdout.strip()
        if not stdout:
            return {}

        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            logger.error("Réponse non-JSON de finary_uapi %s: %s", subcommand, stdout[:200])
            raise RuntimeError(
                f"finary_uapi {subcommand} a retourné une réponse non-JSON. "
                "La session a peut-être expiré — relancer: make finary-signin MFA=<code>"
            )

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    # --- Interface BasePortfolioAdapter ---

    def get_portfolio(self) -> dict:
        """Portfolio complet normalisé."""
        accounts = self.get_accounts()
        total = sum(a["balance"] for a in accounts)
        return {
            "accounts": accounts,
            "total_net_worth": round(total, 2),
            "last_sync": self._now(),
        }

    def get_accounts(self) -> list:
        """Tous les comptes depuis holdings_accounts."""
        raw = self._run_command("holdings_accounts")
        return self._normalize_accounts(raw)

    def get_crypto(self) -> list:
        """Positions crypto uniquement."""
        raw = self._run_command("cryptos")
        return self._normalize_crypto(raw)

    # --- Méthodes additionnelles ---

    def get_savings(self) -> list:
        """Livrets et comptes épargne."""
        raw = self._run_command("savings_accounts")
        return self._normalize_savings(raw)

    def get_dashboard(self) -> dict:
        """Patrimoine brut total depuis le dashboard."""
        raw = self._run_command("dashboard")
        if isinstance(raw, dict):
            return {"total_gross": raw.get("total", raw.get("gross", 0)), "last_sync": self._now()}
        return {"total_gross": 0, "last_sync": self._now()}

    # --- Normalisation vers le format interne ---

    def _normalize_accounts(self, raw: dict | list) -> list:
        """Transforme la réponse holdings_accounts → format interne."""
        now = self._now()
        # API returns {"result": [...], "message": ..., "error": ...}
        items = raw.get("result", raw) if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            return []
        return [self._normalize_single(item, now) for item in items]

    def _normalize_single(self, item: dict, now: str) -> dict:
        name = item.get("name", "")
        slug = item.get("slug", "")
        currency = item.get("currency", {})
        currency_code = currency.get("code", "EUR") if isinstance(currency, dict) else "EUR"
        # display_balance is always in user's reference currency (EUR)
        balance_eur = float(item.get("display_balance", item.get("balance", 0)))
        return {
            "id": str(item.get("id", "")),
            "type": self._map_type(slug, name),
            "institution": name or "Inconnu",
            "balance": balance_eur,
            "currency": "EUR",
            "original_currency": currency_code,
            "unrealized_pnl": item.get("display_unrealized_pnl"),
            "last_updated": now,
            "raw_name": name,
        }

    def _normalize_crypto(self, raw: dict | list) -> list:
        now = self._now()
        # API returns {"result": [...], ...}
        items = raw.get("result", raw) if isinstance(raw, dict) else raw
        if not isinstance(items, list):
            return []
        result = []
        for item in items:
            crypto_info = item.get("crypto", item.get("valuable", {}))
            result.append({
                "id": str(item.get("id", "")),
                "type": "crypto",
                "symbol": crypto_info.get("code", ""),
                "name": crypto_info.get("name", item.get("correlation_id", "")),
                "quantity": float(item.get("quantity", 0)),
                "balance": float(item.get("display_current_value", item.get("current_value", 0))),
                "unrealized_pnl": item.get("display_unrealized_pnl"),
                "currency": "EUR",
                "last_updated": now,
            })
        return result

    def _normalize_savings(self, raw: dict | list) -> list:
        now = self._now()
        items = raw if isinstance(raw, list) else raw.get("data", [])
        return [
            {
                "id": str(item.get("id", "")),
                "type": "savings",
                "institution": item.get("bank", {}).get("name", "Inconnu"),
                "balance": float(item.get("balance", 0)),
                "interest_rate": float(item.get("yearly_interest_rate", 0)),
                "currency": "EUR",
                "last_updated": now,
            }
            for item in (items if isinstance(items, list) else [])
        ]

    def _map_type(self, slug: str, name: str) -> str:
        name_lower = name.lower()
        slug_lower = slug.lower()
        if "pea" in name_lower or "plan d'épargne" in name_lower:
            return "pea"
        if "livret" in name_lower:
            return "livret"
        if "epargne" in name_lower or "épargne" in name_lower or "saving" in slug_lower:
            return "savings"
        if any(x in slug_lower for x in ("binance", "coinbase", "kraken", "wallet", "crypto")):
            return "crypto"
        if "pro" in name_lower or "checking" in slug_lower or "bancaire" in name_lower:
            return "checking"
        return "other"

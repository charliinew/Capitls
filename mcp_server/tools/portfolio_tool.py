"""
Tool MCP : portfolio Finary, suivi PEA, revenus, décisions.

Toutes les données personnelles transitent par le profil unique (mcp_server/profile) :
la synchro Finary y écrit les soldes, les tools d'analyse la relisent.
Tout appel Finary passe par FinaryAdapter.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from adapters.finary_adapter import FinaryAdapter, FinaryAuthError
from mcp_server.profile import store
from mcp_server.profile.schema import (
    Account,
    CryptoPosition,
    Decision,
    FinarySnapshot,
    FinarySnapshotAccount,
    MonthlyIncome,
    PEAOrder,
    UserProfile,
)
from skills.situation_review import liquidity

logger = logging.getLogger(__name__)

AUTO_SYNC_AFTER = timedelta(hours=1)

# Type Finary normalisé (FinaryAdapter._map_type) → catégorie du profil
_FINARY_TYPE_TO_CATEGORY = {
    "pea": "pea",
    "livret": "regulated_savings",
    "savings": "savings",
    "crypto": "crypto",
    "checking": "checking",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _auth_error(e: Exception) -> dict:
    return {
        "status": "auth_error",
        "error": str(e),
        "action_required": "Session Finary expirée — lancer : make finary-signin",
    }


def _slug(name: str, existing: set[str]) -> str:
    import re

    base = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "compte"
    slug, i = base, 2
    while slug in existing:
        slug, i = f"{base}_{i}", i + 1
    return slug


def apply_finary_sync(profile: UserProfile, accounts: list[dict], cryptos: list[dict], now: datetime) -> list[str]:
    """Écrit les soldes Finary dans le profil. Les comptes inconnus sont ajoutés « à classer »."""
    changes = []
    stamp = now.isoformat(timespec="seconds")
    ids = {a.id for a in profile.accounts}

    for fin in accounts:
        name = fin.get("raw_name") or fin.get("institution") or "Compte"
        balance = round(float(fin.get("balance", 0.0)), 2)
        account = profile.account_by_finary_name(name)
        if account is None:
            account = Account(
                id=_slug(name, ids),
                name=name,
                finary_name=name,
                category=_FINARY_TYPE_TO_CATEGORY.get(fin.get("type", ""), "other"),  # type: ignore[arg-type]
                needs_classification=True,
            )
            ids.add(account.id)
            profile.accounts.append(account)
            changes.append(f"Nouveau compte Finary « {name} » ajouté (à classer)")
        if account.balance != balance:
            changes.append(f"{account.name}: {account.balance} € → {balance} €")
        account.balance = balance
        account.balance_updated_at = stamp

    if cryptos:
        total_crypto = round(sum(c["balance"] for c in cryptos), 2)
        if profile.crypto.total_value != total_crypto:
            changes.append(f"Crypto total: {profile.crypto.total_value} € → {total_crypto} €")
        profile.crypto.total_value = total_crypto
        profile.crypto.positions = [
            CryptoPosition(
                symbol=c["symbol"],
                name=c.get("name"),
                qty=round(c["quantity"], 6),
                value_eur=round(c["balance"], 2),
                pnl_eur=round(c["unrealized_pnl"], 2) if c.get("unrealized_pnl") else 0.0,
            )
            for c in cryptos
        ]

    profile.finary_snapshot = FinarySnapshot(
        date=stamp,
        total_net_worth=round(sum(a["balance"] for a in accounts), 2),
        accounts=[
            FinarySnapshotAccount(
                name=a.get("raw_name") or a["institution"], type=a["type"], balance=round(a["balance"], 2)
            )
            for a in accounts
        ],
    )
    return changes


def sync_profile() -> dict:
    """Synchronise le profil avec les soldes Finary live (crée le profil si absent)."""
    try:
        adapter = FinaryAdapter()
        accounts = adapter.get_accounts()
        cryptos = adapter.get_crypto()
    except FinaryAuthError as e:
        return _auth_error(e)
    except Exception as e:
        return {"status": "error", "error": str(e)}

    profile = store.load_profile() or store.new_profile()
    changes = apply_finary_sync(profile, accounts, cryptos, _now())
    store.save_profile(profile)

    unclassified = [a.name for a in profile.accounts if a.needs_classification]
    return {
        "status": "ok",
        "synced_at": profile.finary_snapshot.date if profile.finary_snapshot else None,
        "total_net_worth": profile.finary_snapshot.total_net_worth if profile.finary_snapshot else 0,
        "changes": changes or ["Aucun changement détecté"],
        "accounts_synced": len(accounts),
        "crypto_positions": len(cryptos),
        "unclassified_accounts": unclassified,
        "note": "Comptes à classer : demander leur rôle à l'utilisateur puis update_situation()"
        if unclassified
        else None,
        "source": "Finary (tier_2)",
    }


def _ensure_recent_sync(profile: UserProfile | None) -> tuple[UserProfile | None, dict | None]:
    """Synchro auto si la dernière date de plus d'1h. Retourne (profil, erreur éventuelle)."""
    last = profile.finary_snapshot.date if profile and profile.finary_snapshot else None
    try:
        last_dt = datetime.fromisoformat(last) if last else None
    except ValueError:
        last_dt = None
    if last_dt is not None and last_dt.tzinfo is None:
        last_dt = last_dt.replace(tzinfo=timezone.utc)
    stale = last_dt is None or _now() - last_dt > AUTO_SYNC_AFTER
    if not stale:
        return profile, None
    result = sync_profile()
    if result["status"] != "ok":
        return profile, result
    return store.load_profile(), None


def get_portfolio() -> dict:
    """Portfolio complet (synchro Finary automatique si > 1h)."""
    profile, sync_error = _ensure_recent_sync(store.load_profile())
    if profile is None:
        return sync_error or {"status": "error", "error": "Aucun profil ni données Finary"}

    accounts = [a.model_dump() for a in profile.accounts]
    result = {
        "status": "ok",
        "accounts": accounts,
        "total_net_worth": round(sum(a["balance"] for a in accounts), 2),
        "crypto": profile.crypto.model_dump(),
        "last_sync": profile.finary_snapshot.date if profile.finary_snapshot else None,
        "source": "Finary (tier_2)",
    }
    if sync_error:
        result["warning"] = (
            f"Synchro Finary impossible ({sync_error.get('error')}) — soldes du "
            f"{result['last_sync'] or 'jamais synchronisés'}, conseils basés sur les soldes NON fiables."
        )
        result["sync_status"] = sync_error["status"]
    return result


def get_accounts_summary() -> dict:
    """Résumé des comptes + vérification des règles personnelles (liquidité, part crypto)."""
    portfolio = get_portfolio()
    if portfolio["status"] != "ok":
        return portfolio
    profile = store.require_profile()
    accounts = portfolio["accounts"]
    total = portfolio["total_net_worth"]
    liq = liquidity(accounts)
    crypto_val = sum(a["balance"] for a in accounts if a["category"] == "crypto")
    crypto_pct = crypto_val / total if total > 0 else 0.0

    rules = profile.rules
    warnings = []
    if rules.liquidity_min is not None and liq["total"] < rules.liquidity_min:
        warnings.append(f"⚠️ Liquidité {liq['total']:.0f} € < minimum {rules.liquidity_min:.0f} €")
    if rules.crypto_max_pct is not None and crypto_pct > rules.crypto_max_pct:
        warnings.append(f"⚠️ Crypto {crypto_pct * 100:.1f} % > max {rules.crypto_max_pct * 100:.0f} %")
    missing = [
        name
        for name, value in (
            ("rules.liquidity_min", rules.liquidity_min),
            ("rules.crypto_max_pct", rules.crypto_max_pct),
        )
        if value is None
    ]

    return {
        "status": "ok",
        "accounts": accounts,
        "summary": {
            "total_net_worth": total,
            "liquid_assets": liq["total"],
            "available_above_minimums": liq["available_above_minimums"],
            "crypto_value": round(crypto_val, 2),
            "crypto_pct": round(crypto_pct * 100, 1),
        },
        "rules_check": {"warnings": warnings, "undefined_rules": missing},
        **({"warning": portfolio["warning"]} if "warning" in portfolio else {}),
        "source": "Finary (tier_2) + profil utilisateur",
    }


def get_dca_reminder() -> dict:
    """Vérifie si l'ordre PEA du mois a été enregistré."""
    profile = store.require_profile()
    pea = profile.pea
    if pea.status != "open":
        return {"status": "ok", "reminder_needed": False, "message": f"PEA non ouvert (statut : {pea.status})"}

    current_month = _now().strftime("%Y-%m")
    this_month = [o for o in pea.orders if o.date.startswith(current_month)]
    if this_month:
        return {
            "status": "ok",
            "reminder_needed": False,
            "message": f"Ordre {current_month} déjà enregistré : {this_month[-1].model_dump()}",
            "orders_this_month": len(this_month),
        }

    broker = pea.broker
    fee_hint = (
        f" (≤ {broker.free_order_max:.0f} € pour un ordre gratuit chez {broker.name})" if broker.free_order_max else ""
    )
    return {
        "status": "ok",
        "reminder_needed": True,
        "message": f"⏰ Aucun ordre PEA enregistré pour {current_month}.{fee_hint}",
        "monthly_target": pea.monthly_target,
        "target_etf": pea.target_etf,
    }


def record_monthly_income(month: str, income: float, source: str) -> dict:
    """Historise un revenu mensuel (un seul par mois et par source)."""
    try:
        datetime.strptime(month, "%Y-%m")
    except ValueError:
        return {"status": "error", "error": "month doit être au format YYYY-MM"}
    profile = store.load_profile() or store.new_profile()
    history = [e for e in profile.income.history if not (e.month == month and e.source == source)]
    entry = MonthlyIncome(month=month, income=round(income, 2), source=source)
    profile.income.history = history + [entry]
    store.save_profile(profile)
    return {"status": "ok", "recorded": entry.model_dump(), "total_months": len(profile.income.history)}


def update_decision_history(decision: str, details: dict) -> dict:
    """Journalise une décision financière dans le profil."""
    profile = store.load_profile() or store.new_profile()
    entry = Decision(date=_now().date().isoformat(), decision=decision, details=details)
    profile.decisions.append(entry)
    store.save_profile(profile)
    return {"status": "ok", "recorded": entry.model_dump()}


def get_pea_status() -> dict:
    """Statut du PEA : compte à rebours fiscal, performance au prix actuel, prochain ordre."""
    from mcp_server.tools import market_tool, reference_tool
    from skills.pea_tracker import calculate_pea_countdown, calculate_pea_performance, get_next_order_info

    profile = store.require_profile()
    pea = profile.pea
    orders = [o.model_dump() for o in pea.orders]
    reference = reference_tool.get_reference()
    years = int(reference_tool.get_fact(reference, "pea.duree_exoneration_ans"))

    performance = None
    price_error = None
    tickers = sorted({o["ticker"] for o in orders}) or ([pea.target_etf] if pea.target_etf else [])
    if orders:
        performance = {}
        for ticker in tickers:
            quote = market_tool.get_etf_quote(ticker)
            if "price" in quote:
                performance[ticker] = calculate_pea_performance(orders, quote["price"], ticker)
            else:
                price_error = f"Prix {ticker} indisponible: {quote.get('error')}"

    return {
        "status": "ok",
        "pea_status": pea.status,
        "broker": pea.broker.model_dump(),
        "countdown": calculate_pea_countdown(pea.first_deposit_date, years),
        "performance": performance,
        "price_error": price_error,
        "next_order": get_next_order_info(orders, pea.monthly_target, pea.broker.free_order_max)
        if pea.status == "open"
        else None,
        "order_count": len(orders),
        "source": "profil utilisateur + Yahoo Finance (tier_2)",
    }


def record_pea_order(date: str, ticker: str, amount: float, price: float) -> dict:
    """Enregistre un ordre PEA exécuté."""
    from skills.pea_tracker import add_pea_order

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        return {"status": "error", "error": "date doit être au format YYYY-MM-DD"}
    if amount <= 0 or price <= 0:
        return {"status": "error", "error": "amount et price doivent être > 0"}

    profile = store.require_profile()
    orders = add_pea_order(
        [o.model_dump() for o in profile.pea.orders],
        date,
        ticker.upper().replace(".PA", ""),
        amount,
        price,
        profile.pea.broker.free_order_max,
    )
    profile.pea.orders = [PEAOrder(**o) for o in orders]
    if profile.pea.first_deposit_date is None or date < profile.pea.first_deposit_date:
        profile.pea.first_deposit_date = date
    if profile.pea.status in ("none", "planned", "opening"):
        profile.pea.status = "open"
    store.save_profile(profile)
    return {"status": "ok", "order_recorded": orders[-1], "total_orders": len(orders)}

"""
Tool MCP : lecture du portfolio Finary.
Utilise FinaryAdapter — tout appel Finary passe par cet adapter.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from adapters.finary_adapter import FinaryAdapter, FinaryAuthError

logger = logging.getLogger(__name__)

PROFILE_PATH = Path(__file__).parent.parent / "context" / "user_profile.json"


def get_portfolio() -> dict:
    """
    Récupère le portfolio complet depuis Finary.
    Retourne le format interne normalisé + données du profil utilisateur.
    """
    try:
        adapter = FinaryAdapter()
        portfolio = adapter.get_portfolio()
        profile = _load_profile()

        return {
            "status": "ok",
            "portfolio": portfolio,
            "user_context": {
                "liquidity_minimum": profile["regles_personnelles"]["liquidite_minimale"],
                "pea_status": profile["patrimoine"]["pea"]["statut"],
                "courtier": profile["patrimoine"]["pea"]["courtier"],
            },
            "source": "Finary (tier_2)",
        }
    except FinaryAuthError as e:
        return {
            "status": "auth_error",
            "error": str(e),
            "action_required": "Lancer: make finary-signin MFA=<code_2fa>",
        }
    except Exception as e:
        logger.error("Erreur get_portfolio: %s", e)
        return {"status": "error", "error": str(e)}


def get_accounts_summary() -> dict:
    """
    Résumé des comptes avec comparaison aux règles personnelles.
    Signale si la liquidité de précaution est respectée.
    """
    try:
        adapter = FinaryAdapter()
        accounts = adapter.get_accounts()
        profile = _load_profile()

        liquid_min = profile["regles_personnelles"]["liquidite_minimale"]
        crypto_max_pct = profile["regles_personnelles"]["part_crypto_max"]

        total = sum(a["balance"] for a in accounts)
        excluded = set(profile.get("regles_personnelles", {}).get("liquidite_comptes_exclus", []))
        liquid = sum(
            a["balance"] for a in accounts
            if a["type"] in ("savings", "checking", "livret") and a.get("institution") not in excluded
        )
        crypto_val = sum(a["balance"] for a in accounts if a["type"] == "crypto")
        crypto_pct = (crypto_val / total) if total > 0 else 0

        warnings = []
        if liquid < liquid_min:
            warnings.append(f"⚠️ Liquidité {liquid:.0f}€ < minimum {liquid_min}€")
        if crypto_pct > crypto_max_pct:
            warnings.append(f"⚠️ Crypto {crypto_pct*100:.1f}% > max {crypto_max_pct*100:.0f}%")

        return {
            "status": "ok",
            "accounts": accounts,
            "summary": {
                "total_net_worth": round(total, 2),
                "liquid_assets": round(liquid, 2),
                "crypto_value": round(crypto_val, 2),
                "crypto_pct": round(crypto_pct * 100, 1),
            },
            "rules_check": {
                "liquidity_ok": liquid >= liquid_min,
                "crypto_allocation_ok": crypto_pct <= crypto_max_pct,
                "warnings": warnings,
            },
            "source": "Finary (tier_2)",
        }
    except FinaryAuthError as e:
        return {"status": "auth_error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def sync_profile() -> dict:
    """
    Synchronise user_profile.json avec les données live Finary.
    Met à jour les soldes, positions crypto et snapshot.
    Ne touche pas aux règles, objectifs, ni au statut PEA.
    """
    from datetime import datetime, timezone

    try:
        adapter = FinaryAdapter()
        accounts = adapter.get_accounts()
        cryptos = adapter.get_crypto()
        today = datetime.now(timezone.utc).date().isoformat()
    except FinaryAuthError as e:
        return {"status": "auth_error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

    profile = _load_profile()
    changes = []

    # Mapping raw_name Finary → clé patrimoine dans le profil
    ACCOUNT_MAP = {
        "Livret Jeune":        ("sg_livret_jeune",   "montant"),
        "Compte Bancaire":     ("sg_compte_courant",  "montant"),
        "Pro":                 ("indy_pro",            "montant"),
        "Revolut Current EUR": ("revolut_courant",     "montant"),
        "Epargne":             ("revolut_epargne",     "montant"),
    }

    # Mise à jour des soldes de comptes
    for account in accounts:
        name = account["raw_name"]
        if name in ACCOUNT_MAP:
            section, field = ACCOUNT_MAP[name]
            if section in profile["patrimoine"]:
                old = profile["patrimoine"][section].get(field, 0)
                new = round(account["balance"], 2)
                if old != new:
                    changes.append(f"{name}: {old}€ → {new}€")
                profile["patrimoine"][section][field] = new
                # Mettre à jour disponible_investissement pour revolut_epargne
                if section == "revolut_epargne":
                    minimum = profile["patrimoine"][section].get("minimum_absolu", 600)
                    profile["patrimoine"][section]["disponible_investissement"] = round(
                        max(0, new - minimum), 2
                    )

    # Mise à jour crypto
    if cryptos:
        total_crypto = round(sum(c["balance"] for c in cryptos), 2)
        old_crypto = profile["patrimoine"]["crypto"].get("valeur_estimee", 0)
        if old_crypto != total_crypto:
            changes.append(f"Crypto total: {old_crypto}€ → {total_crypto}€")
        profile["patrimoine"]["crypto"]["valeur_estimee"] = total_crypto
        profile["patrimoine"]["crypto"]["positions"] = [
            {
                "symbol": c["symbol"],
                "name": c["name"],
                "qty": round(c["quantity"], 6),
                "valeur_eur": round(c["balance"], 2),
                "pnl_eur": round(c["unrealized_pnl"], 2) if c.get("unrealized_pnl") else 0.0,
            }
            for c in cryptos
        ]

    # Mise à jour snapshot Finary
    total = round(sum(a["balance"] for a in accounts), 2)
    profile["snapshot_finary"] = {
        "date": today,
        "total_net_worth": total,
        "comptes": [
            {"nom": a["institution"], "type": a["type"], "balance": round(a["balance"], 2)}
            for a in accounts
        ],
    }

    profile["last_updated"] = today

    with open(PROFILE_PATH, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    return {
        "status": "ok",
        "synced_at": today,
        "total_net_worth": total,
        "changes": changes if changes else ["Aucun changement détecté"],
        "accounts_synced": len(accounts),
        "crypto_positions": len(cryptos),
    }


def get_dca_reminder() -> dict:
    """
    Vérifie si l'ordre DCA mensuel a déjà été passé ce mois-ci.
    Retourne un rappel si aucun ordre détecté pour le mois courant.
    """
    from datetime import datetime, timezone

    profile = _load_profile()
    order_history = profile["patrimoine"]["pea"].get("order_history", [])
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")

    this_month_orders = [
        o for o in order_history
        if o.get("date", "").startswith(current_month)
    ]

    if this_month_orders:
        return {
            "status": "ok",
            "reminder_needed": False,
            "message": f"Ordre {current_month} déjà enregistré : {this_month_orders[-1]}",
            "orders_this_month": len(this_month_orders),
        }

    return {
        "status": "ok",
        "reminder_needed": True,
        "message": (
            f"⏰ Rappel : aucun ordre PEA enregistré pour {current_month}. "
            "Passer l'ordre mensuel sur Fortuneo (≤500€ pour ordre gratuit)."
        ),
        "monthly_target": profile["patrimoine"]["pea"].get("versement_mensuel_cible", 200),
        "etf_cible": profile["patrimoine"]["pea"].get("etf_cible", "DCAM"),
    }


def record_monthly_income(month: str, income: float, source: str = "stage") -> dict:
    """
    Enregistre un revenu mensuel dans le profil pour suivi de capacité DCA.
    month: format YYYY-MM, income: montant en €, source: stage/freelance/autre
    """
    try:
        profile = _load_profile()
        from datetime import datetime, timezone

        if "historique_mensuel" not in profile["revenus"]:
            profile["revenus"]["historique_mensuel"] = []

        entry = {"month": month, "income": round(income, 2), "source": source}

        # Éviter les doublons sur le même mois+source
        existing = [
            e for e in profile["revenus"]["historique_mensuel"]
            if not (e["month"] == month and e["source"] == source)
        ]
        existing.append(entry)
        profile["revenus"]["historique_mensuel"] = existing
        profile["last_updated"] = datetime.now(timezone.utc).date().isoformat()

        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)

        return {"status": "ok", "recorded": entry, "total_months": len(existing)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def update_decision_history(decision: str, details: dict) -> dict:
    """
    Enregistre une décision financière dans l'historique du profil.
    Permet de tracer les actions prises.
    """
    try:
        profile = _load_profile()
        from datetime import datetime, timezone

        entry = {
            "date": datetime.now(timezone.utc).date().isoformat(),
            "decision": decision,
            "details": details,
        }
        profile["historique_decisions"].append(entry)
        profile["last_updated"] = entry["date"]

        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)

        return {"status": "ok", "recorded": entry}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def get_pea_status() -> dict:
    """
    Retourne l'état complet du PEA : countdown, performance, prochain ordre.
    Lit user_profile.json, appelle les fonctions pea_tracker.
    """
    from skills.pea_tracker import (
        calculate_pea_countdown, calculate_pea_performance, get_next_order_info
    )
    profile = _load_profile()
    pea = profile["patrimoine"]["pea"]
    opening_date = pea.get("opening_date", None)
    order_history = pea.get("order_history", [])
    monthly_target = pea.get("versement_mensuel_cible", 200.0)

    target_ticker = pea.get("etf_cible", "DCAM")

    countdown = calculate_pea_countdown(opening_date)
    performance = calculate_pea_performance(order_history, 0.0, target_ticker)
    next_order = get_next_order_info(order_history, monthly_target)

    return {
        "status": "ok",
        "pea_status": pea.get("statut", "inconnu"),
        "countdown": countdown,
        "performance": performance,
        "next_order": next_order,
        "order_count": len(order_history),
        "source": "user_profile.json (tier_2)",
    }


def record_pea_order(date: str, ticker: str, amount: float, price: float) -> dict:
    """
    Persiste un ordre PEA dans user_profile.json.
    Même pattern que update_decision_history().
    """
    from skills.pea_tracker import add_pea_order
    try:
        profile = _load_profile()
        if "order_history" not in profile["patrimoine"]["pea"]:
            profile["patrimoine"]["pea"]["order_history"] = []

        new_history = add_pea_order(
            profile["patrimoine"]["pea"]["order_history"],
            date, ticker, amount, price
        )
        profile["patrimoine"]["pea"]["order_history"] = new_history

        from datetime import datetime, timezone
        profile["last_updated"] = datetime.now(timezone.utc).date().isoformat()

        with open(PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)

        return {
            "status": "ok",
            "order_recorded": new_history[-1],
            "total_orders": len(new_history),
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _load_profile() -> dict:
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return json.load(f)

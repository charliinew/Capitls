"""
Migration de l'ancien format de profil (v1, clés libres sous `patrimoine`) vers le schéma v2.
Fonction pure : restructure sans modifier aucune valeur. Les champs non reconnus sont
conservés sous `legacy` pour ne rien perdre.
"""

from __future__ import annotations

import re

_PEA_STATUS = {
    "à ouvrir": "planned",
    "a ouvrir": "planned",
    "en cours d'ouverture": "opening",
    "ouvert": "open",
    "actif": "open",
    "clôturé": "closed",
    "fermé": "closed",
}


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "compte"


def _guess_category(key: str, data: dict) -> str:
    text = f"{key} {data.get('role', '')} {data.get('note', '')}".lower()
    if any(w in text for w in ("urssaf", "provision", "pro ")) or key.endswith("_pro") or key == "pro":
        return "pro_reserved"
    if "livret" in text or "lep" in text or "ldds" in text:
        return "regulated_savings"
    if "epargne" in text or "épargne" in text or "saving" in text or "précaution" in text:
        return "savings"
    if "courant" in text or "quotidien" in text or "checking" in text:
        return "checking"
    if "assurance" in text:
        return "life_insurance"
    return "other"


def _parse_broker_fees(tarif: str | None) -> tuple[int | None, float | None]:
    """'1 ordre/mois < 500€ gratuit' → (1, 500.0)"""
    if not tarif:
        return None, None
    per_month = re.search(r"(\d+)\s*ordres?\s*/?\s*(?:par\s*)?mois", tarif, re.I)
    amount = re.search(r"(\d[\d\s]*)\s*€", tarif)
    return (
        int(per_month.group(1)) if per_month else None,
        float(re.sub(r"\s", "", amount.group(1))) if amount else None,
    )


def _match_finary_names(accounts: list[dict], snapshot: dict | None) -> None:
    """
    Associe chaque compte à son nom Finary en comparant les soldes avec le dernier snapshot
    Finary (la synchro v1 y écrivait les mêmes valeurs arrondies). Correspondances ambiguës ignorées.
    """
    if not snapshot:
        return
    snap_accounts = snapshot.get("comptes") or snapshot.get("accounts") or []
    used: set[str] = set()
    for account in accounts:
        balance = account.get("balance")
        if not balance:
            continue
        candidates = [
            s
            for s in snap_accounts
            if round(float(s.get("balance", 0)), 2) == round(float(balance), 2)
            and (s.get("nom") or s.get("name")) not in used
        ]
        if len(candidates) == 1:
            name = candidates[0].get("nom") or candidates[0].get("name")
            account["finary_name"] = name
            used.add(name)


def is_legacy(profile: dict) -> bool:
    return int(profile.get("schema_version", 0) or 0) < 2


def migrate_v1_to_v2(old: dict) -> dict:
    """Ancien profil (dict) → dict conforme à UserProfile v2."""
    identity_old = old.get("identity", {})
    revenus = old.get("revenus", {})
    patrimoine = dict(old.get("patrimoine", {}))
    regles = old.get("regles_personnelles", {})
    last_updated = old.get("last_updated")
    as_of = last_updated if last_updated and last_updated != "YYYY-MM-DD" else None

    identity = {
        "age": identity_old.get("age") or None,
        "age_as_of": as_of if identity_old.get("age") else None,
        "situation": identity_old.get("situation"),
    }
    for key in identity_old:
        if key not in ("age", "situation"):
            identity[key] = identity_old[key]

    sources = []
    for i, src in enumerate(revenus.get("sources", [])):
        sources.append(
            {
                "id": f"{_slug(src.get('type', 'revenu'))}_{i + 1}",
                "type": src.get("type", "autre"),
                "label": src.get("employeur") or src.get("label"),
                "monthly_amount": src.get("montant_mensuel"),
                "end": src.get("fin") if src.get("fin") not in (None, "YYYY-MM") else None,
                "regular": src.get("montant_mensuel") is not None,
                "note": src.get("note"),
                **{
                    k: v
                    for k, v in src.items()
                    if k not in ("type", "employeur", "label", "montant_mensuel", "fin", "note")
                },
            }
        )

    crypto_old = patrimoine.pop("crypto", {}) or {}
    pea_old = patrimoine.pop("pea", {}) or {}

    excluded = set(regles.get("liquidite_comptes_exclus", []))
    accounts = []
    for key, data in patrimoine.items():
        if not isinstance(data, dict):
            continue
        category = _guess_category(key, data)
        known = {"montant", "role", "minimum_absolu"} | ({"note"} if not data.get("role") else set())
        accounts.append(
            {
                "id": key,
                "name": key.replace("_", " ").title(),
                "category": category,
                "balance": float(data.get("montant", 0) or 0),
                "balance_updated_at": as_of,
                "minimum_balance": float(data.get("minimum_absolu", 0) or 0),
                "exclude_from_liquidity": category == "pro_reserved",
                "role": data.get("role") or data.get("note"),
                **{k: v for k, v in data.items() if k not in known and k != "disponible_investissement"},
            }
        )

    snapshot_old = old.get("snapshot_finary")
    _match_finary_names(accounts, snapshot_old)
    for account in accounts:
        if account.get("finary_name") in excluded:
            account["exclude_from_liquidity"] = True

    per_month, free_max = _parse_broker_fees(pea_old.get("tarif_cle"))
    orders = pea_old.get("order_history", [])
    status_raw = str(pea_old.get("statut", "")).strip().lower()
    pea = {
        "status": _PEA_STATUS.get(status_raw, "none" if not status_raw else "planned"),
        "broker": {
            "name": pea_old.get("courtier") or None,
            "free_orders_per_month": regles.get("ordres_pea_max_par_mois") or per_month,
            "free_order_max": regles.get("montant_max_ordre_gratuit") or free_max,
            "auto_invest": bool(pea_old.get("dca_automatique", False)),
            "notes": [pea_old["tarif_cle"]] if pea_old.get("tarif_cle") else [],
        },
        "first_deposit_date": pea_old.get("opening_date") or (min(o["date"] for o in orders) if orders else None),
        "initial_deposit_target": pea_old.get("apport_initial_cible") or None,
        "monthly_target": pea_old.get("versement_mensuel_cible") or None,
        "target_etf": pea_old.get("etf_cible"),
        "referral": pea_old.get("parrainage") if (pea_old.get("parrainage") or {}).get("actif") else None,
        "orders": orders,
    }

    snapshot = None
    if snapshot_old:
        snapshot = {
            "date": snapshot_old.get("date"),
            "total_net_worth": snapshot_old.get("total_net_worth", 0),
            "accounts": [
                {"name": s.get("nom") or s.get("name"), "type": s.get("type", "other"), "balance": s.get("balance", 0)}
                for s in snapshot_old.get("comptes") or snapshot_old.get("accounts") or []
            ],
        }

    objectifs = old.get("objectifs", {})
    handled = {
        "version",
        "last_updated",
        "_note",
        "identity",
        "revenus",
        "patrimoine",
        "regles_personnelles",
        "objectifs",
        "snapshot_finary",
        "historique_decisions",
    }
    legacy = {k: v for k, v in old.items() if k not in handled}

    return {
        "schema_version": 2,
        "identity": identity,
        "income": {
            "sources": sources,
            "fixed_expenses": None,
            "history": revenus.get("historique_mensuel", []),
        },
        "accounts": accounts,
        "crypto": {
            "total_value": crypto_old.get("valeur_estimee", 0) or 0,
            "positions": [
                {
                    "symbol": p.get("symbol", ""),
                    "name": p.get("name"),
                    "qty": p.get("qty", 0),
                    "value_eur": p.get("valeur_eur", 0),
                    "pnl_eur": p.get("pnl_eur", 0),
                }
                for p in crypto_old.get("positions", [])
            ],
        },
        "pea": pea,
        "rules": {
            "liquidity_min": regles.get("liquidite_minimale") or None,
            "crypto_max_pct": regles.get("part_crypto_max"),
            "max_orders_per_month": regles.get("ordres_pea_max_par_mois"),
        },
        "goals": {
            "horizon": objectifs.get("horizon"),
            "main_goal": objectifs.get("objectif_principal") or None,
            "risk_tolerance": objectifs.get("tolerance_risque"),
        },
        "review": {"last_review_date": None, "interval_days": 30, "balances_at_last_review": {}, "history": []},
        "finary_snapshot": snapshot,
        "decisions": old.get("historique_decisions", []),
        "meta": {"last_updated": as_of, "migrated_from": f"v{old.get('version', '1')}"},
        **({"legacy": legacy} if legacy else {}),
    }

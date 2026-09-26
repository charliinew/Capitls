"""
Tool MCP : données de référence publiques (taux, plafonds, fiscalité, catalogue ETF).

Stockage centralisé : data/reference_data.json (versionné, aucune donnée personnelle).
- Rafraîchi automatiquement si le dernier fetch réussi date de plus de 24h.
- Chaque valeur récupérée remplace la valeur de repli.
- Les changements de valeur sont journalisés (actualités réglementaires).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from skills import reference_data as ref

logger = logging.getLogger(__name__)

REFERENCE_PATH = Path(
    os.getenv("CAPITLS_REFERENCE_PATH", Path(__file__).parent.parent.parent / "data" / "reference_data.json")
)
_MAX_CHANGES = 200


def _now() -> datetime:
    return datetime.now(timezone.utc)


def load_reference() -> dict:
    with open(REFERENCE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _save_reference(reference: dict) -> None:
    tmp = REFERENCE_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(reference, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, REFERENCE_PATH)


def refresh(force: bool = False, adapter=None) -> dict:
    """
    Rafraîchit les données si nécessaire (> 24h) ou si force=True.
    Retourne un rapport : {refreshed, new_changes, errors, last_successful_fetch}.
    """
    reference = load_reference()
    now = _now()
    if not force and not ref.needs_refresh(reference, now):
        return {
            "refreshed": False,
            "reason": "données fraîches (< 24h)",
            "last_successful_fetch": reference.get("last_successful_fetch"),
            "new_changes": [],
            "errors": [],
        }

    if adapter is None:
        from adapters.reference_adapter import ReferenceAdapter

        adapter = ReferenceAdapter()

    today = now.date().isoformat()
    reference["last_fetch_attempt"] = now.isoformat()

    values, sources, errors = adapter.fetch_regulatory_facts()
    facts, changes = ref.merge_facts(reference.get("facts", {}), values, today)
    for key, source in sources.items():
        if key in facts:
            facts[key].setdefault("source", source)
    reference["facts"] = facts

    etfs = reference.get("etfs", {})
    isin_to_ticker = {e["isin"]: t for t, e in etfs.items() if e.get("isin")}
    profiles, etf_errors = adapter.fetch_etf_profiles(list(isin_to_ticker))
    errors += etf_errors
    for isin, profile in profiles.items():
        ticker = isin_to_ticker[isin]
        etfs[ticker], etf_changes = ref.merge_etf(etfs[ticker], profile, today)
        changes += etf_changes
    reference["etfs"] = etfs

    fetched_any = any(v is not None for v in values.values()) or any(
        p.get("ter") is not None for p in profiles.values()
    )
    if fetched_any:
        reference["last_successful_fetch"] = now.isoformat()
    reference["last_fetch_errors"] = errors
    reference["changes"] = (reference.get("changes", []) + changes)[-_MAX_CHANGES:]
    _save_reference(reference)

    return {
        "refreshed": fetched_any,
        "last_successful_fetch": reference.get("last_successful_fetch"),
        "new_changes": changes,
        "errors": errors,
    }


def get_reference(auto_refresh: bool = True) -> dict:
    """Charge les données de référence, rafraîchies si > 24h (échec réseau → valeurs de repli)."""
    if auto_refresh:
        try:
            refresh()
        except Exception as e:  # le repli local doit toujours rester utilisable
            logger.warning("Rafraîchissement des données de référence impossible: %s", e)
    return load_reference()


def get_fact(reference: dict, key: str) -> float | int:
    value = ref.fact_value(reference, key)
    if value is None:
        raise KeyError(f"Donnée de référence manquante: {key}")
    return value


def get_reference_data(force_refresh: bool = False) -> dict:
    """Vue complète des données de référence + fraîcheur."""
    try:
        report = refresh(force=force_refresh)
    except Exception as e:
        report = {"refreshed": False, "errors": [str(e)], "new_changes": []}
    reference = load_reference()
    today = _now().date()
    return {
        "refresh": report,
        "facts": {
            key: {
                "label": fact.get("label"),
                "value": fact.get("value"),
                "display": ref.format_value(fact.get("value"), fact.get("unit")),
                "verified_at": fact.get("verified_at"),
                "source": fact.get("source"),
            }
            for key, fact in reference.get("facts", {}).items()
        },
        "etfs": reference.get("etfs", {}),
        "stale_facts": ref.stale_facts(reference.get("facts", {}), today),
        "last_successful_fetch": reference.get("last_successful_fetch"),
        "source": "service-public.fr + justETF (tier_1) — valeurs de repli si source indisponible",
    }


def get_regulatory_news(since: str | None = None) -> dict:
    """
    Changements de taux / fiscalité / TER depuis `since` (ISO), ou depuis la dernière
    consultation enregistrée dans le profil utilisateur. Marque ensuite ces actualités comme vues.
    """
    from mcp_server.profile import store

    try:
        refresh()
    except Exception as e:
        logger.warning("Rafraîchissement impossible: %s", e)
    reference = load_reference()

    profile = store.load_profile()
    if since is None and profile is not None:
        since = profile.meta.last_news_check

    news = ref.changes_since(reference.get("changes", []), since)
    facts = reference.get("facts", {})
    formatted = []
    for change in news:
        unit = facts.get(change["key"], {}).get("unit", "taux" if ".ter" in change["key"] else None)
        formatted.append(
            {
                **change,
                "summary": f"{change['label']} : {ref.format_value(change['old'], unit)} → "
                f"{ref.format_value(change['new'], unit)} (le {change['date']})",
            }
        )

    if profile is not None:
        profile.meta.last_news_check = _now().date().isoformat()
        store.save_profile(profile)

    today = _now().date()
    return {
        "since": since,
        "news": formatted,
        "count": len(formatted),
        "stale_facts": ref.stale_facts(facts, today),
        "fetch_errors": reference.get("last_fetch_errors", []),
        "source": "service-public.fr + justETF (tier_1)",
    }


def record_verified_fact(key: str, value: float, source_url: str) -> dict:
    """
    Enregistre une valeur vérifiée manuellement (ex: par recherche web) pour un fait
    que le fetch automatique n'a pas pu confirmer. Journalise le changement.
    """
    reference = load_reference()
    today = _now().date().isoformat()
    facts, changes = ref.merge_facts(reference.get("facts", {}), {key: value}, today)
    facts[key]["origin"] = "verified_by_agent"
    facts[key]["source"] = source_url
    reference["facts"] = facts
    reference["changes"] = (reference.get("changes", []) + changes)[-_MAX_CHANGES:]
    _save_reference(reference)
    return {"status": "ok", "fact": {key: facts[key]}, "changes": changes}

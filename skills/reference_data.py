"""
Données de référence (taux, plafonds, fiscalité, ETF) — logique pure, sans réseau.

Principe :
- chaque fait porte sa valeur, sa source, `verified_at` (dernière confirmation live)
  et `updated_at` (dernier changement de valeur) ;
- un fetch réussi met à jour la valeur ET devient la nouvelle valeur de repli ;
- un changement de valeur est journalisé dans `changes` (sert aux « actualités »).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

REFRESH_TTL = timedelta(hours=24)
RETRY_AFTER_FAILURE = timedelta(hours=1)
STALE_AFTER_DAYS = 30


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def needs_refresh(reference: dict, now: datetime) -> bool:
    """
    True si le dernier fetch réussi date de plus de 24h (ou n'a jamais eu lieu),
    sauf si une tentative a échoué il y a moins d'1h (évite de marteler les sources).
    """
    last_success = parse_iso(reference.get("last_successful_fetch"))
    last_attempt = parse_iso(reference.get("last_fetch_attempt"))
    if last_success and now - last_success < REFRESH_TTL:
        return False
    if last_attempt and (not last_success or last_attempt > last_success):
        return now - last_attempt >= RETRY_AFTER_FAILURE
    return True


def _values_differ(old: object, new: object) -> bool:
    if isinstance(old, (int, float)) and isinstance(new, (int, float)):
        return abs(float(old) - float(new)) > 1e-9
    return old != new


def merge_facts(
    facts: dict[str, dict],
    fetched: dict[str, float | int | None],
    fetched_on: str,
) -> tuple[dict[str, dict], list[dict]]:
    """
    Fusionne des valeurs fraîchement récupérées dans les faits connus.
    Les valeurs None (non trouvées) sont ignorées : l'ancienne valeur reste le repli.
    Retourne (faits mis à jour, changements détectés).
    """
    updated = {key: dict(fact) for key, fact in facts.items()}
    changes = []
    for key, value in fetched.items():
        if value is None:
            continue
        fact = updated.setdefault(key, {"label": key})
        old = fact.get("value")
        if old is not None and _values_differ(old, value):
            changes.append(
                {
                    "date": fetched_on,
                    "key": key,
                    "label": fact.get("label", key),
                    "old": old,
                    "new": value,
                }
            )
        if old is None or _values_differ(old, value):
            fact["updated_at"] = fetched_on
        fact["value"] = value
        fact["verified_at"] = fetched_on
        fact["origin"] = "live"
    return updated, changes


def merge_etf(entry: dict, fetched: dict, fetched_on: str) -> tuple[dict, list[dict]]:
    """Met à jour une entrée du catalogue ETF (TER, encours, éligibilité PEA)."""
    updated = dict(entry)
    changes = []
    for field in ("ter", "fund_size_meur", "pea_eligible", "name"):
        value = fetched.get(field)
        if value is None:
            continue
        old = updated.get(field)
        if field == "ter" and old is not None and _values_differ(old, value):
            changes.append(
                {
                    "date": fetched_on,
                    "key": f"etf.{entry.get('ticker', '?')}.ter",
                    "label": f"TER {entry.get('ticker', '?')}",
                    "old": old,
                    "new": value,
                }
            )
        updated[field] = value
    updated["verified_at"] = fetched_on
    return updated, changes


def stale_facts(facts: dict[str, dict], today: date, max_age_days: int = STALE_AFTER_DAYS) -> list[dict]:
    """Faits dont la dernière vérification live dépasse max_age_days (à revérifier)."""
    stale = []
    for key, fact in facts.items():
        verified = parse_iso(fact.get("verified_at"))
        age = (today - verified.date()).days if verified else None
        if age is None or age > max_age_days:
            stale.append(
                {
                    "key": key,
                    "label": fact.get("label", key),
                    "value": fact.get("value"),
                    "verified_at": fact.get("verified_at"),
                    "age_days": age,
                    "source": fact.get("source"),
                }
            )
    return stale


def changes_since(changes: list[dict], since: str | None) -> list[dict]:
    """Changements dont la date est postérieure à `since` (ISO). Tous si since est None."""
    if not since:
        return list(changes)
    return [c for c in changes if c.get("date", "") > since]


def fact_value(reference: dict, key: str) -> float | int | None:
    """Valeur courante d'un fait (None si inconnu)."""
    return reference.get("facts", {}).get(key, {}).get("value")


def format_value(value: object, unit: str | None) -> str:
    if value is None:
        return "inconnu"
    if unit == "taux" and isinstance(value, (int, float)):
        return f"{value * 100:.2f}".rstrip("0").rstrip(".").replace(".", ",") + " %"
    if unit == "euros" and isinstance(value, (int, float)):
        return f"{value:,.0f}".replace(",", " ") + " €"
    return str(value)

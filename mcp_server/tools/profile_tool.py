"""
Tool MCP : profil utilisateur et revue de situation.

Flux :
1. review_situation() → résumé point par point + changements probables
   + « Votre situation a-t-elle changé depuis le … ? »
2a. Oui → update_situation(changes_json)
2b. Non → confirm_situation_unchanged()
Déclenché quand l'utilisateur évoque un changement, ou automatiquement tous les
`review.interval_days` jours (voir start_session).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import ValidationError

from mcp_server.profile import store
from mcp_server.profile.changes import apply_changes
from mcp_server.profile.schema import ReviewEntry, UserProfile
from skills import situation_review as sr


def _today():
    return datetime.now(timezone.utc).date()


def _reference_facts() -> dict:
    from mcp_server.tools import reference_tool

    reference = reference_tool.get_reference()
    return {k: f.get("value") for k, f in reference.get("facts", {}).items()}


def _mark_reviewed(profile: UserProfile, outcome: str, changes: list[str]) -> None:
    today = _today().isoformat()
    profile.review.last_review_date = today
    profile.review.balances_at_last_review = {a.id: a.balance for a in profile.accounts}
    profile.review.history.append(ReviewEntry(date=today, outcome=outcome, changes=changes))  # type: ignore[arg-type]
    profile.review.history = profile.review.history[-50:]


def review_situation() -> dict:
    """Résumé de la situation enregistrée + changements probables à confirmer."""
    profile = store.load_profile()
    if profile is None:
        return {
            "status": "onboarding",
            "message": "Aucun profil enregistré. Poser ces questions (une ou deux à la fois), "
            "puis enregistrer les réponses avec update_situation().",
            "questions": sr.onboarding_questions(None),
            "privacy": "Le profil reste en local (mcp_server/context/user_profile.json, gitignoré).",
        }

    data = profile.model_dump()
    today = _today()
    last = profile.review.last_review_date
    return {
        "status": "ok",
        "last_review_date": last,
        "review_due": sr.is_review_due(data, today),
        "summary": sr.summarize_situation(data, today),
        "probable_changes": sr.detect_probable_changes(data, _reference_facts(), today),
        "missing_info": sr.onboarding_questions(data),
        "question": (
            f"Votre situation a-t-elle changé depuis le {last} ?"
            if last
            else "Ce résumé correspond-il toujours à votre situation ?"
        ),
        "next_step": "Si oui → update_situation(changes_json). Si non → confirm_situation_unchanged().",
    }


def update_situation(changes_json: str) -> dict:
    """
    Applique des changements au profil (profil partiel en JSON).
    Exemples :
      {"income": {"sources": [{"id": "stage_1", "end": "2026-08"}]}}
      {"accounts": [{"id": "livret_x", "category": "regulated_savings", "needs_classification": false}]}
      {"pea": {"status": "open", "first_deposit_date": "2026-06-02"}}
    """
    try:
        changes = json.loads(changes_json)
    except json.JSONDecodeError as e:
        return {"status": "error", "error": f"JSON invalide: {e}"}
    if not isinstance(changes, dict):
        return {"status": "error", "error": "changes_json doit être un objet JSON"}

    existing = store.load_profile()
    is_new = existing is None
    profile = existing or store.new_profile()

    try:
        updated_data, summary = apply_changes(profile.model_dump(), changes)
        updated = UserProfile.model_validate(updated_data)
    except (ValueError, ValidationError) as e:
        return {"status": "error", "error": str(e), "note": "Aucune modification enregistrée"}

    _mark_reviewed(updated, "onboarding" if is_new else "updated", summary)
    store.save_profile(updated)
    return {
        "status": "ok",
        "changes_applied": summary or ["Aucun changement"],
        "missing_info": sr.onboarding_questions(updated.model_dump()),
    }


def confirm_situation_unchanged() -> dict:
    """L'utilisateur confirme que rien n'a changé : on enregistre la revue et on continue."""
    profile = store.require_profile()
    _mark_reviewed(profile, "unchanged", [])
    store.save_profile(profile)
    return {
        "status": "ok",
        "last_review_date": profile.review.last_review_date,
        "next_review_in_days": profile.review.interval_days,
    }


def start_session() -> dict:
    """
    Point d'entrée de session : données de référence à jour (fetch si > 24h),
    synchro Finary, actualités réglementaires, et revue de situation si elle est due.
    """
    from mcp_server.tools import portfolio_tool, reference_tool

    try:
        reference_report = reference_tool.refresh()
    except Exception as e:
        reference_report = {"refreshed": False, "errors": [str(e)]}
    sync = portfolio_tool.sync_profile()
    news = reference_tool.get_regulatory_news()

    profile = store.load_profile()
    review_due = sr.is_review_due(profile.model_dump(), _today()) if profile else {"due": True, "reason": "onboarding"}

    result = {
        "reference_data": {
            "refreshed": reference_report.get("refreshed"),
            "last_successful_fetch": reference_report.get("last_successful_fetch"),
            "errors": reference_report.get("errors", []),
        },
        "finary_sync": {
            k: sync.get(k)
            for k in (
                "status",
                "synced_at",
                "total_net_worth",
                "changes",
                "unclassified_accounts",
                "error",
                "action_required",
            )
            if sync.get(k) is not None
        },
        "regulatory_news": news["news"],
        "stale_reference_facts": news["stale_facts"],
        "review_due": review_due,
    }
    if review_due["due"]:
        result["situation_review"] = review_situation()
        result["instruction"] = (
            "Présenter le résumé point par point à l'utilisateur et lui demander si sa situation "
            "a changé avant de donner des conseils."
        )
    return result

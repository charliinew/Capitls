"""
Application de mises à jour partielles au profil — fonction pure (dict → dict).

Format des changements : un profil partiel.
- Objets : fusion récursive (`{"rules": {"liquidity_min": 800}}`).
- Listes d'objets avec `id` (accounts, income.sources) : fusion par `id`,
  ajout si l'id est nouveau, suppression avec `{"id": "...", "_delete": true}`.
- Autres listes / valeurs : remplacées.
"""

from __future__ import annotations

import copy

PROTECTED_KEYS = {"schema_version", "meta", "review", "finary_snapshot"}


def _merge_list(current: list, updates: list, path: str, summary: list[str]) -> list:
    if not all(isinstance(u, dict) and "id" in u for u in updates):
        summary.append(f"{path} remplacé")
        return copy.deepcopy(updates)

    result = copy.deepcopy(current)
    for update in updates:
        index = next(
            (i for i, item in enumerate(result) if isinstance(item, dict) and item.get("id") == update["id"]), None
        )
        if update.get("_delete"):
            if index is not None:
                result.pop(index)
                summary.append(f"{path}[{update['id']}] supprimé")
            continue
        if index is None:
            result.append({k: v for k, v in update.items() if k != "_delete"})
            summary.append(f"{path}[{update['id']}] ajouté")
        else:
            result[index] = _merge_dict(result[index], update, f"{path}[{update['id']}]", summary)
    return result


def _merge_dict(current: dict, updates: dict, path: str, summary: list[str]) -> dict:
    result = copy.deepcopy(current)
    for key, value in updates.items():
        sub_path = f"{path}.{key}" if path else key
        old = result.get(key)
        if isinstance(value, dict) and isinstance(old, dict):
            result[key] = _merge_dict(old, value, sub_path, summary)
        elif isinstance(value, list) and isinstance(old, list):
            result[key] = _merge_list(old, value, sub_path, summary)
        elif old != value:
            result[key] = copy.deepcopy(value)
            if key != "id":
                summary.append(f"{sub_path}: {old!r} → {value!r}")
    return result


def apply_changes(profile: dict, changes: dict) -> tuple[dict, list[str]]:
    """Retourne (profil mis à jour, résumé lisible des changements). Clés système protégées."""
    forbidden = PROTECTED_KEYS & set(changes)
    if forbidden:
        raise ValueError(f"Champs non modifiables via update_situation : {sorted(forbidden)}")
    summary: list[str] = []
    return _merge_dict(profile, changes, "", summary), summary

"""
Persistance du profil utilisateur — point d'accès unique en lecture/écriture.

- Fichier local uniquement (gitignoré), permissions 600.
- Écriture atomique (fichier temporaire + os.replace) : pas de JSON corrompu en cas de crash.
- Migration automatique de l'ancien format, avec sauvegarde `.v1.bak` avant la première écriture.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path

from mcp_server.profile.migration import is_legacy, migrate_v1_to_v2
from mcp_server.profile.schema import UserProfile

PROFILE_PATH = Path(
    os.getenv(
        "CAPITLS_PROFILE_PATH",
        Path(__file__).parent.parent / "context" / "user_profile.json",
    )
)


class ProfileMissingError(Exception):
    """Aucun profil : l'onboarding (review_situation) doit être lancé."""


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def load_profile() -> UserProfile | None:
    """Charge (et migre si besoin) le profil. None si aucun profil n'existe encore."""
    if not PROFILE_PATH.exists():
        return None
    with open(PROFILE_PATH, encoding="utf-8") as f:
        raw = json.load(f)

    if is_legacy(raw):
        backup = PROFILE_PATH.with_suffix(".json.v1.bak")
        if not backup.exists():
            shutil.copy2(PROFILE_PATH, backup)
            os.chmod(backup, 0o600)
        profile = UserProfile.model_validate(migrate_v1_to_v2(raw))
        _write(profile)
        return profile

    return UserProfile.model_validate(raw)


def require_profile() -> UserProfile:
    profile = load_profile()
    if profile is None:
        raise ProfileMissingError("Aucun profil utilisateur. Lancer review_situation() pour l'onboarding.")
    return profile


def _write(profile: UserProfile) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PROFILE_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(profile.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.chmod(tmp, 0o600)
    os.replace(tmp, PROFILE_PATH)


def save_profile(profile: UserProfile) -> None:
    profile.meta.last_updated = _today()
    if profile.meta.created_at is None:
        profile.meta.created_at = _today()
    _write(profile)


def new_profile() -> UserProfile:
    profile = UserProfile()
    profile.meta.created_at = _today()
    return profile

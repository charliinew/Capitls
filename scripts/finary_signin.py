"""
Connexion Finary automatisée avec génération TOTP.
Lit FINARY_EMAIL, FINARY_PASSWORD, FINARY_TOTP_SECRET depuis .env
Usage : uv run python scripts/finary_signin.py
"""

import os
import sys

import pyotp
from dotenv import load_dotenv

load_dotenv()


def signin():
    email = os.getenv("FINARY_EMAIL")
    password = os.getenv("FINARY_PASSWORD")
    totp_secret = os.getenv("FINARY_TOTP_SECRET")

    if not email or not password:
        print("❌ FINARY_EMAIL ou FINARY_PASSWORD manquant dans .env")
        sys.exit(1)

    # Générer le code TOTP automatiquement
    otp_code = ""
    if totp_secret:
        totp = pyotp.TOTP(totp_secret.strip())
        otp_code = totp.now()
        print("✓ Code TOTP généré automatiquement")
    else:
        print("⚠️  FINARY_TOTP_SECRET absent — tentative sans MFA")

    # Lancer la connexion via finary_uapi
    from finary_uapi.signin import signin as finary_signin

    try:
        result = finary_signin(otp_code)
        status = result.get("response", {}).get("status", "")
        if status == "complete" or "client" in result:
            print("✅ Connexion Finary réussie. Session sauvegardée.")
        elif status == "needs_second_factor":
            print("❌ Code TOTP incorrect ou expiré. Vérifier FINARY_TOTP_SECRET dans .env")
            sys.exit(1)
        else:
            print(f"❌ Réponse inattendue : {result}")
            sys.exit(1)
    except RuntimeError as e:
        print(f"❌ Erreur : {e}")
        sys.exit(1)


if __name__ == "__main__":
    signin()

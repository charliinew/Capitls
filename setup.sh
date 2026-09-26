#!/usr/bin/env bash
# setup.sh — Initialisation complète du projet Capitls
# Usage : bash setup.sh

set -e

echo "🚀 Setup Capitls — Agent Financier Personnel"
echo "============================================"

# 1. Vérifier uv
if ! command -v uv &> /dev/null; then
    echo "→ Installation de uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi
echo "✓ uv disponible"

# 2. Dépendances + fichiers locaux (.env, credentials.json, .mcp.json)
make setup

echo ""
echo "✅ Setup terminé !"
echo ""
echo "Prochaines étapes :"
echo "  1. Remplir .env (FINARY_EMAIL, FINARY_PASSWORD, FINARY_TOTP_SECRET)"
echo "  2. Remplir credentials.json (email/password, utilisé par finary_uapi)"
echo "  3. make finary-signin   ← connexion initiale"
echo "  4. make test            ← vérifier que tout fonctionne"
echo "  5. Redémarrer Claude Code puis lancer /capitls — l'onboarding construit ton profil"
echo "     (stocké uniquement en local dans mcp_server/context/user_profile.json, gitignoré)"

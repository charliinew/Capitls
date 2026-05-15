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
    export PATH="$HOME/.cargo/bin:$PATH"
fi
echo "✓ uv disponible"

# 2. Installer les dépendances
echo "→ Installation des dépendances Python..."
uv sync --dev
echo "✓ Dépendances installées"

# 3. Créer le .env si absent
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  .env créé depuis .env.example"
    echo "   Ouvrir .env et remplir :"
    echo "   - FINARY_EMAIL=ton.email@finary.com"
    echo "   - FINARY_PASSWORD=ton_mot_de_passe"
    echo ""
fi

# 4. Vérifier credentials.json pour finary_uapi
if [ ! -f credentials.json ]; then
    if [ -f credentials.json.tpl ]; then
        cp credentials.json.tpl credentials.json
        echo "⚠️  credentials.json créé depuis le template — remplir avec tes identifiants Finary"
    else
        cat > credentials.json << 'EOF'
{
    "email": "",
    "password": ""
}
EOF
        echo "⚠️  credentials.json créé — remplir avec tes identifiants Finary"
    fi
fi

echo ""
echo "✅ Setup terminé !"
echo ""
echo "Prochaines étapes :"
echo "  1. Remplir .env avec tes credentials Finary"
echo "  2. Remplir credentials.json avec email/password"
echo "  3. make finary-signin MFA=<code_2fa>  ← connexion initiale (2FA requis)"
echo "  4. make test                           ← vérifier que les skills fonctionnent"
echo "  5. make run                            ← lancer le serveur MCP"
echo ""
echo "Claude Code détecte automatiquement le serveur via .claude/settings.json"
echo "Redémarre Claude Code pour activer le MCP server."

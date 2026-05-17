.PHONY: setup run test test-cov lint finary-signin help

help:
	@echo "Commandes disponibles:"
	@echo "  make setup              Initialisation complète du projet"
	@echo "  make run                Lance le serveur MCP (test stdio)"
	@echo "  make test               Tests unitaires"
	@echo "  make test-cov           Tests avec rapport de couverture"
	@echo "  make lint               Ruff + mypy"
	@echo "  make finary-signin MFA=123456  Connexion Finary (2FA requis)"

setup:
	@echo "→ Installation des dépendances..."
	uv sync --dev
	@echo "→ Création du .env..."
	@test -f .env || cp .env.example .env && echo "  .env créé — remplir FINARY_EMAIL et FINARY_PASSWORD"
	@test -f credentials.json || cp credentials.json.tpl credentials.json 2>/dev/null || echo "  credentials.json.tpl non trouvé, créer credentials.json manuellement"
	@echo "→ Génération de .claude/settings.json..."
	@mkdir -p .claude
	@if [ ! -f .claude/settings.json ]; then \
		sed "s|{{PROJECT_DIR}}|$$(pwd)|g" .claude/settings.json.example > .claude/settings.json && \
		echo "  .claude/settings.json généré (cwd: $$(pwd))"; \
	else \
		echo "  .claude/settings.json déjà présent"; \
	fi
	@echo "→ Profil utilisateur..."
	@if [ ! -f mcp_server/context/user_profile.json ] && [ -f mcp_server/context/user_profile.example.json ]; then \
		cp mcp_server/context/user_profile.example.json mcp_server/context/user_profile.json && \
		echo "  user_profile.json créé depuis l'exemple"; \
	fi
	@echo "✓ Setup terminé. Lancer: make finary-signin MFA=<code>"

run:
	uv run python -m mcp_server.main

test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ --cov=skills --cov=adapters --cov-report=term-missing

lint:
	uv run ruff check .
	uv run mypy mcp_server/ adapters/ skills/

finary-signin:
	uv run python scripts/finary_signin.py

.PHONY: setup run test test-cov lint finary-signin refresh-reference help

help:
	@echo "Commandes disponibles:"
	@echo "  make setup              Initialisation complète du projet"
	@echo "  make run                Lance le serveur MCP (test stdio)"
	@echo "  make test               Tests unitaires"
	@echo "  make test-cov           Tests avec rapport de couverture"
	@echo "  make lint               Ruff + mypy"
	@echo "  make finary-signin      Connexion Finary (TOTP généré depuis .env)"
	@echo "  make refresh-reference  Force la mise à jour des taux / ETF (service-public, justETF)"

setup:
	@echo "→ Installation des dépendances..."
	uv sync --dev
	@echo "→ Création du .env..."
	@test -f .env || (cp .env.example .env && echo "  .env créé — remplir FINARY_EMAIL, FINARY_PASSWORD, FINARY_TOTP_SECRET")
	@test -f credentials.json || cp credentials.json.tpl credentials.json
	@chmod 600 .env credentials.json 2>/dev/null || true
	@echo "→ Génération de .mcp.json (serveur MCP projet pour Claude Code)..."
	@if [ ! -f .mcp.json ]; then \
		sed "s|{{PROJECT_DIR}}|$$(pwd)|g" .mcp.json.example > .mcp.json && \
		echo "  .mcp.json généré (répertoire: $$(pwd))"; \
	else \
		echo "  .mcp.json déjà présent"; \
	fi
	@echo "✓ Setup terminé. Le profil utilisateur est créé au premier lancement (onboarding via review_situation)."
	@echo "  Étape suivante : make finary-signin"

run:
	uv run python -m mcp_server.main

test:
	uv run pytest tests/ -v

test-cov:
	uv run pytest tests/ --cov=skills --cov=adapters --cov=mcp_server --cov-report=term-missing

lint:
	uv run ruff check .
	uv run mypy mcp_server/ adapters/ skills/

finary-signin:
	uv run python scripts/finary_signin.py

refresh-reference:
	uv run python -c "from mcp_server.tools import reference_tool as r; import json; print(json.dumps(r.get_reference_data(force_refresh=True)['refresh'], indent=2, ensure_ascii=False))"

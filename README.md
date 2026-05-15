# Capitls

Agent MCP de finance personnelle connecté à Finary, spécialisé marché français (PEA, ETFs, DCA).

S'utilise dans Claude Code via le skill `/capitls` ou directement avec les tools MCP. L'agent récupère le portfolio Finary en temps réel, analyse l'allocation, calcule un plan DCA Fortuneo, compare les ETFs, et projette le patrimoine sur plusieurs scénarios.

---

## Prérequis

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) — gestionnaire de paquets
- Un compte Finary avec 2FA activée
- Claude Code (CLI)

---

## Setup

### 1. Installer les dépendances

```bash
make setup
```

Crée le virtualenv, installe les dépendances, et génère un `.env` depuis `.env.example`.

### 2. Configurer les credentials

Remplir `.env` :

```env
FINARY_EMAIL=ton@email.com
FINARY_PASSWORD=ton_mot_de_passe_finary
FINARY_TOTP_SECRET=ABCDEF...   # secret TOTP base32 depuis ton app d'authentification
```

Pour récupérer `FINARY_TOTP_SECRET` : dans Apple Passwords / Authy, affiche les détails de l'entrée Finary — le secret base32 est visible dans les paramètres avancés.

### 3. Se connecter à Finary

```bash
make finary-signin
```

Génère le code TOTP automatiquement et sauvegarde la session (cookies + JWT). À refaire si la session expire (généralement après quelques semaines).

### 4. Activer le serveur MCP

Le fichier `~/.claude/.mcp.json` est configuré pour un accès global depuis n'importe quel projet Claude Code. **Redémarrer Claude Code** suffit.

Pour Claude Desktop, ajouter dans `~/Library/Application Support/Claude/claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "capitls": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_server.main"],
      "cwd": "/chemin/absolu/vers/Capitls"
    }
  }
}
```

---

## Utilisation

### Skill orchestrateur

```
/capitls analyse mon portfolio
/capitls prix de DCAM aujourd'hui
/capitls est-ce que WPEA est éligible PEA ?
/capitls que faire avec mes 200€ ce mois ?
/capitls simule un portfolio 70% world, 20% épargne, 10% crypto
```

Le skill `/capitls` identifie l'intention et route automatiquement vers le bon agent spécialisé.

### Agents spécialisés (invocables directement)

| Agent | Usage |
|-------|-------|
| `capitls-portfolio` | Analyse Finary temps réel, allocation, alertes liquidité |
| `capitls-market` | Prix ETF Euronext Paris, crypto, comparaisons |
| `capitls-regulation` | Règles PEA 2026, fiscalité, éligibilité ISIN |
| `capitls-advisor` | Conseil complet — DCA Fortuneo, projections, recommandations |

---

## Fonctionnalités détaillées

### Portfolio Finary

- **Sync temps réel** — `sync_profile()` synchronise `user_profile.json` avec les soldes Finary live (comptes, crypto, total net worth)
- **Résumé des comptes** — vérifie la liquidité minimale (600€), l'allocation crypto, exclut le compte Indy Pro (provision URSSAF)
- **Historique des décisions** — enregistrement horodaté des décisions financières dans le profil

### Données de marché

- **ETF Euronext Paris** — prix, variation 1j, historique jusqu'à 10 ans (Yahoo Finance) pour DCAM, WPEA, CW8 et tout ETF avec suffixe `.PA`
- **Crypto** — prix en EUR en temps réel via CoinGecko (BTC, ETH, SOL, etc.)
- **Snapshot MSCI World** — comparaison instantanée de tous les ETFs World PEA principaux

### Réglementation PEA

- **Règles 2026** — plafond 150 000€, fiscalité avant/après 5 ans (0% IR + 18.6% PS après 5 ans), conditions de retrait
- **Comparaison fiscale** — calcul chiffré de l'avantage PEA vs flat tax CTO pour un montant de gains donné
- **Éligibilité ISIN** — vérification base 2026 pour tout ISIN

### DCA Fortuneo

- **Plan DCA adapté** — calcule le nombre de parts à acheter, vérifie que l'ordre est ≤ 500€ (gratuit Fortuneo), projette sur N ans
- **Timing d'achat** — score 0-100 basé sur le percentile prix/SMA63j : ≤30 = bon point d'entrée, >70 = prix élevé
- **Rappel mensuel** — `get_dca_reminder()` détecte si l'ordre du mois a été passé et alerte si non
- **Capacité d'investissement** — calcule le montant investissable selon revenus et dépenses fixes (stage 900€ + freelance variable)

### Suivi PEA

- **Countdown 5 ans** — jours/mois restants avant l'exonération totale (0% IR), calculé depuis `opening_date`
- **Historique des ordres** — chaque ordre enregistré via `record_pea_order()` : date, ETF, montant, prix, nombre de parts, is_free
- **Performance P&L** — calcul du gain/perte sur l'historique des ordres vs prix actuel
- **Prochain ordre recommandé** — date et montant basés sur le dernier ordre enregistré

### Analyse et projections

- **Projections multi-scénarios** — pessimiste (4%), neutre (7%), optimiste (10%) sur N ans
- **Comparaison DCA vs lump sum** — simulation sur données historiques, win rate sur les 12 derniers mois
- **Benchmark** — comparaison performance ETF vs MSCI World (EUNL.DE) sur 1y/2y/5y
- **Simulation d'allocation** — impact d'un rééquilibrage cible (world/crypto/épargne) avec actions concrètes
- **Modèle étudiant** — comparaison vs allocation de référence 70% World / 20% épargne / 10% crypto
- **Alerte crypto** — détection si la part crypto dépasse le seuil recommandé (15% du patrimoine)

### Budget et revenus

- **Enregistrement des revenus** — `record_monthly_income()` historise les revenus mensuels (stage + freelance)
- **DCA optimal** — calcul du montant investissable basé sur l'historique des revenus, recommandation conservatrice (mois le plus faible)

### ETFs MSCI World PEA — référence 2026

| ETF | ISIN | TER | Note |
|-----|------|-----|------|
| **DCAM** (Amundi PEA Monde) | FR001400U5Q4 | 0.20% | Recommandé — lancé mars 2025 |
| **WPEA** (iShares MSCI World Swap) | IE0002XZSHO1 | 0.20% | Recommandé — lancé avril 2024 |
| CW8 (Amundi MSCI World) | LU1681043599 | 0.38% | Très liquide (5.6Md€) |
| ~~EWLD~~ | FR0011869353 | 0.45% | Obsolète — déconseillé |

Tous en réplication synthétique (swap) pour l'éligibilité PEA.

---

## Outils MCP (22 tools)

### Portfolio
| Tool | Description |
|------|-------------|
| `sync_profile` | Synchronise user_profile.json avec les soldes Finary live |
| `get_portfolio` | Portfolio complet Finary (comptes, soldes, net worth) |
| `get_accounts_summary` | Résumé des comptes avec vérification des règles personnelles |
| `get_pea_status` | Statut complet du PEA : countdown 5 ans, P&L, prochain ordre |
| `record_pea_order` | Enregistre un ordre PEA exécuté dans le profil |
| `get_dca_reminder` | Vérifie si l'ordre mensuel a été passé ce mois |
| `record_monthly_income` | Enregistre un revenu mensuel (stage/freelance) |
| `record_decision` | Historique des décisions financières |

### Marché
| Tool | Description |
|------|-------------|
| `get_etf_price` | Prix et variation 1j d'un ETF Euronext Paris |
| `get_etf_history` | Historique prix (1d → 10y) |
| `get_world_etfs` | Snapshot DCAM, WPEA, CW8, EWLD |
| `get_crypto_prices` | Prix crypto en EUR (BTC, ETH, SOL…) |

### Réglementation
| Tool | Description |
|------|-------------|
| `get_pea_rules` | Règles PEA 2026 |
| `get_tax_comparison` | Comparaison fiscale PEA vs CTO pour un montant de gains |
| `check_etf_pea_eligibility` | Éligibilité PEA par ISIN |

### Analyse
| Tool | Description |
|------|-------------|
| `analyze_portfolio` | Diversification, liquidité, alertes |
| `recommend_dca_plan` | Plan DCA adapté Fortuneo (1 ordre/mois ≤ 500€) |
| `compare_etfs` | Comparaison ETFs (TER, ISIN, impact frais) |
| `project_wealth` | Projection patrimoine multi-scénarios |
| `get_dca_timing` | Score timing achat 0-100 (percentile prix/SMA63j) |
| `get_investment_capacity` | Capacité DCA mensuelle selon revenus |
| `compare_vs_benchmark` | ETF vs MSCI World (EUNL.DE) sur 1y/2y/5y |
| `simulate_portfolio` | Simulation rééquilibrage cible world/crypto/épargne |

---

## Architecture

```
Capitls/
├── mcp_server/
│   ├── main.py                  # 22 tools MCP enregistrés
│   ├── tools/
│   │   ├── portfolio_tool.py    # Finary sync, PEA tracker, revenus
│   │   ├── market_tool.py       # ETF + crypto temps réel
│   │   ├── regulation_tool.py   # Règles PEA, fiscalité, ISIN
│   │   └── analysis_tool.py     # DCA, projections, benchmark, simulation
│   └── context/
│       └── user_profile.json    # Situation persistée (gitignorée)
│
├── adapters/
│   ├── base_adapter.py          # Interface abstraite
│   ├── finary_adapter.py        # finary_uapi → format interne (subprocess)
│   └── market_adapter.py        # yfinance + CoinGecko → format interne
│
├── skills/                      # Calculs financiers purs (zéro réseau, testables)
│   ├── dca.py                   # Projections DCA, plan Fortuneo
│   ├── tax.py                   # Fiscalité PEA, retour réel
│   ├── diversification.py       # Score diversification, overlaps ETF
│   ├── projection.py            # Projections multi-scénarios
│   ├── etf.py                   # Catalogue ETF, TER, recommandations
│   ├── pea_tracker.py           # Countdown 5 ans, historique ordres, P&L
│   ├── timing.py                # Score timing achat (percentile SMA)
│   ├── benchmark.py             # DCA vs lump sum, comparaison rendements
│   ├── simulation.py            # Simulation allocation, modèle étudiant, alerte crypto
│   └── budget.py                # Capacité d'investissement, DCA optimal
│
├── scripts/
│   └── finary_signin.py         # Connexion Finary avec TOTP automatique
│
└── tests/
    └── test_skills.py           # 94 tests unitaires (zéro réseau)
```

**Règle fondamentale** : tout appel réseau passe par un adapter. Les skills sont des fonctions pures. Les tools MCP appellent adapters et skills, jamais les sources directement.

---

## Développement

```bash
make test        # 94 tests unitaires
make test-cov    # Tests avec couverture
make lint        # Ruff + mypy
make run         # Lance le serveur MCP en local (test stdio)
make finary-signin  # Reconnexion Finary (si session expirée)
```

### Dépendances clés

| Package | Version | Rôle |
|---------|---------|------|
| `fastmcp` | ≥3.2.0 | Serveur MCP (stdio) |
| `finary-uapi` | ≥0.2.3 | Client Finary non-officiel |
| `yfinance` | ≥0.2.50,<1.3.0 | Données ETF/actions |
| `pycoingecko` | ≥3.1 | Données crypto |
| `pyotp` | ≥2.9 | Génération TOTP automatique |

> `yfinance` est contraint à `<1.3.0` pour éviter un conflit avec `curl-cffi` utilisé par `finary-uapi`.

---

## Sécurité

- `.env`, `credentials.json`, `jwt.json`, `localCookiesMozilla.txt` et `user_profile.json` sont dans `.gitignore`
- Ne jamais committer de credentials ou de données financières réelles

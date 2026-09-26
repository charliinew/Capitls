# Capitls

Agent MCP de finance personnelle connecté à Finary, spécialisé marché français (PEA, ETF, épargne réglementée, DCA).

S'utilise dans Claude Code via le skill `/capitls` ou directement avec les tools MCP. L'agent synchronise vos comptes Finary, construit votre profil par un court questionnaire, garde les taux et la fiscalité à jour automatiquement, et vous conseille selon **votre** situation : courtier, règles d'épargne, objectifs.

- **Générique** : aucune situation n'est supposée. Chaque utilisateur a son profil, stocké uniquement en local.
- **Données toujours à jour** : taux des livrets, plafonds, fiscalité et frais des ETF sont récupérés sur service-public.fr et justETF (au plus toutes les 24h), avec une valeur de repli datée si une source est indisponible.
- **Suivi de situation** : à intervalle régulier, ou dès que vous évoquez un changement, l'agent résume votre situation point par point et vous demande si elle a changé.

---

## Prérequis

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Un compte Finary (2FA TOTP recommandée)
- Claude Code

---

## Installation

```bash
git clone <repo>
cd Capitls
make setup
```

`make setup` :
- installe les dépendances (dont les outils de dev) via `uv sync --dev`
- crée `.env` depuis `.env.example` et `credentials.json` depuis `credentials.json.tpl` (chmod 600)
- génère `.mcp.json` (déclaration du serveur MCP pour Claude Code, chemin absolu de ce clone)

### Identifiants Finary

Dans `.env` :

```env
FINARY_EMAIL=vous@example.com
FINARY_PASSWORD=...
FINARY_TOTP_SECRET=...   # secret TOTP base32 de votre application d'authentification
```

Dans `credentials.json` (utilisé par `finary_uapi`) : `{ "email": "...", "password": "..." }`

> Le secret TOTP et le mot de passe dans le même fichier annulent l'intérêt de la 2FA si ce fichier fuite : gardez `.env` en `chmod 600`, hors de toute sauvegarde partagée.

### Connexion et démarrage

```bash
make finary-signin   # génère le code TOTP et enregistre la session (à refaire quand elle expire)
make test            # vérifie l'installation (aucun appel réseau)
```

Redémarrez Claude Code : le serveur `capitls` est détecté via `.mcp.json`. Lancez `/capitls` : au premier usage, l'agent vous pose quelques questions (revenus, épargne de précaution, PEA et courtier, objectifs…) et crée votre profil.

Pour Claude Desktop, ajoutez dans `~/Library/Application Support/Claude/claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "capitls": {
      "command": "uv",
      "args": ["run", "--directory", "/chemin/absolu/vers/Capitls", "python", "-m", "mcp_server.main"]
    }
  }
}
```

---

## Utilisation

```
/capitls analyse mon patrimoine
/capitls que faire avec mon épargne ce mois-ci ?
/capitls quel est le taux du LEP et suis-je éligible ?
/capitls j'ai changé de travail
/capitls simule 70 % ETF monde, 10 % crypto, 20 % épargne
```

Le skill `/capitls` démarre la session (taux à jour, synchro Finary, actualités réglementaires, revue de situation si elle est due), puis route vers l'agent adapté :

| Agent | Rôle |
|-------|------|
| `capitls-portfolio` | Soldes Finary, allocation, liquidité, alertes, comptes à classer |
| `capitls-market` | Cours ETF / crypto, TER et encours des ETF |
| `capitls-regulation` | PEA, livrets, assurance-vie, fiscalité, éligibilité PEA d'un ISIN |
| `capitls-advisor` | Recommandations complètes : DCA, projections, arbitrages |

---

## Où sont les données ?

| Donnée | Emplacement | Partagée ? |
|--------|-------------|-----------|
| Votre profil : revenus, comptes, soldes Finary, courtier, PEA, règles, objectifs, revues, décisions | `mcp_server/context/user_profile.json` | **Non** : local, gitignoré, chmod 600 |
| Données publiques de référence : taux, plafonds, fiscalité, catalogue ETF | `data/reference_data.json` | Oui, aucune donnée personnelle |
| Identifiants et session Finary | `.env`, `credentials.json`, `jwt.json`, cookies | **Non** : gitignorés |

Un ancien profil (format v1) est migré automatiquement au premier lancement, sans modifier aucune valeur. Une sauvegarde `user_profile.json.v1.bak` est créée.

Le schéma complet du profil, avec des valeurs fictives, se trouve dans [`mcp_server/context/user_profile.example.json`](mcp_server/context/user_profile.example.json).

---

## Tools MCP

### Session et profil
| Tool | Description |
|------|-------------|
| `start_session` | Taux à jour, synchro Finary, actualités réglementaires, revue de situation si due |
| `review_situation` | Résumé point par point, changements probables, questions manquantes (ou onboarding) |
| `update_situation` | Met à jour le profil (profil partiel JSON, fusion des listes par `id`) |
| `confirm_situation_unchanged` | Enregistre une revue sans changement |

### Données de référence
| Tool | Description |
|------|-------------|
| `get_reference_data` | Tous les taux / plafonds / fiscalité / ETF avec date de vérification et source |
| `get_regulatory_news` | Changements depuis votre dernière consultation |
| `get_savings_rates` | Livret A, LDDS, LEP (+ plafond de revenus), Livret Jeune |
| `record_verified_fact` | Enregistre une valeur vérifiée à la main si le fetch automatique a échoué |

### Portfolio
| Tool | Description |
|------|-------------|
| `sync_profile` | Synchronise les soldes Finary (nouveaux comptes → « à classer ») |
| `get_portfolio` | Comptes et soldes (synchro automatique si > 1h) |
| `get_accounts_summary` | Liquidité disponible, part crypto, vérification de vos règles |
| `get_pea_status` | Compte à rebours fiscal, performance au prix actuel, prochain ordre |
| `record_pea_order` | Enregistre un ordre PEA exécuté |
| `get_dca_reminder` | L'ordre du mois a-t-il été passé ? |
| `record_monthly_income` | Historise un revenu mensuel |
| `record_decision` | Journal des décisions |

### Marché
| Tool | Description |
|------|-------------|
| `get_etf_price` / `get_etf_history` | Cours et historique (Euronext Paris par défaut) |
| `get_world_etfs` | Cours des ETF du catalogue |
| `get_crypto_prices` | Cours crypto en EUR |

### Réglementation
| Tool | Description |
|------|-------------|
| `get_pea_rules` | Plafonds, fiscalité avant / après exonération |
| `get_tax_comparison` | Même gain imposé en PEA, CTO et assurance-vie |
| `check_etf_pea_eligibility` | Éligibilité PEA d'un ISIN (catalogue, sinon justETF en direct) |

### Analyse
| Tool | Description |
|------|-------------|
| `analyze_portfolio` | Diversification, liquidité, actions prioritaires |
| `recommend_dca_plan` | Ordre mensuel adapté aux frais de votre courtier, ETF recommandé, projections |
| `compare_etfs` | TER, encours, éligibilité PEA, coût des frais sur 10 ans |
| `project_wealth` | Projection multi-scénarios |
| `get_dca_timing` | Position du prix vs sa moyenne 3 mois (indicatif, ne remplace pas le DCA) |
| `get_investment_capacity` | Capacité d'investissement selon revenus et dépenses fixes |
| `compare_vs_benchmark` | ETF vs benchmark sur 1y / 2y / 5y |
| `simulate_portfolio` | Simulation d'une allocation cible |

---

## Architecture

```
Capitls/
├── mcp_server/
│   ├── main.py            # Déclaration des tools
│   ├── profile/           # Schéma Pydantic, persistance, migration, mises à jour
│   ├── tools/             # profile, reference, portfolio, market, regulation, analysis
│   └── context/           # user_profile.json (local) + exemple fictif
├── adapters/              # Finary (subprocess finary_uapi), marché (yfinance, CoinGecko), référence (HTTP)
├── skills/                # Calculs purs : parseurs, revue de situation, DCA, fiscalité, ETF, projections…
├── data/                  # reference_data.json (données publiques auto-mises à jour)
├── .claude/               # Agents et skill /capitls génériques
└── tests/                 # Tests unitaires + fixtures HTML réelles, zéro réseau
```

**Principes :** tout accès externe passe par un adapter ; les skills sont des fonctions pures sans taux ni seuil personnel en dur (tout est passé en paramètre) ; si une information manque, le tool renvoie la question à poser plutôt qu'une valeur par défaut.

---

## Développement

```bash
make test               # tests unitaires (aucun réseau)
make test-cov           # avec couverture
make lint               # ruff + mypy
make run                # serveur MCP en stdio
make refresh-reference  # force la mise à jour des taux / ETF
```

> `yfinance` est contraint à `<1.3.0` pour éviter un conflit avec `curl-cffi` (utilisé par `finary-uapi`).

## Avertissement

Usage personnel. Les informations produites ne constituent pas un conseil en investissement au sens de la réglementation AMF.

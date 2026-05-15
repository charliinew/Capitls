# Capitls — Agent Financier Personnel

Agent MCP Python connecté à Finary, spécialisé en finance personnelle française.
Développement strictement personnel — aucune contrainte réglementaire AMF.

---

## Profil utilisateur (contexte persistant)

```
Étudiant EPITECH, 20 ans, Paris
Revenus irréguliers:
  - Stage Scaleway ~900€/mois (jusqu'en août 2026)
  - Freelance (variable, ponctuel)
```

### Patrimoine actuel

| Compte | Montant | Rôle |
|--------|---------|------|
| Livret Jeune | 1 600€ (plafonné) | Épargne réglementée, 1.5-3.5% exonéré |
| Épargne Revolut | 600€ (minimum à ne jamais toucher) | Liquidité de précaution |
| Crypto | ~750€ | Position longue terme |
| PEA Fortuneo | À ouvrir (1 000€ apport initial prévu) | Investissement long terme |

### Courtier PEA : Fortuneo (décision prise)

- **Tarif clé** : 1 ordre/mois < 500€ = **GRATUIT** → contrainte forte sur la fréquence
- **Parrainage actif** : 160€ offerts si 1 000€ investis initialement (à ne pas rater)
- **PAS de DCA automatique** → l'agent doit calculer et rappeler les ordres manuels
- Pas Trade Republic, pas Boursorama

### Stratégie PEA

- Apport initial : 1 000€ (étalé sur 6 mois ≈ 167€/mois supplémentaires)
- Versement mensuel cible : 200€/mois ensuite
- ETF cible : MSCI World éligible PEA (voir section ETFs)
- 1 ordre/mois maximum (contrainte Fortuneo gratuit)

---

## Contexte réglementaire France (factuel, tier_1)

### PEA — Règles 2026

- Plafond versements : **150 000€** (classique)
- Fiscalité **avant 5 ans** : 31.4% (12.8% PFU + 18.6% PS) + clôture si retrait
- Fiscalité **après 5 ans** : **0% IR + 18.6% PS** uniquement — exonération totale des gains
- Retraits partiels possibles sans clôture seulement **après 5 ans**
- Point de départ du délai : date du **premier versement** (pas date d'ouverture de compte)

### ETFs MSCI World éligibles PEA — Comparatif 2026

| ETF | ISIN | TER | Note |
|-----|------|-----|------|
| **DCAM** (Amundi PEA Monde) | FR001400U5Q4 | **0.20%** | ✅ Meilleur choix, lancé mar 2025 |
| **WPEA** (iShares MSCI World Swap) | IE0002XZSHO1 | **0.20%** | ✅ Excellent, lancé avr 2024 |
| CW8 (Amundi MSCI World Swap) | LU1681043599 | 0.38% | OK, très liquide (5.6Md€) |
| ~~EWLD~~ (Lyxor) | FR0011869353 | ~~0.45%~~ | ❌ Obsolète, frais trop élevés |

Tous utilisent la **réplication synthétique** (swap) pour être éligibles PEA.
L'agent **recommande activement** DCAM ou WPEA pour tout nouvel investissement.

### Livret Jeune

- Taux : 1.5% à 3.5% selon banque (minimum légal = taux Livret A)
- Plafond : 1 600€ (déjà atteint)
- Exonéré d'IR et de prélèvements sociaux
- Fermeture automatique au 31 décembre de l'année des 25 ans

---

## Architecture technique

```
Capitls/
├── mcp_server/           # Serveur MCP (FastMCP) — exposé à Claude Code
│   ├── main.py           # Point d'entrée, déclaration des tools
│   ├── tools/            # Tools MCP par domaine
│   │   ├── portfolio_tool.py    # Lecture portfolio Finary
│   │   ├── market_tool.py       # Cours ETF/crypto temps réel
│   │   ├── regulation_tool.py   # Règles PEA, fiscalité FR
│   │   └── analysis_tool.py     # DCA, projections, recommandations
│   └── context/
│       └── user_profile.json    # Situation persistée
│
├── adapters/             # Wrapping des sources externes
│   ├── base_adapter.py          # Interface abstraite
│   ├── finary_adapter.py        # finary_uapi → format interne
│   └── market_adapter.py        # yfinance + CoinGecko → format interne
│
├── skills/               # Calculs financiers purs (testables, sans réseau)
│   ├── dca.py            # Projections DCA, calendriers
│   ├── tax.py            # Fiscalité PEA, retour réel
│   ├── diversification.py # Score diversification, overlaps
│   ├── projection.py     # Projections multi-scénarios
│   └── etf.py            # Comparaison ETF, TER, perf
│
├── sources/
│   └── trust_hierarchy.py  # Hiérarchisation des sources
│
├── tests/
│   └── test_skills.py    # Tests unitaires skills (no network)
│
└── prompts/
    └── system_prompt.md  # Prompt système de l'agent
```

### Pattern Adapter — règle fondamentale

Tout appel à une source externe passe par un adapter. Si Finary change son API,
seul `finary_adapter.py` change. Les tools MCP appellent les adapters, jamais les
sources directement.

### Skills = fonctions pures

- Aucun appel réseau dans `skills/`
- Testables sans connexion
- Entrée → calcul → sortie (dict)

---

## Données techniques — Sources externes

### finary_uapi (version 0.2.3)

```
pip install finary-uapi
```

Auth : session cookies via `curl-cffi` (bypass anti-bot).
**L'utilisateur a la 2FA activée** → le signin initial nécessite un code MFA.

Procédure de connexion initiale (à faire une fois) :
```bash
cp credentials.json.tpl credentials.json
# Remplir email + password dans credentials.json
python -m finary_uapi signin MFA_CODE
```

Une fois connecté, la session persiste via cookies. L'adapter utilise cette session.

**Méthodes disponibles** (noms réels, pas ceux du brief initial) :
- `holdings_accounts` : tous les comptes (crypto, actions, checking, savings)
- `investments` : holdings et dividendes
- `cryptos` : positions crypto
- `savings_accounts` : livrets et épargne
- `dashboard` : patrimoine brut total
- `timeseries` : valorisation historique du portfolio

### FastMCP (MCP SDK recommandé)

```
pip install fastmcp
```

Pattern : `@mcp.tool` decorator, type hints → JSON schema auto.
Transport : stdio (Claude Code), HTTP optionnel.

### Market data

- `yfinance` : ETF/actions — utiliser suffixe `.PA` pour Euronext Paris (ex: `CW8.PA`)
  - Données Paris parfois lacunaires, tester avant de dépendre
- `pycoingecko` : crypto — API publique fiable, 30 req/min sur compte gratuit

---

## Configuration MCP (Claude Code)

Le serveur MCP est enregistré dans `.claude/settings.json` (projet) :

```json
{
  "mcpServers": {
    "capitls": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_server.main"],
      "cwd": "/Users/charlesignoux/Documents/PERSO/Capitls"
    }
  }
}
```

Pour Claude Desktop, ajouter dans `~/Library/Application Support/Claude/claude_desktop_config.json`.

---

## Commandes de développement

```bash
make setup      # Initialisation complète (uv install + .env)
make run        # Lance le serveur MCP en local (test stdio)
make test       # Tests unitaires skills
make test-cov   # Tests avec couverture
make finary-signin MFA=123456  # Connexion Finary avec code 2FA
make lint       # Ruff + mypy
```

---

## Règles de développement

1. **Ne jamais hardcoder les credentials** — toujours `.env` + `python-dotenv`
2. **`.env` dans `.gitignore`** dès le premier commit
3. **Skills = fonctions pures** — zéro appel réseau dans `skills/`
4. **Pydantic** pour valider le format interne normalisé
5. **V1 d'abord** — ne pas anticiper multi-agents avant que le mono-agent soit stable
6. **finary_uapi est non officielle** — tout appel isolé dans `finary_adapter.py`
7. **Fortuneo : 1 ordre/mois** — l'agent ne doit jamais recommander plus d'un ordre mensuel

## Format de réponse attendu de l'agent

```
[SOURCE] Tier_1 (AMF) / Tier_2 (Yahoo Finance) / Tier_3 (analyse)
[FAIT] Données objectives
[RECOMMANDATION] Contextualisée au profil et contraintes Fortuneo
[CONFIANCE] FACTUEL / ANALYSE / OPINION
```

---

## Roadmap

### V1 — ✅ Terminée
- [x] Setup projet + contexte CLAUDE.md
- [x] Structure fichiers + skills de base (56 tests unitaires)
- [x] finary_adapter.py fonctionnel (subprocess, session cookies, TOTP auto)
- [x] Test end-to-end : "Analyse mon portfolio Finary" (live via MCP)
- [x] Premier conseil DCA Fortuneo contextualisé

### V2 — ✅ Terminée
- [x] Yahoo Finance intégré (ETF Euronext Paris — DCAM, WPEA, CW8, EWLD)
- [x] CoinGecko intégré (prix temps réel + historique)
- [x] trust_hierarchy.py actif (tier_1/2/3 dans toutes les réponses)
- [x] Historique décisions dans user_profile.json
- [x] Score diversification corrigé (pénalité -25 si aucun PEA/actions)
- [x] Liquidité corrigée (compte Indy Pro exclu — provision URSSAF)
- [x] user_profile.json synchronisé avec données Finary réelles

### V3 — ✅ Terminée
- [x] Auto-sync user_profile.json depuis Finary (tool `sync_profile()`)
- [x] Agent `capitls-portfolio` — analyse portfolio Finary temps réel
- [x] Agent `capitls-market` — prix ETF Euronext Paris + crypto
- [x] Agent `capitls-regulation` — règles PEA et fiscalité française
- [x] Agent `capitls-advisor` — orchestrateur, recommandations DCA, projections
- [x] Skill `/capitls` — router intention → agent spécialisé
- [x] Serveur MCP enregistré globalement (`~/.claude/.mcp.json`)

### V4 — Idées

#### Suivi PEA actif (prioritaire dès validation Fortuneo)
- [x] Infrastructure `user_profile.json` — champs `opening_date`, `order_history`, `five_year_deadline`, `etf_cible`
- [x] `skills/pea_tracker.py` — countdown 5 ans, P&L, gestion historique ordres (fonctions pures)
- [x] MCP `get_pea_status()` — statut complet PEA : countdown, performance, prochain ordre
- [x] MCP `record_pea_order()` — persistance d'un ordre exécuté dans le profil
- [ ] Renseigner `opening_date` dans `user_profile.json` dès validation Fortuneo

#### Rappels DCA automatiques
- [x] MCP `get_dca_reminder()` — vérifie si l'ordre mensuel a été passé, retourne rappel si non
- [x] MCP `record_monthly_income()` — enregistrement des revenus mensuels dans le profil
- [ ] Cron mensuel automatique via `/schedule` (à configurer manuellement une fois PEA actif)

#### Analyse avancée
- [x] `skills/timing.py` — score timing 0-100 (percentile prix/SMA63j)
- [x] MCP `get_dca_timing(ticker)` — recommandation contextualisée Fortuneo
- [x] `skills/benchmark.py` — compare_returns() + calculate_dca_vs_lumpsum()
- [x] MCP `compare_vs_benchmark(etf, benchmark, period)` — ETF vs EUNL.DE

#### Budget et revenus
- [x] `skills/budget.py` — capacité d'investissement + DCA optimal sur historique revenus
- [x] MCP `get_investment_capacity(monthly_income, fixed_expenses)` — calcul capacité DCA
- [x] Champ `revenus.historique_mensuel` dans user_profile.json

#### Diversification future
- [x] `skills/simulation.py` — simulation allocation, comparaison modèle étudiant, alerte crypto
- [x] MCP `simulate_portfolio(world_pct, crypto_pct, savings_pct)` — simulation rééquilibrage

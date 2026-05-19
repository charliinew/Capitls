# Capitls — Agent Financier Personnel

Agent MCP Python connecté à Finary, spécialisé en finance personnelle française.
Développement strictement personnel — aucune contrainte réglementaire AMF.

---

## Profil utilisateur

Le profil de l'utilisateur (patrimoine, comptes ouverts, courtier, montants, revenus, stratégie personnelle) est stocké exclusivement dans :
- `mcp_server/context/user_profile.json` (données live, **dans `.gitignore`**)
- La mémoire privée Claude (`~/.claude/projects/.../memory/`)

**Ne jamais committer de données personnelles dans ce repo public.**

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

## Univers d'investissement exhaustif — Checklist systématique

> **Règle agent** : lors de toute recommandation, parcourir cette liste exhaustive et justifier explicitement pourquoi chaque produit est retenu ou écarté selon le profil chargé depuis `user_profile.json`. Ne jamais omettre un produit éligible sans explication.

### Épargne réglementée (livrets)

| Produit | Taux 2026 | Plafond | Fiscalité | Conditions d'éligibilité |
|---------|-----------|---------|-----------|--------------------------|
| **LEP** | **2.5%** (depuis 01/02/2026) | 10 000€ | Exonéré IR+PS | RFR < 22 419€ (vérifier avis d'imposition) |
| **Livret Jeune** | min 1.5% (= Livret A) — SG : 2.00%, CA : 2.40%, CIC/CM : 3.5% | 1 600€ | Exonéré IR+PS | 12–25 ans |
| **Livret A** | 1.5% (depuis 01/02/2026) | 22 950€ | Exonéré IR+PS | Aucune |
| **LDDS** | 1.5% (depuis 01/02/2026) | 12 000€ | Exonéré IR+PS | Majeur, résident FR |
| **CEL** | ~0.5% | 15 300€ | Fiscalisé (PFU) | — |
| **PEL** | 1.75% brut (~1.2% net post-2024) | 61 200€ | PFU 30% dès €1 | Bloqué 4 ans min |

### Investissement boursier

| Produit | Fiscalité | Plafond | Conditions |
|---------|-----------|---------|------------|
| **PEA** | 0% IR + 18.6% PS après 5 ans | 150 000€ | Résident FR, 1 par personne |
| **PEA-PME** | Idem PEA | 225 000€ cumulé PEA+PEA-PME | Résident FR |
| **CTO** | PFU 30% | Illimité | Aucune |

### Épargne longue durée

| Produit | Rendement | Fiscalité | Liquidité |
|---------|-----------|-----------|-----------|
| **Assurance-vie fonds euros** | ~2.5–3.0% brut | PFU 30% avant 8 ans / 7.5%+PS après 8 ans | Semi (quelques jours) |
| **Assurance-vie UC (ETF)** | Variable (marché) | Idem AV | Semi |
| **PER individuel** | Variable | Déduction IR à l'entrée / fiscalisé à la sortie | Bloqué jusqu'à retraite |

### Immobilier indirect

| Produit | Rendement moyen | Fiscalité | Liquidité |
|---------|----------------|-----------|-----------|
| **SCPI** | 4–6% brut | Revenus fonciers (TMI+PS) | Faible (marché secondaire) |
| **Crowdfunding immo** | 8–12% brut | PFU 30% | Bloqué 12–24 mois |
| **SIIC / foncières cotées** | Variable | PFU 30% (ou PEA si éligible) | Immédiate (bourse) |

### Crypto-actifs

| Produit | Fiscalité | Liquidité |
|---------|-----------|-----------|
| **BTC, ETH, SOL...** | 30% PFU sur cessions | Immédiate |
| **Staking / yield** | Revenus imposables à réception | Variable |
| **ETF crypto (ETP)** | PFU 30% via CTO | Immédiate |

### Obligations / produits de taux

| Produit | Rendement | Fiscalité |
|---------|-----------|-----------|
| **ETF obligataire (CTO/PEA)** | ~3–5% selon duration | PFU 30% (CTO) |
| **OAT (obligations d'État FR)** | ~3% | PFU 30% |
| **ETF monétaire (ex: EMARB)** | ~3.5% (ESTER) | PFU 30% (CTO) ou dans PEA |

### Ordre de priorisation générique (profil étudiant, revenus modestes, horizon long terme)

```
1. LEP             → si éligible (RFR < seuil) — meilleur taux liquide exonéré
2. PEA             → DCA ETF MSCI World, horizon 5+ ans
3. Livret Jeune    → si < 25 ans, conserver jusqu'au plafond
4. LDDS            → compléter quand LEP saturé
5. Assurance-vie   → ouvrir tôt pour faire courir le délai fiscal de 8 ans
6. SCPI / Immo     → à partir d'une épargne significative disponible
7. CTO             → après saturation PEA
8. PER             → pertinent quand TMI élevée (revenus stables, > 30 ans)
```

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
      "cwd": "/path/to/Capitls"
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
7. **Contrainte courtier** — respecter la fréquence d'ordres définie dans `user_profile.json` (ex: 1 ordre/mois gratuit selon courtier)

## Format de réponse attendu de l'agent

```
[SOURCE] Tier_1 (AMF) / Tier_2 (Yahoo Finance/Finary) / Tier_3 (analyse)
[FAIT] Données objectives
[RECOMMANDATION] Contextualisée au profil chargé depuis user_profile.json
[CONFIANCE] FACTUEL / ANALYSE / OPINION
```

---

## Roadmap

### V1 — ✅ Terminée
- [x] Setup projet + contexte CLAUDE.md
- [x] Structure fichiers + skills de base (56 tests unitaires)
- [x] finary_adapter.py fonctionnel (subprocess, session cookies, TOTP auto)
- [x] Test end-to-end : "Analyse mon portfolio Finary" (live via MCP)
- [x] Premier conseil DCA le courtier configuré contextualisé

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

#### Suivi PEA actif (prioritaire dès validation le courtier configuré)
- [x] Infrastructure `user_profile.json` — champs `opening_date`, `order_history`, `five_year_deadline`, `etf_cible`
- [x] `skills/pea_tracker.py` — countdown 5 ans, P&L, gestion historique ordres (fonctions pures)
- [x] MCP `get_pea_status()` — statut complet PEA : countdown, performance, prochain ordre
- [x] MCP `record_pea_order()` — persistance d'un ordre exécuté dans le profil
- [ ] Renseigner `opening_date` dans `user_profile.json` dès validation le courtier configuré

#### Rappels DCA automatiques
- [x] MCP `get_dca_reminder()` — vérifie si l'ordre mensuel a été passé, retourne rappel si non
- [x] MCP `record_monthly_income()` — enregistrement des revenus mensuels dans le profil
- [ ] Cron mensuel automatique via `/schedule` (à configurer manuellement une fois PEA actif)

#### Analyse avancée
- [x] `skills/timing.py` — score timing 0-100 (percentile prix/SMA63j)
- [x] MCP `get_dca_timing(ticker)` — recommandation contextualisée le courtier configuré
- [x] `skills/benchmark.py` — compare_returns() + calculate_dca_vs_lumpsum()
- [x] MCP `compare_vs_benchmark(etf, benchmark, period)` — ETF vs EUNL.DE

#### Budget et revenus
- [x] `skills/budget.py` — capacité d'investissement + DCA optimal sur historique revenus
- [x] MCP `get_investment_capacity(monthly_income, fixed_expenses)` — calcul capacité DCA
- [x] Champ `revenus.historique_mensuel` dans user_profile.json

#### Diversification future
- [x] `skills/simulation.py` — simulation allocation, comparaison modèle étudiant, alerte crypto
- [x] MCP `simulate_portfolio(world_pct, crypto_pct, savings_pct)` — simulation rééquilibrage

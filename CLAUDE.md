# Capitls — Agent Financier Personnel

Serveur MCP Python connecté à Finary, spécialisé en finance personnelle française (PEA, ETF,
épargne réglementée, DCA). Générique : utilisable par n'importe qui, chaque utilisateur a son
propre profil local. Usage personnel — pas de conseil au sens réglementaire AMF.

---

## Données : deux sources centralisées, jamais éparpillées

| Donnée | Fichier | Versionné | Mise à jour |
|--------|---------|-----------|-------------|
| **Profil utilisateur** (identité, revenus, comptes, soldes Finary, courtier, PEA, règles, objectifs, revues, décisions) | `mcp_server/context/user_profile.json` | ❌ gitignoré, chmod 600 | onboarding + `update_situation`, synchro Finary |
| **Données de référence publiques** (taux livrets, plafonds, fiscalité, catalogue ETF) | `data/reference_data.json` | ✅ (aucune donnée perso) | fetch auto service-public.fr + justETF si > 24h |

- **Ne jamais committer de données personnelles** : ni dans le code, ni dans les tests, ni dans la doc,
  ni dans les exemples (valeurs fictives uniquement). Aucun nom de compte, banque, courtier, montant
  ou employeur réel dans le repo.
- **Ne jamais écrire de taux, plafond ou TER en dur** (code ou doc) : ils vivent dans
  `data/reference_data.json` et sont lus via `mcp_server/tools/reference_tool.py`.
- Le schéma du profil est `mcp_server/profile/schema.py` (Pydantic). Toute lecture/écriture passe par
  `mcp_server/profile/store.py` (écriture atomique, migration automatique des anciens formats + `.v1.bak`).

### Données de référence — cycle de vie

1. Tout tool qui a besoin d'un taux appelle `reference_tool.get_reference()`.
2. Si le dernier fetch réussi date de plus de 24h → `adapters/reference_adapter.py` récupère les pages,
   `skills/reference_parsers.py` extrait les valeurs.
3. Chaque valeur trouvée remplace la valeur de repli ; une valeur introuvable garde la précédente
   (et reste signalée « à revérifier » au-delà de 30 jours).
4. Tout changement de valeur est journalisé dans `changes` → `get_regulatory_news()`.
5. Faits non récupérables automatiquement : l'agent vérifie sur la source officielle puis
   `record_verified_fact()`.

Pour ajouter un fait : une entrée dans `SERVICE_PUBLIC_FACTS` (page + regex), sa valeur de repli dans
`data/reference_data.json`, un extrait réel de la page dans `tests/fixtures/`.

### Revue de situation

- `start_session()` en début de session : taux à jour, synchro Finary, actualités, et revue si due
  (tous les `review.interval_days` jours, 30 par défaut).
- `review_situation()` aussi dès que l'utilisateur évoque un changement : résumé point par point,
  changements probables détectés (revenu terminé, âge / Livret Jeune, écarts de soldes, PEA, comptes
  Finary à classer), puis « Votre situation a-t-elle changé depuis le … ? »
  → oui : `update_situation(changes_json)` ; non : `confirm_situation_unchanged()`.
- Profil absent → onboarding (questions générées par `skills/situation_review.onboarding_questions`).

---

## Univers d'investissement — checklist systématique

> **Règle agent** : pour toute recommandation, parcourir cette liste et justifier pourquoi chaque produit
> est retenu ou écarté selon le profil. Taux et plafonds : `get_savings_rates()`, `get_pea_rules()`,
> `get_tax_comparison()`, `get_reference_data()` — jamais de mémoire.

- **Épargne réglementée** : LEP (sous condition de revenu fiscal de référence), Livret Jeune
  (tranche d'âge), Livret A, LDDS — exonérés d'IR et de prélèvements sociaux. CEL / PEL : fiscalisés.
- **Bourse** : PEA (exonération d'IR après la durée légale, prélèvements sociaux dus ; point de départ =
  premier versement), PEA-PME, CTO (flat tax).
- **Épargne longue** : assurance-vie (fonds euros / UC, fiscalité réduite après 8 ans, prélèvements
  sociaux spécifiques), PER (déduction à l'entrée, pertinent si TMI élevée).
- **Immobilier indirect** : SCPI, crowdfunding immobilier, foncières cotées.
- **Crypto** : flat tax sur les cessions ; ETP crypto via CTO.
- **Taux** : ETF obligataires, OAT, ETF monétaires.

### Ordre de priorisation générique (horizon long terme, revenus modestes)

```
1. Épargne de précaution (règle rules.liquidity_min) sur livrets
2. LEP si éligible
3. PEA — DCA sur un ETF monde éligible (le moins cher du catalogue : recommend_etf_for_pea)
4. Livret Jeune si dans la tranche d'âge
5. Assurance-vie — ouvrir tôt pour faire courir le délai fiscal
6. SCPI / immobilier — à partir d'une épargne significative
7. CTO — après saturation du PEA
8. PER — quand la TMI est élevée
```

---

## Architecture

```
Capitls/
├── mcp_server/
│   ├── main.py                # Déclaration des tools MCP (FastMCP)
│   ├── profile/               # Profil utilisateur : schema (Pydantic), store, migration, changes
│   ├── tools/
│   │   ├── profile_tool.py    # start_session, review/update/confirm situation
│   │   ├── reference_tool.py  # Données de référence (refresh 24h, actualités)
│   │   ├── portfolio_tool.py  # Synchro Finary → profil, PEA, revenus, décisions
│   │   ├── market_tool.py     # Cours ETF / crypto
│   │   ├── regulation_tool.py # Règles PEA, livrets, fiscalité, éligibilité ISIN
│   │   └── analysis_tool.py   # Analyse, DCA, projections, simulation
│   └── context/               # user_profile.json (local, gitignoré) + exemple fictif
├── adapters/                  # Tout accès externe : finary, market (yfinance/CoinGecko), reference (HTTP)
├── skills/                    # Fonctions pures (aucun réseau, aucune donnée perso en dur)
├── data/reference_data.json   # Données publiques de référence (auto-mises à jour)
├── .claude/agents, .claude/skills/capitls   # Agents et skill génériques
└── tests/                     # Tests unitaires + fixtures HTML réelles (sans réseau)
```

### Règles de conception

1. **Adapter** : tout appel externe passe par `adapters/`. Si Finary ou une page source change, seul
   l'adapter / le parseur change.
2. **Skills = fonctions pures** : entrée → calcul → dict. Taux, seuils et règles personnelles sont des
   paramètres (fournis par les tools depuis le profil et les données de référence).
3. **Pydantic** pour le profil ; `extra="allow"` pour ne jamais perdre de donnée existante.
4. **Pas de valeur personnelle par défaut** : si une info manque, le tool renvoie
   `status: missing_info` avec la question à poser.
5. **finary_uapi est non officielle** — tout appel isolé dans `finary_adapter.py`.
6. **Credentials** : `.env` + `credentials.json` (gitignorés, chmod 600), jamais en dur.

---

## Sources externes

- **finary_uapi** (CLI, via subprocess) — session cookies ; `make finary-signin` génère le code TOTP
  depuis `FINARY_TOTP_SECRET`.
- **service-public.fr** (tier_1) — taux, plafonds, fiscalité (pages F2365, F2368, F2367, F2904, F2385,
  F21618, F22414).
- **justETF** (tier_1) — TER, encours, mention « Éligible au PEA ».
- **yfinance** (tier_2) — cours ETF (suffixe `.PA` pour Euronext Paris).
- **CoinGecko** (tier_2) — cours crypto.

## Commandes

```bash
make setup              # uv sync --dev, .env, credentials.json, .mcp.json
make finary-signin      # Connexion Finary (TOTP automatique)
make run                # Serveur MCP en stdio
make test / test-cov    # Tests (aucun réseau)
make lint               # ruff + mypy
make refresh-reference  # Force la mise à jour des données de référence
```

## Format de réponse attendu de l'agent

```
[SOURCE] Tier_1 (service-public.fr / justETF) / Tier_2 (Finary / Yahoo Finance / CoinGecko) / Tier_3 (analyse)
[FAIT] Données objectives, datées
[RECOMMANDATION] Contextualisée au profil
[CONFIANCE] FACTUEL / ANALYSE / OPINION
```

---

## Roadmap

### V1–V4 — ✅ Terminées
Serveur MCP, adapters Finary / marché, skills purs testés, agents spécialisés, suivi PEA,
rappels DCA, timing, benchmark, budget, simulation d'allocation.

### V5 — ✅ Générique & données vivantes
- [x] Données de référence auto-mises à jour (service-public.fr, justETF), repli daté, actualités
- [x] Profil Pydantic unique, migration automatique, aucune donnée perso dans le repo
- [x] Revue de situation périodique / à la demande + onboarding
- [x] Courtier paramétrable (plus de courtier codé en dur), `.mcp.json` généré

### Idées
- [ ] Rappel DCA mensuel automatique (`/schedule`)
- [ ] Offres promotionnelles courtier (ordres gratuits temporaires) dans `pea.broker.notes` → prises en compte par le plan DCA
- [ ] Suivi assurance-vie / PER (dates d'ouverture, délai fiscal)
- [ ] Plafond LEP selon le nombre de parts fiscales (tableau complet)

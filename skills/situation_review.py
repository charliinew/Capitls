"""
Revue de situation — fonctions pures sur le profil (dict, format UserProfile v2).

- is_review_due : revue périodique (tous les `review.interval_days` jours)
- summarize_situation : résumé point par point de la situation enregistrée
- detect_probable_changes : changements probables à confirmer avec l'utilisateur
- onboarding_questions : questionnaire initial / informations manquantes
"""

from __future__ import annotations

from datetime import date

LIQUID_CATEGORIES = ("checking", "savings", "regulated_savings")
BALANCE_CHANGE_MIN_EUR = 100.0
BALANCE_CHANGE_MIN_PCT = 0.20

CATEGORY_LABELS = {
    "checking": "compte courant",
    "savings": "épargne",
    "regulated_savings": "livret réglementé",
    "pea": "PEA",
    "cto": "compte-titres",
    "life_insurance": "assurance-vie",
    "retirement": "PER",
    "crypto": "crypto",
    "pro_reserved": "réservé pro",
    "other": "autre",
}

PEA_STATUS_LABELS = {
    "none": "pas de PEA",
    "planned": "à ouvrir",
    "opening": "en cours d'ouverture",
    "open": "ouvert",
    "closed": "clôturé",
}


def _eur(value: float | None) -> str:
    if value is None:
        return "non renseigné"
    return f"{value:,.0f} €".replace(",", " ")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _month_end_passed(month: str | None, today: date) -> bool:
    """'2026-08' est passé si on est en septembre 2026 ou après."""
    if not month:
        return False
    try:
        year, mon = (int(x) for x in month[:7].split("-"))
    except ValueError:
        return False
    return (today.year, today.month) > (year, mon)


def estimate_age(identity: dict, today: date) -> int | None:
    if identity.get("birth_year"):
        return today.year - identity["birth_year"]
    age = identity.get("age")
    if not age:
        return None
    as_of = _parse_date(identity.get("age_as_of"))
    if as_of is None:
        return age
    return age + (today - as_of).days // 365


def is_review_due(profile: dict, today: date) -> dict:
    review = profile.get("review", {})
    last = _parse_date(review.get("last_review_date"))
    interval = review.get("interval_days", 30)
    if last is None:
        return {"due": True, "reason": "aucune revue de situation enregistrée", "days_since": None}
    days = (today - last).days
    return {
        "due": days >= interval,
        "reason": f"dernière revue il y a {days} jours (fréquence : {interval} jours)",
        "days_since": days,
    }


def summarize_situation(profile: dict, today: date) -> list[str]:
    """Résumé point par point de la situation enregistrée."""
    points = []
    identity = profile.get("identity", {})
    age = estimate_age(identity, today)
    who = ", ".join(x for x in [f"{age} ans (estimé)" if age else None, identity.get("situation")] if x)
    points.append(f"Profil : {who or 'non renseigné'}")

    income = profile.get("income", {})
    sources = income.get("sources", [])
    if sources:
        for src in sources:
            status = " — terminé ?" if _month_end_passed(src.get("end"), today) else ""
            end = f", fin prévue {src['end']}" if src.get("end") else ""
            label = src.get("label") or src.get("type")
            points.append(
                f"Revenu « {label} » ({src.get('type')}) : {_eur(src.get('monthly_amount'))}/mois{end}{status}"
            )
    else:
        points.append("Revenus : aucune source déclarée")
    if income.get("fixed_expenses") is not None:
        points.append(f"Dépenses fixes : {_eur(income['fixed_expenses'])}/mois")

    for account in profile.get("accounts", []):
        flags = []
        if account.get("minimum_balance"):
            flags.append(f"minimum {_eur(account['minimum_balance'])}")
        if account.get("exclude_from_liquidity"):
            flags.append("hors liquidité")
        if account.get("needs_classification"):
            flags.append("à classer")
        extra = f" ({', '.join(flags)})" if flags else ""
        points.append(
            f"Compte « {account.get('name')} » [{CATEGORY_LABELS.get(account.get('category'), 'autre')}] : "
            f"{_eur(account.get('balance'))}{extra}"
        )

    crypto = profile.get("crypto", {})
    if crypto.get("total_value"):
        points.append(f"Crypto : {_eur(crypto['total_value'])} ({len(crypto.get('positions', []))} positions)")

    pea = profile.get("pea", {})
    broker = pea.get("broker", {}) or {}
    pea_line = f"PEA : {PEA_STATUS_LABELS.get(pea.get('status'), pea.get('status'))}"
    if broker.get("name"):
        pea_line += f" chez {broker['name']}"
    if pea.get("first_deposit_date"):
        pea_line += f", 1er versement le {pea['first_deposit_date']}"
    if pea.get("monthly_target"):
        pea_line += f", objectif {_eur(pea['monthly_target'])}/mois"
    if pea.get("target_etf"):
        pea_line += f" sur {pea['target_etf']}"
    if pea.get("orders"):
        pea_line += f", {len(pea['orders'])} ordre(s) enregistré(s)"
    points.append(pea_line)

    rules = profile.get("rules", {})
    rule_parts = []
    if rules.get("liquidity_min") is not None:
        rule_parts.append(f"épargne de précaution ≥ {_eur(rules['liquidity_min'])}")
    if rules.get("crypto_max_pct") is not None:
        rule_parts.append(f"crypto ≤ {rules['crypto_max_pct'] * 100:.0f} %")
    points.append("Règles : " + (", ".join(rule_parts) if rule_parts else "aucune définie"))

    goals = profile.get("goals", {})
    goal_parts = [goals.get(k) for k in ("main_goal", "horizon", "risk_tolerance") if goals.get(k)]
    points.append("Objectifs : " + (" / ".join(goal_parts) if goal_parts else "non renseignés"))
    return points


def _balance_changes(profile: dict) -> list[dict]:
    previous = profile.get("review", {}).get("balances_at_last_review", {}) or {}
    changes = []
    for account in profile.get("accounts", []):
        old = previous.get(account["id"])
        if old is None:
            continue
        new = account.get("balance", 0.0)
        delta = new - old
        if abs(delta) >= BALANCE_CHANGE_MIN_EUR and (old == 0 or abs(delta) / abs(old) >= BALANCE_CHANGE_MIN_PCT):
            changes.append(
                {
                    "kind": "balance_change",
                    "message": f"Solde « {account['name']} » : {_eur(old)} → {_eur(new)} depuis la dernière revue",
                    "question": "Ce mouvement correspond-il à un changement de situation (revenu, dépense exceptionnelle, projet) ?",
                }
            )
    return changes


def detect_probable_changes(profile: dict, reference_facts: dict, today: date) -> list[dict]:
    """
    Changements probables à confirmer. reference_facts : {clé: valeur} (ex: livret_jeune.age_max).
    """
    changes: list[dict] = []

    for src in profile.get("income", {}).get("sources", []):
        if _month_end_passed(src.get("end"), today):
            label = src.get("label") or src.get("type")
            changes.append(
                {
                    "kind": "income_ended",
                    "message": f"Le revenu « {label} » devait se terminer en {src['end']}",
                    "question": "Ce revenu est-il terminé ? Avez-vous une nouvelle source de revenus ?",
                }
            )

    identity = profile.get("identity", {})
    age = estimate_age(identity, today)
    as_of = _parse_date(identity.get("age_as_of"))
    if identity.get("age") and not identity.get("birth_year") and as_of and (today - as_of).days >= 365:
        changes.append(
            {
                "kind": "age_outdated",
                "message": f"Âge renseigné le {as_of.isoformat()} ({identity['age']} ans) — probablement {age} ans aujourd'hui",
                "question": "Quelle est votre année de naissance ? (évite de redemander l'âge)",
            }
        )

    age_max = reference_facts.get("livret_jeune.age_max")
    has_livret_jeune = any(
        "jeune" in f"{a.get('id', '')} {a.get('name', '')} {a.get('finary_name') or ''}".lower()
        for a in profile.get("accounts", [])
    )
    if age is not None and age_max and has_livret_jeune:
        if age >= age_max:
            changes.append(
                {
                    "kind": "livret_jeune_closing",
                    "message": f"Le Livret Jeune ferme au 31 décembre de l'année des {age_max} ans (âge estimé : {age})",
                    "question": "Le Livret Jeune a-t-il été clôturé ? Où les fonds ont-ils été transférés ?",
                }
            )
        elif age == age_max - 1:
            changes.append(
                {
                    "kind": "livret_jeune_closing_soon",
                    "message": f"Le Livret Jeune fermera au 31/12 de l'année de vos {age_max} ans",
                    "question": "Voulez-vous anticiper le transfert de ce livret ?",
                }
            )

    changes += _balance_changes(profile)

    pea = profile.get("pea", {})
    if pea.get("status") in ("planned", "opening"):
        changes.append(
            {
                "kind": "pea_opening",
                "message": f"PEA noté « {PEA_STATUS_LABELS[pea['status']]} »",
                "question": "Le PEA est-il ouvert ? Si oui, date du premier versement ?",
            }
        )
    elif pea.get("status") == "open" and not pea.get("first_deposit_date"):
        changes.append(
            {
                "kind": "pea_first_deposit_missing",
                "message": "PEA ouvert sans date de premier versement",
                "question": "Quelle est la date du premier versement ? (départ du délai fiscal)",
            }
        )
    first_deposit = _parse_date(pea.get("first_deposit_date"))
    if first_deposit:
        years = reference_facts.get("pea.duree_exoneration_ans", 5)
        try:
            milestone = first_deposit.replace(year=first_deposit.year + int(years))
        except ValueError:  # 29 février
            milestone = first_deposit.replace(year=first_deposit.year + int(years), day=28)
        days_left = (milestone - today).days
        if 0 <= days_left <= 90:
            changes.append(
                {
                    "kind": "pea_milestone",
                    "message": f"Le PEA atteint {years} ans le {milestone.isoformat()} (dans {days_left} jours)",
                    "question": "Souhaitez-vous revoir votre stratégie PEA à l'approche de l'exonération d'IR ?",
                }
            )

    for account in profile.get("accounts", []):
        if account.get("needs_classification"):
            changes.append(
                {
                    "kind": "account_unclassified",
                    "message": f"Nouveau compte détecté sur Finary : « {account.get('finary_name') or account['name']} »",
                    "question": "Quel est son rôle (courant, épargne, livret, PEA, pro réservé…) ? Faut-il l'exclure de la liquidité disponible ?",
                }
            )
    return changes


def onboarding_questions(profile: dict | None) -> list[dict]:
    """Informations manquantes à demander (toutes si profil absent)."""
    p = profile or {}
    questions = []

    def ask(field: str, question: str) -> None:
        questions.append({"field": field, "question": question})

    identity = p.get("identity", {})
    if not identity.get("birth_year") and not identity.get("age"):
        ask("identity.birth_year", "Quelle est votre année de naissance ?")
    if not identity.get("situation"):
        ask("identity.situation", "Quelle est votre situation (étudiant, salarié, indépendant…) ?")
    if identity.get("reference_tax_income") is None:
        ask(
            "identity.reference_tax_income",
            "Quel est votre revenu fiscal de référence (avis d'imposition) ? Utile pour l'éligibilité au LEP.",
        )
    if not p.get("income", {}).get("sources"):
        ask("income.sources", "Quelles sont vos sources de revenus (type, montant mensuel, date de fin éventuelle) ?")
    if p.get("income", {}).get("fixed_expenses") is None:
        ask("income.fixed_expenses", "À combien estimez-vous vos dépenses fixes mensuelles ?")
    if not p.get("accounts"):
        ask("accounts", "Quels comptes détenez-vous (nom, type, rôle) ? Ils seront aussi détectés via Finary.")
    if p.get("rules", {}).get("liquidity_min") is None:
        ask(
            "rules.liquidity_min",
            "Quel montant minimum voulez-vous toujours garder disponible (épargne de précaution) ?",
        )
    if p.get("rules", {}).get("crypto_max_pct") is None:
        ask("rules.crypto_max_pct", "Quelle part maximale de votre patrimoine acceptez-vous en crypto ?")
    pea = p.get("pea", {})
    if pea.get("status", "none") == "none":
        ask("pea.status", "Avez-vous un PEA (ou prévoyez-vous d'en ouvrir un) ? Chez quel courtier ?")
    elif not (pea.get("broker") or {}).get("name"):
        ask(
            "pea.broker",
            "Chez quel courtier est votre PEA, et quelles sont ses conditions de frais (ordres gratuits…) ?",
        )
    if pea.get("status") in ("planned", "opening", "open") and pea.get("monthly_target") is None:
        ask("pea.monthly_target", "Combien souhaitez-vous investir chaque mois ?")
    goals = p.get("goals", {})
    if not goals.get("main_goal"):
        ask(
            "goals.main_goal",
            "Quel est votre objectif principal (épargne de précaution, achat immobilier, retraite, indépendance financière…) ?",
        )
    if not goals.get("risk_tolerance"):
        ask("goals.risk_tolerance", "Quelle est votre tolérance au risque (faible, modérée, élevée) ?")
    return questions


def liquidity(accounts: list[dict]) -> dict:
    """Liquidité totale et disponible (au-delà des minimums), hors comptes exclus."""
    liquid = [a for a in accounts if a.get("category") in LIQUID_CATEGORIES and not a.get("exclude_from_liquidity")]
    total = sum(a.get("balance", 0.0) for a in liquid)
    available = sum(max(0.0, a.get("balance", 0.0) - a.get("minimum_balance", 0.0)) for a in liquid)
    return {"total": round(total, 2), "available_above_minimums": round(available, 2)}

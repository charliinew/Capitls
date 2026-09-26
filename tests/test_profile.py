"""
Tests du profil utilisateur : migration v1 → v2, mises à jour partielles, persistance,
revue de situation et synchro Finary. Données fictives uniquement, aucun appel réseau.
"""

import json
import os
from datetime import date, datetime, timezone

import pytest

from mcp_server.profile.changes import apply_changes
from mcp_server.profile.migration import is_legacy, migrate_v1_to_v2
from mcp_server.profile.schema import UserProfile
from skills import situation_review as sr

LEGACY_PROFILE = {
    "version": "1.2",
    "last_updated": "2026-05-20",
    "identity": {"age": 30, "situation": "salarié", "revenus_reguliers": True},
    "revenus": {
        "sources": [
            {
                "type": "cdd",
                "employeur": "Entreprise A",
                "montant_mensuel": 2000,
                "fin": "2026-08",
                "compte_reception": "Banque A",
            },
            {"type": "freelance", "montant_mensuel": None, "note": "variable"},
        ],
        "historique_mensuel": [{"month": "2026-04", "income": 2000, "source": "cdd"}],
    },
    "patrimoine": {
        "banque_a_livret": {"montant": 5000.0, "role": "épargne réglementée", "statut": "actif", "taux_min": 0.015},
        "banque_a_courant": {"montant": 1234.56, "role": "compte courant"},
        "freelance_pro": {"montant": 800.0, "role": "provision URSSAF à ne pas toucher"},
        "neo_epargne": {
            "montant": 3000.0,
            "minimum_absolu": 1000,
            "disponible_investissement": 2000,
            "role": "liquidité de précaution",
        },
        "crypto": {
            "valeur_estimee": 1200.0,
            "positions": [{"symbol": "BTC", "name": "Bitcoin", "qty": 0.01, "valeur_eur": 1200.0, "pnl_eur": 50.0}],
        },
        "pea": {
            "statut": "en cours d'ouverture",
            "courtier": "Courtier X",
            "apport_initial_cible": 1000,
            "versement_mensuel_cible": 150,
            "tarif_cle": "1 ordre/mois < 500€ gratuit",
            "dca_automatique": False,
            "parrainage": {"actif": True, "bonus": 50, "condition": "1000€ investis"},
            "opening_date": None,
            "order_history": [],
            "etf_cible": "DCAM",
        },
    },
    "regles_personnelles": {"liquidite_minimale": 1000, "part_crypto_max": 0.2, "liquidite_comptes_exclus": ["Pro"]},
    "snapshot_finary": {
        "date": "2026-05-20",
        "total_net_worth": 11034.56,
        "comptes": [
            {"nom": "Livret", "type": "livret", "balance": 5000.0},
            {"nom": "Compte Courant", "type": "checking", "balance": 1234.56},
            {"nom": "Pro", "type": "checking", "balance": 800.0},
            {"nom": "Epargne", "type": "savings", "balance": 3000.0},
        ],
    },
    "historique_decisions": [{"date": "2026-05-01", "decision": "Ouvrir un PEA", "details": {}}],
    "etfs_recommandes_2026": ["DCAM"],
}


@pytest.fixture
def migrated() -> dict:
    return migrate_v1_to_v2(LEGACY_PROFILE)


class TestMigration:
    def test_detects_legacy(self):
        assert is_legacy(LEGACY_PROFILE) is True
        assert is_legacy({"schema_version": 2}) is False

    def test_result_is_valid_v2(self, migrated):
        profile = UserProfile.model_validate(migrated)
        assert profile.schema_version == 2

    def test_values_are_preserved(self, migrated):
        accounts = {a["id"]: a for a in migrated["accounts"]}
        assert accounts["banque_a_courant"]["balance"] == 1234.56
        assert accounts["neo_epargne"]["minimum_balance"] == 1000
        assert accounts["banque_a_livret"]["taux_min"] == 0.015  # champ inconnu conservé
        assert migrated["crypto"]["total_value"] == 1200.0
        assert migrated["crypto"]["positions"][0]["value_eur"] == 1200.0
        assert migrated["income"]["sources"][0]["monthly_amount"] == 2000
        assert migrated["income"]["sources"][0]["end"] == "2026-08"
        assert migrated["income"]["sources"][0]["label"] == "Entreprise A"
        assert migrated["income"]["history"][0]["income"] == 2000
        assert migrated["decisions"][0]["decision"] == "Ouvrir un PEA"
        assert migrated["legacy"]["etfs_recommandes_2026"] == ["DCAM"]

    def test_categories_inferred(self, migrated):
        cats = {a["id"]: a["category"] for a in migrated["accounts"]}
        assert cats == {
            "banque_a_livret": "regulated_savings",
            "banque_a_courant": "checking",
            "freelance_pro": "pro_reserved",
            "neo_epargne": "savings",
        }

    def test_finary_names_matched_by_balance(self, migrated):
        names = {a["id"]: a.get("finary_name") for a in migrated["accounts"]}
        assert names["banque_a_courant"] == "Compte Courant"
        assert names["freelance_pro"] == "Pro"

    def test_excluded_accounts(self, migrated):
        excluded = {a["id"] for a in migrated["accounts"] if a["exclude_from_liquidity"]}
        assert excluded == {"freelance_pro"}

    def test_pea_and_broker(self, migrated):
        pea = migrated["pea"]
        assert pea["status"] == "opening"
        assert pea["broker"] == {
            "name": "Courtier X",
            "free_orders_per_month": 1,
            "free_order_max": 500.0,
            "auto_invest": False,
            "notes": ["1 ordre/mois < 500€ gratuit"],
        }
        assert pea["monthly_target"] == 150
        assert pea["referral"]["bonus"] == 50

    def test_rules(self, migrated):
        assert migrated["rules"]["liquidity_min"] == 1000
        assert migrated["rules"]["crypto_max_pct"] == 0.2

    def test_review_starts_empty(self, migrated):
        assert migrated["review"]["last_review_date"] is None


class TestChanges:
    def test_nested_merge(self):
        updated, summary = apply_changes(
            {"rules": {"liquidity_min": 500, "crypto_max_pct": 0.2}}, {"rules": {"liquidity_min": 800}}
        )
        assert updated["rules"] == {"liquidity_min": 800, "crypto_max_pct": 0.2}
        assert summary == ["rules.liquidity_min: 500 → 800"]

    def test_list_merge_by_id(self):
        profile = {"accounts": [{"id": "a", "name": "A", "balance": 10}, {"id": "b", "name": "B"}]}
        updated, summary = apply_changes(
            profile,
            {
                "accounts": [
                    {"id": "a", "category": "savings"},
                    {"id": "c", "name": "C"},
                    {"id": "b", "_delete": True},
                ]
            },
        )
        assert updated["accounts"] == [
            {"id": "a", "name": "A", "balance": 10, "category": "savings"},
            {"id": "c", "name": "C"},
        ]
        assert "accounts[c] ajouté" in summary and "accounts[b] supprimé" in summary

    def test_protected_keys(self):
        with pytest.raises(ValueError):
            apply_changes({}, {"review": {"last_review_date": "2020-01-01"}})

    def test_input_not_mutated(self):
        profile = {"rules": {"liquidity_min": 500}}
        apply_changes(profile, {"rules": {"liquidity_min": 800}})
        assert profile["rules"]["liquidity_min"] == 500


TODAY = date(2026, 9, 26)
FACTS = {"livret_jeune.age_max": 25, "pea.duree_exoneration_ans": 5}


def _profile(**overrides) -> dict:
    data = UserProfile.model_validate(migrate_v1_to_v2(LEGACY_PROFILE)).model_dump()
    data.update(overrides)
    return data


class TestSituationReview:
    def test_review_due_when_never_done(self):
        assert sr.is_review_due(_profile(), TODAY)["due"] is True

    def test_review_not_due_within_interval(self):
        p = _profile(
            review={"last_review_date": "2026-09-10", "interval_days": 30, "balances_at_last_review": {}, "history": []}
        )
        assert sr.is_review_due(p, TODAY)["due"] is False
        p["review"]["last_review_date"] = "2026-08-01"
        assert sr.is_review_due(p, TODAY)["due"] is True

    def test_summary_is_point_by_point(self):
        points = sr.summarize_situation(_profile(), TODAY)
        text = "\n".join(points)
        assert "Entreprise A" in text and "terminé ?" in text
        assert "Neo Epargne" in text and "minimum 1 000 €" in text
        assert "PEA : en cours d'ouverture chez Courtier X" in text
        assert "épargne de précaution ≥ 1 000 €" in text

    def test_detects_ended_income_and_pea_opening(self):
        kinds = {c["kind"] for c in sr.detect_probable_changes(_profile(), FACTS, TODAY)}
        assert "income_ended" in kinds
        assert "pea_opening" in kinds

    def test_detects_outdated_age(self):
        p = _profile()
        p["identity"]["age_as_of"] = "2025-01-01"
        kinds = {c["kind"] for c in sr.detect_probable_changes(p, FACTS, TODAY)}
        assert "age_outdated" in kinds

    def test_livret_jeune_closing(self):
        p = _profile()
        p["identity"] = {"birth_year": 2001}
        p["accounts"].append(
            {"id": "livret_jeune", "name": "Livret Jeune", "category": "regulated_savings", "balance": 1600}
        )
        kinds = {c["kind"] for c in sr.detect_probable_changes(p, FACTS, TODAY)}
        assert "livret_jeune_closing" in kinds
        p["identity"] = {"birth_year": 2002}
        kinds = {c["kind"] for c in sr.detect_probable_changes(p, FACTS, TODAY)}
        assert "livret_jeune_closing_soon" in kinds

    def test_balance_change_detection(self):
        p = _profile()
        p["review"]["balances_at_last_review"] = {"neo_epargne": 3000.0, "banque_a_courant": 1200.0}
        p["accounts"][3]["balance"] = 1500.0  # neo_epargne : -1500
        messages = [c["message"] for c in sr.detect_probable_changes(p, FACTS, TODAY) if c["kind"] == "balance_change"]
        assert len(messages) == 1 and "Neo Epargne" in messages[0]

    def test_pea_milestone(self):
        p = _profile()
        p["pea"]["status"] = "open"
        p["pea"]["first_deposit_date"] = "2021-11-01"
        kinds = {c["kind"] for c in sr.detect_probable_changes(p, FACTS, TODAY)}
        assert "pea_milestone" in kinds

    def test_unclassified_account(self):
        p = _profile()
        p["accounts"].append(
            {"id": "x", "name": "Nouveau", "finary_name": "Nouveau", "category": "other", "needs_classification": True}
        )
        kinds = {c["kind"] for c in sr.detect_probable_changes(p, FACTS, TODAY)}
        assert "account_unclassified" in kinds

    def test_onboarding_questions_for_new_user(self):
        fields = {q["field"] for q in sr.onboarding_questions(None)}
        assert {"identity.birth_year", "income.sources", "rules.liquidity_min", "pea.status"} <= fields

    def test_onboarding_questions_only_missing(self):
        fields = {q["field"] for q in sr.onboarding_questions(_profile())}
        assert "rules.liquidity_min" not in fields
        assert "income.fixed_expenses" in fields

    def test_liquidity_excludes_reserved_and_counts_minimums(self):
        accounts = [
            {"category": "checking", "balance": 1000},
            {"category": "savings", "balance": 3000, "minimum_balance": 1000},
            {"category": "pro_reserved", "balance": 800},
            {"category": "checking", "balance": 500, "exclude_from_liquidity": True},
            {"category": "pea", "balance": 5000},
        ]
        assert sr.liquidity(accounts) == {"total": 4000, "available_above_minimums": 3000}


@pytest.fixture
def profile_store(tmp_path, monkeypatch):
    from mcp_server.profile import store

    path = tmp_path / "user_profile.json"
    monkeypatch.setattr(store, "PROFILE_PATH", path)
    return path


class TestStore:
    def test_missing_profile_returns_none(self, profile_store):
        from mcp_server.profile import store

        assert store.load_profile() is None
        with pytest.raises(store.ProfileMissingError):
            store.require_profile()

    def test_legacy_file_is_migrated_with_backup(self, profile_store):
        from mcp_server.profile import store

        profile_store.write_text(json.dumps(LEGACY_PROFILE), encoding="utf-8")
        profile = store.load_profile()
        assert profile.schema_version == 2
        backup = profile_store.with_suffix(".json.v1.bak")
        assert json.loads(backup.read_text(encoding="utf-8")) == LEGACY_PROFILE
        assert json.loads(profile_store.read_text(encoding="utf-8"))["schema_version"] == 2
        assert oct(os.stat(profile_store).st_mode)[-3:] == "600"

    def test_save_and_reload(self, profile_store):
        from mcp_server.profile import store

        profile = store.new_profile()
        profile.rules.liquidity_min = 750
        store.save_profile(profile)
        assert store.load_profile().rules.liquidity_min == 750


class TestProfileTool:
    def test_onboarding_then_update_then_confirm(self, profile_store, monkeypatch):
        from mcp_server.tools import profile_tool

        monkeypatch.setattr(profile_tool, "_reference_facts", lambda: FACTS)
        first = profile_tool.review_situation()
        assert first["status"] == "onboarding"

        result = profile_tool.update_situation(
            json.dumps(
                {
                    "identity": {"birth_year": 1995, "situation": "salarié"},
                    "rules": {"liquidity_min": 2000},
                    "accounts": [{"id": "courant", "name": "Courant", "category": "checking", "balance": 2500}],
                }
            )
        )
        assert result["status"] == "ok"
        assert any("accounts[courant] ajouté" in c for c in result["changes_applied"])

        review = profile_tool.review_situation()
        assert review["status"] == "ok"
        assert review["review_due"]["due"] is False
        assert review["question"].startswith("Votre situation a-t-elle changé depuis le")

        confirmed = profile_tool.confirm_situation_unchanged()
        assert confirmed["status"] == "ok"

    def test_invalid_update_is_rejected_without_writing(self, profile_store):
        from mcp_server.tools import profile_tool

        result = profile_tool.update_situation(
            json.dumps({"accounts": [{"id": "x", "name": "X", "category": "banane"}]})
        )
        assert result["status"] == "error"
        assert not profile_store.exists()


class TestFinarySync:
    def test_known_accounts_updated_unknown_added(self):
        from mcp_server.tools.portfolio_tool import apply_finary_sync

        profile = UserProfile.model_validate(migrate_v1_to_v2(LEGACY_PROFILE))
        accounts = [
            {"raw_name": "Compte Courant", "institution": "Compte Courant", "type": "checking", "balance": 999.0},
            {"raw_name": "Nouveau Livret", "institution": "Nouveau Livret", "type": "livret", "balance": 100.0},
        ]
        cryptos = [{"symbol": "ETH", "name": "Ethereum", "quantity": 1.0, "balance": 2000.0, "unrealized_pnl": None}]
        changes = apply_finary_sync(profile, accounts, cryptos, datetime(2026, 9, 26, tzinfo=timezone.utc))

        courant = profile.account_by_finary_name("Compte Courant")
        assert courant.balance == 999.0 and courant.id == "banque_a_courant"
        new = profile.account_by_finary_name("Nouveau Livret")
        assert new.needs_classification is True and new.category == "regulated_savings"
        assert profile.crypto.total_value == 2000.0
        assert profile.finary_snapshot.total_net_worth == 1099.0
        assert any("Nouveau compte Finary" in c for c in changes)


def test_example_profile_is_valid_v2():
    from pathlib import Path

    example = Path(__file__).parent.parent / "mcp_server" / "context" / "user_profile.example.json"
    data = json.loads(example.read_text(encoding="utf-8"))
    profile = UserProfile.model_validate(data)
    assert profile.schema_version == 2 and not is_legacy(data)

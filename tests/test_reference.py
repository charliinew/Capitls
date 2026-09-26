"""
Tests des données de référence : parseurs (fixtures = extraits réels des pages),
fusion / fraîcheur / actualités, et rafraîchissement du tool avec un adapter factice.
Aucun appel réseau.
"""

import json
import shutil
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from skills import reference_data as ref
from skills.reference_parsers import (
    html_to_text,
    parse_french_number,
    parse_justetf_profile,
    parse_service_public_page,
    service_public_pages,
)

FIXTURES = Path(__file__).parent / "fixtures"
REPO_REFERENCE = Path(__file__).parent.parent / "data" / "reference_data.json"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


class TestParsers:
    def test_french_numbers(self):
        assert parse_french_number("22 950") == 22950
        assert parse_french_number("1,7") == pytest.approx(1.7)
        assert parse_french_number("2,50") == pytest.approx(2.5)
        assert parse_french_number("23 028") == 23028

    def test_html_to_text_strips_scripts_and_entities(self):
        text = html_to_text("<p>Taux&nbsp;: <b>1,7 %</b></p><script>var x='9,9 %';</script>")
        assert text == "Taux : 1,7 %"

    @pytest.mark.parametrize(
        "page,expected",
        [
            ("F2365", {"livret_a.taux": 0.017, "livret_a.plafond": 22950}),
            ("F2368", {"ldds.taux": 0.017, "ldds.plafond": 12000}),
            ("F2367", {"lep.taux": 0.025, "lep.plafond": 10000, "lep.rfr_1_part": 23028}),
            ("F2904", {"livret_jeune.plafond": 1600, "livret_jeune.age_min": 12, "livret_jeune.age_max": 25}),
            ("F2385", {"pea.plafond": 150000, "pea_pme.plafond": 225000, "pea_jeune.plafond": 20000}),
            (
                "F21618",
                {"fiscalite.pfu_total": 0.314, "fiscalite.ir_forfaitaire": 0.128, "fiscalite.ps_placements": 0.186},
            ),
            ("F22414", {"fiscalite.ps_assurance_vie": 0.172, "assurance_vie.ir_apres_8_ans": 0.075}),
        ],
    )
    def test_service_public_pages(self, page, expected):
        parsed = parse_service_public_page(page, _fixture(f"service_public_{page}.html"))
        for key, value in expected.items():
            assert parsed[key] == pytest.approx(value), key

    def test_every_page_has_a_fixture(self):
        for page in service_public_pages():
            assert (FIXTURES / f"service_public_{page}.html").exists(), page

    def test_changed_page_structure_returns_none(self):
        parsed = parse_service_public_page("F2365", "<html><body>Page refondue</body></html>")
        assert parsed == {"livret_a.taux": None, "livret_a.plafond": None}

    def test_justetf_eligible_etf(self):
        profile = parse_justetf_profile(_fixture("justetf_DCAM.html"))
        assert profile["ter"] == pytest.approx(0.002)
        assert profile["pea_eligible"] is True
        assert profile["fund_size_meur"] == pytest.approx(1516)
        assert "PEA Monde" in profile["name"]

    def test_justetf_non_pea_etf_is_not_marked_eligible(self):
        profile = parse_justetf_profile(_fixture("justetf_IWDA.html"))
        assert profile["pea_eligible"] is None
        assert profile["ter"] == pytest.approx(0.002)


class TestReferenceLogic:
    NOW = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc)

    def test_needs_refresh_when_never_fetched(self):
        assert ref.needs_refresh({}, self.NOW) is True

    def test_no_refresh_within_24h(self):
        recent = (self.NOW - timedelta(hours=23)).isoformat()
        assert ref.needs_refresh({"last_successful_fetch": recent}, self.NOW) is False

    def test_refresh_after_24h(self):
        old = (self.NOW - timedelta(hours=25)).isoformat()
        assert ref.needs_refresh({"last_successful_fetch": old}, self.NOW) is True

    def test_failed_attempt_throttles_retries_for_one_hour(self):
        old = (self.NOW - timedelta(days=2)).isoformat()
        attempt = (self.NOW - timedelta(minutes=20)).isoformat()
        data = {"last_successful_fetch": old, "last_fetch_attempt": attempt}
        assert ref.needs_refresh(data, self.NOW) is False
        data["last_fetch_attempt"] = (self.NOW - timedelta(hours=2)).isoformat()
        assert ref.needs_refresh(data, self.NOW) is True

    def test_merge_records_change_and_updates_fallback(self):
        facts = {"livret_a.taux": {"label": "Taux Livret A", "value": 0.015, "verified_at": "2026-05-01"}}
        merged, changes = ref.merge_facts(facts, {"livret_a.taux": 0.017}, "2026-08-01")
        assert merged["livret_a.taux"]["value"] == 0.017
        assert merged["livret_a.taux"]["verified_at"] == "2026-08-01"
        assert merged["livret_a.taux"]["updated_at"] == "2026-08-01"
        assert changes == [
            {"date": "2026-08-01", "key": "livret_a.taux", "label": "Taux Livret A", "old": 0.015, "new": 0.017}
        ]
        assert facts["livret_a.taux"]["value"] == 0.015  # entrée non modifiée

    def test_merge_keeps_fallback_when_value_not_found(self):
        facts = {"lep.taux": {"value": 0.025, "verified_at": "2026-05-01"}}
        merged, changes = ref.merge_facts(facts, {"lep.taux": None}, "2026-09-26")
        assert merged["lep.taux"]["value"] == 0.025
        assert merged["lep.taux"]["verified_at"] == "2026-05-01"
        assert changes == []

    def test_same_value_refreshes_verification_without_change(self):
        facts = {"lep.taux": {"value": 0.025, "verified_at": "2026-05-01", "updated_at": "2026-02-01"}}
        merged, changes = ref.merge_facts(facts, {"lep.taux": 0.025}, "2026-09-26")
        assert changes == []
        assert merged["lep.taux"]["verified_at"] == "2026-09-26"
        assert merged["lep.taux"]["updated_at"] == "2026-02-01"

    def test_etf_ter_change_is_news(self):
        entry = {"ticker": "WPEA", "ter": 0.0025}
        merged, changes = ref.merge_etf(
            entry, {"ter": 0.002, "fund_size_meur": 2206, "pea_eligible": True, "name": None}, "2026-09-26"
        )
        assert merged["ter"] == 0.002 and merged["fund_size_meur"] == 2206
        assert changes[0]["key"] == "etf.WPEA.ter"

    def test_stale_facts(self):
        facts = {
            "fresh": {"value": 1, "verified_at": "2026-09-20"},
            "old": {"value": 2, "verified_at": "2026-06-01"},
            "never": {"value": 3},
        }
        stale = {s["key"] for s in ref.stale_facts(facts, date(2026, 9, 26))}
        assert stale == {"old", "never"}

    def test_changes_since(self):
        changes = [{"date": "2026-01-01"}, {"date": "2026-08-01"}]
        assert ref.changes_since(changes, "2026-06-01") == [{"date": "2026-08-01"}]
        assert len(ref.changes_since(changes, None)) == 2

    def test_format_value(self):
        assert ref.format_value(0.017, "taux") == "1,7 %"
        assert ref.format_value(0.186, "taux") == "18,6 %"
        assert ref.format_value(22950, "euros") == "22 950 €"


class FakeAdapter:
    def __init__(self, livret_a=0.02, ter=0.0018):
        self.livret_a = livret_a
        self.ter = ter

    def fetch_regulatory_facts(self):
        return (
            {"livret_a.taux": self.livret_a, "lep.taux": None},
            {"livret_a.taux": "https://example/F2365", "lep.taux": "https://example/F2367"},
            ["lep.taux introuvable"],
        )

    def fetch_etf_profiles(self, isins):
        return {
            isin: {"ter": self.ter, "fund_size_meur": 1.0, "pea_eligible": True, "name": None} for isin in isins
        }, []


@pytest.fixture
def reference_copy(tmp_path, monkeypatch):
    from mcp_server.tools import reference_tool

    path = tmp_path / "reference_data.json"
    shutil.copy(REPO_REFERENCE, path)
    monkeypatch.setattr(reference_tool, "REFERENCE_PATH", path)
    return path


class TestReferenceTool:
    def test_refresh_updates_file_and_logs_news(self, reference_copy):
        from mcp_server.tools import reference_tool

        report = reference_tool.refresh(force=True, adapter=FakeAdapter())
        data = json.loads(reference_copy.read_text(encoding="utf-8"))

        assert report["refreshed"] is True
        assert data["facts"]["livret_a.taux"]["value"] == 0.02
        assert data["facts"]["lep.taux"]["value"] == 0.025  # repli conservé
        assert data["last_fetch_errors"] == ["lep.taux introuvable"]
        keys = {c["key"] for c in report["new_changes"]}
        assert "livret_a.taux" in keys and "etf.DCAM.ter" in keys
        assert data["changes"][-1]["date"] == data["facts"]["livret_a.taux"]["verified_at"]

    def test_no_refetch_within_24h(self, reference_copy):
        from mcp_server.tools import reference_tool

        reference_tool.refresh(force=True, adapter=FakeAdapter())
        report = reference_tool.refresh(adapter=FakeAdapter(livret_a=0.99))
        assert report["refreshed"] is False
        data = json.loads(reference_copy.read_text(encoding="utf-8"))
        assert data["facts"]["livret_a.taux"]["value"] == 0.02

    def test_record_verified_fact(self, reference_copy):
        from mcp_server.tools import reference_tool

        result = reference_tool.record_verified_fact("fiscalite.ps_epargne_logement", 0.186, "https://example/F2329")
        assert result["fact"]["fiscalite.ps_epargne_logement"]["origin"] == "verified_by_agent"
        assert result["changes"][0]["old"] == 0.172

    def test_repo_reference_file_has_all_parsed_keys(self):
        from skills.reference_parsers import SERVICE_PUBLIC_FACTS

        data = json.loads(REPO_REFERENCE.read_text(encoding="utf-8"))
        assert set(SERVICE_PUBLIC_FACTS) <= set(data["facts"])

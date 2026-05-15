"""
Tests unitaires des skills — aucun appel réseau.
Exécuter : uv run pytest tests/ -v
"""

import pytest
from datetime import date, timedelta

from skills.dca import calculate_dca_projection, calculate_fortuneo_dca_plan, calculate_optimal_dca_schedule
from skills.diversification import analyze_diversification, detect_etf_overlap
from skills.etf import calculate_ter_impact, compare_etfs, get_etf_info, recommend_etf_for_pea
from skills.projection import project_pea_goal, project_portfolio, project_portfolio_multi_scenarios
from skills.tax import calculate_livret_jeune_vs_pea, calculate_pea_tax_advantage, calculate_real_return
from skills.pea_tracker import calculate_pea_countdown, add_pea_order, calculate_pea_performance, get_next_order_info
from skills.timing import calculate_timing_score, calculate_sma
from skills.benchmark import calculate_dca_vs_lumpsum, compare_returns
from skills.simulation import simulate_allocation, compare_vs_model_portfolio, get_crypto_alert
from skills.budget import calculate_investment_capacity, calculate_optimal_dca


class TestDCA:
    def test_basic_projection(self):
        result = calculate_dca_projection(
            monthly_amount=200,
            initial_amount=1000,
            annual_rate=0.07,
            years=10,
        )
        assert result["total_invested"] == pytest.approx(25000, rel=0.01)
        assert result["final_value"] > result["total_invested"]
        assert len(result["by_year"]) == 10

    def test_zero_rate(self):
        result = calculate_dca_projection(200, 1000, 0.0, 5)
        assert result["final_value"] == pytest.approx(result["total_invested"], rel=0.001)

    def test_fortuneo_plan_within_limit(self):
        result = calculate_fortuneo_dca_plan(monthly_budget=200, etf_price=5.12)
        assert result["is_free_order"] is True
        assert result["order_amount"] == pytest.approx(200)
        assert result["shares_to_buy"] == pytest.approx(200 / 5.12, rel=0.001)

    def test_fortuneo_plan_over_limit(self):
        # Budget 600 > 500 → order is capped at 500, leftover = 100
        result = calculate_fortuneo_dca_plan(monthly_budget=600, etf_price=5.12)
        assert result["order_amount"] == pytest.approx(500)
        assert result["leftover_cash"] == pytest.approx(100)
        assert result["is_free_order"] is True

    def test_dca_schedule_totals(self):
        schedule = calculate_optimal_dca_schedule(total_amount=1000, months=6)
        assert len(schedule) == 6
        total = sum(p["amount"] for p in schedule)
        assert total == pytest.approx(1000, rel=0.001)
        assert schedule[0]["amount"] > schedule[1]["amount"]  # premier versement plus élevé

    def test_dca_projection_zero_budget_returns_zero_gain_pct(self):
        result = calculate_dca_projection(monthly_amount=0, initial_amount=0, annual_rate=0.07, years=5)
        assert result["gain_pct"] == 0.0
        assert result["final_value"] == pytest.approx(0.0)

    def test_dca_projection_zero_years_returns_initial(self):
        result = calculate_dca_projection(monthly_amount=200, initial_amount=1000, annual_rate=0.07, years=0)
        assert result["final_value"] == pytest.approx(1000)
        assert result["total_invested"] == pytest.approx(1000)
        assert result["total_gains"] == pytest.approx(0)
        assert result["by_year"] == []

    def test_dca_projection_gains_negative_when_rate_negative(self):
        result = calculate_dca_projection(monthly_amount=200, initial_amount=1000, annual_rate=-0.50, years=5)
        assert result["total_gains"] < 0
        assert result["gain_pct"] < 0

    def test_fortuneo_exact_500_is_free(self):
        # At exactly 500€ (= limit), order is free (≤ max_free_order)
        result = calculate_fortuneo_dca_plan(monthly_budget=500, etf_price=10.0)
        assert result["order_amount"] == pytest.approx(500)
        assert result["leftover_cash"] == pytest.approx(0)
        assert result["is_free_order"] is True

    def test_dca_schedule_zero_months_returns_empty(self):
        schedule = calculate_optimal_dca_schedule(total_amount=1000, months=0)
        assert schedule == []

    def test_dca_schedule_negative_amount_returns_empty(self):
        schedule = calculate_optimal_dca_schedule(total_amount=-100, months=6)
        assert schedule == []

    def test_dca_schedule_single_month_receives_full_amount(self):
        schedule = calculate_optimal_dca_schedule(total_amount=1000, months=1)
        assert len(schedule) == 1
        assert schedule[0]["amount"] == pytest.approx(1000)
        assert schedule[0]["cumulative"] == pytest.approx(1000)

    def test_dca_schedule_month_numbers_are_sequential(self):
        schedule = calculate_optimal_dca_schedule(total_amount=600, months=3)
        months = [p["month"] for p in schedule]
        assert months == [1, 2, 3]

    def test_dca_schedule_cumulative_equals_final_total(self):
        schedule = calculate_optimal_dca_schedule(total_amount=900, months=4)
        assert schedule[-1]["cumulative"] == pytest.approx(900, rel=0.001)


class TestTax:
    def test_before_5_years(self):
        result = calculate_pea_tax_advantage(gross_gains=1000, years_held=3)
        assert result["eligible_for_exemption"] is False
        assert result["pea_tax"] == pytest.approx(314, rel=0.01)
        assert result["savings_vs_flat_tax"] == pytest.approx(0, rel=0.01)

    def test_after_5_years(self):
        result = calculate_pea_tax_advantage(gross_gains=1000, years_held=5)
        assert result["eligible_for_exemption"] is True
        assert result["pea_tax"] == pytest.approx(186, rel=0.01)
        assert result["savings_vs_flat_tax"] > 0

    def test_real_return(self):
        # MSCI World 7% brut, inflation 2%, TER 0.2%
        real = calculate_real_return(0.07, 0.02, 0.002)
        assert 0.04 < real < 0.06

    def test_pea_tax_exactly_5_years_is_eligible(self):
        # Boundary: exactly 5 years must be eligible (years >= 5)
        result = calculate_pea_tax_advantage(gross_gains=1000, years_held=5)
        assert result["eligible_for_exemption"] is True
        assert result["pea_tax"] == pytest.approx(186.0, rel=0.01)

    def test_pea_tax_exactly_4_years_is_not_eligible(self):
        # One year before the threshold: still taxed at full rate
        result = calculate_pea_tax_advantage(gross_gains=1000, years_held=4)
        assert result["eligible_for_exemption"] is False
        assert result["pea_tax"] == pytest.approx(314.0, rel=0.01)
        assert result["savings_vs_flat_tax"] == pytest.approx(0.0, abs=0.01)

    def test_pea_tax_note_contains_years_remaining_before_threshold(self):
        result = calculate_pea_tax_advantage(gross_gains=500, years_held=2)
        assert "3" in result["note"]  # "Encore 3 an(s)..."

    def test_livret_jeune_vs_pea_pea_wins_at_high_rate(self):
        result = calculate_livret_jeune_vs_pea(amount=5000, livret_rate=0.03, pea_annual_rate=0.10, years=20)
        assert result["verdict"] == "PEA"
        assert result["pea_after_5y"]["final_value"] > result["livret_jeune"]["final_value"]

    def test_livret_jeune_wins_when_pea_rate_is_low(self):
        # Livret at 3%, PEA at 2% after tax → Livret should win
        result = calculate_livret_jeune_vs_pea(amount=5000, livret_rate=0.04, pea_annual_rate=0.02, years=5)
        assert result["verdict"] == "Livret Jeune"

    def test_real_return_with_zero_inflation_and_zero_fees(self):
        # Should equal nominal return
        real = calculate_real_return(0.07, 0.0, 0.0)
        assert real == pytest.approx(0.07, rel=0.001)


class TestProjection:
    def test_multi_scenarios(self):
        result = project_portfolio_multi_scenarios(
            current_value=1000,
            monthly_contribution=200,
            years=10,
        )
        assert "pessimiste" in result
        assert "neutre" in result
        assert "optimiste" in result
        assert result["optimiste"]["final_value"] > result["neutre"]["final_value"]
        assert result["neutre"]["final_value"] > result["pessimiste"]["final_value"]

    def test_no_contribution(self):
        # Source uses monthly compounding: (1 + 0.07/12)^120, not (1.07)^10
        result = project_portfolio(1000, 0, 0.07, 10)
        expected = 1000 * (1 + 0.07 / 12) ** 120
        assert result["final_value"] == pytest.approx(expected, rel=0.001)

    def test_projection_zero_years_returns_current_value(self):
        result = project_portfolio(current_value=1000, monthly_contribution=200, annual_rate=0.07, years=0)
        assert result["final_value"] == pytest.approx(1000)
        assert result["total_invested"] == pytest.approx(1000)
        assert result["total_gains"] == pytest.approx(0)
        assert result["by_year"] == []

    def test_projection_by_year_length_matches_years(self):
        result = project_portfolio(current_value=5000, monthly_contribution=100, annual_rate=0.07, years=5)
        assert len(result["by_year"]) == 5

    def test_projection_gains_equal_value_minus_invested(self):
        result = project_portfolio(current_value=2000, monthly_contribution=300, annual_rate=0.07, years=3)
        assert result["total_gains"] == pytest.approx(
            result["final_value"] - result["total_invested"], rel=0.001
        )

    def test_multi_scenarios_only_pessimiste(self):
        result = project_portfolio_multi_scenarios(1000, 100, 5, scenarios=["pessimiste"])
        assert "pessimiste" in result
        assert "neutre" not in result
        assert "optimiste" not in result

    def test_multi_scenarios_unknown_scenario_is_skipped(self):
        result = project_portfolio_multi_scenarios(1000, 100, 5, scenarios=["neutre", "inexistant"])
        assert "neutre" in result
        assert "inexistant" not in result

    def test_pea_goal_reaches_target(self):
        result = project_pea_goal(target_value=50000, current_value=10000, monthly_contribution=200)
        assert result["reached"] is True
        assert result["final_value"] >= 50000
        assert result["total_months"] > 0

    def test_pea_goal_unreachable_within_max_years(self):
        # Zero contributions, zero initial value, zero rate — will never reach target
        result = project_pea_goal(target_value=50000, current_value=0, monthly_contribution=0, max_years=5)
        assert result["reached"] is False
        assert "non atteinte" in result["note"]


class TestDiversification:
    def test_good_diversification(self):
        portfolio = {
            "accounts": [
                {"type": "pea", "balance": 5000},
                {"type": "savings", "balance": 2000},
                {"type": "crypto", "balance": 500},
            ]
        }
        result = analyze_diversification(portfolio)
        assert result["score"] > 70
        assert len(result["warnings"]) == 0

    def test_crypto_overweight(self):
        portfolio = {
            "accounts": [
                {"type": "crypto", "balance": 5000},
                {"type": "savings", "balance": 1000},
            ]
        }
        result = analyze_diversification(portfolio)
        assert any("Crypto" in w or "crypto" in w for w in result["warnings"])

    def test_insufficient_liquidity(self):
        portfolio = {
            "accounts": [
                {"type": "pea", "balance": 10000},
                {"type": "savings", "balance": 200},
            ]
        }
        result = analyze_diversification(portfolio)
        assert any("iquidité" in w for w in result["warnings"])

    def test_etf_overlap(self):
        result = detect_etf_overlap(["FR001400U5Q4", "LU1681043599"])  # DCAM + CW8
        assert result["overlaps_found"] is True
        assert "MSCI World" in result["overlaps"][0]["index"]

    def test_no_overlap(self):
        result = detect_etf_overlap(["FR001400U5Q4"])  # Un seul ETF
        assert result["overlaps_found"] is False

    def test_empty_portfolio_returns_score_zero(self):
        result = analyze_diversification({})
        assert result["score"] == 0
        assert "Portfolio vide" in result["warnings"]

    def test_portfolio_with_all_zero_balances_returns_score_zero(self):
        portfolio = {"accounts": [{"type": "pea", "balance": 0}]}
        result = analyze_diversification(portfolio)
        assert result["score"] == 0
        assert any("0" in w for w in result["warnings"])

    def test_single_asset_class_has_concentration_warning(self):
        portfolio = {"accounts": [{"type": "pea", "balance": 50000}]}
        result = analyze_diversification(portfolio)
        assert any("seule" in w or "Concentration" in w for w in result["warnings"])
        assert result["asset_classes_count"] == 1

    def test_etf_overlap_three_msci_world(self):
        # Three ETFs tracking same index → one overlap entry with all three ISINs
        result = detect_etf_overlap(["FR001400U5Q4", "LU1681043599", "IE0002XZSHO1"])
        assert result["overlaps_found"] is True
        overlap = result["overlaps"][0]
        assert len(overlap["isins"]) == 3
        assert overlap["overlap_pct"] == 100

    def test_etf_overlap_unknown_isin_does_not_cause_false_overlap(self):
        result = detect_etf_overlap(["NOTANISIN"])
        # Single unknown → no overlap (only one ETF in "Unknown" bucket)
        assert result["overlaps_found"] is False

    def test_etf_overlap_recommendation_mentions_one_etf_when_overlap(self):
        result = detect_etf_overlap(["FR001400U5Q4", "LU1681043599"])
        assert "UN SEUL" in result["recommendation"]

    def test_no_pea_penalizes_score(self):
        portfolio = {
            "accounts": [
                {"type": "livret",  "balance": 1600},
                {"type": "checking","balance": 1200},
                {"type": "savings", "balance": 1000},
                {"type": "crypto",  "balance": 500},
            ]
        }
        result = analyze_diversification(portfolio)
        assert result["score"] <= 90  # penalized for absence of PEA/securities (-25 + bonus +10 classes = 85)
        assert any("bourse" in w or "PEA" in w for w in result["warnings"])


class TestETF:
    def test_get_dcam_info(self):
        info = get_etf_info("DCAM")
        assert info["isin"] == "FR001400U5Q4"
        assert info["ter"] == 0.0020
        assert info["eligible_pea"] is True

    def test_unknown_etf(self):
        info = get_etf_info("UNKNOWN")
        assert "error" in info

    def test_compare_etfs_sorted_by_ter(self):
        result = compare_etfs(["CW8", "DCAM", "WPEA"])
        ters = [e["ter"] for e in result]
        assert ters == sorted(ters)

    def test_recommend_etf(self):
        rec = recommend_etf_for_pea(courtier="fortuneo", monthly_budget=200)
        assert rec["recommended"]["ter"] <= 0.0020
        assert rec["recommended"]["eligible_pea"] is True

    def test_get_etf_with_pa_suffix_resolves_correctly(self):
        info = get_etf_info("DCAM.PA")
        assert info["isin"] == "FR001400U5Q4"

    def test_compare_etfs_filters_out_unknown_tickers(self):
        result = compare_etfs(["DCAM", "UNKNOWN", "CW8"])
        tickers = [e["ticker"] for e in result]
        assert "UNKNOWN" not in tickers
        assert "DCAM" in tickers
        assert "CW8" in tickers

    def test_compare_etfs_empty_list_returns_empty(self):
        result = compare_etfs([])
        assert result == []

    def test_calculate_ter_impact_higher_ter_gives_lower_final_value(self):
        result = calculate_ter_impact(
            initial=10000, monthly=200, years=20,
            ter_a=0.0020, ter_b=0.0038,
        )
        assert result["ter_a"]["final_value"] > result["ter_b"]["final_value"]
        assert result["difference"] == pytest.approx(3548.18, rel=0.01)

    def test_calculate_ter_impact_equal_ters_give_zero_difference(self):
        result = calculate_ter_impact(
            initial=10000, monthly=200, years=10,
            ter_a=0.0020, ter_b=0.0020,
        )
        assert result["difference"] == pytest.approx(0.0, abs=0.01)

    def test_calculate_ter_impact_note_mentions_years(self):
        result = calculate_ter_impact(10000, 200, 15, 0.002, 0.005)
        assert "15" in result["note"]

    def test_recommend_etf_ewld_not_in_candidates(self):
        # EWLD is explicitly excluded from recommendation (TER too high)
        rec = recommend_etf_for_pea()
        all_tickers = [rec["recommended"]["ticker"]] + [a["ticker"] for a in rec["alternatives"]]
        assert "EWLD" not in all_tickers

    def test_get_all_catalog_etfs_return_expected_fields(self):
        for ticker in ["DCAM", "WPEA", "CW8", "EWLD"]:
            info = get_etf_info(ticker)
            assert "isin" in info
            assert "ter" in info
            assert "eligible_pea" in info


class TestPEATracker:
    def test_countdown_not_active(self):
        # opening_date=None → PEA not yet opened
        result = calculate_pea_countdown(opening_date=None)
        assert result["is_active"] is False
        # is_exempt is None (not False) when PEA is not opened — source returns None
        assert result["is_exempt"] is None
        assert result["days_remaining"] is None

    def test_countdown_future(self):
        # Opening date = today → active, not yet exempt, ~1826 days remaining
        today = date.today()
        result = calculate_pea_countdown(opening_date=today.isoformat())
        assert result["is_active"] is True
        assert result["is_exempt"] is False
        assert 1820 <= result["days_remaining"] <= 1830
        # exemption_date is returned as an ISO string
        expected_exemption = (today + timedelta(days=1826)).isoformat()
        assert result["exemption_date"] == expected_exemption

    def test_countdown_exempt(self):
        # Opened 6 years ago → should be exempt, 0 days remaining
        six_years_ago = date.today() - timedelta(days=6 * 365 + 2)
        result = calculate_pea_countdown(opening_date=six_years_ago.isoformat())
        assert result["is_exempt"] is True
        assert result["days_remaining"] == 0

    def test_add_order_basic(self):
        # 200€ at 150€/share → ~1.333 shares, free (≤ 500€)
        result = add_pea_order([], "2026-05-15", "DCAM", 200, 150)
        assert len(result) == 1
        assert result[0]["shares"] == pytest.approx(200 / 150, rel=0.01)
        assert result[0]["is_free"] is True

    def test_add_order_not_free(self):
        # 600€ > 500€ threshold → is_free=False
        result = add_pea_order([], "2026-05-15", "DCAM", 600, 100)
        assert result[0]["is_free"] is False

    def test_add_order_immutable(self):
        # Original list must not be mutated
        original = []
        add_pea_order(original, "2026-05-15", "DCAM", 200, 100)
        assert original == []

    def test_performance_empty(self):
        # No orders → all zeros
        result = calculate_pea_performance(order_history=[], current_price=100, ticker="DCAM")
        assert result["total_invested"] == 0
        assert result["gain_pct"] == 0

    def test_performance_gain(self):
        # 200€ at 100€/share = 2 shares; current price 120€ → 240€ value, +40€ gain
        order = {"date": "2026-01-15", "ticker": "DCAM", "amount": 200, "price": 100, "shares": 2.0, "is_free": True}
        result = calculate_pea_performance(order_history=[order], current_price=120, ticker="DCAM")
        assert result["current_value"] == pytest.approx(240, rel=0.01)
        assert result["gain_eur"] == pytest.approx(40, rel=0.01)
        # gain_pct in source is expressed as percentage (20.0), not ratio (0.20)
        assert result["gain_pct"] == pytest.approx(20.0, rel=0.01)

    def test_performance_loss(self):
        # 200€ at 100€/share, price drops to 80€ → negative gain
        order = {"date": "2026-01-15", "ticker": "DCAM", "amount": 200, "price": 100, "shares": 2.0, "is_free": True}
        result = calculate_pea_performance(order_history=[order], current_price=80, ticker="DCAM")
        assert result["gain_eur"] < 0
        assert result["gain_pct"] < 0

    def test_next_order_empty_history(self):
        # No prior orders → next_date is today, is_free_order True (200€ ≤ 500€)
        result = get_next_order_info(order_history=[], monthly_target=200)
        today = date.today()
        next_date = date.fromisoformat(result["next_date"])
        assert (next_date - today).days <= 1
        assert result["is_free_order"] is True

    def test_next_order_with_history(self):
        # Last order 2 days ago → next_date ≈ 28 days from today (1 calendar month ahead)
        two_days_ago = date.today() - timedelta(days=2)
        order = {"date": two_days_ago.isoformat(), "ticker": "DCAM", "amount": 200, "price": 100, "shares": 2.0, "is_free": True}
        result = get_next_order_info(order_history=[order], monthly_target=200)
        today = date.today()
        days_until_next = (date.fromisoformat(result["next_date"]) - today).days
        assert 26 <= days_until_next <= 30


class TestTiming:
    def test_sma_basic(self):
        # Last 3 of [1,2,3,4,5] → (3+4+5)/3 = 4.0
        result = calculate_sma([1.0, 2.0, 3.0, 4.0, 5.0], window=3)
        assert result == pytest.approx(4.0, rel=0.01)

    def test_sma_not_enough_data(self):
        # 2 prices, window=5 → None
        result = calculate_sma([1.0, 2.0], window=5)
        assert result is None

    def test_score_insufficient_data(self):
        # Single price → score=50 (neutral, insufficient data)
        result = calculate_timing_score(prices=[100.0])
        assert result["score"] == 50

    def test_score_flat_prices(self):
        # Flat series: all ratios = 1.0, so 100% are <= current ratio → score=100
        # The algorithm counts ratios <= current_ratio; with all equal, score=100
        prices = [100.0] * 300
        result = calculate_timing_score(prices=prices)
        assert result["score"] == 100

    def test_score_low_entry(self):
        # 300 stable prices followed by a sharp drop: last price is far below the SMA
        # built over the stable period → the current ratio is a historical low → low score
        prices = [100.0] * 300 + [50.0]
        result = calculate_timing_score(prices=prices)
        assert result["score"] <= 30

    def test_score_high_entry(self):
        # 300 stable prices followed by a sharp spike: last price far exceeds its SMA
        # → the current ratio is a historical high → high score
        prices = [100.0] * 300 + [200.0]
        result = calculate_timing_score(prices=prices)
        assert result["score"] >= 70

    def test_score_interpretation_bon(self):
        # Sharp drop after flat base → low score → "Bon point d'entrée"
        prices = [100.0] * 300 + [50.0]
        result = calculate_timing_score(prices=prices)
        assert result["score"] <= 30
        assert "Bon" in result["interpretation"] or "bon" in result["interpretation"]

    def test_score_interpretation_eleve(self):
        # Sharp spike after flat base → high score → "Prix élevé"
        prices = [100.0] * 300 + [200.0]
        result = calculate_timing_score(prices=prices)
        assert result["score"] >= 70
        assert any(word in result["interpretation"] for word in ["élevé", "haut", "Élevé", "Haut"])


class TestBenchmark:
    def test_dca_vs_lumpsum_basic(self):
        # 13 mois de prix croissants — DCA achète à des prix variés
        prices = [100.0 + i for i in range(13 * 21 + 1)]
        result = calculate_dca_vs_lumpsum(prices, monthly_amount=200.0, months=12)
        assert "dca_final" in result
        assert "lumpsum_final" in result
        assert result["total_invested"] == pytest.approx(2400.0, rel=0.01)
        assert isinstance(result["dca_wins"], bool)

    def test_dca_vs_lumpsum_not_enough_data(self):
        # Moins d'un mois de données → utilise ce qui est disponible
        prices = [100.0, 105.0, 110.0]
        result = calculate_dca_vs_lumpsum(prices, monthly_amount=200.0, months=12)
        assert "dca_final" in result
        assert result["months_compared"] >= 1

    def test_dca_lumpsum_flat_market(self):
        # Prix plat → DCA et lump sum donnent le même résultat
        prices = [100.0] * (13 * 21 + 1)
        result = calculate_dca_vs_lumpsum(prices, monthly_amount=200.0, months=12)
        assert result["dca_final"] == pytest.approx(result["lumpsum_final"], rel=0.01)

    def test_compare_returns_basic(self):
        prices_a = [100.0, 110.0, 120.0]
        prices_b = [100.0, 105.0, 115.0]
        result = compare_returns(prices_a, prices_b, "ETF", "Benchmark")
        assert result["ETF"]["return_pct"] == pytest.approx(20.0, rel=0.01)
        assert result["Benchmark"]["return_pct"] == pytest.approx(15.0, rel=0.01)
        assert result["outperformance_pct"] == pytest.approx(5.0, rel=0.01)
        assert result["winner"] == "ETF"

    def test_compare_returns_insufficient_data(self):
        result = compare_returns([100.0], [100.0])
        assert "error" in result

    def test_compare_returns_underperformance(self):
        prices_a = [100.0, 95.0]
        prices_b = [100.0, 105.0]
        result = compare_returns(prices_a, prices_b, "ETF", "Bench")
        assert result["outperformance_pct"] < 0
        assert result["winner"] == "Bench"


class TestSimulation:
    def test_simulate_allocation_basic(self):
        current = {"world": 0.0, "crypto": 0.35, "savings": 0.65}
        target = {"world": 0.70, "crypto": 0.10, "savings": 0.20}
        result = simulate_allocation(current, target, total_value=3000.0)
        assert result["total_value"] == 3000.0
        assert "rebalancing_actions" in result
        assert len(result["rebalancing_actions"]) > 0

    def test_simulate_no_change(self):
        alloc = {"world": 0.70, "crypto": 0.10, "savings": 0.20}
        result = simulate_allocation(alloc, alloc, total_value=5000.0)
        # Pas de mouvement significatif (delta = 0)
        assert result["rebalancing_actions"] == ["Aucun mouvement significatif requis"]

    def test_compare_vs_model_close(self):
        # Allocation proche du modèle → score d'écart faible
        alloc = {"world": 0.72, "savings": 0.18, "crypto": 0.10}
        result = compare_vs_model_portfolio(alloc)
        assert result["ecart_score"] <= 20

    def test_compare_vs_model_far(self):
        # Allocation très différente du modèle
        alloc = {"world": 0.0, "savings": 0.65, "crypto": 0.35}
        result = compare_vs_model_portfolio(alloc)
        assert result["ecart_score"] > 40

    def test_crypto_alert_triggered(self):
        # 25% crypto → alerte (seuil 15%)
        result = get_crypto_alert(crypto_value=750.0, total_value=3000.0, threshold=0.15)
        assert result["alert"] is True
        assert result["crypto_pct"] == pytest.approx(25.0, rel=0.01)
        assert result["excess_eur"] > 0

    def test_crypto_alert_ok(self):
        # 10% crypto → pas d'alerte
        result = get_crypto_alert(crypto_value=300.0, total_value=3000.0, threshold=0.15)
        assert result["alert"] is False
        assert result["excess_eur"] == 0.0

    def test_crypto_alert_zero_total(self):
        result = get_crypto_alert(crypto_value=100.0, total_value=0.0)
        assert "error" in result


class TestBudget:
    def test_investment_capacity_stage(self):
        # Revenu 900€, dépenses 600€, buffer 10% → investissable = 900-600-90 = 210€
        result = calculate_investment_capacity(monthly_income=900.0, fixed_expenses=600.0)
        assert result["investable_amount"] == pytest.approx(210.0, rel=0.01)
        assert result["is_free_order"] is True  # 210 ≤ 500

    def test_investment_capacity_zero_income(self):
        result = calculate_investment_capacity(monthly_income=0.0)
        assert result["investable_amount"] == 0.0
        assert result["is_free_order"] is False

    def test_investment_capacity_high_income(self):
        # Revenu 3000€, dépenses 1000€ → net 2000€, buffer 300€ → investissable 1700€
        result = calculate_investment_capacity(monthly_income=3000.0, fixed_expenses=1000.0)
        assert result["investable_amount"] == pytest.approx(1700.0, rel=0.01)
        assert result["is_free_order"] is False  # 1700 > 500

    def test_investment_capacity_not_enough(self):
        # Dépenses > revenus → investissable = 0
        result = calculate_investment_capacity(monthly_income=500.0, fixed_expenses=700.0)
        assert result["investable_amount"] == 0.0

    def test_optimal_dca_empty_history(self):
        result = calculate_optimal_dca(income_history=[])
        assert result["recommended_monthly_dca"] == 200.0
        assert result["months_analyzed"] == 0

    def test_optimal_dca_with_history(self):
        history = [
            {"month": "2026-03", "income": 900.0},
            {"month": "2026-04", "income": 1200.0},
            {"month": "2026-05", "income": 700.0},
        ]
        result = calculate_optimal_dca(history, fixed_expenses=600.0)
        assert result["months_analyzed"] == 3
        # Recommandation basée sur mois le plus faible (700€) → 700-600-70 = 30€
        assert result["recommended_monthly_dca"] == pytest.approx(30.0, rel=0.01)
        assert result["is_free_order"] is True

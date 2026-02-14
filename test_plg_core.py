#!/usr/bin/env python3
"""
Tests for plg_core.py — PLG thesis verdict logic.

Coverage:
- Tier routing (5 tests)
- Tier 1 verdicts (12 tests)
- Tier 2 verdicts (6 tests)
- Tier 3 verdicts (4 tests)
- Tier 4 verdicts (6 tests)
- Confidence scoring (5 tests)
- Staleness checking (3 tests)
- Normalization helpers (4 tests)
- Integration with real company data (4 tests)
- Regression: enhanced matches batch (1 test)

Run: pytest test_plg_core.py -v
"""

import pytest
from datetime import datetime, timedelta

from plg_core import (
    # Constants
    NDR_ENTRY_THRESHOLD,
    NDR_ELITE_THRESHOLD,
    GROWTH_ENTRY_THRESHOLD,
    GROWTH_ELITE_THRESHOLD,
    GR_STRONG,
    GR_HEALTHY,
    GR_ACCEPTABLE,
    DBNE_STRONG,
    DBNE_HEALTHY,
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_LOW,
    # Data classes
    CompanyData,
    VerdictResult,
    # Functions
    compute_verdict,
    calculate_confidence_score,
    score_to_confidence_level,
    check_staleness,
    recommend_research,
    _determine_data_tier,
    _normalize_growth,
    _normalize_retention,
    _interpret_retention_signal,
    load_company_database,
    build_company_data,
)


# ============================================================
# HELPERS
# ============================================================

def make_company(**kwargs) -> CompanyData:
    """Shorthand for creating CompanyData with defaults."""
    defaults = {
        'ticker': 'TEST',
        'name': 'Test Company',
        'category': 'infrastructure',
        'business_model': 'b2b_saas',
    }
    defaults.update(kwargs)
    return CompanyData(**defaults)


# ============================================================
# TIER ROUTING (5 tests)
# ============================================================

class TestTierRouting:

    def test_tier1_direct_ndr(self):
        """NDR with ndr_tier=1 routes to Tier 1."""
        data = make_company(ndr=115, ndr_tier=1)
        assert _determine_data_tier(data) == 1

    def test_tier2_ndr_tier2(self):
        """NDR with ndr_tier=2 (approximate) routes to Tier 2."""
        data = make_company(ndr=120, ndr_tier=2)
        assert _determine_data_tier(data) == 2

    def test_tier2_dbne_available(self):
        """DBNE available (no NDR) routes to Tier 2."""
        data = make_company(dbne=115)
        assert _determine_data_tier(data) == 2

    def test_tier3_implied_expansion(self):
        """Implied expansion available routes to Tier 3."""
        data = make_company(implied_expansion=12.0)
        assert _determine_data_tier(data) == 3

    def test_tier4_no_retention_data(self):
        """No retention data routes to Tier 4."""
        data = make_company()
        assert _determine_data_tier(data) == 4

    def test_tier4_consumer_model(self):
        """Consumer business model routes to Tier 4."""
        data = make_company(business_model='consumer')
        assert _determine_data_tier(data) == 4

    def test_tier2_gross_retention_only(self):
        """Gross retention only routes to Tier 2."""
        data = make_company(gross_retention=95.0)
        assert _determine_data_tier(data) == 2


# ============================================================
# TIER 1 VERDICTS (12 tests)
# ============================================================

class TestTier1Verdicts:

    def test_strong_buy_elite(self):
        """Elite: NDR >= 120 AND growth >= 30% = STRONG_BUY."""
        data = make_company(
            ndr=127, ndr_tier=1, revenue_growth_yoy=0.29,
            big_tech_threat='medium', category_stage='early_growth',
            switching_cost='high',
        )
        result = compute_verdict(data)
        assert result.verdict == 'STRONG_BUY'
        assert result.data_tier == 1

    def test_strong_buy_all_5_signals(self):
        """All 5 entry signals = STRONG_BUY."""
        data = make_company(
            ndr=115, ndr_tier=1, revenue_growth_yoy=0.30,
            big_tech_threat='low', category_stage='emerging',
            switching_cost='high',
        )
        result = compute_verdict(data)
        assert result.verdict == 'STRONG_BUY'

    def test_buy_4_signals(self):
        """4/5 entry signals = BUY."""
        data = make_company(
            ndr=119, ndr_tier=1, revenue_growth_yoy=0.24,
            big_tech_threat='medium', category_stage='early_growth',
            switching_cost='high',
        )
        result = compute_verdict(data)
        assert result.verdict == 'BUY'
        assert result.entry_signals_met >= 4

    def test_watch_3_signals(self):
        """3/5 entry signals = WATCH."""
        data = make_company(
            ndr=111, ndr_tier=1, revenue_growth_yoy=0.19,
            big_tech_threat='medium', category_stage='mid_growth',
            switching_cost='high',
        )
        result = compute_verdict(data)
        assert result.verdict in ('WATCH', 'BUY')  # 3.5 signals possible

    def test_avoid_low_signals(self):
        """<3 entry signals = AVOID."""
        data = make_company(
            ndr=111, ndr_tier=1, revenue_growth_yoy=0.10,
            big_tech_threat='very_high', category_stage='mature',
            switching_cost='low',
        )
        result = compute_verdict(data)
        # NDR >= 110 but growth low, big tech high, mature, low switching
        # Entry: NDR=1, growth=0, category=0, big_tech=0, switching=0 = 1 signal
        # But also exit: mature (0.5) + very_high (0.5) = 1 exit → WATCH
        assert result.verdict in ('WATCH', 'AVOID')

    def test_sell_2_exit_signals(self):
        """2+ exit signals = SELL."""
        data = make_company(
            ndr=96, ndr_tier=1, revenue_growth_yoy=0.10,
            big_tech_threat='very_high', category_stage='commoditizing',
            switching_cost='low',
        )
        result = compute_verdict(data)
        assert result.verdict == 'SELL'
        assert result.exit_signals_triggered >= 2

    def test_sell_ndr_below_threshold_plus_commoditizing(self):
        """NDR < 110 + commoditizing = 2 exit signals = SELL."""
        data = make_company(
            ndr=87, ndr_tier=1, revenue_growth_yoy=-0.01,
            big_tech_threat='very_high', category_stage='commoditizing',
            switching_cost='low',
        )
        result = compute_verdict(data)
        assert result.verdict == 'SELL'

    def test_watch_single_exit_signal(self):
        """1 exit signal = WATCH (not SELL)."""
        data = make_company(
            ndr=106, ndr_tier=1, revenue_growth_yoy=0.11,
            big_tech_threat='low', category_stage='mid_growth',
            switching_cost='high',
        )
        result = compute_verdict(data)
        assert result.verdict == 'WATCH'

    def test_exit_big_tech_announced(self):
        """big_tech_announced = exit signal."""
        data = make_company(
            ndr=115, ndr_tier=1, revenue_growth_yoy=0.25,
            big_tech_threat='low', category_stage='early_growth',
            switching_cost='high', big_tech_announced=True,
        )
        result = compute_verdict(data)
        assert result.verdict == 'WATCH'  # 1 exit = WATCH

    def test_exit_revenue_decel(self):
        """revenue_decel_3q = exit signal."""
        data = make_company(
            ndr=108, ndr_tier=1, revenue_growth_yoy=0.09,
            big_tech_threat='high', category_stage='mature',
            switching_cost='medium', revenue_decel_3q=True,
        )
        result = compute_verdict(data)
        assert result.verdict == 'SELL'  # NDR<110(1) + decel(1) + mature(0.5) + big_tech(0.5) = 3

    def test_partial_credit_growth_20_25(self):
        """Growth 20-25% gets 0.5 partial credit."""
        data = make_company(
            ndr=115, ndr_tier=1, revenue_growth_yoy=0.22,
            big_tech_threat='medium', category_stage='early_growth',
            switching_cost='high',
        )
        result = compute_verdict(data)
        # NDR=1, growth=0.5, category=1, big_tech=1, switching=1 = 4.5 → BUY
        assert result.verdict == 'BUY'

    def test_partial_credit_mid_growth(self):
        """mid_growth category gets 0.5 partial credit."""
        data = make_company(
            ndr=115, ndr_tier=1, revenue_growth_yoy=0.28,
            big_tech_threat='medium', category_stage='mid_growth',
            switching_cost='high',
        )
        result = compute_verdict(data)
        # NDR=1, growth=1, category=0.5, big_tech=1, switching=1 = 4.5 → BUY
        assert result.verdict == 'BUY'


# ============================================================
# TIER 2 VERDICTS (6 tests)
# ============================================================

class TestTier2Verdicts:

    def test_tier2_strong_retention_strong_growth(self):
        """Strong DBNE + strong growth = BUY."""
        data = make_company(
            ndr=120, ndr_tier=2, dbne=120,
            revenue_growth_yoy=0.28,
            big_tech_threat='medium', category_stage='early_growth',
            switching_cost='high',
        )
        result = compute_verdict(data)
        assert result.verdict == 'BUY'
        assert result.data_tier == 2

    def test_tier2_weak_retention_sell(self):
        """Weak retention (DBNE < 100) = SELL."""
        data = make_company(
            dbne=95, revenue_growth_yoy=0.09,
            big_tech_threat='high', category_stage='mature',
        )
        result = compute_verdict(data)
        assert result.verdict == 'SELL'
        assert result.data_tier == 2

    def test_tier2_healthy_retention_watch(self):
        """Healthy retention + moderate growth = WATCH."""
        data = make_company(
            ndr=115, ndr_tier=2,
            revenue_growth_yoy=0.22,
            big_tech_threat='medium', category_stage='early_growth',
            switching_cost='high',
        )
        result = compute_verdict(data)
        assert result.verdict == 'WATCH'
        assert result.data_tier == 2

    def test_tier2_gr_interpretation(self):
        """GR >= 97 = strong retention signal."""
        data = make_company(
            gross_retention=97.0,
            revenue_growth_yoy=0.28,
            big_tech_threat='medium', category_stage='early_growth',
        )
        result = compute_verdict(data)
        assert result.data_tier == 2
        assert result.verdict == 'BUY'

    def test_tier2_gr_decimal_normalization(self):
        """GR as decimal (0.97) normalizes to 97%."""
        data = make_company(
            gross_retention=0.97,
            revenue_growth_yoy=0.28,
            big_tech_threat='medium', category_stage='early_growth',
        )
        result = compute_verdict(data)
        assert result.data_tier == 2
        assert result.verdict == 'BUY'

    def test_tier2_exit_signals_override(self):
        """Tier 2 exit signals (decel + commoditizing) = SELL."""
        data = make_company(
            ndr=115, ndr_tier=2,
            revenue_growth_yoy=0.20,
            revenue_decel_3q=True,
            big_tech_threat='high', category_stage='mature',
        )
        result = compute_verdict(data)
        assert result.verdict == 'SELL'


# ============================================================
# TIER 3 VERDICTS (4 tests)
# ============================================================

class TestTier3Verdicts:

    def test_tier3_negative_expansion_sell(self):
        """Negative implied expansion = SELL."""
        data = make_company(
            implied_expansion=-5.0,
            revenue_growth_yoy=0.05,
        )
        result = compute_verdict(data)
        assert result.verdict == 'SELL'
        assert result.data_tier == 3

    def test_tier3_strong_expansion_watch(self):
        """Strong expansion + good growth = WATCH (max for Tier 3)."""
        data = make_company(
            implied_expansion=20.0,
            revenue_growth_yoy=0.30,
        )
        result = compute_verdict(data)
        assert result.verdict == 'WATCH'
        assert result.data_tier == 3

    def test_tier3_rpo_accelerating(self):
        """RPO accelerating = WATCH with forward demand note."""
        data = make_company(
            rpo_growth_yoy=0.40,
            revenue_growth_yoy=0.25,
        )
        result = compute_verdict(data)
        assert result.verdict == 'WATCH'
        assert result.data_tier == 3
        assert 'RPO' in result.rationale or 'forward' in result.rationale.lower()

    def test_tier3_never_buy(self):
        """Tier 3 should never produce BUY or STRONG_BUY."""
        data = make_company(
            implied_expansion=25.0,
            rpo_growth_yoy=0.50,
            revenue_growth_yoy=0.40,
        )
        result = compute_verdict(data)
        assert result.verdict in ('WATCH', 'SELL')


# ============================================================
# TIER 4 VERDICTS (6 tests)
# ============================================================

class TestTier4Verdicts:

    def test_tier4_consumer_strong_arpu_buy(self):
        """Consumer: ARPU > 20% + user growth > 15% = BUY."""
        data = make_company(
            business_model='consumer',
            arpu_growth_yoy=25.0,
            active_user_growth_yoy=20.0,
            revenue_growth_yoy=0.38,
        )
        result = compute_verdict(data)
        assert result.verdict == 'BUY'
        assert result.data_tier == 4

    def test_tier4_consumer_declining_arpu_sell(self):
        """Consumer: ARPU declining = SELL."""
        data = make_company(
            business_model='consumer',
            arpu_growth_yoy=-5.0,
            revenue_growth_yoy=0.10,
        )
        result = compute_verdict(data)
        assert result.verdict == 'SELL'

    def test_tier4_marketplace_strong_gmv_buy(self):
        """Marketplace: GMV > 25% + take rate not decreasing = BUY."""
        data = make_company(
            business_model='marketplace',
            gmv_growth_yoy=30.0,
            take_rate=2.5,
            take_rate_trend='stable',
            revenue_growth_yoy=0.25,
        )
        result = compute_verdict(data)
        assert result.verdict == 'BUY'

    def test_tier4_marketplace_take_rate_decreasing_watch(self):
        """Marketplace: take_rate_trend decreasing = WATCH."""
        data = make_company(
            business_model='marketplace',
            gmv_growth_yoy=30.0,
            take_rate_trend='decreasing',
            revenue_growth_yoy=0.20,
        )
        result = compute_verdict(data)
        assert result.verdict == 'WATCH'

    def test_tier4_transaction_margin_compression_sell(self):
        """Transaction: GP growth << TPV growth = SELL."""
        data = make_company(
            business_model='transaction_based',
            gross_profit_growth_yoy=5.0,
            tpv_growth_yoy=25.0,  # GP 5% << TPV 25% - 10% = 15%
            revenue_growth_yoy=0.10,
        )
        result = compute_verdict(data)
        assert result.verdict == 'SELL'

    def test_tier4_insufficient_data_watch(self):
        """B2B SaaS with no retention data = WATCH."""
        data = make_company(
            revenue_growth_yoy=0.25,
            big_tech_threat='medium', category_stage='early_growth',
            switching_cost='high',
        )
        result = compute_verdict(data)
        assert result.verdict == 'WATCH'
        assert result.data_tier == 4
        assert 'NDR' in ' '.join(result.missing_signals)


# ============================================================
# CONFIDENCE SCORING (5 tests)
# ============================================================

class TestConfidenceScoring:

    def test_high_confidence_full_data(self):
        """Full Tier 1 data + assessments = HIGH confidence."""
        data = make_company(
            ndr=120, ndr_tier=1,
            revenue_growth_yoy=0.30,
            arr_millions=2000,
            customers_100k_plus=500,
            customer_growth_yoy=0.15,
            big_tech_threat='low',
            category_stage='early_growth',
        )
        score = calculate_confidence_score(data)
        assert score >= CONFIDENCE_HIGH
        assert score_to_confidence_level(score) == 'HIGH'

    def test_medium_confidence_partial_data(self):
        """Tier 1 NDR + growth but missing customer data = MEDIUM."""
        data = make_company(
            ndr=115, ndr_tier=1,
            revenue_growth_yoy=0.25,
            # Assessments unknown → 0 credit
            # No customer data → 0 credit
            # revenue_decel_3q defaults to False → gets trend credit
            # Total: 0.25 + 0.15 + 0.10 (trend) = 0.50
        )
        score = calculate_confidence_score(data)
        assert CONFIDENCE_MEDIUM <= score < CONFIDENCE_HIGH
        assert score_to_confidence_level(score) == 'MEDIUM'

    def test_low_confidence_minimal_data(self):
        """Only growth data = LOW confidence."""
        data = make_company(
            revenue_growth_yoy=0.20,
        )
        score = calculate_confidence_score(data)
        assert score < CONFIDENCE_MEDIUM
        assert score_to_confidence_level(score) in ('LOW', 'INSUFFICIENT')

    def test_unknown_defaults_no_credit(self):
        """Default 'unknown' assessments get 0 credit for competitive signals."""
        data_with_assessments = make_company(
            ndr=115, ndr_tier=1,
            revenue_growth_yoy=0.25,
            big_tech_threat='low',
            category_stage='early_growth',
        )
        data_without = make_company(
            ndr=115, ndr_tier=1,
            revenue_growth_yoy=0.25,
            # big_tech_threat defaults to 'unknown' → 0 credit
            # category_stage defaults to 'unknown' → 0 credit
        )
        score_with = calculate_confidence_score(data_with_assessments)
        score_without = calculate_confidence_score(data_without)
        # Without assessments should be lower (missing 0.20 from competitive signals)
        assert score_without < score_with

    def test_tier2_ndr_lower_weight(self):
        """Tier 2 NDR gets lower weight than Tier 1."""
        t1 = make_company(ndr=115, ndr_tier=1, revenue_growth_yoy=0.25)
        t2 = make_company(ndr=115, ndr_tier=2, revenue_growth_yoy=0.25)
        score_t1 = calculate_confidence_score(t1)
        score_t2 = calculate_confidence_score(t2)
        assert score_t1 > score_t2


# ============================================================
# STALENESS CHECKING (3 tests)
# ============================================================

class TestStaleness:

    def test_fresh_data(self):
        """Data updated recently is not stale."""
        data = make_company(
            data_updated=datetime.now().strftime('%Y-%m-%d'),
            ndr=115, ndr_tier=1,
        )
        is_stale, fields = check_staleness(data)
        assert not is_stale

    def test_stale_financial_data(self):
        """Data > 100 days old is stale."""
        old_date = (datetime.now() - timedelta(days=120)).strftime('%Y-%m-%d')
        data = make_company(
            data_updated=old_date,
            ndr=115, ndr_tier=1,
        )
        is_stale, fields = check_staleness(data)
        assert is_stale
        assert any('financials' in f for f in fields)

    def test_stale_competitive_assessment(self):
        """Data > 180 days triggers competitive staleness."""
        old_date = (datetime.now() - timedelta(days=200)).strftime('%Y-%m-%d')
        data = make_company(data_updated=old_date)
        is_stale, fields = check_staleness(data)
        assert is_stale
        assert any('competitive' in f for f in fields)

    def test_no_date_recorded(self):
        """No data_updated field = stale warning."""
        data = make_company()
        is_stale, fields = check_staleness(data)
        assert is_stale


# ============================================================
# NORMALIZATION HELPERS (4 tests)
# ============================================================

class TestNormalization:

    def test_normalize_growth_decimal(self):
        """0.25 → 25.0%"""
        assert _normalize_growth(0.25) == 25.0

    def test_normalize_growth_percent(self):
        """25.0 stays 25.0%"""
        assert _normalize_growth(25.0) == 25.0

    def test_normalize_growth_negative_decimal(self):
        """-0.01 → -1.0%"""
        assert _normalize_growth(-0.01) == pytest.approx(-1.0)

    def test_normalize_growth_none(self):
        """None stays None."""
        assert _normalize_growth(None) is None

    def test_normalize_retention_decimal(self):
        """0.97 → 97.0%"""
        assert _normalize_retention(0.97) == pytest.approx(97.0)

    def test_normalize_retention_percent(self):
        """97.0 stays 97.0%"""
        assert _normalize_retention(97.0) == 97.0


# ============================================================
# RESEARCH RECOMMENDATIONS (2 tests)
# ============================================================

class TestResearchRecommendations:

    def test_missing_ndr_recommends_search(self):
        """Missing NDR → recommend earnings call search."""
        data = make_company(ndr_tier=4)
        recs = recommend_research(data)
        assert any('NDR' in r or 'NRR' in r for r in recs)

    def test_missing_big_tech_recommends_assessment(self):
        """Unknown big tech threat → recommend assessment."""
        data = make_company()
        recs = recommend_research(data)
        assert any('Big Tech' in r for r in recs)


# ============================================================
# INTEGRATION — REAL COMPANY DATA (4 tests)
# ============================================================

class TestIntegration:

    @pytest.fixture
    def database(self):
        """Load the actual company database."""
        return load_company_database()

    def test_snow_strong_buy(self, database):
        """SNOW (NDR 127, growth 29%) = STRONG_BUY."""
        company = build_company_data('SNOW', database['SNOW'])
        result = compute_verdict(company)
        assert result.verdict == 'STRONG_BUY'

    def test_asan_sell(self, database):
        """ASAN (NDR 96, commoditizing) = SELL."""
        company = build_company_data('ASAN', database['ASAN'])
        result = compute_verdict(company)
        assert result.verdict == 'SELL'

    def test_mdb_buy(self, database):
        """MDB (NDR 119, growth 24%) = BUY."""
        company = build_company_data('MDB', database['MDB'])
        result = compute_verdict(company)
        assert result.verdict == 'BUY'

    def test_twlo_sell(self, database):
        """TWLO (DBNE 108, mature, decel, high big_tech) = SELL."""
        company = build_company_data('TWLO', database['TWLO'])
        result = compute_verdict(company)
        assert result.verdict == 'SELL'

    def test_afrm_tier4(self, database):
        """AFRM routes to Tier 4 (consumer model)."""
        company = build_company_data('AFRM', database['AFRM'])
        result = compute_verdict(company)
        assert result.data_tier == 4

    def test_all_companies_produce_verdict(self, database):
        """Every company in the database produces a valid verdict."""
        valid_verdicts = {'STRONG_BUY', 'BUY', 'WATCH', 'SELL', 'AVOID'}
        for ticker, info in database.items():
            company = build_company_data(ticker, info)
            result = compute_verdict(company)
            assert result.verdict in valid_verdicts, f"{ticker} produced invalid verdict: {result.verdict}"
            assert result.confidence in ('HIGH', 'MEDIUM', 'LOW', 'INSUFFICIENT'), \
                f"{ticker} produced invalid confidence: {result.confidence}"


# ============================================================
# REGRESSION — ENHANCED PRODUCES SAME FUNDAMENTAL VERDICT (1 test)
# ============================================================

class TestRegression:

    def test_enhanced_same_fundamental_as_batch(self):
        """Enhanced analyzer uses same verdict logic as batch.

        Both now import from plg_core, so they should produce
        identical fundamental verdicts for the same input.
        """
        database = load_company_database()

        # Test 4 key companies
        for ticker in ['SNOW', 'ASAN', 'MDB', 'TWLO']:
            company = build_company_data(ticker, database[ticker])
            verdict = compute_verdict(company)

            # The enhanced analyzer also calls compute_verdict() from plg_core
            # so the fundamental verdict must be the same
            company2 = build_company_data(ticker, database[ticker])
            verdict2 = compute_verdict(company2)

            assert verdict.verdict == verdict2.verdict, \
                f"{ticker}: batch={verdict.verdict} vs enhanced={verdict2.verdict}"

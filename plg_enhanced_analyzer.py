#!/usr/bin/env python3
"""
PLG Analysis - Enhanced with Valuation + Price Signals

Catches mispricings: Strong fundamentals + beaten down stock = opportunity

Key Insight: NDR/revenue growth are LAGGING indicators.
By the time they deteriorate, stock may have already fallen.
Use price action to identify:
1. Entry opportunities (good fundamentals, cheap stock)
2. Exit timing (weak fundamentals, expensive stock rallying)
3. Avoid traps (weak fundamentals, cheap stock = value trap)

Usage:
    python plg_enhanced_analyzer.py                # Analyze all companies
    python plg_enhanced_analyzer.py MDB SNOW       # Analyze specific tickers
"""

import yfinance as yf
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Dict, List
import sys

from plg_core import (
    CompanyData,
    VerdictResult,
    load_company_database,
    build_company_data,
    fetch_sec_edgar_data,
    compute_verdict,
    format_verdict,
    format_growth,
    _normalize_growth,
)


# ============================================================
# ENHANCED DATA STRUCTURES
# ============================================================

@dataclass
class PriceData:
    """Stock price and technical indicators."""
    current_price: Optional[float] = None
    week_52_high: Optional[float] = None
    week_52_low: Optional[float] = None
    pct_off_high: Optional[float] = None  # How far below 52w high
    ytd_return: Optional[float] = None
    return_3m: Optional[float] = None
    return_6m: Optional[float] = None

    # Valuation
    price_to_sales: Optional[float] = None
    forward_pe: Optional[float] = None

    # Technical
    rsi_14: Optional[float] = None  # Relative Strength Index
    sma_50: Optional[float] = None  # 50-day moving average
    sma_200: Optional[float] = None  # 200-day moving average
    above_sma_50: Optional[bool] = None
    above_sma_200: Optional[bool] = None


@dataclass
class ValuationSignal:
    """Valuation assessment relative to fundamentals."""
    valuation_tier: str  # cheap, fair, expensive, very_expensive
    opportunity_score: float  # 0-100, higher = better opportunity
    valuation_rationale: str
    timing_signal: str  # buy_now, wait_for_pullback, avoid


@dataclass
class EnhancedVerdict:
    """Verdict with valuation overlay."""
    fundamental_verdict: str  # From plg_core.compute_verdict()
    valuation_verdict: str  # Adjusted for price
    final_recommendation: str  # Combined recommendation
    confidence: str
    opportunity_score: float
    timing: str
    rationale: str


# ============================================================
# FETCH PRICE DATA
# ============================================================

def fetch_enhanced_price_data(ticker: str) -> PriceData:
    """Fetch comprehensive price and technical data."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1y")

        if hist.empty:
            return PriceData()

        current_price = hist['Close'].iloc[-1]
        week_52_high = hist['High'].max()
        week_52_low = hist['Low'].min()
        pct_off_high = ((current_price - week_52_high) / week_52_high) * 100

        # Returns - convert hist.index to timezone-naive for easier comparison
        hist.index = hist.index.tz_localize(None) if hist.index.tz is None else hist.index.tz_convert(None)

        ytd_start_date = datetime(datetime.now().year, 1, 1)
        ytd_hist = hist[hist.index >= ytd_start_date]
        ytd_return = None
        if not ytd_hist.empty:
            ytd_return = ((current_price - ytd_hist['Close'].iloc[0]) / ytd_hist['Close'].iloc[0]) * 100

        # 3m and 6m returns
        date_3m_ago = datetime.now() - timedelta(days=90)
        date_6m_ago = datetime.now() - timedelta(days=180)

        hist_3m = hist[hist.index >= date_3m_ago]
        hist_6m = hist[hist.index >= date_6m_ago]

        return_3m = None
        return_6m = None

        if not hist_3m.empty:
            return_3m = ((current_price - hist_3m['Close'].iloc[0]) / hist_3m['Close'].iloc[0]) * 100

        if not hist_6m.empty:
            return_6m = ((current_price - hist_6m['Close'].iloc[0]) / hist_6m['Close'].iloc[0]) * 100

        # Moving averages
        sma_50 = hist['Close'].tail(50).mean() if len(hist) >= 50 else None
        sma_200 = hist['Close'].tail(200).mean() if len(hist) >= 200 else None

        above_sma_50 = current_price > sma_50 if sma_50 else None
        above_sma_200 = current_price > sma_200 if sma_200 else None

        # RSI
        rsi_14 = calculate_rsi(hist['Close'], 14) if len(hist) >= 15 else None

        # Valuation
        info = stock.info
        price_to_sales = info.get('priceToSalesTrailing12Months')
        forward_pe = info.get('forwardPE')

        return PriceData(
            current_price=current_price,
            week_52_high=week_52_high,
            week_52_low=week_52_low,
            pct_off_high=pct_off_high,
            ytd_return=ytd_return,
            return_3m=return_3m,
            return_6m=return_6m,
            price_to_sales=price_to_sales,
            forward_pe=forward_pe,
            rsi_14=rsi_14,
            sma_50=sma_50,
            sma_200=sma_200,
            above_sma_50=above_sma_50,
            above_sma_200=above_sma_200,
        )

    except Exception as e:
        print(f"    Warning: Could not fetch enhanced price data: {e}")
        return PriceData()


def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index."""
    if len(prices) < period + 1:
        return None

    deltas = prices.diff()
    gains = deltas.where(deltas > 0, 0)
    losses = -deltas.where(deltas < 0, 0)

    avg_gain = gains.rolling(window=period).mean()
    avg_loss = losses.rolling(window=period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi.iloc[-1] if not rsi.empty else None


# ============================================================
# VALUATION ANALYSIS
# ============================================================

def analyze_valuation(
    fundamental_verdict: str,
    ndr: Optional[float],
    revenue_growth: Optional[float],
    price_data: PriceData,
    category_stage: str,
) -> ValuationSignal:
    """Analyze valuation to find mispricings.

    Logic:
    - Strong fundamentals + beaten down stock = BUY NOW (opportunity)
    - Strong fundamentals + expensive = WAIT FOR PULLBACK
    - Weak fundamentals + expensive = AVOID
    - Weak fundamentals + cheap = VALUE TRAP (still avoid)
    """

    # Default values if data missing
    if not price_data.price_to_sales or not revenue_growth:
        return ValuationSignal(
            valuation_tier='unknown',
            opportunity_score=50.0,
            valuation_rationale='Insufficient valuation data',
            timing_signal='monitor',
        )

    ps_ratio = price_data.price_to_sales
    growth_pct = _normalize_growth(revenue_growth) or 0

    # === DETERMINE VALUATION TIER ===

    valuation_tier = 'fair'

    if fundamental_verdict in ['STRONG_BUY', 'BUY']:
        # Strong fundamentals - what's appropriate P/S?
        if ndr and ndr >= 120 and growth_pct >= 30:
            # Elite tier - can justify 15-25x
            if ps_ratio > 25:
                valuation_tier = 'very_expensive'
            elif ps_ratio > 15:
                valuation_tier = 'expensive'
            elif ps_ratio > 10:
                valuation_tier = 'fair'
            else:
                valuation_tier = 'cheap'

        elif ndr and ndr >= 110 and growth_pct >= 20:
            # Good tier - can justify 10-15x
            if ps_ratio > 20:
                valuation_tier = 'very_expensive'
            elif ps_ratio > 15:
                valuation_tier = 'expensive'
            elif ps_ratio > 10:
                valuation_tier = 'fair'
            else:
                valuation_tier = 'cheap'

        else:
            # Lower tier - 10-15x is fair
            if ps_ratio > 15:
                valuation_tier = 'expensive'
            elif ps_ratio > 10:
                valuation_tier = 'fair'
            else:
                valuation_tier = 'cheap'

    else:
        # Weak fundamentals - discount required
        if ps_ratio > 12:
            valuation_tier = 'very_expensive'
        elif ps_ratio > 8:
            valuation_tier = 'expensive'
        elif ps_ratio > 5:
            valuation_tier = 'fair'
        else:
            valuation_tier = 'cheap'

    # === CALCULATE OPPORTUNITY SCORE (0-100) ===

    opportunity_score = 50.0  # Baseline

    # Factor 1: Fundamental strength (40 points)
    if fundamental_verdict == 'STRONG_BUY':
        opportunity_score += 20
    elif fundamental_verdict == 'BUY':
        opportunity_score += 15
    elif fundamental_verdict == 'WATCH':
        opportunity_score += 5
    elif fundamental_verdict == 'SELL':
        opportunity_score -= 15
    elif fundamental_verdict == 'AVOID':
        opportunity_score -= 20

    # Factor 2: Valuation (30 points)
    if valuation_tier == 'cheap':
        opportunity_score += 15
    elif valuation_tier == 'fair':
        opportunity_score += 5
    elif valuation_tier == 'expensive':
        opportunity_score -= 10
    elif valuation_tier == 'very_expensive':
        opportunity_score -= 20

    # Factor 3: Price momentum (20 points)
    if price_data.pct_off_high is not None:
        if price_data.pct_off_high < -30:  # >30% off highs
            if fundamental_verdict in ['STRONG_BUY', 'BUY']:
                opportunity_score += 15  # Mispricing!
            else:
                opportunity_score -= 5  # Falling knife
        elif price_data.pct_off_high < -15:  # >15% off highs
            if fundamental_verdict in ['STRONG_BUY', 'BUY']:
                opportunity_score += 10
            else:
                opportunity_score -= 3
        elif price_data.pct_off_high > -5:  # Near highs
            opportunity_score -= 10  # Expensive

    # Factor 4: Technical position (10 points)
    if price_data.rsi_14 is not None:
        if price_data.rsi_14 < 30:  # Oversold
            if fundamental_verdict in ['STRONG_BUY', 'BUY']:
                opportunity_score += 10
        elif price_data.rsi_14 > 70:  # Overbought
            opportunity_score -= 10

    # Cap at 0-100
    opportunity_score = max(0, min(100, opportunity_score))

    # === TIMING SIGNAL ===

    timing_signal = 'monitor'

    if fundamental_verdict in ['STRONG_BUY', 'BUY']:
        if valuation_tier in ['cheap', 'fair']:
            if price_data.pct_off_high and price_data.pct_off_high < -20:
                timing_signal = 'buy_now'
            elif price_data.rsi_14 and price_data.rsi_14 < 40:
                timing_signal = 'buy_now'
            else:
                timing_signal = 'accumulate'
        else:
            timing_signal = 'wait_for_pullback'

    elif fundamental_verdict == 'WATCH':
        if valuation_tier == 'cheap' and price_data.pct_off_high and price_data.pct_off_high < -25:
            timing_signal = 'monitor_closely'
        else:
            timing_signal = 'monitor'

    else:  # SELL or AVOID
        if price_data.return_3m and price_data.return_3m > 10:
            timing_signal = 'sell_rally'
        else:
            timing_signal = 'avoid'

    # === RATIONALE ===

    growth_str = f"{growth_pct:.0f}%" if growth_pct else "N/A"
    ps_str = f"{ps_ratio:.1f}x" if ps_ratio else "N/A"
    off_high_str = f"{price_data.pct_off_high:.0f}%" if price_data.pct_off_high else "N/A"

    rationale = f"P/S {ps_str} vs {growth_str} growth ({valuation_tier}). Stock {off_high_str} from 52w high."

    return ValuationSignal(
        valuation_tier=valuation_tier,
        opportunity_score=opportunity_score,
        valuation_rationale=rationale,
        timing_signal=timing_signal,
    )


def compute_enhanced_verdict(
    fundamental_verdict: str,
    confidence: str,
    valuation_signal: ValuationSignal,
    ndr: Optional[float],
    revenue_growth: Optional[float],
) -> EnhancedVerdict:
    """Combine fundamental verdict with valuation signal."""

    # === ADJUST VERDICT BASED ON VALUATION ===

    valuation_verdict = fundamental_verdict
    timing = valuation_signal.timing_signal

    # Upgrade if mispricing detected
    if fundamental_verdict == 'BUY' and valuation_signal.valuation_tier == 'cheap':
        if valuation_signal.opportunity_score >= 80:
            valuation_verdict = 'STRONG_BUY'
            timing = 'buy_now'

    # Downgrade if too expensive
    if fundamental_verdict in ['STRONG_BUY', 'BUY']:
        if valuation_signal.valuation_tier == 'very_expensive':
            valuation_verdict = 'WATCH'
            timing = 'wait_for_pullback'

    # Flag value traps
    if fundamental_verdict in ['SELL', 'AVOID']:
        if valuation_signal.valuation_tier == 'cheap':
            timing = 'value_trap'

    # === FINAL RECOMMENDATION ===

    if timing == 'buy_now':
        final_recommendation = f"{valuation_verdict} NOW"
    elif timing == 'accumulate':
        final_recommendation = f"{valuation_verdict} (Accumulate)"
    elif timing == 'wait_for_pullback':
        final_recommendation = f"{fundamental_verdict} (Wait for Pullback)"
    elif timing == 'monitor_closely':
        final_recommendation = "WATCH (Monitor for Entry)"
    elif timing == 'sell_rally':
        final_recommendation = "SELL (Exit on Rally)"
    elif timing == 'value_trap':
        final_recommendation = f"{fundamental_verdict} (Value Trap)"
    else:
        final_recommendation = valuation_verdict

    # === RATIONALE ===

    growth_pct = _normalize_growth(revenue_growth)
    growth_str = f"{growth_pct:.0f}%" if growth_pct else "N/A"
    ndr_str = f"NDR {ndr}%" if ndr else "NDR N/A"

    rationale = f"{ndr_str}, {growth_str} growth. {valuation_signal.valuation_rationale}"

    return EnhancedVerdict(
        fundamental_verdict=fundamental_verdict,
        valuation_verdict=valuation_verdict,
        final_recommendation=final_recommendation,
        confidence=confidence,
        opportunity_score=valuation_signal.opportunity_score,
        timing=timing,
        rationale=rationale,
    )


# ============================================================
# COMPANY ANALYSIS
# ============================================================

def analyze_company_enhanced(ticker: str, company_info: dict) -> dict:
    """Full analysis with valuation overlay.

    Uses plg_core.compute_verdict() for fundamental verdict,
    then layers valuation + price signals on top.
    """

    print(f"  Analyzing {ticker}...", end='', flush=True)

    # Fetch price data
    price_data = fetch_enhanced_price_data(ticker)

    # Build CompanyData and compute fundamental verdict via plg_core
    sec_data = fetch_sec_edgar_data(ticker, company_info.get('cik', ''))
    yf_data = {
        'current_price': price_data.current_price,
    }
    company = build_company_data(ticker, company_info, yf_data, sec_data)
    verdict_result = compute_verdict(company)

    fundamental_verdict = verdict_result.verdict
    confidence = verdict_result.confidence

    # Get normalized values for valuation analysis
    ndr = company.ndr
    revenue_growth = company.revenue_growth_yoy
    category_stage = company.category_stage

    # Valuation analysis
    valuation_signal = analyze_valuation(
        fundamental_verdict=fundamental_verdict,
        ndr=ndr,
        revenue_growth=revenue_growth,
        price_data=price_data,
        category_stage=category_stage,
    )

    # Enhanced verdict
    enhanced_verdict = compute_enhanced_verdict(
        fundamental_verdict=fundamental_verdict,
        confidence=confidence,
        valuation_signal=valuation_signal,
        ndr=ndr,
        revenue_growth=revenue_growth,
    )

    print(f" {enhanced_verdict.final_recommendation} (Score: {valuation_signal.opportunity_score:.0f})")

    growth_pct = _normalize_growth(revenue_growth)

    return {
        'ticker': ticker,
        'name': company_info.get('name', ticker),
        'fundamental_verdict': fundamental_verdict,
        'data_tier': verdict_result.data_tier,
        'valuation_verdict': enhanced_verdict.valuation_verdict,
        'final_recommendation': enhanced_verdict.final_recommendation,
        'opportunity_score': valuation_signal.opportunity_score,
        'confidence': confidence,
        'timing': valuation_signal.timing_signal,

        # Fundamentals
        'ndr': ndr,
        'revenue_growth_pct': growth_pct,

        # Valuation
        'price_to_sales': price_data.price_to_sales,
        'valuation_tier': valuation_signal.valuation_tier,

        # Price signals
        'current_price': price_data.current_price,
        'pct_off_52w_high': price_data.pct_off_high,
        'ytd_return': price_data.ytd_return,
        'return_3m': price_data.return_3m,
        'rsi_14': price_data.rsi_14,

        # Rationale
        'rationale': enhanced_verdict.rationale,
        'staleness_warning': verdict_result.staleness_warning,
        'research_recommendations': verdict_result.research_recommendations[:2],
    }


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    # Load company database from JSON
    database = load_company_database()

    # Parse command line args
    if len(sys.argv) > 1:
        tickers = [t.upper() for t in sys.argv[1:]]
        print(f"Analyzing specific tickers: {', '.join(tickers)}")
    else:
        tickers = list(database.keys())

    print("\n" + "="*70)
    print("ENHANCED PLG ANALYSIS - Valuation + Price Signals")
    print("="*70 + "\n")

    results = []

    for ticker in tickers:
        if ticker not in database:
            print(f"  {ticker}... SKIPPED (not in database)")
            continue
        try:
            result = analyze_company_enhanced(ticker, database[ticker])
            results.append(result)
        except Exception as e:
            print(f"  {ticker}... ERROR: {e}")
            continue

    # Print summary table
    print("\n" + "="*70)
    print("OPPORTUNITY RANKING")
    print("="*70 + "\n")

    # Sort by opportunity score
    results.sort(key=lambda x: x['opportunity_score'], reverse=True)

    print(f"{'Ticker':<8} {'Score':<7} {'Recommendation':<28} {'P/S':<7} {'vs 52w High':<12} {'Tier':<5}")
    print("-" * 70)

    for r in results:
        ps_str = f"{r['price_to_sales']:.1f}x" if r['price_to_sales'] else "N/A"
        off_high_str = f"{r['pct_off_52w_high']:.0f}%" if r['pct_off_52w_high'] else "N/A"

        print(f"{r['ticker']:<8} {r['opportunity_score']:<7.0f} {r['final_recommendation']:<28} {ps_str:<7} {off_high_str:<12} T{r['data_tier']}")

    print("\n" + "="*70)

    # Save results
    with open('enhanced_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)

    print(f"\nResults saved to enhanced_analysis.json")
    print(f"Analyzed {len(results)} companies\n")

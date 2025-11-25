#!/usr/bin/env python3
"""
PLG Analysis Prototype - Single Company Test
Testing data collection and verdict logic for MongoDB (MDB)
"""

import yfinance as yf
import requests
import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

# ============================================================
# DATA STRUCTURES
# ============================================================

@dataclass
class CompanyData:
    ticker: str
    name: str
    category: str
    business_model: str
    
    # Automated (from APIs)
    market_cap: Optional[float] = None
    revenue_ttm: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    current_price: Optional[float] = None
    
    # Semi-automated (from transcripts/manual)
    ndr: Optional[float] = None
    ndr_tier: int = 4  # 1=direct, 2=variant, 3=derived, 4=unavailable
    gross_retention: Optional[float] = None
    arr_millions: Optional[float] = None
    arr_growth_yoy: Optional[float] = None
    customers_100k_plus: Optional[int] = None
    
    # Manual assessment
    big_tech_threat: str = "medium"  # low, medium, medium_high, high, very_high
    category_stage: str = "mid_growth"  # emerging, early_growth, mid_growth, mature, commoditizing
    switching_cost: str = "medium"  # low, medium, high
    
    # Metadata
    data_as_of: str = ""
    notes: str = ""


@dataclass
class VerdictResult:
    verdict: str  # STRONG_BUY, BUY, WATCH, SELL, AVOID
    confidence: str  # HIGH, MEDIUM, LOW, INSUFFICIENT
    confidence_score: float  # 0.0 - 1.0
    rationale: str
    data_tier: int
    missing_signals: list
    entry_signals_met: int
    exit_signals_triggered: int


# ============================================================
# DATA FETCHING - AUTOMATED
# ============================================================

def fetch_yfinance_data(ticker: str) -> dict:
    """Fetch basic financials from Yahoo Finance (free)."""
    print(f"  Fetching Yahoo Finance data for {ticker}...")
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        return {
            'market_cap': info.get('marketCap'),
            'revenue_ttm': info.get('totalRevenue'),
            'revenue_growth_yoy': info.get('revenueGrowth'),  # as decimal
            'gross_margin': info.get('grossMargins'),  # as decimal
            'operating_margin': info.get('operatingMargins'),  # as decimal
            'current_price': info.get('currentPrice'),
            'name': info.get('longName'),
            'sector': info.get('sector'),
            'industry': info.get('industry'),
        }
    except Exception as e:
        print(f"  Error fetching yfinance data: {e}")
        return {}


def fetch_sec_edgar_data(cik: str) -> dict:
    """Fetch company facts from SEC EDGAR (free, no API key)."""
    print(f"  Fetching SEC EDGAR data for CIK {cik}...")
    
    try:
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
        headers = {"User-Agent": "PLGAnalysis test@example.com"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract recent revenue
            revenues = []
            try:
                rev_data = data['facts']['us-gaap']['RevenueFromContractWithCustomerExcludingAssessedTax']['units']['USD']
                # Get quarterly data
                quarterly = [r for r in rev_data if r.get('form') == '10-Q']
                revenues = sorted(quarterly, key=lambda x: x.get('end', ''), reverse=True)[:8]
            except KeyError:
                pass
            
            return {
                'entity_name': data.get('entityName'),
                'recent_revenues': revenues,
            }
        else:
            print(f"  SEC EDGAR returned status {response.status_code}")
            return {}
            
    except Exception as e:
        print(f"  Error fetching SEC EDGAR data: {e}")
        return {}


# ============================================================
# MANUAL DATA INPUT (simulating transcript extraction)
# ============================================================

def get_manual_saas_metrics(ticker: str) -> dict:
    """
    Manual input of SaaS metrics from earnings calls.
    In production, this would come from transcript parsing or manual entry.
    
    Data sourced from MongoDB Q2 FY2026 earnings (Sep 2025).
    """
    
    # MongoDB (MDB) - Q2 FY2026 data from your project documents
    manual_data = {
        'MDB': {
            'ndr': 119,  # Directly disclosed
            'ndr_tier': 1,
            'ndr_source': 'Q2 FY2026 earnings call',
            'gross_retention': None,  # Not disclosed
            'arr_millions': None,  # MongoDB reports revenue, not ARR
            'arr_growth_yoy': None,
            'customers_100k_plus': None,  # Not in your docs
            'revenue_growth_yoy': 0.24,  # 24% from your analysis
            'atlas_growth_yoy': 0.29,  # 29% cloud growth
            'notes': 'Atlas (cloud) is 74% of revenue, growing 29%. NDR of 119% is strong.',
            
            # Manual assessments from your thesis
            'big_tech_threat': 'medium',  # AWS DocumentDB exists but multi-cloud positioning helps
            'category_stage': 'early_growth',  # NoSQL + AI database TAM expanding
            'switching_cost': 'high',  # Deep data integration, query language lock-in
        }
    }
    
    return manual_data.get(ticker, {})


# ============================================================
# VERDICT CALCULATION
# ============================================================

def calculate_confidence_score(data: CompanyData) -> float:
    """Calculate confidence score based on data availability."""
    
    weights = {
        'ndr_tier_1': 0.25,
        'ndr_tier_2': 0.15,
        'ndr_tier_3': 0.08,
        'revenue_growth': 0.20,
        'gross_retention': 0.10,
        'big_tech_assessed': 0.10,
        'category_assessed': 0.10,
        'customers_100k': 0.05,
    }
    
    score = 0.0
    
    # NDR contribution
    if data.ndr is not None:
        if data.ndr_tier == 1:
            score += weights['ndr_tier_1']
        elif data.ndr_tier == 2:
            score += weights['ndr_tier_2']
        elif data.ndr_tier == 3:
            score += weights['ndr_tier_3']
    
    # Revenue growth
    if data.revenue_growth_yoy is not None:
        score += weights['revenue_growth']
    
    # Gross retention
    if data.gross_retention is not None:
        score += weights['gross_retention']
    
    # Competitive assessments (always count if set)
    if data.big_tech_threat != "medium":  # Non-default
        score += weights['big_tech_assessed']
    else:
        score += weights['big_tech_assessed'] * 0.5  # Partial credit for default
    
    if data.category_stage != "mid_growth":  # Non-default
        score += weights['category_assessed']
    else:
        score += weights['category_assessed'] * 0.5
    
    # Customer counts
    if data.customers_100k_plus is not None:
        score += weights['customers_100k']
    
    return score


def score_to_confidence(score: float) -> str:
    """Convert numeric score to confidence level."""
    if score >= 0.70:
        return 'HIGH'
    elif score >= 0.45:
        return 'MEDIUM'
    elif score >= 0.25:
        return 'LOW'
    else:
        return 'INSUFFICIENT'


def compute_verdict(data: CompanyData) -> VerdictResult:
    """Apply PLG thesis logic to generate verdict."""
    
    missing = []
    
    # Calculate confidence
    confidence_score = calculate_confidence_score(data)
    confidence = score_to_confidence(confidence_score)
    
    # ---- EXIT SIGNALS ----
    exit_signals = 0
    exit_reasons = []
    
    # NDR below 110 for 2+ quarters
    if data.ndr is not None and data.ndr < 110:
        exit_signals += 1
        exit_reasons.append(f"NDR {data.ndr}% below 110% threshold")
    
    # Revenue deceleration (would need historical data)
    # Skipping for now - need time series
    
    # Category commoditizing
    if data.category_stage == 'commoditizing':
        exit_signals += 1
        exit_reasons.append("Category commoditizing")
    
    if data.category_stage == 'mature':
        exit_signals += 0.5  # Partial signal
        exit_reasons.append("Category mature (warning)")
    
    # Big Tech threat
    if data.big_tech_threat in ['high', 'very_high']:
        exit_signals += 0.5
        exit_reasons.append(f"Big Tech threat: {data.big_tech_threat}")
    
    # ---- ENTRY SIGNALS ----
    entry_signals = 0
    entry_details = []
    
    # NDR > 110
    if data.ndr is not None:
        if data.ndr >= 110:
            entry_signals += 1
            entry_details.append(f"NDR {data.ndr}% ≥ 110%")
        if data.ndr >= 120:
            entry_details.append("(Elite NDR ≥ 120%)")
    else:
        missing.append("NDR not available")
    
    # Revenue growth > 25%
    if data.revenue_growth_yoy is not None:
        growth_pct = data.revenue_growth_yoy * 100 if data.revenue_growth_yoy < 1 else data.revenue_growth_yoy
        if growth_pct >= 25:
            entry_signals += 1
            entry_details.append(f"Revenue growth {growth_pct:.0f}% ≥ 25%")
        elif growth_pct >= 20:
            entry_signals += 0.5
            entry_details.append(f"Revenue growth {growth_pct:.0f}% (close to 25%)")
    else:
        missing.append("Revenue growth not available")
    
    # Category expanding
    if data.category_stage in ['emerging', 'early_growth']:
        entry_signals += 1
        entry_details.append(f"Category stage: {data.category_stage}")
    elif data.category_stage == 'mid_growth':
        entry_signals += 0.5
        entry_details.append(f"Category stage: {data.category_stage} (partial)")
    
    # No Big Tech bundling
    if data.big_tech_threat in ['low', 'medium']:
        entry_signals += 1
        entry_details.append(f"Big Tech threat: {data.big_tech_threat}")
    
    # High switching costs
    if data.switching_cost == 'high':
        entry_signals += 1
        entry_details.append("High switching costs")
    elif data.switching_cost == 'medium':
        entry_signals += 0.5
        entry_details.append("Medium switching costs")
    
    # ---- DETERMINE VERDICT ----
    
    # Exit signals take priority
    if exit_signals >= 2:
        verdict = "SELL"
        rationale = f"Exit signals triggered: {'; '.join(exit_reasons)}"
    elif exit_signals >= 1:
        verdict = "WATCH"
        rationale = f"Warning signals: {'; '.join(exit_reasons)}"
    # Entry signals
    elif data.ndr is not None and data.ndr >= 120 and entry_signals >= 4:
        verdict = "STRONG_BUY"
        rationale = f"Elite NDR + {entry_signals:.1f}/5 entry signals: {'; '.join(entry_details)}"
    elif entry_signals >= 4:
        verdict = "BUY"
        rationale = f"{entry_signals:.1f}/5 entry signals: {'; '.join(entry_details)}"
    elif entry_signals >= 3:
        verdict = "WATCH"
        rationale = f"Only {entry_signals:.1f}/5 entry signals: {'; '.join(entry_details)}"
    else:
        verdict = "AVOID"
        rationale = f"Only {entry_signals:.1f}/5 entry signals met"
    
    return VerdictResult(
        verdict=verdict,
        confidence=confidence,
        confidence_score=confidence_score,
        rationale=rationale,
        data_tier=data.ndr_tier,
        missing_signals=missing,
        entry_signals_met=int(entry_signals),
        exit_signals_triggered=int(exit_signals),
    )


# ============================================================
# MAIN ANALYSIS
# ============================================================

def analyze_company(ticker: str, cik: str) -> tuple[CompanyData, VerdictResult]:
    """Run full analysis pipeline for a single company."""
    
    print(f"\n{'='*60}")
    print(f"ANALYZING: {ticker}")
    print(f"{'='*60}")
    
    # Step 1: Fetch automated data
    print("\n[1/3] Fetching automated data...")
    yf_data = fetch_yfinance_data(ticker)
    sec_data = fetch_sec_edgar_data(cik)
    
    # Step 2: Get manual/transcript data
    print("\n[2/3] Loading manual SaaS metrics...")
    manual_data = get_manual_saas_metrics(ticker)
    
    # Step 3: Combine into CompanyData
    print("\n[3/3] Combining data and computing verdict...")
    
    company = CompanyData(
        ticker=ticker,
        name=yf_data.get('name', ticker),
        category='developer_tools',
        business_model='b2b_saas',
        
        # Automated
        market_cap=yf_data.get('market_cap'),
        revenue_ttm=yf_data.get('revenue_ttm'),
        revenue_growth_yoy=manual_data.get('revenue_growth_yoy') or yf_data.get('revenue_growth_yoy'),
        gross_margin=yf_data.get('gross_margin'),
        operating_margin=yf_data.get('operating_margin'),
        current_price=yf_data.get('current_price'),
        
        # Manual
        ndr=manual_data.get('ndr'),
        ndr_tier=manual_data.get('ndr_tier', 4),
        gross_retention=manual_data.get('gross_retention'),
        arr_millions=manual_data.get('arr_millions'),
        arr_growth_yoy=manual_data.get('arr_growth_yoy'),
        customers_100k_plus=manual_data.get('customers_100k_plus'),
        
        # Assessments
        big_tech_threat=manual_data.get('big_tech_threat', 'medium'),
        category_stage=manual_data.get('category_stage', 'mid_growth'),
        switching_cost=manual_data.get('switching_cost', 'medium'),
        
        # Metadata
        data_as_of=datetime.now().strftime('%Y-%m-%d'),
        notes=manual_data.get('notes', ''),
    )
    
    # Compute verdict
    verdict = compute_verdict(company)
    
    return company, verdict


def print_results(company: CompanyData, verdict: VerdictResult):
    """Pretty print analysis results."""
    
    # Format helpers
    def fmt_pct(val):
        if val is None:
            return "N/A"
        if val < 1:
            return f"{val*100:.1f}%"
        return f"{val:.1f}%"
    
    def fmt_num(val, suffix=''):
        if val is None:
            return "N/A"
        if val >= 1e9:
            return f"${val/1e9:.2f}B{suffix}"
        if val >= 1e6:
            return f"${val/1e6:.0f}M{suffix}"
        return f"${val:,.0f}{suffix}"
    
    # Verdict emoji
    verdict_emoji = {
        'STRONG_BUY': '🟢🟢',
        'BUY': '🟢',
        'WATCH': '🟡',
        'SELL': '🔴',
        'AVOID': '🔴',
    }
    
    confidence_emoji = {
        'HIGH': '🟢',
        'MEDIUM': '🟡',
        'LOW': '🟠',
        'INSUFFICIENT': '🔴',
    }
    
    print(f"\n{'='*60}")
    print(f"RESULTS: {company.ticker} ({company.name})")
    print(f"{'='*60}")
    
    print(f"\n📊 VERDICT: {verdict_emoji.get(verdict.verdict, '')} {verdict.verdict}")
    print(f"   Confidence: {confidence_emoji.get(verdict.confidence, '')} {verdict.confidence} ({verdict.confidence_score:.0%})")
    print(f"   Data Tier: {verdict.data_tier}")
    print(f"   Entry Signals: {verdict.entry_signals_met}/5")
    print(f"   Exit Signals: {verdict.exit_signals_triggered}")
    print(f"\n   Rationale: {verdict.rationale}")
    
    if verdict.missing_signals:
        print(f"\n   ⚠️ Missing: {', '.join(verdict.missing_signals)}")
    
    print(f"\n📈 KEY METRICS")
    print(f"   Market Cap:     {fmt_num(company.market_cap)}")
    print(f"   Revenue (TTM):  {fmt_num(company.revenue_ttm)}")
    print(f"   Revenue Growth: {fmt_pct(company.revenue_growth_yoy)}")
    print(f"   Gross Margin:   {fmt_pct(company.gross_margin)}")
    print(f"   Op. Margin:     {fmt_pct(company.operating_margin)}")
    
    print(f"\n🎯 SAAS METRICS (Tier {company.ndr_tier})")
    print(f"   NDR:            {company.ndr}%" if company.ndr else "   NDR:            N/A")
    print(f"   Gross Ret.:     {company.gross_retention}%" if company.gross_retention else "   Gross Ret.:     N/A")
    print(f"   ARR:            {fmt_num(company.arr_millions * 1e6) if company.arr_millions else 'N/A'}")
    print(f"   Customers $100K+: {company.customers_100k_plus or 'N/A'}")
    
    print(f"\n🛡️ COMPETITIVE POSITION")
    print(f"   Big Tech Threat: {company.big_tech_threat}")
    print(f"   Category Stage:  {company.category_stage}")
    print(f"   Switching Cost:  {company.switching_cost}")
    
    if company.notes:
        print(f"\n📝 Notes: {company.notes}")
    
    print(f"\n   Data as of: {company.data_as_of}")
    print(f"{'='*60}\n")


# ============================================================
# RUN ANALYSIS
# ============================================================

if __name__ == "__main__":
    # MongoDB
    # CIK: 0001441816
    
    company, verdict = analyze_company("MDB", "1441816")
    print_results(company, verdict)
    
    # Save results to JSON
    results = {
        "ticker": company.ticker,
        "name": company.name,
        "verdict": verdict.verdict,
        "confidence": verdict.confidence,
        "confidence_score": verdict.confidence_score,
        "data_tier": verdict.data_tier,
        "rationale": verdict.rationale,
        "metrics": {
            "market_cap": company.market_cap,
            "revenue_ttm": company.revenue_ttm,
            "revenue_growth_yoy": company.revenue_growth_yoy,
            "ndr": company.ndr,
            "gross_margin": company.gross_margin,
        },
        "assessments": {
            "big_tech_threat": company.big_tech_threat,
            "category_stage": company.category_stage,
            "switching_cost": company.switching_cost,
        },
        "analyzed_at": datetime.now().isoformat(),
    }
    
    with open('mdb_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    print("\n✅ Results saved to mdb_analysis.json")

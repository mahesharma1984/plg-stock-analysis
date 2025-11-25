#!/usr/bin/env python3
"""
PLG Analysis - Batch Analyzer
Analyzes all 40 companies from the PLG investment thesis
"""

import yfinance as yf
import json
import csv
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, List, Dict
import sys

# Import core logic from prototype
@dataclass
class CompanyData:
    ticker: str
    name: str
    category: str
    business_model: str
    
    # Automated
    market_cap: Optional[float] = None
    revenue_ttm: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    current_price: Optional[float] = None
    
    # Manual SaaS metrics
    ndr: Optional[float] = None
    ndr_tier: int = 4
    gross_retention: Optional[float] = None
    arr_millions: Optional[float] = None
    customers_100k_plus: Optional[int] = None
    
    # Assessments
    big_tech_threat: str = "medium"
    category_stage: str = "mid_growth"
    switching_cost: str = "medium"
    
    # Metadata
    cik: str = ""
    data_as_of: str = ""
    notes: str = ""


@dataclass
class VerdictResult:
    verdict: str
    confidence: str
    confidence_score: float
    rationale: str
    data_tier: int
    missing_signals: list
    entry_signals_met: int
    exit_signals_triggered: int


# ============================================================
# COMPANY DATABASE - All 40 companies from project docs
# ============================================================

COMPANY_DATABASE = {
    # === STRONG (Early Growth) - NDR >110%, Revenue >20% ===
    'RBRK': {
        'name': 'Rubrik',
        'cik': '1658919',
        'category': 'security',
        'business_model': 'b2b_saas',
        'ndr': 120,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.47,
        'big_tech_threat': 'low',
        'category_stage': 'early_growth',
        'switching_cost': 'high',
        'notes': '2024 IPO. Cyber resilience category expanding. 47% growth.',
    },
    
    'NET': {
        'name': 'Cloudflare',
        'cik': '1477333',
        'category': 'infrastructure',
        'business_model': 'b2b_saas',
        'ndr': 114,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.28,
        'big_tech_threat': 'medium',
        'category_stage': 'early_growth',
        'switching_cost': 'high',
        'notes': 'Edge computing TAM exploding. AI workloads at edge. Multi-cloud neutral.',
    },
    
    'MDB': {
        'name': 'MongoDB',
        'cik': '1441816',
        'category': 'developer_tools',
        'business_model': 'b2b_saas',
        'ndr': 119,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.24,
        'customers_100k_plus': 2800,
        'big_tech_threat': 'medium',
        'category_stage': 'early_growth',
        'switching_cost': 'high',
        'notes': 'Atlas (cloud) 74% of revenue, growing 29%. AI database demand strong.',
    },
    
    'SNOW': {
        'name': 'Snowflake',
        'cik': '1640147',
        'category': 'infrastructure',
        'business_model': 'b2b_saas',
        'ndr': 127,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.29,
        'big_tech_threat': 'medium',
        'category_stage': 'early_growth',
        'switching_cost': 'high',
        'notes': 'Elite NDR. Multi-cloud data platform. AI/ML workloads expanding TAM.',
    },
    
    'DDOG': {
        'name': 'Datadog',
        'cik': '1561550',
        'category': 'observability',
        'business_model': 'b2b_saas',
        'ndr': 120,
        'ndr_tier': 2,  # Approximate
        'revenue_growth_yoy': 0.28,
        'big_tech_threat': 'medium',
        'category_stage': 'early_growth',
        'switching_cost': 'high',
        'notes': 'Observability leader. Multi-cloud moat. AI workloads driving growth.',
    },
    
    'CRWD': {
        'name': 'CrowdStrike',
        'cik': '1535527',
        'category': 'security',
        'business_model': 'b2b_saas',
        'ndr': 112,
        'ndr_tier': 1,
        'gross_retention': 0.97,
        'revenue_growth_yoy': 0.21,
        'arr_millions': 4660,
        'big_tech_threat': 'medium_high',
        'category_stage': 'early_growth',
        'switching_cost': 'high',
        'notes': 'Recovering from July 2024 outage. Platform consolidation trend favors comprehensive vendors.',
    },
    
    'ZS': {
        'name': 'Zscaler',
        'cik': '1713683',
        'category': 'security',
        'business_model': 'b2b_saas',
        'ndr': None,
        'ndr_tier': 4,
        'revenue_growth_yoy': 0.22,
        'arr_millions': 3015,
        'big_tech_threat': 'medium',
        'category_stage': 'early_growth',
        'switching_cost': 'high',
        'notes': 'Zero Trust category still expanding. 22% ARR growth stable.',
    },
    
    'IOT': {
        'name': 'Samsara',
        'cik': '1720635',
        'category': 'vertical_saas',
        'business_model': 'b2b_saas',
        'ndr': None,
        'ndr_tier': 4,
        'revenue_growth_yoy': 0.30,
        'arr_millions': 1600,
        'big_tech_threat': 'low',
        'category_stage': 'early_growth',
        'switching_cost': 'high',
        'notes': 'Highest growth in cohort at 30%. IoT/connected operations TAM expanding rapidly.',
    },
    
    'CFLT': {
        'name': 'Confluent',
        'cik': '1699838',
        'category': 'developer_tools',
        'business_model': 'b2b_saas',
        'ndr': 114,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.19,
        'customers_100k_plus': 1487,
        'big_tech_threat': 'medium_high',
        'category_stage': 'early_growth',
        'switching_cost': 'high',
        'notes': 'Event streaming/Kafka. Cloud 24% growth. Flink momentum creating differentiation.',
    },
    
    'DT': {
        'name': 'Dynatrace',
        'cik': '1773383',
        'category': 'observability',
        'business_model': 'b2b_saas',
        'ndr': 111,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.19,
        'arr_millions': 1822,
        'big_tech_threat': 'medium',
        'category_stage': 'mid_growth',
        'switching_cost': 'high',
        'notes': 'Profitable growth. 29% operating margin. Observability + AI monitoring.',
    },
    
    'FROG': {
        'name': 'JFrog',
        'cik': '1773027',
        'category': 'developer_tools',
        'business_model': 'b2b_saas',
        'ndr': 115,
        'ndr_tier': 2,  # "Mid-teens" disclosed
        'revenue_growth_yoy': 0.23,
        'big_tech_threat': 'medium',
        'category_stage': 'early_growth',
        'switching_cost': 'high',
        'notes': 'DevOps/software supply chain. Cloud 38% growth. Infrastructure moat.',
    },
    
    # === TRANSITIONAL - NDR 100-110%, growth slowing ===
    
    'BRZE': {
        'name': 'Braze',
        'cik': '1787142',
        'category': 'marketing',
        'business_model': 'b2b_saas',
        'ndr': 111,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.26,
        'big_tech_threat': 'high',
        'category_stage': 'mid_growth',
        'switching_cost': 'medium',
        'notes': 'NDR declining (117% → 111%). Facing Salesforce/Adobe competition.',
    },
    
    'OKTA': {
        'name': 'Okta',
        'cik': '1660134',
        'category': 'security',
        'business_model': 'b2b_saas',
        'ndr': None,
        'ndr_tier': 4,
        'revenue_growth_yoy': 0.14,
        'big_tech_threat': 'very_high',
        'category_stage': 'mid_growth',
        'switching_cost': 'medium',
        'notes': 'Growth slowing 15% → 10%. Microsoft Entra/Azure AD bundling threat.',
    },
    
    'FRSH': {
        'name': 'Freshworks',
        'cik': '1783431',
        'category': 'collaboration',
        'business_model': 'b2b_saas',
        'ndr': 105,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.14,
        'big_tech_threat': 'high',
        'category_stage': 'mid_growth',
        'switching_cost': 'low',
        'notes': 'Growth slowing 18% → 14%. SMB/mid-market CRM highly competitive.',
    },
    
    'TWLO': {
        'name': 'Twilio',
        'cik': '1447669',
        'category': 'collaboration',
        'business_model': 'b2b_saas',
        'ndr': 108,
        'ndr_tier': 2,  # DBNE variant
        'revenue_growth_yoy': 0.09,
        'big_tech_threat': 'high',
        'category_stage': 'mature',
        'switching_cost': 'medium',
        'notes': 'DBNE 108%. Growth slowing 13% → 9%. Communications APIs commoditizing.',
    },
    
    'PCOR': {
        'name': 'Procore',
        'cik': '1687426',
        'category': 'vertical_saas',
        'business_model': 'b2b_saas',
        'ndr': 106,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.11,
        'big_tech_threat': 'low',
        'category_stage': 'mid_growth',
        'switching_cost': 'high',
        'notes': 'NDR 106%, growth decelerating to 11-13%. Vertical SaaS moat but TAM limited.',
    },
    
    # === MATURE/COMMODITIZING - NDR <100%, growth <10% ===
    
    'ASAN': {
        'name': 'Asana',
        'cik': '1477720',
        'category': 'collaboration',
        'business_model': 'b2b_saas',
        'ndr': 96,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.10,
        'big_tech_threat': 'very_high',
        'category_stage': 'commoditizing',
        'switching_cost': 'low',
        'notes': 'CLASSIC COMMODITIZATION. NDR below 100%. Microsoft Teams/Planner bundling.',
    },
    
    'ZI': {
        'name': 'ZoomInfo',
        'cik': '1794515',
        'category': 'marketing',
        'business_model': 'b2b_saas',
        'ndr': 87,
        'ndr_tier': 1,
        'revenue_growth_yoy': -0.01,
        'big_tech_threat': 'very_high',
        'category_stage': 'commoditizing',
        'switching_cost': 'low',
        'notes': 'DEATH SPIRAL. Revenue declining -1%. LinkedIn Sales Navigator commoditized category.',
    },
    
    'DOCU': {
        'name': 'DocuSign',
        'cik': '1261333',
        'category': 'collaboration',
        'business_model': 'b2b_saas',
        'ndr': 102,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.07,
        'big_tech_threat': 'very_high',
        'category_stage': 'mature',
        'switching_cost': 'low',
        'notes': 'E-signature solved. Adobe/Microsoft/Google all offer. 7% growth.',
    },
    
    'BILL': {
        'name': 'Bill.com',
        'cik': '1792789',
        'category': 'fintech',
        'business_model': 'b2b_saas',
        'ndr': 92,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.09,
        'big_tech_threat': 'high',
        'category_stage': 'mature',
        'switching_cost': 'medium',
        'notes': 'NDR collapsed 111% → 92%. Intuit QuickBooks bundling threat.',
    },
    
    'PATH': {
        'name': 'UiPath',
        'cik': '1842749',
        'category': 'automation',
        'business_model': 'b2b_saas',
        'ndr': 108,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.11,
        'big_tech_threat': 'very_high',
        'category_stage': 'mature',
        'switching_cost': 'medium',
        'notes': 'RPA commoditizing. Microsoft Power Automate bundling. Growth 24% → 11%.',
    },
    
    'ZM': {
        'name': 'Zoom',
        'cik': '1585521',
        'category': 'collaboration',
        'business_model': 'b2b_saas',
        'ndr': None,
        'ndr_tier': 4,
        'revenue_growth_yoy': 0.03,
        'big_tech_threat': 'very_high',
        'category_stage': 'commoditizing',
        'switching_cost': 'low',
        'notes': 'Classic example. Video conferencing commoditized. Microsoft Teams destroyed pricing power.',
    },
    
    'DBX': {
        'name': 'Dropbox',
        'cik': '1467623',
        'category': 'collaboration',
        'business_model': 'b2b_saas',
        'ndr': None,
        'ndr_tier': 4,
        'revenue_growth_yoy': -0.01,
        'big_tech_threat': 'very_high',
        'category_stage': 'commoditizing',
        'switching_cost': 'low',
        'notes': 'File sync commoditized. Google Drive/OneDrive free alternatives.',
    },
    
    # === Consumer/Non-traditional PLG ===
    
    'AFRM': {
        'name': 'Affirm',
        'cik': '1820953',
        'category': 'fintech',
        'business_model': 'consumer',
        'ndr': None,
        'ndr_tier': 4,
        'revenue_growth_yoy': 0.38,
        'big_tech_threat': 'medium_high',
        'category_stage': 'early_growth',
        'switching_cost': 'low',
        'notes': 'BNPL strong growth but Big Tech can easily bundle (Apple Pay Later risk).',
    },
    
    'SQ': {
        'name': 'Block',
        'cik': '1512673',
        'category': 'fintech',
        'business_model': 'transaction_based',
        'ndr': None,
        'ndr_tier': 4,
        'revenue_growth_yoy': 0.10,
        'big_tech_threat': 'high',
        'category_stage': 'mature',
        'switching_cost': 'low',
        'notes': 'Payments commoditized. Not traditional PLG. 10% growth.',
    },
    
    'TOST': {
        'name': 'Toast',
        'cik': '1650164',
        'category': 'vertical_saas',
        'business_model': 'b2b_saas',
        'ndr': None,
        'ndr_tier': 4,
        'revenue_growth_yoy': 0.25,
        'arr_millions': 1900,
        'big_tech_threat': 'low',
        'category_stage': 'mid_growth',
        'switching_cost': 'high',
        'notes': 'Vertical SaaS scale + profitability. 35% EBITDA margin. Still early penetration.',
    },
    
    'S': {
        'name': 'SentinelOne',
        'cik': '1805284',
        'category': 'security',
        'business_model': 'b2b_saas',
        'ndr': None,
        'ndr_tier': 4,
        'revenue_growth_yoy': 0.28,
        'arr_millions': 860,
        'big_tech_threat': 'medium_high',
        'category_stage': 'early_growth',
        'switching_cost': 'high',
        'notes': 'NDR not disclosed. Strong 28% growth. Microsoft Defender bundling threat.',
    },
    
    # Additional companies from universe
    
    'MNDY': {
        'name': 'Monday.com',
        'cik': '1845338',
        'category': 'collaboration',
        'business_model': 'b2b_saas',
        'ndr': 111,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.27,
        'big_tech_threat': 'very_high',
        'category_stage': 'mid_growth',
        'switching_cost': 'medium',
        'notes': 'NDR at minimum threshold. Microsoft can bundle (Teams/Loop). At risk.',
    },
    
    'SHOP': {
        'name': 'Shopify',
        'cik': '1594805',
        'category': 'infrastructure',
        'business_model': 'b2b_saas',
        'ndr': 100,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.31,
        'big_tech_threat': 'medium',
        'category_stage': 'mid_growth',
        'switching_cost': 'high',
        'notes': 'Strong 31% growth but NDR only 100%. E-commerce platform, different dynamics.',
    },
    
    'TEAM': {
        'name': 'Atlassian',
        'cik': '1650372',
        'category': 'collaboration',
        'business_model': 'b2b_saas',
        'ndr': None,
        'ndr_tier': 4,
        'revenue_growth_yoy': 0.21,
        'big_tech_threat': 'medium',
        'category_stage': 'mid_growth',
        'switching_cost': 'high',
        'notes': 'Jira/Confluence sticky but becoming internal infrastructure rather than growth drivers.',
    },
    
    'GTLB': {
        'name': 'GitLab',
        'cik': '1653482',
        'category': 'developer_tools',
        'business_model': 'b2b_saas',
        'ndr': None,
        'ndr_tier': 4,
        'revenue_growth_yoy': 0.30,
        'big_tech_threat': 'medium_high',
        'category_stage': 'early_growth',
        'switching_cost': 'high',
        'notes': 'DevOps platform. GitHub (Microsoft) is main competitor. Strong growth.',
    },
    
    'ESTC': {
        'name': 'Elastic',
        'cik': '1707753',
        'category': 'observability',
        'business_model': 'b2b_saas',
        'ndr': None,
        'ndr_tier': 4,
        'revenue_growth_yoy': 0.18,
        'big_tech_threat': 'high',
        'category_stage': 'mid_growth',
        'switching_cost': 'medium',
        'notes': 'Search & observability. Competing with AWS OpenSearch.',
    },
    
    'DOCN': {
        'name': 'DigitalOcean',
        'cik': '1582961',
        'category': 'infrastructure',
        'business_model': 'b2b_saas',
        'ndr': 100,
        'ndr_tier': 1,
        'revenue_growth_yoy': 0.14,
        'big_tech_threat': 'very_high',
        'category_stage': 'mature',
        'switching_cost': 'medium',
        'notes': 'NDR just hit 100% from below. Cloud infrastructure commoditizing.',
    },
}


# ============================================================
# BATCH ANALYSIS FUNCTIONS
# ============================================================

def fetch_yfinance_data(ticker: str) -> dict:
    """Fetch live data from Yahoo Finance."""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        return {
            'market_cap': info.get('marketCap'),
            'revenue_ttm': info.get('totalRevenue'),
            'revenue_growth_yoy': info.get('revenueGrowth'),
            'gross_margin': info.get('grossMargins'),
            'operating_margin': info.get('operatingMargins'),
            'current_price': info.get('currentPrice'),
        }
    except Exception as e:
        print(f"    Warning: Could not fetch Yahoo Finance data: {e}")
        return {}


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
    
    if data.ndr is not None:
        if data.ndr_tier == 1:
            score += weights['ndr_tier_1']
        elif data.ndr_tier == 2:
            score += weights['ndr_tier_2']
        elif data.ndr_tier == 3:
            score += weights['ndr_tier_3']
    
    if data.revenue_growth_yoy is not None:
        score += weights['revenue_growth']
    
    if data.gross_retention is not None:
        score += weights['gross_retention']
    
    if data.big_tech_threat != "medium":
        score += weights['big_tech_assessed']
    else:
        score += weights['big_tech_assessed'] * 0.5
    
    if data.category_stage != "mid_growth":
        score += weights['category_assessed']
    else:
        score += weights['category_assessed'] * 0.5
    
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
    """Apply PLG thesis logic."""
    missing = []
    
    confidence_score = calculate_confidence_score(data)
    confidence = score_to_confidence(confidence_score)
    
    # Exit signals
    exit_signals = 0
    exit_reasons = []
    
    if data.ndr is not None and data.ndr < 110:
        exit_signals += 1
        exit_reasons.append(f"NDR {data.ndr}% < 110%")
    
    if data.category_stage == 'commoditizing':
        exit_signals += 1
        exit_reasons.append("Category commoditizing")
    elif data.category_stage == 'mature':
        exit_signals += 0.5
        exit_reasons.append("Category mature")
    
    if data.big_tech_threat in ['high', 'very_high']:
        exit_signals += 0.5
        exit_reasons.append(f"Big Tech: {data.big_tech_threat}")
    
    # Entry signals
    entry_signals = 0
    entry_details = []
    
    if data.ndr is not None:
        if data.ndr >= 110:
            entry_signals += 1
            entry_details.append(f"NDR {data.ndr}%")
        if data.ndr >= 120:
            entry_details.append("(Elite)")
    else:
        missing.append("NDR")
    
    if data.revenue_growth_yoy is not None:
        growth_pct = data.revenue_growth_yoy * 100 if data.revenue_growth_yoy < 1 else data.revenue_growth_yoy
        if growth_pct >= 25:
            entry_signals += 1
            entry_details.append(f"Growth {growth_pct:.0f}%")
        elif growth_pct >= 20:
            entry_signals += 0.5
            entry_details.append(f"Growth {growth_pct:.0f}%")
    else:
        missing.append("Growth")
    
    if data.category_stage in ['emerging', 'early_growth']:
        entry_signals += 1
        entry_details.append(f"{data.category_stage}")
    elif data.category_stage == 'mid_growth':
        entry_signals += 0.5
        entry_details.append(f"{data.category_stage}")
    
    if data.big_tech_threat in ['low', 'medium']:
        entry_signals += 1
        entry_details.append(f"Tech threat: {data.big_tech_threat}")
    
    if data.switching_cost == 'high':
        entry_signals += 1
        entry_details.append("High switching costs")
    elif data.switching_cost == 'medium':
        entry_signals += 0.5
        entry_details.append("Med switching costs")
    
    # Determine verdict
    if exit_signals >= 2:
        verdict = "SELL"
        rationale = f"Exit signals: {'; '.join(exit_reasons)}"
    elif exit_signals >= 1:
        verdict = "WATCH"
        rationale = f"Warning: {'; '.join(exit_reasons)}"
    elif data.ndr is not None and data.ndr >= 120 and entry_signals >= 4:
        verdict = "STRONG_BUY"
        rationale = f"Elite NDR + {entry_signals:.1f}/5: {'; '.join(entry_details)}"
    elif entry_signals >= 4:
        verdict = "BUY"
        rationale = f"{entry_signals:.1f}/5: {'; '.join(entry_details)}"
    elif entry_signals >= 3:
        verdict = "WATCH"
        rationale = f"{entry_signals:.1f}/5: {'; '.join(entry_details)}"
    else:
        verdict = "AVOID"
        rationale = f"Only {entry_signals:.1f}/5 signals"
    
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


def analyze_company(ticker: str, company_info: dict) -> tuple:
    """Analyze a single company."""
    print(f"  {ticker}...", end='', flush=True)
    
    # Fetch live data
    yf_data = fetch_yfinance_data(ticker)
    
    # Build CompanyData
    company = CompanyData(
        ticker=ticker,
        name=company_info.get('name', ticker),
        cik=company_info.get('cik', ''),
        category=company_info.get('category', 'unknown'),
        business_model=company_info.get('business_model', 'b2b_saas'),
        
        # Automated
        market_cap=yf_data.get('market_cap'),
        revenue_ttm=yf_data.get('revenue_ttm'),
        revenue_growth_yoy=company_info.get('revenue_growth_yoy') or yf_data.get('revenue_growth_yoy'),
        gross_margin=yf_data.get('gross_margin'),
        operating_margin=yf_data.get('operating_margin'),
        current_price=yf_data.get('current_price'),
        
        # Manual
        ndr=company_info.get('ndr'),
        ndr_tier=company_info.get('ndr_tier', 4),
        gross_retention=company_info.get('gross_retention'),
        arr_millions=company_info.get('arr_millions'),
        customers_100k_plus=company_info.get('customers_100k_plus'),
        
        # Assessments
        big_tech_threat=company_info.get('big_tech_threat', 'medium'),
        category_stage=company_info.get('category_stage', 'mid_growth'),
        switching_cost=company_info.get('switching_cost', 'medium'),
        
        # Metadata
        data_as_of=datetime.now().strftime('%Y-%m-%d'),
        notes=company_info.get('notes', ''),
    )
    
    verdict = compute_verdict(company)
    
    print(f" {verdict.verdict}", flush=True)
    
    return company, verdict


def batch_analyze(tickers: List[str] = None) -> Dict:
    """Analyze multiple companies."""
    
    if tickers is None:
        tickers = list(COMPANY_DATABASE.keys())
    
    print(f"\n{'='*60}")
    print(f"PLG BATCH ANALYSIS - {len(tickers)} Companies")
    print(f"{'='*60}\n")
    
    print("Analyzing companies:")
    
    results = []
    
    for ticker in tickers:
        if ticker not in COMPANY_DATABASE:
            print(f"  {ticker}... SKIPPED (not in database)")
            continue
        
        try:
            company, verdict = analyze_company(ticker, COMPANY_DATABASE[ticker])
            
            results.append({
                'company': company,
                'verdict': verdict,
            })
        except Exception as e:
            print(f" ERROR: {e}")
            continue
    
    return results


def generate_summary(results: List[Dict]) -> Dict:
    """Generate summary statistics."""
    
    verdict_counts = {}
    by_verdict = {
        'STRONG_BUY': [],
        'BUY': [],
        'WATCH': [],
        'SELL': [],
        'AVOID': [],
    }
    
    for r in results:
        verdict = r['verdict'].verdict
        ticker = r['company'].ticker
        ndr = r['company'].ndr
        growth = r['company'].revenue_growth_yoy
        
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
        by_verdict[verdict].append({
            'ticker': ticker,
            'name': r['company'].name,
            'ndr': ndr,
            'growth_pct': growth * 100 if growth and growth < 1 else growth,
            'confidence': r['verdict'].confidence,
        })
    
    return {
        'total_analyzed': len(results),
        'verdict_counts': verdict_counts,
        'by_verdict': by_verdict,
    }


def print_summary(summary: Dict, results: List[Dict]):
    """Print formatted summary."""
    
    print(f"\n{'='*60}")
    print(f"SUMMARY: {summary['total_analyzed']} Companies Analyzed")
    print(f"{'='*60}\n")
    
    # Verdict breakdown
    print("📊 VERDICT BREAKDOWN:")
    for verdict in ['STRONG_BUY', 'BUY', 'WATCH', 'SELL', 'AVOID']:
        count = summary['verdict_counts'].get(verdict, 0)
        if count > 0:
            emoji = {'STRONG_BUY': '🟢🟢', 'BUY': '🟢', 'WATCH': '🟡', 'SELL': '🔴', 'AVOID': '⚫'}
            print(f"  {emoji.get(verdict, '')} {verdict}: {count}")
    
    # Top picks
    print(f"\n🟢 STRONG BUY ({len(summary['by_verdict']['STRONG_BUY'])}):")
    for co in summary['by_verdict']['STRONG_BUY']:
        ndr_str = f"NDR {co['ndr']}%" if co['ndr'] else "NDR N/A"
        growth_str = f"{co['growth_pct']:.0f}% growth" if co['growth_pct'] else "N/A"
        print(f"  • {co['ticker']:6s} ({co['name'][:20]:20s}) - {ndr_str}, {growth_str}")
    
    print(f"\n🟢 BUY ({len(summary['by_verdict']['BUY'])}):")
    for co in summary['by_verdict']['BUY'][:10]:  # Top 10
        ndr_str = f"NDR {co['ndr']}%" if co['ndr'] else "NDR N/A"
        growth_str = f"{co['growth_pct']:.0f}% growth" if co['growth_pct'] else "N/A"
        print(f"  • {co['ticker']:6s} ({co['name'][:20]:20s}) - {ndr_str}, {growth_str}")
    
    print(f"\n🟡 WATCH ({len(summary['by_verdict']['WATCH'])}):")
    for co in summary['by_verdict']['WATCH'][:5]:  # Top 5
        ndr_str = f"NDR {co['ndr']}%" if co['ndr'] else "NDR N/A"
        print(f"  • {co['ticker']:6s} ({co['name'][:20]:20s}) - {ndr_str}")
    
    print(f"\n🔴 SELL/AVOID ({len(summary['by_verdict']['SELL']) + len(summary['by_verdict']['AVOID'])}):")
    for co in summary['by_verdict']['SELL'] + summary['by_verdict']['AVOID']:
        ndr_str = f"NDR {co['ndr']}%" if co['ndr'] else "NDR N/A"
        print(f"  • {co['ticker']:6s} ({co['name'][:20]:20s}) - {ndr_str}")


def save_results(results: List[Dict], summary: Dict):
    """Save results to JSON and CSV."""
    
    # JSON - Full data
    output_data = []
    for r in results:
        output_data.append({
            'ticker': r['company'].ticker,
            'name': r['company'].name,
            'verdict': r['verdict'].verdict,
            'confidence': r['verdict'].confidence,
            'confidence_score': r['verdict'].confidence_score,
            'data_tier': r['verdict'].data_tier,
            'ndr': r['company'].ndr,
            'revenue_growth_yoy': r['company'].revenue_growth_yoy,
            'market_cap': r['company'].market_cap,
            'big_tech_threat': r['company'].big_tech_threat,
            'category_stage': r['company'].category_stage,
            'entry_signals': r['verdict'].entry_signals_met,
            'exit_signals': r['verdict'].exit_signals_triggered,
            'rationale': r['verdict'].rationale,
        })
    
    with open('plg_batch_results.json', 'w') as f:
        json.dump({
            'analyzed_at': datetime.now().isoformat(),
            'summary': summary,
            'results': output_data,
        }, f, indent=2)
    
    # CSV - Summary view
    with open('plg_batch_summary.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'ticker', 'name', 'verdict', 'confidence', 'ndr', 'growth_pct',
            'market_cap', 'big_tech_threat', 'category_stage'
        ])
        writer.writeheader()
        
        for r in results:
            growth_pct = None
            if r['company'].revenue_growth_yoy:
                growth_pct = r['company'].revenue_growth_yoy * 100 if r['company'].revenue_growth_yoy < 1 else r['company'].revenue_growth_yoy
            
            writer.writerow({
                'ticker': r['company'].ticker,
                'name': r['company'].name,
                'verdict': r['verdict'].verdict,
                'confidence': r['verdict'].confidence,
                'ndr': r['company'].ndr,
                'growth_pct': f"{growth_pct:.1f}" if growth_pct else "",
                'market_cap': r['company'].market_cap,
                'big_tech_threat': r['company'].big_tech_threat,
                'category_stage': r['company'].category_stage,
            })
    
    print(f"\n✅ Results saved:")
    print(f"   • plg_batch_results.json (full data)")
    print(f"   • plg_batch_summary.csv (spreadsheet view)")


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    
    # Parse command line args
    if len(sys.argv) > 1:
        # Specific tickers provided
        tickers = [t.upper() for t in sys.argv[1:]]
        print(f"Analyzing specific tickers: {', '.join(tickers)}")
    else:
        # Analyze all
        tickers = None
    
    # Run batch analysis
    results = batch_analyze(tickers)
    
    # Generate summary
    summary = generate_summary(results)
    
    # Print results
    print_summary(summary, results)
    
    # Save to files
    save_results(results, summary)
    
    print(f"\n{'='*60}\n")

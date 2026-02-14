#!/usr/bin/env python3
"""
PLG Core — Shared logic for the PLG investment thesis analyzer.

Single source of truth for:
- Threshold constants
- Data classes (CompanyData, VerdictResult)
- Confidence scoring
- Staleness checking
- Research recommendations
- Tiered verdict logic (Tier 1/2/3/4)
- Data fetching (yfinance, SEC EDGAR)
- Company database I/O (JSON)
- Formatting utilities

Design docs:
- plg_verdict_logic.md  (verdict rules + pseudocode)
- plg_data_schema.md    (data structures)
- plg_data_sourcing.md  (data sources + extraction)
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple

# ============================================================
# THRESHOLD CONSTANTS
# ============================================================

# --- Entry Signal Thresholds ---
NDR_ENTRY_THRESHOLD = 110        # NDR >= 110% = entry signal
NDR_ELITE_THRESHOLD = 120        # NDR >= 120% = elite tier
GROWTH_ENTRY_THRESHOLD = 25      # Revenue growth >= 25%
GROWTH_ELITE_THRESHOLD = 30      # Revenue growth >= 30% (for STRONG_BUY)
GROWTH_PARTIAL_THRESHOLD = 20    # 20-25% = partial credit (0.5)

# --- Tier 2: Gross Retention ---
GR_STRONG = 97                   # GR >= 97% = strong retention signal
GR_HEALTHY = 93                  # GR >= 93% = healthy
GR_ACCEPTABLE = 90               # GR >= 90% = acceptable
# GR < 90% = weak

# --- Tier 2: Dollar-Based Net Expansion (DBNE) ---
DBNE_STRONG = 120                # DBNE >= 120% = strong
DBNE_HEALTHY = 110               # DBNE >= 110% = healthy
DBNE_ACCEPTABLE = 100            # DBNE >= 100% = acceptable
# DBNE < 100% = weak

# --- Tier 2: Large Customer NDR (stricter thresholds) ---
LARGE_CUST_NDR_STRONG = 125      # Large Customer NDR >= 125%
LARGE_CUST_NDR_HEALTHY = 115     # >= 115%
LARGE_CUST_NDR_ACCEPTABLE = 105  # >= 105%
# < 105% = weak

# --- Tier 3: Implied Expansion ---
IMPLIED_EXP_STRONG = 15          # > 15% = strong expansion
IMPLIED_EXP_HEALTHY = 5          # > 5% = healthy
# > 0% = modest, <= 0% = negative

# --- Tier 3: RPO Forward Indicator ---
RPO_ACCELERATING_DELTA = 10      # RPO growth > revenue growth + 10%

# --- Tier 4: Consumer Model ---
CONSUMER_ARPU_GROWTH_BUY = 20    # ARPU growth > 20%
CONSUMER_USER_GROWTH_BUY = 15    # User growth > 15%
CONSUMER_REVENUE_GROWTH_WATCH = 30  # Revenue > 30% = WATCH

# --- Tier 4: Marketplace Model ---
MARKETPLACE_GMV_GROWTH_BUY = 25  # GMV growth > 25%

# --- Tier 4: Transaction Model ---
TRANSACTION_MARGIN_COMPRESSION_DELTA = 10  # GP growth < TPV growth - 10%

# --- Confidence Thresholds ---
CONFIDENCE_HIGH = 0.70
CONFIDENCE_MEDIUM = 0.45
CONFIDENCE_LOW = 0.25
# < 0.25 = INSUFFICIENT

# --- Staleness Thresholds (days) ---
STALENESS_FINANCIAL = 100        # Financials, NDR, customer counts
STALENESS_COMPETITIVE = 180      # Competitive assessment

# --- Entry/Exit Signal Counts ---
ENTRY_STRONG_BUY = 5             # 5/5 entry signals
ENTRY_BUY = 4                    # 4/5
ENTRY_WATCH = 3                  # 3/5
# < 3 = AVOID
EXIT_SELL = 2                    # 2+ exit signals = SELL
EXIT_WATCH = 1                   # 1 exit signal = WATCH

# --- Confidence Scoring Weights ---
SIGNAL_WEIGHTS = {
    # Retention signals (40% total)
    'ndr_tier_1': 0.25,
    'ndr_tier_2': 0.15,
    'ndr_tier_3': 0.08,
    # Growth signals (30% total)
    'revenue_growth_current': 0.15,
    'revenue_growth_trend': 0.10,
    'arr_disclosed': 0.05,
    # Competitive signals (20% total)
    'big_tech_threat_assessed': 0.10,
    'category_stage_assessed': 0.10,
    # Customer signals (10% total)
    'large_customer_count': 0.05,
    'customer_growth_rate': 0.05,
}


# ============================================================
# DATA CLASSES
# ============================================================

@dataclass
class CompanyData:
    """All data needed to compute a verdict for one company."""
    ticker: str
    name: str
    category: str
    business_model: str  # b2b_saas, consumer, marketplace, transaction_based, hybrid

    # --- Automated (from yfinance) ---
    market_cap: Optional[float] = None
    revenue_ttm: Optional[float] = None
    revenue_growth_yoy: Optional[float] = None  # decimal (0.25) or percent (25)
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    current_price: Optional[float] = None

    # --- Tier 1: Direct NDR ---
    ndr: Optional[float] = None
    ndr_tier: int = 4  # 1=direct, 2=variant, 3=derived, 4=unavailable

    # --- Tier 2: Variant Metrics ---
    gross_retention: Optional[float] = None  # decimal (0.97) or percent (97)
    dbne: Optional[float] = None             # Dollar-Based Net Expansion
    large_customer_ndr: Optional[float] = None

    # --- Tier 3: Derived Signals ---
    implied_expansion: Optional[float] = None  # ARR growth - customer growth
    rpo_growth_yoy: Optional[float] = None

    # --- Tier 4: Non-SaaS Metrics ---
    arpu_growth_yoy: Optional[float] = None
    active_user_growth_yoy: Optional[float] = None
    gmv_growth_yoy: Optional[float] = None
    take_rate: Optional[float] = None
    take_rate_trend: Optional[str] = None    # increasing, stable, decreasing
    tpv_growth_yoy: Optional[float] = None   # Total Payment Volume
    gross_profit_growth_yoy: Optional[float] = None

    # --- SaaS Metrics ---
    arr_millions: Optional[float] = None
    customers_100k_plus: Optional[int] = None
    customer_growth_yoy: Optional[float] = None

    # --- Assessments ---
    big_tech_threat: str = "unknown"
    category_stage: str = "unknown"
    switching_cost: str = "unknown"

    # --- Exit Signal Data ---
    big_tech_announced: bool = False
    revenue_decel_3q: bool = False

    # --- Metadata ---
    cik: str = ""
    data_as_of: str = ""
    data_updated: Optional[str] = None
    notes: str = ""


@dataclass
class VerdictResult:
    """Output of verdict computation."""
    ticker: str
    verdict: str                         # STRONG_BUY, BUY, WATCH, SELL, AVOID
    confidence: str                      # HIGH, MEDIUM, LOW, INSUFFICIENT
    confidence_score: float              # 0.0 - 1.0
    rationale: str                       # Human-readable explanation
    data_tier: int                       # 1, 2, 3, or 4
    missing_signals: List[str]           # What data would improve confidence
    entry_signals_met: int               # Count of entry signals
    exit_signals_triggered: int          # Count of exit signals
    staleness_warning: bool = False      # True if key data > 100 days old
    stale_fields: List[str] = field(default_factory=list)
    research_recommendations: List[str] = field(default_factory=list)
    last_updated: Optional[str] = None


# ============================================================
# NORMALIZATION HELPERS
# ============================================================

def _normalize_growth(value: Optional[float]) -> Optional[float]:
    """Normalize growth to percentage form.

    Handles both decimal (0.25) and percent (25) representations.
    Returns value in percentage form (e.g. 25.0) or None.
    """
    if value is None:
        return None
    # If value looks like a decimal ratio (between -1 and 1 exclusive,
    # but not exactly 0), convert to percent
    if -1 < value < 1 and value != 0:
        return value * 100
    return float(value)


def _normalize_retention(value: Optional[float]) -> Optional[float]:
    """Normalize retention/GR metrics to percentage form.

    Handles both decimal (0.97) and percent (97) representations.
    Returns value in percentage form (e.g. 97.0) or None.
    """
    if value is None:
        return None
    # If value looks like a decimal ratio (< 2.0), convert to percent
    if value < 2.0:
        return value * 100
    return float(value)


# ============================================================
# CONFIDENCE SCORING
# ============================================================

def calculate_confidence_score(data: CompanyData) -> float:
    """Calculate confidence score based on signal availability.

    Uses SIGNAL_WEIGHTS to weight each data point.
    IMPORTANT: Default assessment values ('unknown') get 0 credit,
    not partial credit. Only explicitly assessed values count.
    """
    score = 0.0

    # Retention signals (40%)
    if data.ndr is not None:
        if data.ndr_tier == 1:
            score += SIGNAL_WEIGHTS['ndr_tier_1']
        elif data.ndr_tier == 2:
            score += SIGNAL_WEIGHTS['ndr_tier_2']
        elif data.ndr_tier == 3:
            score += SIGNAL_WEIGHTS['ndr_tier_3']
    elif data.dbne is not None or data.gross_retention is not None or data.large_customer_ndr is not None:
        # Tier 2 variant data available even without explicit NDR
        score += SIGNAL_WEIGHTS['ndr_tier_2']
    elif data.implied_expansion is not None:
        # Tier 3 derived data
        score += SIGNAL_WEIGHTS['ndr_tier_3']

    # Growth signals (30%)
    if data.revenue_growth_yoy is not None:
        score += SIGNAL_WEIGHTS['revenue_growth_current']

    if data.revenue_decel_3q is True or data.revenue_decel_3q is False:
        # Trend data was explicitly assessed (not just default)
        if data.revenue_decel_3q is True:
            score += SIGNAL_WEIGHTS['revenue_growth_trend']
        else:
            score += SIGNAL_WEIGHTS['revenue_growth_trend']

    if data.arr_millions is not None:
        score += SIGNAL_WEIGHTS['arr_disclosed']

    # Competitive signals (20%)
    # Only count if explicitly assessed (not default 'unknown')
    if data.big_tech_threat != "unknown":
        score += SIGNAL_WEIGHTS['big_tech_threat_assessed']

    if data.category_stage != "unknown":
        score += SIGNAL_WEIGHTS['category_stage_assessed']

    # Customer signals (10%)
    if data.customers_100k_plus is not None:
        score += SIGNAL_WEIGHTS['large_customer_count']

    if data.customer_growth_yoy is not None:
        score += SIGNAL_WEIGHTS['customer_growth_rate']

    return round(score, 4)


def score_to_confidence_level(score: float) -> str:
    """Convert numeric confidence score to label."""
    if score >= CONFIDENCE_HIGH:
        return 'HIGH'
    elif score >= CONFIDENCE_MEDIUM:
        return 'MEDIUM'
    elif score >= CONFIDENCE_LOW:
        return 'LOW'
    else:
        return 'INSUFFICIENT'


# ============================================================
# STALENESS CHECKING
# ============================================================

def check_staleness(data: CompanyData) -> Tuple[bool, List[str]]:
    """Check if key data is stale (> threshold days old).

    Returns (is_stale, list_of_stale_fields).
    """
    stale_fields = []

    if not data.data_updated:
        # No update date recorded — can't check, flag it
        return True, ['data_updated (no date recorded)']

    try:
        updated = datetime.strptime(data.data_updated, '%Y-%m-%d')
    except (ValueError, TypeError):
        return True, ['data_updated (invalid date format)']

    now = datetime.now()
    days_old = (now - updated).days

    if days_old > STALENESS_FINANCIAL:
        stale_fields.append(f'financials ({days_old} days old)')

    if data.ndr is not None and days_old > STALENESS_FINANCIAL:
        stale_fields.append(f'NDR ({days_old} days old)')

    if days_old > STALENESS_COMPETITIVE:
        stale_fields.append(f'competitive assessment ({days_old} days old)')

    return len(stale_fields) > 0, stale_fields


# ============================================================
# RESEARCH RECOMMENDATIONS
# ============================================================

def recommend_research(data: CompanyData) -> List[str]:
    """Generate research recommendations based on missing data.

    Tells the user what to look for to improve verdict confidence.
    """
    recs = []

    if data.ndr is None:
        if data.ndr_tier == 4:
            recs.append(
                f"Search {data.name} earnings call for NDR/NRR/DBNE disclosure. "
                f"Try: 'net dollar retention', 'net revenue retention', 'dollar-based net expansion'."
            )
        elif data.ndr_tier == 3:
            recs.append(
                f"Calculate implied expansion for {data.name}: ARR growth - customer growth."
            )

    if data.gross_retention is None and data.ndr_tier >= 2:
        recs.append(
            f"Look for {data.name} gross retention rate in earnings call or 10-K. "
            f"Often disclosed near NDR or churn discussion."
        )

    if data.revenue_growth_yoy is None:
        recs.append(
            f"Fetch latest quarterly revenue for {data.name} from SEC EDGAR or earnings release."
        )

    if data.big_tech_threat == "unknown":
        recs.append(
            f"Assess Big Tech threat for {data.name}: Does AWS/Azure/GCP/Microsoft bundle a competitor?"
        )

    if data.category_stage == "unknown":
        recs.append(
            f"Assess category stage for {data.name}: emerging, early_growth, mid_growth, mature, or commoditizing?"
        )

    if data.switching_cost == "unknown":
        recs.append(
            f"Assess switching costs for {data.name}: How hard is it to rip and replace?"
        )

    if data.customers_100k_plus is None:
        recs.append(
            f"Look for $100K+ customer count in {data.name} earnings materials."
        )

    # Tier 4 specific
    if data.business_model == 'consumer' and data.arpu_growth_yoy is None:
        recs.append(
            f"Find ARPU and active user metrics for {data.name} (consumer model)."
        )
    if data.business_model == 'marketplace' and data.gmv_growth_yoy is None:
        recs.append(
            f"Find GMV and take rate for {data.name} (marketplace model)."
        )
    if data.business_model == 'transaction_based' and data.tpv_growth_yoy is None:
        recs.append(
            f"Find TPV and gross profit margin for {data.name} (transaction model)."
        )

    return recs


# ============================================================
# TIER ROUTING
# ============================================================

def _determine_data_tier(data: CompanyData) -> int:
    """Route to the correct verdict tier based on available data.

    Priority:
      Tier 1: Direct NDR disclosure (ndr_tier == 1)
      Tier 2: Variant metric (ndr_tier == 2, or GR/DBNE/large customer NDR available)
      Tier 3: Derived signals (implied_expansion or RPO available)
      Tier 4: Non-SaaS or insufficient data
    """
    # Tier 1: Direct NDR
    if data.ndr is not None and data.ndr_tier == 1:
        return 1

    # Tier 2: Variant metrics
    if data.ndr is not None and data.ndr_tier == 2:
        return 2
    if data.dbne is not None:
        return 2
    if data.gross_retention is not None:
        return 2
    if data.large_customer_ndr is not None:
        return 2

    # Tier 3: Derived
    if data.implied_expansion is not None:
        return 3
    if data.rpo_growth_yoy is not None:
        return 3

    # Tier 4: Non-SaaS models or insufficient data
    if data.business_model in ('consumer', 'marketplace', 'transaction_based'):
        return 4

    # Default: Tier 4 (insufficient retention data)
    return 4


# ============================================================
# TIER 1 VERDICT: Direct NDR
# ============================================================

def _compute_verdict_tier1(data: CompanyData) -> VerdictResult:
    """Tier 1 verdict logic — NDR disclosed directly.

    Entry signals (5 total):
      1. NDR >= 110%
      2. Revenue growth >= 25%
      3. Category: emerging or early_growth
      4. Big Tech threat: low or medium
      5. Switching cost: medium or high

    Exit signals (any 2 = SELL):
      - NDR < 110%
      - Revenue decelerating 3+ quarters
      - Big Tech bundled competitor announced
      - Category commoditizing

    Elite: NDR >= 120% AND growth >= 30% → STRONG_BUY
    """
    missing = []
    growth = _normalize_growth(data.revenue_growth_yoy)

    # --- Exit Signals ---
    exit_signals = 0
    exit_reasons = []

    if data.ndr is not None and data.ndr < NDR_ENTRY_THRESHOLD:
        exit_signals += 1
        exit_reasons.append(f"NDR {data.ndr}% < {NDR_ENTRY_THRESHOLD}%")

    if data.revenue_decel_3q:
        exit_signals += 1
        exit_reasons.append("Revenue decelerating 3+ quarters")

    if data.big_tech_announced:
        exit_signals += 1
        exit_reasons.append("Big Tech bundled competitor announced")

    if data.category_stage == 'commoditizing':
        exit_signals += 1
        exit_reasons.append("Category commoditizing")
    elif data.category_stage == 'mature':
        exit_signals += 0.5
        exit_reasons.append("Category mature (partial)")

    if data.big_tech_threat in ('high', 'very_high'):
        exit_signals += 0.5
        exit_reasons.append(f"Big Tech threat: {data.big_tech_threat}")

    # --- Entry Signals ---
    entry_signals = 0
    entry_details = []

    # Signal 1: NDR >= 110%
    if data.ndr is not None:
        if data.ndr >= NDR_ENTRY_THRESHOLD:
            entry_signals += 1
            entry_details.append(f"NDR {data.ndr}%")
        # Elite flagged separately
    else:
        missing.append("NDR")

    # Signal 2: Revenue growth >= 25%
    if growth is not None:
        if growth >= GROWTH_ENTRY_THRESHOLD:
            entry_signals += 1
            entry_details.append(f"Growth {growth:.0f}%")
        elif growth >= GROWTH_PARTIAL_THRESHOLD:
            entry_signals += 0.5
            entry_details.append(f"Growth {growth:.0f}% (partial)")
    else:
        missing.append("Revenue growth")

    # Signal 3: Category stage
    if data.category_stage in ('emerging', 'early_growth'):
        entry_signals += 1
        entry_details.append(f"Category: {data.category_stage}")
    elif data.category_stage == 'mid_growth':
        entry_signals += 0.5
        entry_details.append(f"Category: mid_growth (partial)")
    elif data.category_stage == 'unknown':
        missing.append("Category stage")

    # Signal 4: Big Tech threat
    if data.big_tech_threat in ('low', 'medium'):
        entry_signals += 1
        entry_details.append(f"Big Tech threat: {data.big_tech_threat}")
    elif data.big_tech_threat == 'unknown':
        missing.append("Big Tech threat assessment")

    # Signal 5: Switching costs
    if data.switching_cost == 'high':
        entry_signals += 1
        entry_details.append("High switching costs")
    elif data.switching_cost == 'medium':
        entry_signals += 0.5
        entry_details.append("Medium switching costs (partial)")
    elif data.switching_cost == 'unknown':
        missing.append("Switching cost assessment")

    # --- Determine Verdict ---
    if exit_signals >= EXIT_SELL:
        verdict = "SELL"
        rationale = f"Exit signals ({exit_signals:.1f}): {'; '.join(exit_reasons)}"
    elif exit_signals >= EXIT_WATCH:
        verdict = "WATCH"
        rationale = f"Warning ({exit_signals:.1f} exit signals): {'; '.join(exit_reasons)}"
    elif (data.ndr is not None and data.ndr >= NDR_ELITE_THRESHOLD
          and growth is not None and growth >= GROWTH_ELITE_THRESHOLD):
        verdict = "STRONG_BUY"
        rationale = f"Elite: NDR {data.ndr}%, growth {growth:.0f}%. Entry {entry_signals:.1f}/5: {'; '.join(entry_details)}"
    elif entry_signals >= ENTRY_STRONG_BUY:
        verdict = "STRONG_BUY"
        rationale = f"All 5 entry signals: {'; '.join(entry_details)}"
    elif entry_signals >= ENTRY_BUY:
        verdict = "BUY"
        rationale = f"Entry {entry_signals:.1f}/5: {'; '.join(entry_details)}"
    elif entry_signals >= ENTRY_WATCH:
        verdict = "WATCH"
        rationale = f"Entry {entry_signals:.1f}/5: {'; '.join(entry_details)}"
    else:
        verdict = "AVOID"
        rationale = f"Only {entry_signals:.1f}/5 entry signals: {'; '.join(entry_details) or 'none'}"

    return VerdictResult(
        ticker=data.ticker,
        verdict=verdict,
        confidence='',  # Filled by compute_verdict()
        confidence_score=0.0,
        rationale=rationale,
        data_tier=1,
        missing_signals=missing,
        entry_signals_met=int(entry_signals),
        exit_signals_triggered=int(exit_signals),
    )


# ============================================================
# TIER 2 VERDICT: Variant Metrics (GR, DBNE, Large Customer NDR)
# ============================================================

def _interpret_retention_signal(data: CompanyData) -> str:
    """Interpret Tier 2 variant metrics into a retention signal.

    Returns: 'strong', 'healthy', 'acceptable', or 'weak'.
    Uses the best available variant metric.
    """
    signals = []

    # DBNE (e.g., Twilio)
    if data.dbne is not None:
        dbne = _normalize_retention(data.dbne)
        if dbne >= DBNE_STRONG:
            signals.append('strong')
        elif dbne >= DBNE_HEALTHY:
            signals.append('healthy')
        elif dbne >= DBNE_ACCEPTABLE:
            signals.append('acceptable')
        else:
            signals.append('weak')

    # Gross Retention
    if data.gross_retention is not None:
        gr = _normalize_retention(data.gross_retention)
        if gr >= GR_STRONG:
            signals.append('strong')
        elif gr >= GR_HEALTHY:
            signals.append('healthy')
        elif gr >= GR_ACCEPTABLE:
            signals.append('acceptable')
        else:
            signals.append('weak')

    # Large Customer NDR (stricter thresholds)
    if data.large_customer_ndr is not None:
        lc_ndr = _normalize_retention(data.large_customer_ndr)
        if lc_ndr >= LARGE_CUST_NDR_STRONG:
            signals.append('strong')
        elif lc_ndr >= LARGE_CUST_NDR_HEALTHY:
            signals.append('healthy')
        elif lc_ndr >= LARGE_CUST_NDR_ACCEPTABLE:
            signals.append('acceptable')
        else:
            signals.append('weak')

    # NDR value with ndr_tier == 2 (approximate/variant)
    if data.ndr is not None and data.ndr_tier == 2:
        if data.ndr >= NDR_ELITE_THRESHOLD:
            signals.append('strong')
        elif data.ndr >= NDR_ENTRY_THRESHOLD:
            signals.append('healthy')
        elif data.ndr >= 100:
            signals.append('acceptable')
        else:
            signals.append('weak')

    if not signals:
        return 'unknown'

    # Use the best available signal (most optimistic interpretation,
    # but 'weak' from any metric is a red flag)
    if 'weak' in signals:
        return 'weak'
    if 'strong' in signals:
        return 'strong'
    if 'healthy' in signals:
        return 'healthy'
    return 'acceptable'


def _compute_verdict_tier2(data: CompanyData) -> VerdictResult:
    """Tier 2 verdict logic — variant retention metrics.

    Uses GR, DBNE, and/or Large Customer NDR.
    More conservative than Tier 1 (less precise data).
    """
    missing = []
    growth = _normalize_growth(data.revenue_growth_yoy)
    retention_signal = _interpret_retention_signal(data)

    details = []
    if data.dbne is not None:
        details.append(f"DBNE {_normalize_retention(data.dbne):.0f}%")
    if data.gross_retention is not None:
        details.append(f"GR {_normalize_retention(data.gross_retention):.0f}%")
    if data.large_customer_ndr is not None:
        details.append(f"Large Cust NDR {_normalize_retention(data.large_customer_ndr):.0f}%")
    if data.ndr is not None and data.ndr_tier == 2:
        details.append(f"NDR ~{data.ndr}% (approximate)")

    # Exit check: weak retention = SELL
    if retention_signal == 'weak':
        verdict = "SELL"
        rationale = f"Tier 2: Weak retention ({'; '.join(details)})"
        return VerdictResult(
            ticker=data.ticker,
            verdict=verdict,
            confidence='',
            confidence_score=0.0,
            rationale=rationale,
            data_tier=2,
            missing_signals=missing,
            entry_signals_met=0,
            exit_signals_triggered=1,
        )

    # Also check exit signals (same as Tier 1)
    exit_signals = 0
    exit_reasons = []

    if data.revenue_decel_3q:
        exit_signals += 1
        exit_reasons.append("Revenue decelerating 3+ quarters")
    if data.big_tech_announced:
        exit_signals += 1
        exit_reasons.append("Big Tech bundled competitor announced")
    if data.category_stage == 'commoditizing':
        exit_signals += 1
        exit_reasons.append("Category commoditizing")
    elif data.category_stage == 'mature':
        exit_signals += 0.5
        exit_reasons.append("Category mature (partial)")
    if data.big_tech_threat in ('high', 'very_high'):
        exit_signals += 0.5
        exit_reasons.append(f"Big Tech threat: {data.big_tech_threat}")

    if exit_signals >= EXIT_SELL:
        verdict = "SELL"
        rationale = f"Tier 2: Exit signals ({exit_signals}): {'; '.join(exit_reasons)}"
        return VerdictResult(
            ticker=data.ticker,
            verdict=verdict,
            confidence='',
            confidence_score=0.0,
            rationale=rationale,
            data_tier=2,
            missing_signals=missing,
            entry_signals_met=0,
            exit_signals_triggered=exit_signals,
        )

    # Entry logic
    if growth is None:
        missing.append("Revenue growth")

    entry_signals = 0
    if retention_signal in ('strong', 'healthy'):
        entry_signals += 1
    if growth is not None and growth >= GROWTH_ENTRY_THRESHOLD:
        entry_signals += 1
    elif growth is not None and growth >= GROWTH_PARTIAL_THRESHOLD:
        entry_signals += 0.5

    growth_str = f", growth {growth:.0f}%" if growth is not None else ""

    if retention_signal == 'strong' and growth is not None and growth >= GROWTH_ENTRY_THRESHOLD:
        verdict = "BUY"
        rationale = f"Tier 2: Strong retention + {growth:.0f}% growth. {'; '.join(details)}"
    elif retention_signal in ('healthy', 'strong') and growth is not None and growth >= GROWTH_PARTIAL_THRESHOLD:
        verdict = "WATCH"
        rationale = f"Tier 2: {retention_signal.title()} retention{growth_str}. {'; '.join(details)}. Verify with Tier 1 data."
    else:
        verdict = "WATCH"
        rationale = f"Tier 2: {retention_signal.title()} retention{growth_str}. Incomplete data — manual research recommended."
        missing.append("Direct NDR for higher confidence")

    return VerdictResult(
        ticker=data.ticker,
        verdict=verdict,
        confidence='',
        confidence_score=0.0,
        rationale=rationale,
        data_tier=2,
        missing_signals=missing,
        entry_signals_met=int(entry_signals),
        exit_signals_triggered=int(exit_signals),
    )


# ============================================================
# TIER 3 VERDICT: Derived Signals
# ============================================================

def _compute_verdict_tier3(data: CompanyData) -> VerdictResult:
    """Tier 3 verdict logic — derived signals (implied expansion, RPO).

    Very conservative: even strong signals only produce WATCH.
    Tier 3 data alone cannot justify BUY.
    """
    missing = []
    growth = _normalize_growth(data.revenue_growth_yoy)
    details = []

    # Implied expansion
    expansion = 'unknown'
    if data.implied_expansion is not None:
        ie = _normalize_growth(data.implied_expansion)
        if ie is not None:
            details.append(f"Implied expansion: {ie:.0f}%")
            if ie > IMPLIED_EXP_STRONG:
                expansion = 'strong'
            elif ie > IMPLIED_EXP_HEALTHY:
                expansion = 'healthy'
            elif ie > 0:
                expansion = 'modest'
            else:
                expansion = 'negative'

    # RPO forward indicator
    rpo_signal = 'unknown'
    if data.rpo_growth_yoy is not None and growth is not None:
        rpo = _normalize_growth(data.rpo_growth_yoy)
        if rpo is not None:
            details.append(f"RPO growth: {rpo:.0f}%")
            if rpo > growth + RPO_ACCELERATING_DELTA:
                rpo_signal = 'accelerating'
            elif rpo > growth:
                rpo_signal = 'healthy'
            else:
                rpo_signal = 'decelerating'

    # Exit: negative expansion = SELL
    if expansion == 'negative':
        return VerdictResult(
            ticker=data.ticker,
            verdict="SELL",
            confidence='',
            confidence_score=0.0,
            rationale=f"Tier 3: Negative implied expansion ({'; '.join(details)}). Customers contracting.",
            data_tier=3,
            missing_signals=missing,
            entry_signals_met=0,
            exit_signals_triggered=1,
        )

    growth_str = f", growth {growth:.0f}%" if growth is not None else ""

    # Strong expansion + strong growth = WATCH (needs Tier 1/2 verification)
    if expansion == 'strong' and growth is not None and growth >= GROWTH_ENTRY_THRESHOLD:
        verdict = "WATCH"
        rationale = (
            f"Tier 3: Strong implied expansion{growth_str}. {'; '.join(details)}. "
            f"Promising but needs Tier 1/2 NDR data to upgrade to BUY."
        )
        missing.append("Direct NDR or variant metric for BUY upgrade")
    elif rpo_signal == 'accelerating':
        verdict = "WATCH"
        rationale = (
            f"Tier 3: RPO accelerating{growth_str}. {'; '.join(details)}. "
            f"Forward demand strong but retention data needed."
        )
        missing.append("NDR or retention data")
    else:
        verdict = "WATCH"
        rationale = (
            f"Tier 3: {expansion.title()} expansion{growth_str}. {'; '.join(details)}. "
            f"Insufficient retention data — manual research required."
        )
        missing.append("NDR, GR, or DBNE for meaningful verdict")

    if growth is None:
        missing.append("Revenue growth")

    return VerdictResult(
        ticker=data.ticker,
        verdict=verdict,
        confidence='',
        confidence_score=0.0,
        rationale=rationale,
        data_tier=3,
        missing_signals=missing,
        entry_signals_met=0,
        exit_signals_triggered=0,
    )


# ============================================================
# TIER 4 VERDICT: Non-SaaS Models / Insufficient Data
# ============================================================

def _compute_verdict_tier4(data: CompanyData) -> VerdictResult:
    """Tier 4 verdict logic — non-SaaS or insufficient data.

    Handles consumer, marketplace, and transaction-based models.
    B2B SaaS with no retention data → research-needed WATCH.
    """
    missing = []
    growth = _normalize_growth(data.revenue_growth_yoy)
    details = []
    entry_signals = 0

    if data.business_model == 'consumer':
        return _compute_verdict_tier4_consumer(data, growth, details, missing)
    elif data.business_model == 'marketplace':
        return _compute_verdict_tier4_marketplace(data, growth, details, missing)
    elif data.business_model == 'transaction_based':
        return _compute_verdict_tier4_transaction(data, growth, details, missing)
    else:
        # B2B SaaS with no retention data
        return _compute_verdict_tier4_insufficient(data, growth, details, missing)


def _compute_verdict_tier4_consumer(
    data: CompanyData, growth: Optional[float],
    details: List[str], missing: List[str]
) -> VerdictResult:
    """Consumer model: ARPU growth + user growth."""
    arpu = _normalize_growth(data.arpu_growth_yoy)
    user_growth = _normalize_growth(data.active_user_growth_yoy)

    if arpu is not None:
        details.append(f"ARPU growth: {arpu:.0f}%")
    else:
        missing.append("ARPU growth")

    if user_growth is not None:
        details.append(f"User growth: {user_growth:.0f}%")
    else:
        missing.append("Active user growth")

    if growth is not None:
        details.append(f"Revenue growth: {growth:.0f}%")

    # ARPU growth < 0% = SELL (monetization pressure)
    if arpu is not None and arpu < 0:
        return VerdictResult(
            ticker=data.ticker, verdict="SELL", confidence='',
            confidence_score=0.0,
            rationale=f"Tier 4 Consumer: ARPU declining ({arpu:.0f}%). Monetization pressure. {'; '.join(details)}",
            data_tier=4, missing_signals=missing,
            entry_signals_met=0, exit_signals_triggered=1,
        )

    # ARPU > 20% AND user growth > 15% = BUY
    if (arpu is not None and arpu > CONSUMER_ARPU_GROWTH_BUY
            and user_growth is not None and user_growth > CONSUMER_USER_GROWTH_BUY):
        return VerdictResult(
            ticker=data.ticker, verdict="BUY", confidence='',
            confidence_score=0.0,
            rationale=f"Tier 4 Consumer: Strong ARPU + user growth. {'; '.join(details)}",
            data_tier=4, missing_signals=missing,
            entry_signals_met=2, exit_signals_triggered=0,
        )

    # Revenue > 30% = WATCH (verify unit economics)
    if growth is not None and growth > CONSUMER_REVENUE_GROWTH_WATCH:
        return VerdictResult(
            ticker=data.ticker, verdict="WATCH", confidence='',
            confidence_score=0.0,
            rationale=f"Tier 4 Consumer: Strong revenue growth ({growth:.0f}%), verify unit economics. {'; '.join(details)}",
            data_tier=4, missing_signals=missing,
            entry_signals_met=1, exit_signals_triggered=0,
        )

    # Default WATCH
    return VerdictResult(
        ticker=data.ticker, verdict="WATCH", confidence='',
        confidence_score=0.0,
        rationale=f"Tier 4 Consumer: Insufficient consumer metrics. {'; '.join(details) or 'No details'}",
        data_tier=4, missing_signals=missing,
        entry_signals_met=0, exit_signals_triggered=0,
    )


def _compute_verdict_tier4_marketplace(
    data: CompanyData, growth: Optional[float],
    details: List[str], missing: List[str]
) -> VerdictResult:
    """Marketplace model: GMV growth + take rate trend."""
    gmv = _normalize_growth(data.gmv_growth_yoy)

    if gmv is not None:
        details.append(f"GMV growth: {gmv:.0f}%")
    else:
        missing.append("GMV growth")

    if data.take_rate is not None:
        details.append(f"Take rate: {data.take_rate:.1f}%")
    if data.take_rate_trend is not None:
        details.append(f"Take rate trend: {data.take_rate_trend}")
    else:
        missing.append("Take rate trend")

    if growth is not None:
        details.append(f"Revenue growth: {growth:.0f}%")

    # take_rate_trend decreasing = WATCH (commoditization risk)
    if data.take_rate_trend == 'decreasing':
        return VerdictResult(
            ticker=data.ticker, verdict="WATCH", confidence='',
            confidence_score=0.0,
            rationale=f"Tier 4 Marketplace: Take rate decreasing (commoditization risk). {'; '.join(details)}",
            data_tier=4, missing_signals=missing,
            entry_signals_met=0, exit_signals_triggered=1,
        )

    # GMV > 25% AND take rate not decreasing = BUY
    if gmv is not None and gmv > MARKETPLACE_GMV_GROWTH_BUY and data.take_rate_trend != 'decreasing':
        return VerdictResult(
            ticker=data.ticker, verdict="BUY", confidence='',
            confidence_score=0.0,
            rationale=f"Tier 4 Marketplace: Strong GMV growth with stable/growing take rate. {'; '.join(details)}",
            data_tier=4, missing_signals=missing,
            entry_signals_met=2, exit_signals_triggered=0,
        )

    # Default WATCH
    return VerdictResult(
        ticker=data.ticker, verdict="WATCH", confidence='',
        confidence_score=0.0,
        rationale=f"Tier 4 Marketplace: Insufficient marketplace metrics. {'; '.join(details) or 'No details'}",
        data_tier=4, missing_signals=missing,
        entry_signals_met=0, exit_signals_triggered=0,
    )


def _compute_verdict_tier4_transaction(
    data: CompanyData, growth: Optional[float],
    details: List[str], missing: List[str]
) -> VerdictResult:
    """Transaction-based model: Gross profit growth vs TPV growth."""
    gp_growth = _normalize_growth(data.gross_profit_growth_yoy)
    tpv_growth = _normalize_growth(data.tpv_growth_yoy)

    if gp_growth is not None:
        details.append(f"GP growth: {gp_growth:.0f}%")
    else:
        missing.append("Gross profit growth")

    if tpv_growth is not None:
        details.append(f"TPV growth: {tpv_growth:.0f}%")
    else:
        missing.append("TPV growth")

    if growth is not None:
        details.append(f"Revenue growth: {growth:.0f}%")

    # Margin compression: GP growth < TPV growth - 10% = SELL
    if gp_growth is not None and tpv_growth is not None:
        if gp_growth < tpv_growth - TRANSACTION_MARGIN_COMPRESSION_DELTA:
            return VerdictResult(
                ticker=data.ticker, verdict="SELL", confidence='',
                confidence_score=0.0,
                rationale=f"Tier 4 Transaction: Margin compression (GP growth {gp_growth:.0f}% << TPV growth {tpv_growth:.0f}%). {'; '.join(details)}",
                data_tier=4, missing_signals=missing,
                entry_signals_met=0, exit_signals_triggered=1,
            )

        # GP outpacing TPV = WATCH (verify sustainability)
        if gp_growth > tpv_growth:
            return VerdictResult(
                ticker=data.ticker, verdict="WATCH", confidence='',
                confidence_score=0.0,
                rationale=f"Tier 4 Transaction: GP outpacing TPV (improving margins). {'; '.join(details)}. Verify sustainability.",
                data_tier=4, missing_signals=missing,
                entry_signals_met=1, exit_signals_triggered=0,
            )

    # Default WATCH
    return VerdictResult(
        ticker=data.ticker, verdict="WATCH", confidence='',
        confidence_score=0.0,
        rationale=f"Tier 4 Transaction: Insufficient transaction metrics. {'; '.join(details) or 'No details'}",
        data_tier=4, missing_signals=missing,
        entry_signals_met=0, exit_signals_triggered=0,
    )


def _compute_verdict_tier4_insufficient(
    data: CompanyData, growth: Optional[float],
    details: List[str], missing: List[str]
) -> VerdictResult:
    """B2B SaaS with no retention data at all.

    Uses only growth + competitive signals. Very conservative.
    """
    entry_signals = 0
    exit_signals = 0
    exit_reasons = []

    if growth is not None:
        details.append(f"Revenue growth: {growth:.0f}%")

    missing.append("NDR/NRR (no retention data available)")

    # Check exit signals (still valid without NDR)
    if data.revenue_decel_3q:
        exit_signals += 1
        exit_reasons.append("Revenue decelerating 3+ quarters")
    if data.big_tech_announced:
        exit_signals += 1
        exit_reasons.append("Big Tech bundled competitor announced")
    if data.category_stage == 'commoditizing':
        exit_signals += 1
        exit_reasons.append("Category commoditizing")
    if data.big_tech_threat in ('high', 'very_high'):
        exit_signals += 0.5
        exit_reasons.append(f"Big Tech threat: {data.big_tech_threat}")

    if exit_signals >= EXIT_SELL:
        return VerdictResult(
            ticker=data.ticker, verdict="SELL", confidence='',
            confidence_score=0.0,
            rationale=f"Tier 4 (no retention data): Exit signals ({exit_signals:.1f}): {'; '.join(exit_reasons)}",
            data_tier=4, missing_signals=missing,
            entry_signals_met=0, exit_signals_triggered=int(exit_signals),
        )

    # Some entry signal credit
    if growth is not None and growth >= GROWTH_ENTRY_THRESHOLD:
        entry_signals += 1
    if data.category_stage in ('emerging', 'early_growth'):
        entry_signals += 1
    if data.big_tech_threat in ('low', 'medium') and data.big_tech_threat != 'unknown':
        entry_signals += 0.5
    if data.switching_cost == 'high':
        entry_signals += 0.5

    # Without retention data, best verdict is WATCH
    growth_str = f", growth {growth:.0f}%" if growth is not None else ""
    if entry_signals >= 2:
        verdict = "WATCH"
        rationale = (
            f"Tier 4 (no retention data): Some positive signals{growth_str}. "
            f"{'; '.join(details)}. Research NDR for upgrade."
        )
    elif exit_signals > 0:
        verdict = "WATCH"
        rationale = (
            f"Tier 4 (no retention data): Mixed signals{growth_str}. "
            f"Exit warning: {'; '.join(exit_reasons)}. Research NDR."
        )
    else:
        verdict = "WATCH"
        rationale = (
            f"Tier 4 (no retention data): Insufficient data for conviction{growth_str}. "
            f"Research NDR before acting."
        )

    return VerdictResult(
        ticker=data.ticker, verdict=verdict, confidence='',
        confidence_score=0.0,
        rationale=rationale,
        data_tier=4, missing_signals=missing,
        entry_signals_met=int(entry_signals),
        exit_signals_triggered=int(exit_signals),
    )


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def compute_verdict(data: CompanyData) -> VerdictResult:
    """Compute PLG thesis verdict for a company.

    Routes to the correct tier based on available data,
    then attaches confidence, staleness, and research recommendations.
    """
    # Determine data tier
    tier = _determine_data_tier(data)

    # Route to correct tier logic
    if tier == 1:
        result = _compute_verdict_tier1(data)
    elif tier == 2:
        result = _compute_verdict_tier2(data)
    elif tier == 3:
        result = _compute_verdict_tier3(data)
    else:
        result = _compute_verdict_tier4(data)

    # Attach confidence
    result.confidence_score = calculate_confidence_score(data)
    result.confidence = score_to_confidence_level(result.confidence_score)

    # Attach staleness
    is_stale, stale_fields = check_staleness(data)
    result.staleness_warning = is_stale
    result.stale_fields = stale_fields

    # Attach research recommendations
    result.research_recommendations = recommend_research(data)

    # Attach timestamp
    result.last_updated = datetime.now().isoformat()

    return result


# ============================================================
# DATA FETCHING
# ============================================================

def fetch_yfinance_data(ticker: str) -> dict:
    """Fetch live data from Yahoo Finance.

    Returns dict with market_cap, revenue_ttm, revenue_growth_yoy,
    gross_margin, operating_margin, current_price.
    Empty dict on failure.
    """
    try:
        import yfinance as yf
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
        print(f"    Warning: Could not fetch Yahoo Finance data for {ticker}: {e}")
        return {}


def fetch_sec_edgar_data(ticker: str, cik: str) -> dict:
    """Fetch company facts from SEC EDGAR.

    Returns dict of available financial data from SEC filings.
    Empty dict on failure.
    """
    if not cik:
        return {}

    try:
        import urllib.request
        import json as json_mod

        cik_padded = cik.zfill(10)
        url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik_padded}.json"

        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'PLGAnalyzer/1.0 (research@example.com)')

        with urllib.request.urlopen(req, timeout=10) as response:
            data = json_mod.loads(response.read().decode())

        facts = data.get('facts', {}).get('us-gaap', {})

        result = {}

        # Revenue
        revenue_fact = facts.get('Revenues') or facts.get('RevenueFromContractWithCustomerExcludingAssessedTax')
        if revenue_fact:
            units = revenue_fact.get('units', {}).get('USD', [])
            quarterly = [u for u in units if u.get('form') in ('10-Q', '10-K') and u.get('fp') != 'FY']
            if quarterly:
                latest = sorted(quarterly, key=lambda x: x.get('end', ''))[-1]
                result['latest_revenue'] = latest.get('val')
                result['latest_period'] = latest.get('end')

        return result

    except Exception as e:
        print(f"    Warning: Could not fetch SEC EDGAR data for {ticker}: {e}")
        return {}


# ============================================================
# COMPANY DATABASE I/O
# ============================================================

def load_company_database(path: str = None) -> Dict[str, dict]:
    """Load company database from JSON file.

    Args:
        path: Path to company_database.json. Defaults to same directory as this file.

    Returns:
        Dict mapping ticker -> company info dict.
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'company_database.json')

    with open(path, 'r') as f:
        return json.load(f)


def save_company_database(db: Dict[str, dict], path: str = None) -> None:
    """Save company database to JSON file.

    Args:
        db: Dict mapping ticker -> company info dict.
        path: Path to company_database.json. Defaults to same directory as this file.
    """
    if path is None:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'company_database.json')

    with open(path, 'w') as f:
        json.dump(db, f, indent=2)


def build_company_data(ticker: str, info: dict, yf_data: dict = None) -> CompanyData:
    """Build a CompanyData from database info dict + optional yfinance data.

    Merges manual data from company_database.json with live API data.
    """
    yf_data = yf_data or {}

    return CompanyData(
        ticker=ticker,
        name=info.get('name', ticker),
        cik=info.get('cik', ''),
        category=info.get('category', 'unknown'),
        business_model=info.get('business_model', 'b2b_saas'),

        # Automated (prefer yfinance, fall back to database)
        market_cap=yf_data.get('market_cap'),
        revenue_ttm=yf_data.get('revenue_ttm'),
        revenue_growth_yoy=info.get('revenue_growth_yoy') or yf_data.get('revenue_growth_yoy'),
        gross_margin=yf_data.get('gross_margin'),
        operating_margin=yf_data.get('operating_margin'),
        current_price=yf_data.get('current_price'),

        # Tier 1
        ndr=info.get('ndr'),
        ndr_tier=info.get('ndr_tier', 4),

        # Tier 2
        gross_retention=info.get('gross_retention'),
        dbne=info.get('dbne'),
        large_customer_ndr=info.get('large_customer_ndr'),

        # Tier 3
        implied_expansion=info.get('implied_expansion'),
        rpo_growth_yoy=info.get('rpo_growth_yoy'),

        # Tier 4
        arpu_growth_yoy=info.get('arpu_growth_yoy'),
        active_user_growth_yoy=info.get('active_user_growth_yoy'),
        gmv_growth_yoy=info.get('gmv_growth_yoy'),
        take_rate=info.get('take_rate'),
        take_rate_trend=info.get('take_rate_trend'),
        tpv_growth_yoy=info.get('tpv_growth_yoy'),
        gross_profit_growth_yoy=info.get('gross_profit_growth_yoy'),

        # SaaS
        arr_millions=info.get('arr_millions'),
        customers_100k_plus=info.get('customers_100k_plus'),
        customer_growth_yoy=info.get('customer_growth_yoy'),

        # Assessments (default to 'unknown' if not explicitly set)
        big_tech_threat=info.get('big_tech_threat', 'unknown'),
        category_stage=info.get('category_stage', 'unknown'),
        switching_cost=info.get('switching_cost', 'unknown'),

        # Exit signals
        big_tech_announced=info.get('big_tech_announced', False),
        revenue_decel_3q=info.get('revenue_decel_3q', False),

        # Metadata
        data_as_of=info.get('data_as_of', datetime.now().strftime('%Y-%m-%d')),
        data_updated=info.get('data_updated'),
        notes=info.get('notes', ''),
    )


# ============================================================
# FORMATTING UTILITIES
# ============================================================

def format_verdict(verdict: str) -> str:
    """Format verdict with emoji indicator."""
    emoji_map = {
        'STRONG_BUY': '\u2b50 STRONG BUY',
        'BUY': '\U0001f7e2 BUY',
        'WATCH': '\U0001f7e1 WATCH',
        'SELL': '\U0001f534 SELL',
        'AVOID': '\u26ab AVOID',
    }
    return emoji_map.get(verdict, verdict)


def format_growth(value: Optional[float]) -> str:
    """Format growth value for display."""
    if value is None:
        return "N/A"
    pct = _normalize_growth(value)
    if pct is None:
        return "N/A"
    return f"{pct:.0f}%"


def format_currency(value: Optional[float], billions: bool = True) -> str:
    """Format currency value for display."""
    if value is None:
        return "N/A"
    if billions:
        return f"${value / 1e9:.1f}B"
    return f"${value / 1e6:.0f}M"


def format_confidence(confidence: str, score: float) -> str:
    """Format confidence level with score."""
    return f"{confidence} ({score:.0%})"

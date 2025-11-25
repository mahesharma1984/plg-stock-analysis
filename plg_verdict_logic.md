# PLG Verdict Qualification Logic

## PRINCIPLE

Always issue a verdict. Always flag confidence. The user decides whether to act on low-confidence signals.

---

## 1. CONFIDENCE LEVELS

| Level | Meaning | Action Implication |
|-------|---------|-------------------|
| **HIGH** | Primary signals available, current data | Act with conviction |
| **MEDIUM** | Some signals derived or stale, but pattern clear | Act with caution, verify before large positions |
| **LOW** | Key signals missing or heavily inferred | Treat as hypothesis, requires manual verification |
| **INSUFFICIENT** | Cannot form reasonable verdict | Flag for manual research, no verdict issued |

---

## 2. CONFIDENCE CALCULATION

### Input Weights

```python
SIGNAL_WEIGHTS = {
    # Retention signals (40% total)
    'ndr_tier_1': 0.25,           # Direct NDR disclosure
    'ndr_tier_2': 0.15,           # Variant metric (DBNE, GR, large customer NRR)
    'ndr_tier_3': 0.08,           # Derived/implied expansion
    
    # Growth signals (30% total)
    'revenue_growth_current': 0.15,
    'revenue_growth_trend': 0.10, # 3+ quarters of trajectory data
    'arr_disclosed': 0.05,
    
    # Competitive signals (20% total)
    'big_tech_threat_assessed': 0.10,
    'category_stage_assessed': 0.10,
    
    # Customer signals (10% total)
    'large_customer_count': 0.05,
    'customer_growth_rate': 0.05,
}

def calculate_confidence_score(data: dict) -> float:
    """
    Returns 0.0 - 1.0 confidence score.
    """
    score = 0.0
    
    # NDR - only count highest available tier
    if data.get('ndr') and data.get('ndr_tier') == 1:
        score += SIGNAL_WEIGHTS['ndr_tier_1']
    elif data.get('ndr_variant'):  # DBNE, GR, etc.
        score += SIGNAL_WEIGHTS['ndr_tier_2']
    elif data.get('implied_expansion') is not None:
        score += SIGNAL_WEIGHTS['ndr_tier_3']
    
    # Growth signals
    if data.get('revenue_growth_yoy') is not None:
        score += SIGNAL_WEIGHTS['revenue_growth_current']
    if data.get('revenue_growth_trajectory'):  # 3+ quarters
        score += SIGNAL_WEIGHTS['revenue_growth_trend']
    if data.get('arr') is not None:
        score += SIGNAL_WEIGHTS['arr_disclosed']
    
    # Competitive signals
    if data.get('big_tech_threat_level') is not None:
        score += SIGNAL_WEIGHTS['big_tech_threat_assessed']
    if data.get('category_stage') is not None:
        score += SIGNAL_WEIGHTS['category_stage_assessed']
    
    # Customer signals
    if data.get('customers_100k_plus') is not None:
        score += SIGNAL_WEIGHTS['large_customer_count']
    if data.get('customer_growth_yoy') is not None:
        score += SIGNAL_WEIGHTS['customer_growth_rate']
    
    return score


def score_to_confidence_level(score: float) -> str:
    """
    Map numeric score to confidence level.
    """
    if score >= 0.70:
        return 'HIGH'
    elif score >= 0.45:
        return 'MEDIUM'
    elif score >= 0.25:
        return 'LOW'
    else:
        return 'INSUFFICIENT'
```

---

## 3. VERDICT LOGIC WITH FALLBACKS

### Primary Path (Tier 1 NDR Available)

```python
def compute_verdict_tier1(data: dict) -> tuple[str, str]:
    """
    Full thesis logic when NDR is directly disclosed.
    Returns (verdict, rationale)
    """
    ndr = data['ndr']
    revenue_growth = data['revenue_growth_yoy']
    big_tech_threat = data.get('big_tech_threat_level', 'medium')
    category_stage = data.get('category_stage', 'mid_growth')
    
    # Exit signals first (any 2 = SELL)
    exit_signals = 0
    exit_reasons = []
    
    if ndr < 110:
        exit_signals += 1
        exit_reasons.append(f"NDR {ndr}% below 110% threshold")
    
    if data.get('revenue_decel_3q', False):
        exit_signals += 1
        exit_reasons.append("Revenue decelerating 3+ quarters")
    
    if data.get('big_tech_announced', False):
        exit_signals += 1
        exit_reasons.append("Big Tech bundled competitor announced")
    
    if category_stage == 'commoditizing':
        exit_signals += 1
        exit_reasons.append("Category commoditizing")
    
    if exit_signals >= 2:
        return ('SELL', '; '.join(exit_reasons))
    
    if exit_signals == 1:
        return ('WATCH', f"Warning: {exit_reasons[0]}")
    
    # Entry signals (all 5 for STRONG BUY, 4 for BUY)
    entry_signals = 0
    
    if ndr >= 110:
        entry_signals += 1
    if revenue_growth >= 25:
        entry_signals += 1
    if category_stage in ['emerging', 'early_growth', 'mid_growth']:
        entry_signals += 1
    if big_tech_threat in ['low', 'medium']:
        entry_signals += 1
    if data.get('switching_cost_level') in ['medium', 'high']:
        entry_signals += 1
    
    # Elite tier
    if ndr >= 120 and revenue_growth >= 30:
        return ('STRONG_BUY', f"Elite metrics: NDR {ndr}%, growth {revenue_growth}%")
    
    if entry_signals >= 5:
        return ('STRONG_BUY', f"All 5 entry signals met")
    elif entry_signals >= 4:
        return ('BUY', f"{entry_signals}/5 entry signals met")
    elif entry_signals >= 3:
        return ('WATCH', f"Only {entry_signals}/5 entry signals")
    else:
        return ('AVOID', f"Only {entry_signals}/5 entry signals")
```

### Fallback Path (Tier 2 - Variant Metrics)

```python
def compute_verdict_tier2(data: dict) -> tuple[str, str]:
    """
    When only DBNE, GR, or large-customer NRR available.
    Apply adjusted thresholds.
    """
    
    # Gross Retention interpretation
    if data.get('gross_retention'):
        gr = data['gross_retention']
        # GR > 95% typically indicates healthy base
        # GR > 90% acceptable for high-growth
        # GR < 90% = churn problem
        
        if gr >= 97:
            retention_signal = 'strong'
        elif gr >= 93:
            retention_signal = 'healthy'
        elif gr >= 90:
            retention_signal = 'acceptable'
        else:
            retention_signal = 'weak'
    
    # DBNE interpretation (Twilio-style)
    elif data.get('dbne'):
        dbne = data['dbne']
        # DBNE is roughly equivalent to NDR
        if dbne >= 120:
            retention_signal = 'strong'
        elif dbne >= 110:
            retention_signal = 'healthy'
        elif dbne >= 100:
            retention_signal = 'acceptable'
        else:
            retention_signal = 'weak'
    
    # Large customer NRR only
    elif data.get('large_customer_ndr'):
        lc_ndr = data['large_customer_ndr']
        # Large customers typically have HIGHER retention
        # So thresholds should be stricter
        if lc_ndr >= 125:
            retention_signal = 'strong'
        elif lc_ndr >= 115:
            retention_signal = 'healthy'
        elif lc_ndr >= 105:
            retention_signal = 'acceptable'
        else:
            retention_signal = 'weak'
    else:
        retention_signal = 'unknown'
    
    # Combine with revenue growth
    revenue_growth = data.get('revenue_growth_yoy', 0)
    
    if retention_signal == 'weak':
        return ('SELL', f"Retention signal weak, growth {revenue_growth}%")
    
    if retention_signal == 'strong' and revenue_growth >= 25:
        return ('BUY', f"Strong retention signal, {revenue_growth}% growth (Tier 2 data)")
    
    if retention_signal in ['healthy', 'strong'] and revenue_growth >= 20:
        return ('WATCH', f"Positive signals but Tier 2 data - verify NDR")
    
    return ('WATCH', f"Incomplete retention data - manual review needed")
```

### Fallback Path (Tier 3 - Derived Signals)

```python
def compute_verdict_tier3(data: dict) -> tuple[str, str]:
    """
    When only implied expansion available (ARR growth vs customer growth).
    Lower confidence, wider uncertainty bands.
    """
    
    implied_expansion = data.get('implied_expansion')  # ARR growth - customer growth
    revenue_growth = data.get('revenue_growth_yoy', 0)
    rpo_growth = data.get('rpo_growth_yoy')
    
    signals = []
    
    # Implied expansion interpretation
    if implied_expansion is not None:
        if implied_expansion > 15:
            signals.append(('expansion', 'strong'))
        elif implied_expansion > 5:
            signals.append(('expansion', 'healthy'))
        elif implied_expansion > 0:
            signals.append(('expansion', 'modest'))
        else:
            signals.append(('expansion', 'negative'))
    
    # RPO as forward indicator
    if rpo_growth is not None:
        if rpo_growth > revenue_growth + 10:
            signals.append(('forward_demand', 'accelerating'))
        elif rpo_growth > revenue_growth:
            signals.append(('forward_demand', 'healthy'))
        else:
            signals.append(('forward_demand', 'decelerating'))
    
    # Very conservative verdicts at Tier 3
    expansion_signal = next((s[1] for s in signals if s[0] == 'expansion'), 'unknown')
    
    if expansion_signal == 'negative':
        return ('SELL', f"Implied contraction (Tier 3 - verify)")
    
    if expansion_signal == 'strong' and revenue_growth >= 25:
        return ('WATCH', f"Positive derived signals - needs Tier 1/2 verification")
    
    return ('WATCH', f"Tier 3 data only - manual research required")
```

### Alternative Path (Tier 4 - Non-SaaS Models)

```python
def compute_verdict_tier4(data: dict) -> tuple[str, str]:
    """
    Consumer, marketplace, or transaction-based models.
    NDR concept doesn't apply; use alternative signals.
    """
    
    business_model = data.get('business_model')
    
    if business_model == 'consumer':
        # Use ARPU and user metrics
        arpu_growth = data.get('arpu_growth_yoy', 0)
        user_growth = data.get('active_user_growth_yoy', 0)
        revenue_growth = data.get('revenue_growth_yoy', 0)
        
        if arpu_growth > 20 and user_growth > 15:
            return ('BUY', f"Strong unit economics: ARPU +{arpu_growth}%, users +{user_growth}%")
        elif revenue_growth > 30:
            return ('WATCH', f"High growth ({revenue_growth}%) but verify unit economics")
        elif arpu_growth < 0:
            return ('SELL', f"ARPU declining - monetization pressure")
        else:
            return ('WATCH', f"Consumer model - requires different analysis")
    
    elif business_model == 'marketplace':
        # Use GMV and take rate
        gmv_growth = data.get('gmv_growth_yoy', 0)
        take_rate = data.get('take_rate')
        take_rate_trend = data.get('take_rate_trend')  # 'stable', 'increasing', 'decreasing'
        
        if gmv_growth > 25 and take_rate_trend != 'decreasing':
            return ('BUY', f"GMV +{gmv_growth}%, take rate stable")
        elif take_rate_trend == 'decreasing':
            return ('WATCH', f"Take rate pressure - commoditization risk")
        else:
            return ('WATCH', f"Marketplace model - requires different analysis")
    
    elif business_model == 'transaction_based':
        # Use TPV and gross profit per transaction
        tpv_growth = data.get('tpv_growth_yoy', 0)
        gross_profit_growth = data.get('gross_profit_growth_yoy', 0)
        
        if gross_profit_growth > tpv_growth:
            return ('WATCH', f"Improving unit economics - verify sustainability")
        elif gross_profit_growth < tpv_growth - 10:
            return ('SELL', f"Margin compression - commoditizing")
        else:
            return ('WATCH', f"Transaction model - requires different analysis")
    
    return ('WATCH', f"Non-standard model - manual analysis required")
```

---

## 4. VERDICT OUTPUT FORMAT

```python
@dataclass
class VerdictResult:
    ticker: str
    verdict: str                    # STRONG_BUY, BUY, WATCH, SELL, AVOID
    confidence: str                 # HIGH, MEDIUM, LOW, INSUFFICIENT
    confidence_score: float         # 0.0 - 1.0
    rationale: str                  # Human-readable explanation
    data_tier: int                  # 1, 2, 3, or 4
    missing_signals: list[str]      # What data would improve confidence
    last_updated: datetime
    staleness_warning: bool         # True if key data > 100 days old


def format_verdict(result: VerdictResult) -> str:
    """
    Human-readable verdict with qualification.
    """
    confidence_emoji = {
        'HIGH': '🟢',
        'MEDIUM': '🟡', 
        'LOW': '🟠',
        'INSUFFICIENT': '🔴'
    }
    
    verdict_emoji = {
        'STRONG_BUY': '🟢',
        'BUY': '🟢',
        'WATCH': '🟡',
        'SELL': '🔴',
        'AVOID': '🔴'
    }
    
    output = f"""
{result.ticker}: {verdict_emoji.get(result.verdict, '')} {result.verdict}
Confidence: {confidence_emoji.get(result.confidence, '')} {result.confidence} ({result.confidence_score:.0%})
Data Tier: {result.data_tier}
Rationale: {result.rationale}
"""
    
    if result.missing_signals:
        output += f"Missing: {', '.join(result.missing_signals)}\n"
    
    if result.staleness_warning:
        output += f"⚠️ Data may be stale (>{100} days old)\n"
    
    return output.strip()
```

---

## 5. CONFIDENCE DEGRADATION EXAMPLES

| Company | Data Available | Data Tier | Confidence | Verdict |
|---------|---------------|-----------|------------|---------|
| Snowflake | NDR 127%, growth 29%, all signals | Tier 1 | HIGH (92%) | STRONG_BUY |
| MongoDB | NDR 119%, growth 24%, full data | Tier 1 | HIGH (85%) | BUY |
| CrowdStrike | GR 97% only, NDR not disclosed | Tier 2 | MEDIUM (55%) | WATCH (verify NDR) |
| Toast | No retention metrics, growth 25% | Tier 4 | LOW (35%) | WATCH (different model) |
| Affirm | Consumer model, ARPU +34% | Tier 4 | MEDIUM (48%) | WATCH (consumer signals positive) |
| SentinelOne | NDR not disclosed, growth 28% | Tier 3 | LOW (40%) | WATCH (needs verification) |

---

## 6. MISSING SIGNAL RECOMMENDATIONS

```python
def recommend_research(data: dict) -> list[str]:
    """
    Based on missing data, tell user what to look for.
    """
    recommendations = []
    
    if data.get('ndr') is None and data.get('ndr_variant') is None:
        recommendations.append("Find NDR/NRR in earnings call transcript or investor presentation")
    
    if data.get('gross_retention') is None and data.get('ndr') is None:
        recommendations.append("Look for gross retention rate as NDR proxy")
    
    if data.get('customers_100k_plus') is None:
        recommendations.append("Find $100K+ customer count for enterprise traction signal")
    
    if data.get('big_tech_threat_level') is None:
        recommendations.append("Assess Big Tech bundling risk manually")
    
    if data.get('revenue_growth_trajectory') is None:
        recommendations.append("Pull 4+ quarters of revenue to assess trajectory")
    
    return recommendations
```

---

## 7. STALENESS RULES

```python
def check_staleness(data: dict, current_date: date) -> dict:
    """
    Flag stale data that may invalidate verdict.
    """
    warnings = {}
    
    # Financials stale after ~100 days (1 quarter + buffer)
    if data.get('financials_date'):
        days_old = (current_date - data['financials_date']).days
        if days_old > 100:
            warnings['financials'] = f"Financials {days_old} days old"
    
    # NDR can be stale faster if company is transitioning
    if data.get('ndr_date'):
        days_old = (current_date - data['ndr_date']).days
        if days_old > 100:
            warnings['ndr'] = f"NDR {days_old} days old - verify current quarter"
    
    # Competitive assessment needs review every 6 months
    if data.get('competitive_date'):
        days_old = (current_date - data['competitive_date']).days
        if days_old > 180:
            warnings['competitive'] = f"Competitive assessment {days_old} days old"
    
    return warnings
```

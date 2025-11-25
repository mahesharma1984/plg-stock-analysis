# PLG Analysis Data Schema & Sourcing Strategy

## 1. ENTITY STRUCTURE

### Company Profile (Static - Updated Quarterly)
```
company:
  ticker: string (primary key)
  name: string
  category: enum [security, observability, developer_tools, collaboration, 
                  vertical_saas, fintech, automation, infrastructure]
  subcategory: string (e.g., "endpoint_security", "event_streaming")
  business_model: enum [b2b_saas, consumer, marketplace, transaction_based, hybrid]
  plg_purity: enum [pure_plg, plg_assisted, sales_led_with_plg, not_plg]
  market_cap_usd: float
  fiscal_year_end: string (month)
  reporting_currency: string
```

### Financials (Time Series - Quarterly)
```
financials:
  ticker: string (foreign key)
  period: string (e.g., "Q2_FY2026")
  period_end_date: date
  
  # Revenue Metrics
  revenue_total: float
  revenue_subscription: float | null
  revenue_cloud: float | null (for hybrid cloud/on-prem)
  revenue_growth_yoy: float (%)
  revenue_growth_qoq: float (%)
  
  # ARR/Bookings
  arr: float | null
  arr_growth_yoy: float (%) | null
  net_new_arr: float | null
  rpo: float | null (Remaining Performance Obligations)
  rpo_growth_yoy: float (%) | null
  crpo: float | null (Current RPO)
  
  # Profitability
  gross_margin: float (%)
  operating_margin_gaap: float (%)
  operating_margin_non_gaap: float (%)
  fcf: float
  fcf_margin: float (%)
```

### Retention Metrics (Time Series - Quarterly)
```
retention:
  ticker: string
  period: string
  
  # Tier 1: Direct NDR Disclosure
  ndr: float (%) | null
  ndr_label: string | null (companies use different names)
  
  # Tier 2: Variant Metrics
  dbne: float (%) | null (Dollar-Based Net Expansion - Twilio)
  gross_retention: float (%) | null
  logo_retention: float (%) | null
  large_customer_ndr: float (%) | null (e.g., $500K+ cohort)
  large_customer_ndr_threshold: string | null (e.g., "$500K ARR")
  
  # Tier 3: Derived Signals
  implied_expansion: float (%) | null (calculated: arr_growth - customer_growth)
  cohort_expansion_disclosed: boolean
  
  # Metadata
  ndr_data_tier: enum [tier_1, tier_2, tier_3, tier_4]
  ndr_confidence: enum [high, medium, low, not_applicable]
```

### Customer Metrics (Time Series - Quarterly)
```
customers:
  ticker: string
  period: string
  
  # Counts
  total_customers: int | null
  paying_customers: int | null
  customers_100k_plus: int | null
  customers_1m_plus: int | null
  
  # Growth
  customer_growth_yoy: float (%) | null
  large_customer_growth_yoy: float (%) | null
  net_customer_adds: int | null
  
  # Concentration
  arr_from_large_customers: float | null
  arr_from_large_customers_pct: float (%) | null
```

### Competitive Position (Static - Updated Quarterly)
```
competitive:
  ticker: string
  as_of_date: date
  
  # Big Tech Threat
  big_tech_threat_level: enum [low, medium, medium_high, high, very_high]
  big_tech_competitors: list[string] (e.g., ["Microsoft Defender", "AWS Security Hub"])
  bundling_risk: enum [low, medium, high]
  
  # Category Dynamics
  category_stage: enum [emerging, early_growth, mid_growth, mature, commoditizing]
  feature_parity_with_competitors: enum [low, medium, high]
  switching_cost_level: enum [low, medium, high]
  
  # Moat Factors
  has_network_effects: boolean
  has_data_moat: boolean
  has_platform_ecosystem: boolean
  multi_cloud_positioning: boolean
```

### Thesis Signals (Computed)
```
signals:
  ticker: string
  period: string
  computed_at: datetime
  
  # Entry Signals (all 5 required for BUY)
  signal_ndr_above_110: boolean | null
  signal_ndr_above_110_confidence: enum [high, medium, low, not_applicable]
  signal_revenue_growth_above_25: boolean
  signal_category_expanding: boolean
  signal_no_big_tech_bundle: boolean
  signal_high_switching_costs: boolean
  
  # Exit Signals (any 2 = SELL)
  signal_ndr_below_110_2q: boolean | null
  signal_revenue_decel_3q: boolean
  signal_big_tech_announced: boolean
  signal_feature_parity_3plus: boolean
  signal_margin_compression: boolean
  
  # Composite
  entry_signals_met: int (0-5)
  exit_signals_triggered: int (0-5)
  data_completeness_score: float (0-1)
  
  # Verdict
  verdict: enum [strong_buy, buy, watch, sell, avoid, insufficient_data]
  verdict_confidence: enum [high, medium, low]
```

---

## 2. DATA SOURCING STRATEGY

### Source Hierarchy (by reliability)

| Priority | Source | Data Available | Update Frequency | Access Method |
|----------|--------|----------------|------------------|---------------|
| 1 | Earnings Call Transcripts | NDR, qualitative signals, forward guidance | Quarterly | Seeking Alpha API, manual |
| 2 | Investor Presentations | Cohort data, customer metrics, segmented ARR | Quarterly | Company IR sites |
| 3 | SEC Filings (10-K, 10-Q) | Revenue, customers, RPO, standardized metrics | Quarterly | SEC EDGAR API |
| 4 | Press Releases | Headline metrics (revenue, ARR) | Quarterly | News APIs |
| 5 | Financial APIs | Price, market cap, basic financials | Daily | Yahoo Finance, Alpha Vantage |

### Field-to-Source Mapping

```yaml
# TIER 1 - Direct Disclosure (High Confidence)
ndr:
  primary_source: earnings_call_transcript
  secondary_source: investor_presentation
  extraction_method: regex_pattern + manual_verification
  patterns:
    - "net dollar retention"
    - "net revenue retention"
    - "NRR"
    - "NDR"
    - "dollar-based net expansion"
  notes: "Companies use different terminology; normalize to single metric"

revenue_total:
  primary_source: sec_10q
  secondary_source: press_release
  extraction_method: api (structured)
  
arr:
  primary_source: investor_presentation
  secondary_source: earnings_call_transcript
  extraction_method: regex_pattern
  notes: "Not all companies disclose ARR; some only disclose subscription revenue"

# TIER 2 - Variant Metrics (Medium Confidence)
gross_retention:
  primary_source: earnings_call_transcript
  secondary_source: investor_presentation
  extraction_method: regex_pattern
  patterns:
    - "gross retention"
    - "gross dollar retention"
    - "GRR"
  derivation_if_missing: null (cannot derive)

dbne:
  primary_source: earnings_call_transcript
  extraction_method: regex_pattern
  notes: "Twilio-specific terminology"

large_customer_ndr:
  primary_source: investor_presentation
  extraction_method: manual
  notes: "Often disclosed for $100K+ or $500K+ cohorts when overall NDR is weak"

# TIER 3 - Derived/Inferred (Lower Confidence)
implied_expansion:
  derivation: arr_growth_yoy - customer_growth_yoy
  required_inputs: [arr, arr_growth_yoy, total_customers, customer_growth_yoy]
  confidence: medium
  notes: "Positive value indicates expansion; negative indicates contraction"

rpo_to_revenue_ratio:
  derivation: rpo / (revenue_total * 4)  # annualized
  required_inputs: [rpo, revenue_total]
  confidence: medium
  notes: "Ratio > 1 indicates strong forward demand"

# TIER 4 - Not Applicable
# For consumer/marketplace/transaction models, define alternative signals:
alternative_signals:
  consumer:
    - arpu (Average Revenue Per User)
    - arpu_growth_yoy
    - active_users
    - user_retention_rate
  marketplace:
    - gmv (Gross Merchandise Value)
    - take_rate
    - repeat_purchase_rate
  transaction_based:
    - tpv (Total Payment Volume)
    - transactions_per_user
    - gross_profit_per_transaction
```

### Extraction Patterns

```python
# NDR Extraction Patterns (for earnings call parsing)
NDR_PATTERNS = [
    r"net\s+dollar\s+retention\s+(?:rate\s+)?(?:of\s+)?(\d{2,3})%?",
    r"net\s+revenue\s+retention\s+(?:of\s+)?(\d{2,3})%?",
    r"NRR\s+(?:of\s+)?(\d{2,3})%?",
    r"NDR\s+(?:of\s+)?(\d{2,3})%?",
    r"dollar[- ]based\s+net\s+expansion\s+(?:rate\s+)?(?:of\s+)?(\d{2,3})%?",
    r"DBNE\s+(?:of\s+)?(\d{2,3})%?",
]

# Gross Retention Patterns
GR_PATTERNS = [
    r"gross\s+(?:dollar\s+)?retention\s+(?:rate\s+)?(?:of\s+)?(\d{2,3})%?",
    r"GRR\s+(?:of\s+)?(\d{2,3})%?",
]

# Large Customer Count Patterns
LARGE_CUSTOMER_PATTERNS = [
    r"(\d{1,3}(?:,\d{3})*)\s+customers?\s+(?:spending|with)\s+(?:more\s+than\s+)?\$?100[Kk]",
    r"\$100[Kk]\+?\s+(?:ARR\s+)?customers?:?\s+(\d{1,3}(?:,\d{3})*)",
    r"(\d{1,3}(?:,\d{3})*)\s+customers?\s+above\s+\$1[Mm]",
]
```

---

## 3. DATA QUALITY FLAGS

### Completeness Scoring

```python
def calculate_data_completeness(company_data: dict) -> float:
    """
    Score 0-1 based on availability of key decision inputs.
    Weighted by importance to thesis.
    """
    weights = {
        'ndr': 0.25,                    # Most important signal
        'revenue_growth_yoy': 0.20,     # Second most important
        'gross_retention': 0.10,        # Useful fallback
        'arr': 0.10,
        'customers_100k_plus': 0.10,
        'big_tech_threat_level': 0.10,
        'category_stage': 0.10,
        'fcf_margin': 0.05,
    }
    
    score = 0.0
    for field, weight in weights.items():
        if company_data.get(field) is not None:
            score += weight
    
    return score
```

### Confidence Degradation Rules

| Scenario | NDR Confidence | Verdict Confidence |
|----------|----------------|-------------------|
| NDR directly disclosed, current quarter | High | High |
| NDR disclosed, but 2+ quarters old | Medium | Medium |
| Only gross retention available | Medium | Medium |
| Only implied expansion (derived) | Low | Low |
| Consumer/marketplace model (NDR N/A) | Not Applicable | Depends on alt signals |
| No retention metrics available | Not Applicable | Low |

---

## 4. UPDATE CADENCE

| Data Type | Update Trigger | Staleness Threshold |
|-----------|---------------|---------------------|
| Financials | Earnings release | >100 days = stale |
| NDR/Retention | Earnings call | >100 days = stale |
| Customer counts | Earnings release | >100 days = stale |
| Competitive position | Manual review | >180 days = review needed |
| Big Tech threats | News monitoring | Continuous |
| Market cap | Daily | >1 day = stale |

---

## 5. INITIAL DATA POPULATION

### Companies to Track (from thesis documents)

```yaml
security:
  - ticker: CRWD
    name: CrowdStrike
    ndr_availability: tier_1
  - ticker: S
    name: SentinelOne
    ndr_availability: tier_4  # Not disclosed
  - ticker: ZS
    name: Zscaler
    ndr_availability: tier_1
  - ticker: RBRK
    name: Rubrik
    ndr_availability: tier_1

observability:
  - ticker: DDOG
    name: Datadog
    ndr_availability: tier_2  # Approximate only
  - ticker: DT
    name: Dynatrace
    ndr_availability: tier_1

developer_tools:
  - ticker: MDB
    name: MongoDB
    ndr_availability: tier_1
  - ticker: CFLT
    name: Confluent
    ndr_availability: tier_1
  - ticker: GTLB
    name: GitLab
    ndr_availability: tier_1
  - ticker: FROG
    name: JFrog
    ndr_availability: tier_2

infrastructure:
  - ticker: NET
    name: Cloudflare
    ndr_availability: tier_1
  - ticker: SNOW
    name: Snowflake
    ndr_availability: tier_1
  - ticker: DOCN
    name: DigitalOcean
    ndr_availability: tier_1

collaboration:
  - ticker: ASAN
    name: Asana
    ndr_availability: tier_1
  - ticker: MNDY
    name: Monday.com
    ndr_availability: tier_1

vertical_saas:
  - ticker: TOST
    name: Toast
    ndr_availability: tier_4  # Not disclosed
  - ticker: IOT
    name: Samsara
    ndr_availability: tier_4  # Not disclosed
  - ticker: PCOR
    name: Procore
    ndr_availability: tier_1

fintech:
  - ticker: BILL
    name: Bill.com
    ndr_availability: tier_1
  - ticker: AFRM
    name: Affirm
    ndr_availability: tier_4  # Consumer model
  - ticker: SQ
    name: Block
    ndr_availability: tier_4  # Transaction model

automation:
  - ticker: PATH
    name: UiPath
    ndr_availability: tier_1

marketing:
  - ticker: BRZE
    name: Braze
    ndr_availability: tier_1
  - ticker: ZI
    name: ZoomInfo
    ndr_availability: tier_1
  - ticker: TWLO
    name: Twilio
    ndr_availability: tier_2  # DBNE variant

mature_decline:
  - ticker: ZM
    name: Zoom
    ndr_availability: tier_1
  - ticker: DBX
    name: Dropbox
    ndr_availability: tier_1
  - ticker: DOCU
    name: DocuSign
    ndr_availability: tier_1
```

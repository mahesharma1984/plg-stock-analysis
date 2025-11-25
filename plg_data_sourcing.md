# PLG Data Sourcing Strategy - Practical Implementation

## THE REALITY

**NDR and SaaS-specific metrics (ARR, NRR, GRR) are NOT available through standard financial APIs.**

These are non-GAAP metrics that companies voluntarily disclose in:
- Earnings call transcripts (spoken, not structured)
- Investor presentations (PDFs, slides)
- Press releases (unstructured text)
- Occasionally in 10-K/10-Q MD&A sections (buried in prose)

This means: **Automated extraction requires NLP/parsing, not simple API calls.**

---

## 1. DATA SOURCE MATRIX

| Data Type | Best Source | API Available? | Cost | Extraction Method |
|-----------|-------------|----------------|------|-------------------|
| **Stock price, market cap** | Yahoo Finance / FMP | ✅ Yes (free tier) | Free | Direct API |
| **Revenue (quarterly)** | SEC EDGAR / FMP | ✅ Yes | Free-$30/mo | Direct API (XBRL) |
| **Revenue growth YoY** | Derived from revenue | ✅ Yes | Free | Calculate from API data |
| **Gross margin** | SEC EDGAR (XBRL) | ✅ Yes | Free | Direct API |
| **Operating margin** | SEC EDGAR (XBRL) | ✅ Yes | Free | Direct API |
| **NDR/NRR** | Earnings transcripts | ❌ No structured API | $240-500/yr | NLP extraction |
| **ARR** | Earnings transcripts/IR | ❌ No structured API | $240-500/yr | NLP extraction |
| **Gross retention** | Earnings transcripts | ❌ No structured API | $240-500/yr | NLP extraction |
| **Customer counts ($100K+)** | Earnings transcripts/IR | ❌ No structured API | $240-500/yr | NLP extraction |
| **RPO** | 10-K/10-Q footnotes | ⚠️ Partial (XBRL) | Free | XBRL + parsing |
| **Big Tech threat** | News + analysis | ❌ No | Manual | Human judgment |
| **Category stage** | Analysis | ❌ No | Manual | Human judgment |

---

## 2. TIERED SOURCING APPROACH

### TIER A: Automated via API (High Reliability)

**Sources:**
- Financial Modeling Prep (FMP): https://financialmodelingprep.com
  - Free tier: 250 requests/day
  - Starter: $14/month (unlimited)
  - Revenue, EPS, margins, ratios, SEC filings list
  
- Alpha Vantage: https://alphavantage.co
  - Free tier: 25 requests/day
  - Premium: $50/month
  - Stock prices, fundamentals, technical indicators

- SEC EDGAR (Official): https://data.sec.gov
  - Free, no API key needed
  - XBRL financial statements
  - Bulk download available

**Python packages:**
```python
# Financial data
import yfinance as yf  # Free, unofficial Yahoo Finance
from sec_api import QueryApi, ExtractorApi  # Paid, $40-100/mo

# SEC EDGAR direct (free)
import requests
# https://data.sec.gov/submissions/CIK##########.json
```

**Fields available:**
```yaml
automated_fields:
  - ticker
  - market_cap
  - revenue_quarterly
  - revenue_annual
  - gross_profit
  - operating_income
  - net_income
  - eps
  - shares_outstanding
  - total_assets
  - total_liabilities
  - cash_and_equivalents
  - stock_price_daily
```

### TIER B: Semi-Automated (Earnings Transcripts + NLP)

**The NDR Problem:**
NDR is disclosed verbally in earnings calls, not in structured filings. To extract it programmatically:

**Option 1: Paid Transcript Service + LLM Extraction**

Sources:
- Seeking Alpha Premium: $239/year
  - Transcripts for ~4,500 US companies
  - No API, must scrape or manually download
  
- Koyfin: Free tier available
  - 9,000+ companies globally
  - Some transcript access
  
- Financial Modeling Prep: $30+/month
  - Earnings call transcripts endpoint
  - API access to transcript text

**Extraction approach:**
```python
# Concept: Use LLM to extract NDR from transcript text

def extract_ndr_from_transcript(transcript_text: str) -> dict:
    """
    Use Claude/GPT to extract NDR from earnings call text.
    """
    prompt = """
    Extract the following metrics from this earnings call transcript.
    Return JSON with these fields (null if not mentioned):
    - ndr: Net Dollar Retention (as percentage, e.g., 115)
    - ndr_label: What they called it (e.g., "net revenue retention")
    - gross_retention: Gross Dollar Retention (as percentage)
    - arr: Annual Recurring Revenue (in millions USD)
    - customers_100k_plus: Number of customers over $100K ARR
    - customers_1m_plus: Number of customers over $1M ARR
    
    Transcript:
    {transcript_text}
    """
    
    # Call Claude API
    response = anthropic.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}]
    )
    
    return json.loads(response.content[0].text)
```

**Cost estimate for 40 companies, quarterly:**
- Transcript access: $30-240/year
- Claude API calls: ~$0.50/company/quarter = ~$80/year
- Total: ~$110-320/year

**Option 2: Manual Extraction + Spreadsheet**

For a universe of 40 companies, manual extraction is viable:
- Time: ~15 min/company/quarter = 10 hours/quarter
- Use standardized template
- Source: Free transcripts from Seeking Alpha (limited), company IR pages

### TIER C: Manual Research (Competitive/Qualitative)

**Fields requiring human judgment:**
```yaml
manual_fields:
  - big_tech_threat_level: [low, medium, medium_high, high, very_high]
  - category_stage: [emerging, early_growth, mid_growth, mature, commoditizing]
  - bundling_risk: [low, medium, high]
  - switching_cost_level: [low, medium, high]
  - feature_parity_with_competitors: [low, medium, high]
```

**Process:**
1. Review industry news quarterly
2. Monitor Big Tech product announcements
3. Update competitive position assessments
4. Document reasoning for audit trail

---

## 3. RECOMMENDED ARCHITECTURE

### Minimum Viable System (Budget: Free-$50/month)

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA COLLECTION                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  Yahoo       │    │  SEC EDGAR   │    │  Manual      │  │
│  │  Finance     │    │  (Free API)  │    │  Entry       │  │
│  │  (yfinance)  │    │              │    │  (Google     │  │
│  │              │    │              │    │  Sheets)     │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                   │                   │          │
│         ▼                   ▼                   ▼          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Google Sheets / Airtable               │   │
│  │                 (Central Data Store)                │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                               │
│                            ▼                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Python Verdict Calculator              │   │
│  │        (Applies thesis logic, outputs scores)       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘

Data Sources:
- yfinance: Stock price, market cap (free, rate-limited)
- SEC EDGAR: Revenue from 10-K/10-Q XBRL (free)
- Manual: NDR, ARR, customer counts, competitive position
```

**Workflow:**
1. Weekly: Python script pulls stock prices, market caps
2. Quarterly: After earnings, manually update NDR/ARR from transcripts
3. Quarterly: Run verdict calculator, generate report

### Enhanced System (Budget: $100-300/month)

```
┌─────────────────────────────────────────────────────────────┐
│                     DATA COLLECTION                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │  FMP API     │    │  FMP         │    │  Claude API  │  │
│  │  ($30/mo)    │    │  Transcripts │    │  (LLM        │  │
│  │  Financials  │    │  ($30/mo)    │    │  Extraction) │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                   │                   │          │
│         ▼                   ▼                   ▼          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              PostgreSQL / SQLite                    │   │
│  │                 (Structured Storage)                │   │
│  └─────────────────────────────────────────────────────┘   │
│                            │                               │
│                            ▼                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Automated Pipeline                     │   │
│  │   1. Fetch financials (API)                        │   │
│  │   2. Fetch transcripts (API)                       │   │
│  │   3. Extract SaaS metrics (LLM)                    │   │
│  │   4. Calculate verdicts                            │   │
│  │   5. Generate alerts                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. SPECIFIC API ENDPOINTS

### Financial Modeling Prep (Recommended for Financials)

```python
import requests

API_KEY = "your_api_key"
BASE_URL = "https://financialmodelingprep.com/api/v3"

# Income statement (quarterly)
def get_income_statement(ticker: str, period: str = "quarter", limit: int = 8):
    url = f"{BASE_URL}/income-statement/{ticker}"
    params = {"period": period, "limit": limit, "apikey": API_KEY}
    response = requests.get(url, params=params)
    return response.json()

# Key metrics (includes some growth rates)
def get_key_metrics(ticker: str, period: str = "quarter", limit: int = 8):
    url = f"{BASE_URL}/key-metrics/{ticker}"
    params = {"period": period, "limit": limit, "apikey": API_KEY}
    response = requests.get(url, params=params)
    return response.json()

# Earnings call transcript (if available)
def get_transcript(ticker: str, year: int, quarter: int):
    url = f"{BASE_URL}/earning_call_transcript/{ticker}"
    params = {"year": year, "quarter": quarter, "apikey": API_KEY}
    response = requests.get(url, params=params)
    return response.json()

# Company profile (market cap, sector, etc.)
def get_profile(ticker: str):
    url = f"{BASE_URL}/profile/{ticker}"
    params = {"apikey": API_KEY}
    response = requests.get(url, params=params)
    return response.json()
```

### SEC EDGAR Direct (Free)

```python
import requests

def get_company_facts(cik: str) -> dict:
    """
    Get all XBRL facts for a company.
    CIK must be 10 digits with leading zeros.
    """
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
    headers = {"User-Agent": "YourApp your@email.com"}
    response = requests.get(url, headers=headers)
    return response.json()

def get_submissions(cik: str) -> dict:
    """
    Get filing history for a company.
    """
    url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    headers = {"User-Agent": "YourApp your@email.com"}
    response = requests.get(url, headers=headers)
    return response.json()

# Example: Extract revenue from XBRL
def get_revenue_history(company_facts: dict) -> list:
    """
    Extract quarterly revenue from company facts.
    """
    try:
        revenues = company_facts['facts']['us-gaap']['Revenues']['units']['USD']
        # Filter for quarterly (10-Q) filings
        quarterly = [r for r in revenues if r.get('form') == '10-Q']
        return quarterly
    except KeyError:
        # Try alternative revenue labels
        try:
            revenues = company_facts['facts']['us-gaap']['RevenueFromContractWithCustomerExcludingAssessedTax']['units']['USD']
            return [r for r in revenues if r.get('form') == '10-Q']
        except KeyError:
            return []
```

### Yahoo Finance (Free, Unofficial)

```python
import yfinance as yf

def get_company_data(ticker: str) -> dict:
    """
    Get key financial data from Yahoo Finance.
    """
    stock = yf.Ticker(ticker)
    
    return {
        'market_cap': stock.info.get('marketCap'),
        'revenue_ttm': stock.info.get('totalRevenue'),
        'gross_margin': stock.info.get('grossMargins'),
        'operating_margin': stock.info.get('operatingMargins'),
        'profit_margin': stock.info.get('profitMargins'),
        'current_price': stock.info.get('currentPrice'),
        'forward_pe': stock.info.get('forwardPE'),
        'trailing_pe': stock.info.get('trailingPE'),
        'revenue_growth': stock.info.get('revenueGrowth'),
        'earnings_growth': stock.info.get('earningsGrowth'),
    }

def get_quarterly_financials(ticker: str) -> dict:
    """
    Get quarterly income statement.
    """
    stock = yf.Ticker(ticker)
    return stock.quarterly_income_stmt.to_dict()
```

---

## 5. NDR EXTRACTION STRATEGY

### Pattern Matching Approach

```python
import re

NDR_PATTERNS = [
    # Direct NDR/NRR mentions
    r"net\s+(?:dollar|revenue)\s+retention\s+(?:rate\s+)?(?:of\s+)?(?:was\s+)?(\d{2,3})%?",
    r"(?:NDR|NRR)\s+(?:of\s+)?(?:was\s+)?(\d{2,3})%?",
    r"dollar[- ]based\s+net\s+(?:expansion|retention)\s+(?:rate\s+)?(?:of\s+)?(\d{2,3})%?",
    r"DBNE\s+(?:of\s+)?(?:was\s+)?(\d{2,3})%?",
    
    # Contextual mentions
    r"retention\s+rate\s+(?:of\s+)?(\d{2,3})%?\s+(?:for|in|during)",
    r"(\d{2,3})%?\s+(?:net\s+)?(?:dollar\s+)?retention",
]

GROSS_RETENTION_PATTERNS = [
    r"gross\s+(?:dollar\s+)?retention\s+(?:rate\s+)?(?:of\s+)?(\d{2,3})%?",
    r"GRR\s+(?:of\s+)?(?:was\s+)?(\d{2,3})%?",
    r"gross\s+retention\s+(?:remained|stayed|at)\s+(\d{2,3})%?",
]

ARR_PATTERNS = [
    r"(?:annual\s+recurring\s+revenue|ARR)\s+(?:of\s+)?(?:was\s+)?\$?([\d.]+)\s*(billion|million|B|M)",
    r"\$?([\d.]+)\s*(billion|million|B|M)\s+(?:in\s+)?(?:annual\s+recurring\s+revenue|ARR)",
]

CUSTOMER_PATTERNS = [
    r"(\d{1,3}(?:,\d{3})*)\s+customers?\s+(?:with|spending|over)\s+\$?100[Kk]",
    r"\$100[Kk]\+?\s+(?:ARR\s+)?customers?:?\s+(\d{1,3}(?:,\d{3})*)",
    r"customers?\s+(?:above|over|exceeding)\s+\$1[Mm](?:illion)?:?\s+(\d{1,3}(?:,\d{3})*)",
]

def extract_metrics_regex(text: str) -> dict:
    """
    Extract SaaS metrics using regex patterns.
    Returns first match for each metric.
    """
    results = {
        'ndr': None,
        'gross_retention': None,
        'arr': None,
        'arr_unit': None,
        'customers_100k': None,
    }
    
    # Clean text
    text = text.lower()
    
    # Extract NDR
    for pattern in NDR_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            results['ndr'] = int(match.group(1))
            break
    
    # Extract Gross Retention
    for pattern in GROSS_RETENTION_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            results['gross_retention'] = int(match.group(1))
            break
    
    # Extract ARR
    for pattern in ARR_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            unit = match.group(2).lower()
            if 'b' in unit:
                results['arr'] = value * 1000  # Convert to millions
            else:
                results['arr'] = value
            results['arr_unit'] = 'millions_usd'
            break
    
    # Extract customer counts
    for pattern in CUSTOMER_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            count_str = match.group(1).replace(',', '')
            results['customers_100k'] = int(count_str)
            break
    
    return results
```

### LLM Extraction Approach (More Reliable)

```python
import anthropic
import json

def extract_metrics_llm(transcript_text: str, ticker: str) -> dict:
    """
    Use Claude to extract SaaS metrics from earnings call transcript.
    More reliable than regex for varied phrasing.
    """
    
    client = anthropic.Anthropic()
    
    prompt = f"""Analyze this earnings call transcript for {ticker} and extract the following SaaS metrics.
    
Return ONLY a JSON object with these fields (use null if not mentioned or unclear):

{{
  "ndr": <number 0-200 or null>,
  "ndr_label": "<exact phrase used, e.g. 'net dollar retention' or 'NRR' or null>",
  "ndr_period": "<time period if mentioned, e.g. 'Q2 2025' or null>",
  "gross_retention": <number 0-100 or null>,
  "arr_millions": <number in millions USD or null>,
  "arr_growth_yoy_pct": <number or null>,
  "customers_100k_plus": <integer count or null>,
  "customers_1m_plus": <integer count or null>,
  "rpo_millions": <number in millions USD or null>,
  "revenue_millions": <quarterly revenue in millions or null>,
  "revenue_growth_yoy_pct": <number or null>,
  "notes": "<any relevant context about the metrics>"
}}

TRANSCRIPT:
{transcript_text[:15000]}  # Truncate to fit context
"""
    
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse response
    response_text = message.content[0].text
    
    # Extract JSON from response
    try:
        # Find JSON in response
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            return json.loads(json_match.group())
    except json.JSONDecodeError:
        pass
    
    return {"error": "Failed to parse response", "raw": response_text}
```

---

## 6. QUARTERLY UPDATE WORKFLOW

### Automated Steps (Run after each earnings season)

```python
# quarterly_update.py

import datetime
from typing import List, Dict

def quarterly_update(tickers: List[str]) -> Dict:
    """
    Run quarterly data update for all tracked companies.
    """
    results = {}
    
    for ticker in tickers:
        print(f"Processing {ticker}...")
        
        # Step 1: Get basic financials (automated)
        try:
            financials = get_company_data(ticker)  # yfinance
            profile = get_profile(ticker)  # FMP
        except Exception as e:
            results[ticker] = {"error": f"Failed to fetch financials: {e}"}
            continue
        
        # Step 2: Get earnings transcript (if available)
        quarter = get_current_quarter()
        try:
            transcript = get_transcript(ticker, quarter['year'], quarter['q'])
        except Exception:
            transcript = None
        
        # Step 3: Extract SaaS metrics from transcript
        if transcript:
            saas_metrics = extract_metrics_llm(transcript, ticker)
        else:
            saas_metrics = {"ndr": None, "arr_millions": None, "note": "No transcript available"}
        
        # Step 4: Combine data
        results[ticker] = {
            "updated_at": datetime.datetime.now().isoformat(),
            "financials": financials,
            "saas_metrics": saas_metrics,
            "data_tier": determine_data_tier(saas_metrics),
        }
    
    return results

def determine_data_tier(saas_metrics: dict) -> int:
    """
    Determine data tier based on what's available.
    """
    if saas_metrics.get('ndr') is not None:
        return 1  # Direct NDR
    elif saas_metrics.get('gross_retention') is not None:
        return 2  # Variant metric
    elif saas_metrics.get('arr_millions') is not None:
        return 3  # Can derive implied expansion
    else:
        return 4  # Minimal data
```

### Manual Steps (After automated run)

1. Review extracted NDR values for accuracy
2. Spot-check transcript extraction results
3. Update competitive position assessments
4. Flag any companies with stale data (>100 days)
5. Update Big Tech threat levels if news warrants

---

## 7. COST SUMMARY

| Component | Free Option | Paid Option | Recommendation |
|-----------|-------------|-------------|----------------|
| Stock prices | yfinance | - | Free is sufficient |
| Basic financials | SEC EDGAR | FMP $30/mo | Start free, upgrade if needed |
| Earnings transcripts | Manual from IR sites | FMP $30/mo | Pay if automating |
| SaaS metric extraction | Regex (brittle) | Claude API ~$5/mo | Pay for reliability |
| Data storage | Google Sheets | Postgres | Sheets for <50 companies |

**Recommended starting budget: $0-65/month**
- Phase 1: Free (manual transcript extraction)
- Phase 2: $30/mo (FMP for transcripts)
- Phase 3: $65/mo (FMP + Claude extraction)

---

## 8. NEXT STEPS

1. **Set up free tier first:**
   - Create FMP account (free tier: 250 requests/day)
   - Test SEC EDGAR direct access
   - Build basic data fetcher for ~10 companies

2. **Validate extraction:**
   - Manually extract NDR for 5 companies
   - Compare against regex extraction
   - Compare against LLM extraction
   - Determine error rate for each method

3. **Build storage:**
   - Start with Google Sheets or SQLite
   - Define schema matching data model
   - Create quarterly update workflow

4. **Iterate:**
   - Add companies incrementally
   - Refine extraction patterns
   - Automate verdict calculation

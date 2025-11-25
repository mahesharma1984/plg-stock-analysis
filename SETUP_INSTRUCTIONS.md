# Running the PLG Analysis Prototype Locally

## Prerequisites

- Python 3.8 or higher installed
- Internet connection (for API calls)
- Terminal/Command Prompt access

---

## Step 1: Download the Files

Download these files to a folder on your computer:
- `plg_prototype.py` (the main script)
- Create a new folder called `plg_analysis` and put the file there

---

## Step 2: Install Required Packages

Open your terminal/command prompt and navigate to the folder:

```bash
cd path/to/plg_analysis
```

Then install the required Python packages:

### On Mac/Linux:
```bash
pip3 install yfinance requests
```

### On Windows:
```bash
pip install yfinance requests
```

### If you get permission errors:
```bash
pip3 install --user yfinance requests
# or
pip install --user yfinance requests
```

---

## Step 3: Run the Script

### Basic run (analyzes MongoDB):
```bash
python3 plg_prototype.py
```

Or on Windows:
```bash
python plg_prototype.py
```

### Expected output:
```
============================================================
ANALYZING: MDB
============================================================

[1/3] Fetching automated data...
  Fetching Yahoo Finance data for MDB...
  Fetching SEC EDGAR data for CIK 1441816...

[2/3] Loading manual SaaS metrics...

[3/3] Combining data and computing verdict...

============================================================
RESULTS: MDB (MongoDB, Inc.)
============================================================

📊 VERDICT: 🟢 BUY
   Confidence: 🟢 HIGH (75%)
   Data Tier: 1
   Entry Signals: 4/5
   Exit Signals: 0

   Rationale: 4.5/5 entry signals: NDR 119% ≥ 110%; Revenue growth 24% (close to 25%); ...

📈 KEY METRICS
   Market Cap:     $35.2B
   Revenue (TTM):  $2.4B
   Revenue Growth: 24.0%
   Gross Margin:   73.2%
   Op. Margin:     15.8%

🎯 SAAS METRICS (Tier 1)
   NDR:            119%
   ...

Results saved to mdb_analysis.json
```

### Output files created:
- `mdb_analysis.json` - Structured JSON with results

---

## Step 4: Add More Companies

Edit the `get_manual_saas_metrics()` function in `plg_prototype.py`:

```python
def get_manual_saas_metrics(ticker: str) -> dict:
    """Manual SaaS metrics from earnings calls."""
    
    manual_data = {
        'MDB': {
            'ndr': 119,
            'ndr_tier': 1,
            'revenue_growth_yoy': 0.24,
            'big_tech_threat': 'medium',
            'category_stage': 'early_growth',
            'switching_cost': 'high',
            'notes': 'Atlas cloud growing 29%. Strong NDR.',
        },
        
        # Add more companies here:
        'SNOW': {
            'ndr': 127,
            'ndr_tier': 1,
            'revenue_growth_yoy': 0.29,
            'big_tech_threat': 'medium',
            'category_stage': 'early_growth',
            'switching_cost': 'high',
            'notes': 'Elite NDR. Multi-cloud positioning.',
        },
        
        'DDOG': {
            'ndr': 120,
            'ndr_tier': 2,  # Approximate only
            'revenue_growth_yoy': 0.28,
            'big_tech_threat': 'medium',
            'category_stage': 'early_growth',
            'switching_cost': 'high',
            'notes': 'Observability leader. AI tailwind.',
        },
        
        'ASAN': {
            'ndr': 96,
            'ndr_tier': 1,
            'revenue_growth_yoy': 0.10,
            'big_tech_threat': 'very_high',
            'category_stage': 'commoditizing',
            'switching_cost': 'low',
            'notes': 'WARNING: NDR below 100%. Microsoft bundling threat.',
        },
    }
    
    return manual_data.get(ticker, {})
```

Then modify the main block at the bottom to analyze multiple companies:

```python
if __name__ == "__main__":
    companies = [
        ("MDB", "1441816"),   # MongoDB
        ("SNOW", "1640147"),  # Snowflake
        ("DDOG", "1561550"),  # Datadog
        ("ASAN", "1477720"),  # Asana
    ]
    
    all_results = []
    
    for ticker, cik in companies:
        company, verdict = analyze_company(ticker, cik)
        print_results(company, verdict)
        
        # Save to list
        all_results.append({
            "ticker": ticker,
            "verdict": verdict.verdict,
            "confidence": verdict.confidence,
            "ndr": company.ndr,
            "revenue_growth": company.revenue_growth_yoy,
        })
    
    # Save summary
    with open('plg_summary.json', 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print("\n✅ Summary saved to plg_summary.json")
```

---

## Step 5: Get NDR Data from Earnings Calls

### Where to find NDR:

1. **Company Investor Relations page:**
   - Example: https://investors.mongodb.com/
   - Look for latest earnings call transcript or earnings presentation

2. **Seeking Alpha (free, limited):**
   - https://seekingalpha.com/symbol/MDB/earnings/transcripts
   - Search for "net dollar retention" or "NDR" in transcript

3. **FinChat.io (free tier):**
   - Has some SaaS metrics pre-extracted

4. **Company earnings press release:**
   - Usually has key metrics in bullet points

### What to look for in transcripts:

Search for these phrases:
- "net dollar retention"
- "net revenue retention"
- "NDR"
- "NRR"
- "dollar-based net expansion"
- "DBNE"
- "gross retention"

Example from MongoDB Q2 FY2026:
> "Our net revenue retention rate was 119% in the quarter..."

Add this to the script as: `'ndr': 119`

---

## Troubleshooting

### "command not found: python3"
Try:
```bash
python plg_prototype.py
```

### "No module named 'yfinance'"
Install again with:
```bash
python -m pip install yfinance requests
```

### "Failed to fetch Yahoo Finance data"
This is normal if Yahoo Finance is rate-limiting. The script will continue with manual data.

### "SEC EDGAR returned status 403"
SEC requires a User-Agent header. The script includes this, but if blocked:
1. Add a small delay between requests
2. The script will continue with available data

### Network errors in cloud environments
If running in a restricted environment (like some cloud notebooks), the API calls may be blocked. The script still works with manual data only.

---

## Example Workflow

1. **Run initial test:**
   ```bash
   python3 plg_prototype.py
   ```

2. **Check output files:**
   ```bash
   cat mdb_analysis.json
   ```

3. **Add more companies:**
   - Edit `get_manual_saas_metrics()` 
   - Add ticker/CIK to main block
   - Run again

4. **Review verdicts:**
   - Check confidence levels
   - Note missing signals
   - Prioritize getting NDR for HIGH confidence

5. **Schedule quarterly updates:**
   - After each earnings season, update NDR values
   - Re-run analysis
   - Track verdict changes over time

---

## Next Steps

Once this works:

1. **Expand the universe:**
   - Add all 40 companies from your project docs
   - Source NDR from earnings calls (10-15 min per company)

2. **Build a spreadsheet tracker:**
   - Export to CSV for easier viewing
   - Track verdict changes quarter-over-quarter

3. **Add alerting:**
   - Email when verdict changes
   - Flag NDR drops below 110%

4. **Automate transcript extraction:**
   - Use Financial Modeling Prep API ($30/mo)
   - Add Claude API for NDR extraction ($5/mo)

---

## Key Files

After running, you'll have:

```
plg_analysis/
├── plg_prototype.py          # Main script
├── mdb_analysis.json         # Detailed results
└── plg_summary.json          # Summary (if analyzing multiple)
```

---

## Support

If you encounter issues:
1. Check Python version: `python3 --version` (need 3.8+)
2. Check package installation: `pip3 list | grep yfinance`
3. Test internet connection: `curl https://finance.yahoo.com`
4. Try running with verbose output: `python3 -v plg_prototype.py`

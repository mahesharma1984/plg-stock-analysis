# PLG Batch Analyzer - Quick Start

## What it does

Analyzes all 40 companies from your PLG investment thesis at once:
- Fetches live market cap, revenue, margins from Yahoo Finance
- Uses NDR/growth data from your project documents
- Applies your thesis rules to generate verdicts
- Outputs summary + detailed results

## Run it

```bash
# Analyze all 40 companies
python3 plg_batch_analyzer.py

# Or analyze specific companies
python3 plg_batch_analyzer.py MDB SNOW DDOG
```

## Output files

- `plg_batch_results.json` - Full detailed data
- `plg_batch_summary.csv` - Spreadsheet view (open in Excel)

## Companies included

### 🟢 STRONG (Expected STRONG_BUY/BUY)
- RBRK (Rubrik): NDR 120%, 47% growth - cyber resilience
- NET (Cloudflare): NDR 114%, 28% growth - edge computing
- MDB (MongoDB): NDR 119%, 24% growth - NoSQL/AI database
- SNOW (Snowflake): NDR 127%, 29% growth - data cloud
- DDOG (Datadog): NDR ~120%, 28% growth - observability
- CRWD (CrowdStrike): NDR 112%, 21% growth - endpoint security
- ZS (Zscaler): 22% growth - Zero Trust
- IOT (Samsara): 30% growth - IoT operations
- CFLT (Confluent): NDR 114%, 19% growth - event streaming
- DT (Dynatrace): NDR 111%, 19% growth - observability

### 🟡 TRANSITIONAL (Expected WATCH)
- BRZE (Braze): NDR 111% declining, 26% growth
- OKTA (Okta): 14% growth, Microsoft threat
- FRSH (Freshworks): NDR 105%, 14% growth
- TWLO (Twilio): DBNE 108%, 9% growth
- PCOR (Procore): NDR 106%, 11% growth

### 🔴 MATURE/COMMODITIZING (Expected SELL)
- ASAN (Asana): NDR 96%, 10% growth - work management
- ZI (ZoomInfo): NDR 87%, -1% growth - B2B data
- DOCU (DocuSign): NDR 102%, 7% growth - e-signature
- BILL (Bill.com): NDR 92%, 9% growth - AP/AR
- PATH (UiPath): NDR 108%, 11% growth - RPA
- ZM (Zoom): 3% growth - video conferencing
- DBX (Dropbox): -1% growth - file sync

### 📊 OTHER
- AFRM, SQ, TOST, S, MNDY, SHOP, TEAM, GTLB, ESTC, DOCN

## Expected output

```
============================================================
PLG BATCH ANALYSIS - 40 Companies
============================================================

Analyzing companies:
  RBRK... STRONG_BUY
  NET... BUY
  MDB... BUY
  ...

============================================================
SUMMARY: 40 Companies Analyzed
============================================================

📊 VERDICT BREAKDOWN:
  🟢🟢 STRONG_BUY: 5
  🟢 BUY: 12
  🟡 WATCH: 15
  🔴 SELL: 6
  ⚫ AVOID: 2

🟢 STRONG BUY (5):
  • RBRK   (Rubrik              ) - NDR 120%, 47% growth
  • SNOW   (Snowflake           ) - NDR 127%, 29% growth
  ...

✅ Results saved:
   • plg_batch_results.json (full data)
   • plg_batch_summary.csv (spreadsheet view)
```

## What to do with results

1. **Open CSV in Excel/Sheets:**
   - Sort by verdict to see top picks
   - Filter by NDR > 110%
   - Compare against your manual analysis

2. **Review JSON for details:**
   - Check confidence scores
   - See rationale for each verdict
   - Note missing signals

3. **Track over time:**
   - Re-run quarterly after earnings
   - Compare verdict changes
   - Flag NDR drops

## Customizing

Edit `COMPANY_DATABASE` in the script to:
- Add new companies
- Update NDR from latest earnings
- Adjust competitive assessments

Example:
```python
'MDB': {
    'ndr': 119,  # Update from Q3 earnings
    'revenue_growth_yoy': 0.26,  # Update if accelerated
    'big_tech_threat': 'high',  # Adjust if AWS competes harder
    # ...
}
```

## Next steps

1. Run the batch analyzer
2. Compare results to your manual thesis
3. Identify any mismatches
4. Update NDR values quarterly
5. Build tracking over time

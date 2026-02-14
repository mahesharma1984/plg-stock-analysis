# Debug Runbook

**Version:** 1.0
**Updated:** 2026-02-14
**Purpose:** Triage -> Diagnosis -> Action mapping for common failures.

---

## Triage Order

1. **Identify the symptom** — What's actually wrong? (Use symptom table below)
2. **Trace to component** — Which stage/module produces the bad output?
3. **Diagnose root cause** — Why is it producing bad output?
4. **Fix upstream** — Fix the root cause, not the symptoms downstream

**Key principle:** Fix upstream, not downstream. If signal detection produces bad output because RPC returned bad data, fix the RPC validation — don't add special handling in trend analysis.

---

## RALPH Tracker Symptoms

| # | Symptom | Quick Check | Likely Cause | Fix |
|---|---------|-------------|--------------|-----|
| 1 | **False SELL signals appearing** | Check `ralph_tracker.log` for balance=0 entries | RPC returned 0 on API error, tracker recorded as real | Add Level 0 gate: reject balance=0 when prior balance was >0 without tx confirmation |
| 2 | **False BUY signals after false SELL** | Check log for SELL followed by BUY for same wallet within 1-2 polls | RPC recovered after error, balance restored triggers false BUY | Fix #1 first — if false SELLs are prevented, false BUYs won't occur |
| 3 | **Email alerts not sending** | Check `ralph_config.yaml` email section, verify SMTP creds in `.env` | SMTP config wrong, or Gmail app password expired | Verify `smtp_server`, `sender_email`, and app password. Test with `--snapshot` + email enabled |
| 4 | **Trend analysis shows wrong phase** | Run `python ralph_trend_analysis.py` and compare to manual log review | Corrupted data in `ralph_trends.db` from false signals | Delete `ralph_trends.db`, fix signal detection, re-run trend analysis from clean log |
| 5 | **Tracker crashes on startup** | Check `ralph_config.yaml` format, `.env` exists | YAML parse error or missing environment variable | Validate YAML syntax, ensure `.env` has `HELIUS_API_KEY` |
| 6 | **"Connection refused" or timeout** | Check Helius RPC status, try `curl` to RPC URL | Helius RPC down or rate limited | Wait and retry. Check https://status.helius.dev/. If rate limited, increase poll interval |
| 7 | **Whale balance unchanged for days** | Run `--snapshot` and compare to Solscan | Token account may have been closed, or wallet migrated | Verify wallet on Solscan. If closed, update `ralph_config.yaml` |
| 8 | **Accumulation/Distribution signals firing incorrectly** | Check if 2+ whales had balance changes in same poll | False signals from #1/#2 cascading into coordination detection | Fix #1 first. Coordination detection depends on individual signal accuracy |

---

## PLG Analyzer Symptoms

| # | Symptom | Quick Check | Likely Cause | Fix |
|---|---------|-------------|--------------|-----|
| 9 | **Company shows INSUFFICIENT data** | Check `COMPANY_DATABASE` for that ticker | Missing fields (NDR, revenue_growth) | Add data from latest earnings call |
| 10 | **Verdict seems wrong for known company** | Compare NDR and growth values to latest earnings | Hardcoded data is stale (hasn't been updated after recent earnings) | Update `COMPANY_DATABASE` with latest quarterly data |
| 11 | **yfinance returns None for everything** | Try `python -c "import yfinance; print(yfinance.Ticker('MDB').info)"` | Yahoo Finance API rate limiting or ticker delisted | Wait 30min (rate limit) or check ticker symbol |
| 12 | **SEC EDGAR returns empty** | Check CIK number in `COMPANY_DATABASE` | Wrong CIK, or company hasn't filed yet | Verify CIK at https://www.sec.gov/cgi-bin/browse-edgar |
| 13 | **Opportunity score doesn't match expectations** | Check individual components: fundamental (40pts), valuation (30pts), momentum (20pts), technical (10pts) | One component pulling score in unexpected direction | Debug component scores individually. Most common: P/S ratio stale or RSI in overbought territory |
| 14 | **Batch analyzer crashes mid-run** | Check which ticker caused the error | API error for one ticker crashes whole batch | Add try/except per ticker (should already exist, but verify) |

---

## Diagnostic Procedures

### Procedure 1: RALPH False Signal Investigation

```
1. Open ralph_tracker.log
2. Find the suspect signal (WHALE_BUY or WHALE_SELL)
3. Look at the balance value:
   - If balance = 0 and prior balance was > 0 → API error (Symptom #1)
   - If balance restored to prior value on next poll → Confirmed false signal
4. Check Solscan for the wallet address:
   - If Solscan shows unchanged balance → API error confirmed
   - If Solscan shows real transaction → Signal was correct
5. Fix: Add gate to reject 0-balance when prior was non-zero
```

### Procedure 2: PLG Verdict Investigation

```
1. Which company has the wrong verdict?
2. Check COMPANY_DATABASE for its data:
   - NDR value and tier
   - revenue_growth_yoy
   - big_tech_threat, category_stage, switching_cost
3. Run the verdict logic manually:
   - Count entry signals (need 4-5 for BUY)
   - Count exit signals (need 2 for SELL)
4. Common issues:
   - NDR is None (defaults to Tier 4, very conservative)
   - revenue_growth is decimal (0.25) not percent (25)
   - big_tech_threat is "very_high" which triggers exit signal
```

### Procedure 3: Data Staleness Investigation

```
1. When was COMPANY_DATABASE last updated?
   → git log --oneline plg_batch_analyzer.py
2. When were the latest earnings for the company?
   → Check investor relations site
3. If data is > 100 days old:
   → Update from latest earnings call transcript
   → Document source in notes field
   → Commit with: "chore: update [TICKER] data from Q[N] FY[YEAR] earnings"
```

---

## Escalation Rules

1. **Level 0 failure** (data integrity: RPC returning fake data) → Stop polling, fix immediately
2. **Hard gate failure** (API down, missing critical data) → Skip affected component, continue others
3. **Soft gate failure** (stale data, unusual balance change) → Warn and continue, investigate later
4. **Accumulated soft failures** (3+ warnings in one poll cycle) → Investigate systemic cause

---

## Recovery Templates

### RALPH: Recover from corrupted state

```bash
# 1. Stop the tracker
# 2. Backup current state
cp ralph_tracker_state.json ralph_tracker_state.json.bak

# 3. Get fresh snapshot
python ralph_tracker.py --snapshot

# 4. If snapshot looks correct, resume polling
python ralph_tracker.py
```

### RALPH: Rebuild trend database from clean log

```bash
# 1. Backup corrupted database
mv ralph_trends.db ralph_trends.db.corrupted

# 2. Re-run trend analysis (rebuilds from log)
python ralph_trend_analysis.py
```

### PLG: Re-run after data update

```bash
# 1. Update COMPANY_DATABASE in plg_batch_analyzer.py
# 2. Run batch analysis
python plg_batch_analyzer.py

# 3. Run enhanced analysis for opportunity scores
python plg_enhanced_analyzer.py

# 4. Compare to previous results
diff plg_batch_results.json plg_batch_results.json.bak
```

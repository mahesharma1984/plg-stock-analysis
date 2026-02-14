# Workflow Registry

**Purpose:** Named, repeatable procedures for common operations across the PLG and RALPH subsystems.

---

## Section 1: Atomic Workflows

Atomic workflows are single operations. They can be composed into larger procedures.

### WF-PLG-BATCH: Run batch analysis

**When:** Analyzing all companies or re-running after data changes
**Command:**
```bash
python plg_batch_analyzer.py                    # All 33 companies
python plg_batch_analyzer.py MDB SNOW CRWD      # Specific tickers
```
**Output:** Console verdicts, `plg_batch_results.json`, `plg_batch_summary.csv`
**Verify:** All 33 companies produce verdicts without errors

### WF-PLG-ENHANCED: Run enhanced analysis with valuation

**When:** Need opportunity scoring and valuation overlay
**Command:**
```bash
python plg_enhanced_analyzer.py                  # All companies
python plg_enhanced_analyzer.py MDB SNOW         # Specific tickers
```
**Output:** Console opportunity ranking, `enhanced_analysis.json`
**Verify:** Opportunity scores appear, fundamental verdicts match batch

### WF-PLG-DASHBOARD: Launch interactive dashboard

**When:** Exploring analysis results visually
**Command:**
```bash
streamlit run plg_dashboard.py
```
**Output:** Browser dashboard at http://localhost:8501
**Verify:** All 4 views load (Overview, Deep Dive, Screening, Data Quality)

### WF-PLG-TEST: Run verdict logic tests

**When:** After any change to plg_core.py, company_database.json, or verdict logic
**Command:**
```bash
pytest test_plg_core.py -v
```
**Output:** 59 test results
**Verify:** All 59 tests pass

### WF-RALPH-SNAPSHOT: Check current whale balances

**When:** Quick status check without starting continuous polling
**Command:**
```bash
python ralph_tracker.py --snapshot
```
**Output:** Current wallet balances and signal status
**Verify:** Balances are non-zero (zero = potential API error)

### WF-RALPH-POLL: Start continuous whale tracking

**When:** Monitoring whale activity in real time
**Command:**
```bash
python ralph_tracker.py                          # Default 300s interval
python ralph_tracker.py --interval 60            # Custom interval
```
**Output:** `ralph_tracker.log`, `ralph_tracker_state.json`, email alerts
**Verify:** Log entries appear at expected intervals

### WF-RALPH-HISTORY: View recent whale signals

**When:** Reviewing what happened while tracker was running
**Command:**
```bash
python ralph_tracker.py --history 24h
```
**Output:** Signal timeline for last 24 hours
**Verify:** Signals match expected whale behavior

### WF-RALPH-TREND: Run trend analysis

**When:** Analyzing multi-day whale accumulation/distribution patterns
**Command:**
```bash
python ralph_trend_analysis.py
```
**Output:** Trend phases in `ralph_trends.db`
**Verify:** TrendPhase is one of ACCUMULATION, DISTRIBUTION, CONSOLIDATION

### WF-BACKUP-STATE: Backup current state

**When:** Before risky changes to company_database.json or verdict logic
**Command:**
```bash
git stash                                        # Stash uncommitted changes
# OR
cp company_database.json company_database.json.bak
```
**Output:** Stashed changes or backup file
**Verify:** `git stash list` shows entry, or `.bak` file exists

---

## Section 2: Composed Workflows

Composed workflows combine atomic workflows into multi-step procedures.

### CW-UPDATE-COMPANY-DATA: Update a company's data

**When:** New earnings call data, NDR update, or competitive assessment change
**Steps:**
1. `WF-BACKUP-STATE` — Backup `company_database.json`
2. Edit `company_database.json` — Update fields, set `data_updated` to today's date
3. `WF-PLG-TEST` — Run tests to ensure no verdict regressions
4. `WF-PLG-BATCH` with target ticker — Verify verdict is expected
5. Compare before/after — Did the verdict change as intended?
6. If regression: revert and investigate

### CW-CHANGE-VERDICT-LOGIC: Modify verdict computation

**When:** Changing thresholds, signals, or tier routing in plg_core.py
**Steps:**
1. `WF-BACKUP-STATE` — Backup current state
2. `WF-PLG-BATCH` — Record baseline verdicts for all 33 companies
3. Make the change in `plg_core.py`
4. `WF-PLG-TEST` — Run all 59 tests
5. `WF-PLG-BATCH` — Re-run batch analysis
6. Compare before/after — Which verdicts changed? Were changes intended?
7. `WF-PLG-DASHBOARD` — Visually inspect changes in Data Quality view

### CW-ADD-NEW-COMPANY: Add a new company to the database

**When:** Expanding coverage beyond 33 companies
**Steps:**
1. Research company: NDR, growth, category, business model, competitive position
2. Edit `company_database.json` — Add new entry with all available fields
3. Determine NDR tier (1-4) based on available retention data
4. For Tier 2/4: populate variant fields (`dbne`, `gross_retention`, `arpu_growth_yoy`, etc.)
5. `WF-PLG-TEST` — Ensure no regressions
6. `WF-PLG-BATCH` with new ticker — Verify verdict is reasonable
7. `WF-PLG-DASHBOARD` — Check company appears in all views

### CW-FIX-VERDICT-REGRESSION: Fix a verdict that seems wrong

**When:** A company's verdict doesn't match expectations
**Steps:**
1. Identify the ticker and expected vs actual verdict
2. `WF-PLG-BATCH` with ticker — Get full verdict output with rationale
3. Check `company_database.json` — Is the data correct? Is `ndr_tier` set right?
4. Trace through `plg_core.py` tier routing — Is it hitting the right tier?
5. Check entry/exit signal counts — Are thresholds being hit correctly?
6. If data issue: fix in `company_database.json`
7. If logic issue: fix in `plg_core.py`
8. `WF-PLG-TEST` — Run tests to verify fix doesn't break others
9. `WF-PLG-BATCH` — Full run to check breadth

### CW-RALPH-INVESTIGATE-SIGNAL: Investigate a whale signal

**When:** Unexpected whale buy/sell detected
**Steps:**
1. `WF-RALPH-SNAPSHOT` — Get current balances
2. `WF-RALPH-HISTORY` — Check recent signal timeline
3. Verify balance change is real (not RPC 0 error)
4. Cross-reference with on-chain data if needed
5. `WF-RALPH-TREND` — Check if signal aligns with trend phase

### CW-ROLLBACK: Emergency rollback

**When:** Change caused serious regression, need to revert fast
**Steps:**
1. `git log --oneline -5` — Identify the breaking commit
2. `git revert [commit]` — Revert the change
3. `WF-PLG-TEST` — Verify tests pass
4. `WF-PLG-BATCH` — Verify verdicts are restored

---

## Section 3: Cross-Cutting Patterns

Patterns that apply across multiple workflows.

### Pattern 1: Depth-Then-Breadth

After any change:
1. Measure the target case (depth) — did it improve?
2. Measure other cases (breadth) — did anything regress?
3. Only stabilize when both axes are aligned

**PLG Example:** After updating TWLO's data, verify TWLO's verdict improved, then run full batch to check all 33 companies.

### Pattern 2: Fix Upstream, Not Downstream

When output is wrong:
1. Trace to the component that produces it
2. Fix that component, not downstream consumers
3. Re-run downstream to verify the fix propagated

**PLG Example:** If dashboard shows wrong verdict → fix in `plg_core.py` (not `plg_dashboard.py`). If verdict logic is correct but data is wrong → fix in `company_database.json` (not `plg_core.py`).

### Pattern 3: Level 0 Gates Everything

Before measuring quality:
1. Verify data integrity (Level 0)
2. Only proceed to quality metrics if Level 0 passes
3. If Level 0 fails, fix data integrity first

**RALPH Example:** If RPC returns 0 balance, do NOT record a SELL signal. Verify the balance is real before acting on it.

### Pattern 4: Pin Baseline Before Changes

Before making risky changes:
1. Measure and record current state
2. Pin/tag the current version
3. Make changes
4. Compare against pinned baseline

**PLG Example:** Before changing NDR thresholds, save current `plg_batch_results.json` as `plg_batch_results_baseline.json` and compare after changes.

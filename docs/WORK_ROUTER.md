# Work Router: Symptom-Based Navigation

**Version:** 1.0
**Updated:** 2026-02-14
**Purpose:** Fast routing from "what are you trying to do?" to the right docs and actions.

---

## Category 1: Debugging & Fixing Issues

### Scenario: False signals in RALPH tracker
**Symptoms:** WHALE_BUY or WHALE_SELL appearing when wallet didn't actually transact
**Read:** `docs/DEBUG_RUNBOOK.md` → Symptom #1, #2
**Fix in:** `ralph_tracker.py` → `SignalDetector` class, `_get_token_balance()` method
**Key rule:** Add Level 0 gate — reject balance=0 when prior balance was non-zero

### Scenario: PLG verdict seems wrong
**Symptoms:** Company shows BUY but should be SELL, or vice versa
**Read:** `docs/DEBUG_RUNBOOK.md` → Procedure 2 (Verdict Investigation)
**Fix in:** `company_database.json` (stale data) or `plg_core.py` → tier verdict functions (logic bug)
**Key rule:** Check NDR value, data tier routing, and whether growth is decimal vs percent. Run `pytest test_plg_core.py -v` after any fix.

### Scenario: RALPH tracker crashes
**Symptoms:** Error on startup, crash during polling
**Read:** `docs/DEBUG_RUNBOOK.md` → Symptom #5, #6
**Fix in:** `ralph_config.yaml` (config error) or `ralph_tracker.py` (code error)
**Key rule:** Check YAML syntax, .env file, RPC connectivity

### Scenario: Email alerts not working
**Symptoms:** No emails received despite signals firing
**Read:** `docs/DEBUG_RUNBOOK.md` → Symptom #3
**Fix in:** `ralph_config.yaml` → `email` section, `.env` for SMTP credentials
**Key rule:** Gmail requires App Password, not regular password

### Scenario: Trend analysis showing wrong phases
**Symptoms:** ACCUMULATION when whales are selling, or vice versa
**Read:** `docs/DEBUG_RUNBOOK.md` → Symptom #4
**Fix in:** First fix false signals (#1), then delete `ralph_trends.db` and re-run
**Key rule:** Trend analysis is only as good as the signal data it consumes

---

## Category 2: Building & Feature Work

### Scenario: Add a new whale wallet to RALPH
**Steps:**
1. Verify wallet on Solscan (confirm it holds $RALPH)
2. Add to `ralph_config.yaml` under `wallets:`
3. Test with `python ralph_tracker.py --snapshot`
4. Or use: `python ralph_tracker.py --add-wallet LABEL ADDRESS`
**Files:** `ralph_config.yaml`

### Scenario: Add a new company to PLG analysis
**Steps:**
1. Research NDR, revenue growth, competitive position from latest earnings
2. Add to `company_database.json` with all required fields
3. Set correct `ndr_tier` (1=direct, 2=variant, 3=derived, 4=unavailable)
4. Set correct `business_model` (b2b_saas, consumer, marketplace, transaction_based)
5. For Tier 2: add `dbne`, `gross_retention`, or `large_customer_ndr`
6. For Tier 4 consumer/marketplace: add `arpu_growth_yoy`, `gmv_growth_yoy`, etc.
7. Test: `python plg_batch_analyzer.py [TICKER]`
**Files:** `company_database.json`
**Reference:** `plg_data_schema.md` for field definitions

### Scenario: Update NDR data after earnings
**Steps:**
1. Find earnings call transcript (company IR site, Seeking Alpha)
2. Search for "net dollar retention", "NRR", "net revenue retention"
3. Update `company_database.json` with new value and `data_updated` date
4. Update `notes` field with source and date
5. Set `revenue_decel_3q` if growth is decelerating 3+ quarters
6. Run: `python plg_batch_analyzer.py [TICKER]` to verify verdict
7. Run: `pytest test_plg_core.py -v` to ensure no regressions
**Files:** `company_database.json`
**Reference:** `plg_data_sourcing.md` for extraction patterns

### Scenario: Modify signal detection logic
**Read first:** `CLAUDE.md` § 3 (Failure Gates)
**Steps:**
1. Understand current signal flow (CLAUDE.md § 7 architecture diagram)
2. Make change in `ralph_tracker.py` → `SignalDetector`
3. Test against 5 known real signals from `ralph_tracker.log`
4. Test against 3 known false signals
5. Run `--snapshot` to verify no crashes
**Files:** `ralph_tracker.py`
**Key rule:** Never let API failure propagate into signal reasoning

### Scenario: Modify verdict logic
**Read first:** `plg_verdict_logic.md` (full thesis rules)
**Steps:**
1. Understand current entry/exit signal logic in `plg_core.py`
2. Make change in `plg_core.py` → relevant tier function (`_compute_verdict_tier1/2/3/4`)
3. Run tests: `pytest test_plg_core.py -v` (59 tests must pass)
4. Verify regression cases: TWLO=SELL, SNOW=STRONG_BUY, ASAN=SELL, MDB=BUY
5. Run full batch to check: `python plg_batch_analyzer.py`
**Files:** `plg_core.py` (logic), `plg_verdict_logic.md` (update if rules changed), `test_plg_core.py` (add tests)

### Scenario: Add automated NDR extraction from transcripts
**Read first:** `plg_data_sourcing.md` § 5 (NDR Extraction Strategy)
**Steps:**
1. Review regex patterns in `plg_data_sourcing.md`
2. Review LLM extraction approach (Claude API)
3. Build as separate module (don't modify `plg_batch_analyzer.py` directly)
4. R/P Split: LLM identifies where NDR is mentioned, code extracts exact number
5. Test against 5 known NDR values to validate accuracy
**Files:** New file (e.g., `plg_transcript_extractor.py`)
**Key rule:** Apply R/P Split — LLM reasons about context, code handles exact extraction

---

## Category 3: Understanding Architecture

### Scenario: New to the project
**Read in order:**
1. `CLAUDE.md` — System overview, commands, architecture
2. `docs/CORE_DOCUMENTATION_INDEX.md` — Find what you need
3. `docs/ralph-tracker.md` — RALPH subsystem details
4. `plg_verdict_logic.md` — PLG thesis rules
**Time:** ~30 min for overview

### Scenario: Understanding RALPH signal flow
**Read:** `CLAUDE.md` § 7 (Architecture) → RALPH pipeline diagram
**Then:** `ralph_tracker.py` → classes: `SolanaRPCClient`, `SignalDetector`, `CLIFormatter`
**Reference:** `docs/signals.md` for signal type definitions

### Scenario: Understanding PLG thesis logic
**Read:** `plg_verdict_logic.md` (full rules with code)
**Then:** `plg_data_schema.md` (data structures)
**Then:** `OPPORTUNITY_SCORING_GUIDE.md` (timing overlay)

### Scenario: Understanding the development methodology
**Read:** `docs/DEV_GUIDE_Building_Prototypes_v2.md` (comprehensive methodology)
**Or:** `exports/skills/` for modular skill documents
**Key skills:** R/P Split, Failure Gates, Pattern-First

---

## Category 4: Operational Tasks

### Scenario: Start RALPH polling
**Command:** `python ralph_tracker.py`
**Verify:** Watch console for first poll results
**Note:** Default interval is 300 seconds (5 min)

### Scenario: Get current whale balances
**Command:** `python ralph_tracker.py --snapshot`
**Note:** Safe mode, no continuous polling

### Scenario: Run full PLG analysis
**Command:** `python plg_batch_analyzer.py`
**Output:** Console verdicts + `plg_batch_results.json` + `plg_batch_summary.csv`

### Scenario: Run PLG with opportunity scoring
**Command:** `python plg_enhanced_analyzer.py`
**Note:** Slower (fetches price/technical data for each ticker)

### Scenario: Set up on a new machine
**Steps:**
1. `git clone` the repo
2. `cp .env.example .env` and fill in API keys
3. `pip install -r requirements_ralph.txt`
4. Copy `ralph_config.yaml` from secure backup (not in repo)
5. Test: `python ralph_tracker.py --snapshot`

---

## Routing Decision Tree

```
What are you doing?
|
+-- Something is broken
|   +-- RALPH: False signals           -> Symptom #1, #2
|   +-- RALPH: Crashes/errors          -> Symptom #5, #6
|   +-- RALPH: No email alerts         -> Symptom #3
|   +-- RALPH: Wrong trend phases      -> Symptom #4
|   +-- PLG: Wrong verdict             -> Procedure 2
|   +-- PLG: API errors                -> Symptom #11, #12
|
+-- Building something
|   +-- Add whale wallet               -> Category 2: Add wallet
|   +-- Add company to PLG             -> Category 2: Add company
|   +-- Update earnings data           -> Category 2: Update NDR
|   +-- Change signal detection        -> Category 2: Modify signals
|   +-- Change verdict logic           -> Category 2: Modify verdict
|   +-- Automate NDR extraction        -> Category 2: Transcript extraction
|
+-- Learning the system
|   +-- First time                     -> Category 3: New to project
|   +-- RALPH signal flow              -> Category 3: Signal flow
|   +-- PLG thesis logic               -> Category 3: Thesis logic
|   +-- Methodology                    -> Category 3: Methodology
|
+-- Running/operating
    +-- Start whale monitoring          -> Category 4: Start polling
    +-- Check current balances          -> Category 4: Snapshot
    +-- Run PLG analysis               -> Category 4: Full analysis
    +-- Set up new machine             -> Category 4: Setup
```

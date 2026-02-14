# Claude Code Guide

## 1) Startup Read

Before any code change, read:

1. `docs/CORE_DOCUMENTATION_INDEX.md`
2. `docs/DEVELOPER_GUIDE.md`
3. `docs/RALPH_TRACKER_ASSESSMENT.md` (if working on RALPH)

## Documentation Navigation

**For task-specific routing:** Use [`docs/WORK_ROUTER.md`](docs/WORK_ROUTER.md) for symptom-based routing to specific documentation sections.

**For comprehensive index:** See [`docs/CORE_DOCUMENTATION_INDEX.md`](docs/CORE_DOCUMENTATION_INDEX.md) for Q&A-style quick reference.

## Project Overview

This repo contains two subsystems:

1. **PLG Stock Analysis** — Thesis-based investment framework for 40 SaaS companies. Uses NDR (Net Dollar Retention) as the primary signal, with tiered data sourcing and an opportunity scoring overlay.
2. **RALPH Whale Tracker** — Real-time Solana whale wallet monitoring for $RALPH token. Polls balances via Helius RPC, detects buy/sell signals, tracks trends in SQLite, sends email alerts.

## Git Commit Policy

Key outputs to commit:
- Python scripts (`*.py`)
- Configuration templates (`.env.example`, `ralph_config.yaml` structure)
- Documentation (`docs/*.md`, `*.md` at root)
- Requirements files (`requirements_ralph.txt`)

Key outputs to **never** commit:
- `.env` (API keys)
- `ralph_config.yaml` with real RPC URLs or wallet addresses (use sanitized version)
- `ralph_tracker.log` (runtime output)
- `ralph_tracker_state.json` (runtime state)
- `ralph_trends.db` (runtime database)
- `ralph_launchd.log`
- `plg_batch_results.json`, `plg_batch_summary.csv` (generated output)

---

## 2) Work Modes

### A) Build / Feature Work

Use when adding/changing features, stages, or outputs.

Read in order:
1. This file (CLAUDE.md) for architecture overview
2. `docs/WORK_ROUTER.md` for which files to modify
3. `docs/DEVELOPER_GUIDE.md` for change management rules

### B) Debugging / Regression Work

Use when signals are wrong, tracker crashes, or verdicts seem off.

Read in order:
1. `docs/DEBUG_RUNBOOK.md` for symptom-based diagnosis
2. `docs/RALPH_TRACKER_ASSESSMENT.md` for known data integrity issues
3. The relevant source file (see File Authority Map below)

### C) Understanding Architecture

Use when learning the system or aligning to intent.

Read in order:
1. This file (CLAUDE.md) for system overview
2. `docs/ralph-tracker.md` for RALPH subsystem
3. `plg_verdict_logic.md` + `plg_data_schema.md` for PLG subsystem
4. `docs/DEV_GUIDE_Building_Prototypes_v2.md` for methodology

---

## 3) Decision Rules While Working

### Rule 1: Apply R/P Split

- **REASONING tasks** (signal classification, trend phase detection, verdict computation, competitive assessment) → heuristic code or LLM
- **PRECISION tasks** (balance fetching, transaction parsing, database writes, JSON formatting, regex extraction) → code only
- **If mixed, split into separate steps.** Never let API failure propagate into signal reasoning.

### Rule 2: Explicit Failure Gates

Every pipeline stage must declare hard vs soft gates:

**RALPH Tracker Gates:**

| Gate | Type | Rule | Action on Failure |
|------|------|------|-------------------|
| RPC returns 0 with no prior balance | **HARD** | Cannot distinguish "no tokens" from "API error" | SKIP poll, retain last known state |
| RPC timeout/HTTP error | **HARD** | No data received | SKIP poll, log error, retain state |
| Balance change > 50% in single poll | **SOFT** | Possible API glitch or real whale move | FLAG for verification, record with warning |
| Trend score flips direction | **SOFT** | Could be noise or real reversal | Require 2 consecutive confirmations before changing phase |

**PLG Analyzer Gates:**

| Gate | Type | Rule | Action on Failure |
|------|------|------|-------------------|
| yfinance returns None for revenue | **HARD** | Can't compute verdict without revenue | Skip company, report missing data |
| NDR is None (Tier 4) | **SOFT** | Use alternative verdict path | Fall through to Tier 2/3/4 logic |
| Data older than 100 days | **SOFT** | Stale data warning | Flag staleness, still compute verdict |

### Rule 3: Enforce Pattern-First

- Define schema/structure before populating instances
- Trace causality before edits: What does this consume? Produce? What depends on it?
- Keep stage boundaries stable unless explicitly redesigning

### Rule 4: Project-Specific Rules

- **Never trust RPC balance of 0 without verification** — this is the #1 known bug
- **Always verify signal detection changes against historical log data** (`ralph_tracker.log`)
- **NDR values are manually researched** — treat hardcoded values in `COMPANY_DATABASE` as the source of truth, update only with earnings call evidence
- **Test whale tracker changes with `--snapshot` mode first** before running continuous polling

---

## 4) Document Authority Rules

When docs conflict:
1. Prefer docs marked **AUTHORITATIVE** in `docs/CORE_DOCUMENTATION_INDEX.md`
2. Prefer the file with the newest date
3. If behavior changed in code, update docs in the same change set

---

## 5) Key Commands (Quick Reference)

```bash
# === PLG ANALYSIS ===
python plg_batch_analyzer.py                    # Analyze all 33 companies
python plg_batch_analyzer.py MDB SNOW CRWD      # Analyze specific tickers
python plg_batch_analyzer.py --check-freshness  # Check data staleness
python plg_enhanced_analyzer.py                  # With opportunity scoring
python plg_enhanced_analyzer.py MDB SNOW        # Enhanced for specific tickers

# === PLG DASHBOARD ===
streamlit run plg_dashboard.py                   # Launch interactive dashboard
pip install -r requirements_dashboard.txt        # Install dashboard dependencies

# === PLG TESTS ===
pytest test_plg_core.py -v                      # Run all 59 verdict logic tests

# === RALPH TRACKER ===
python ralph_tracker.py --snapshot               # Current balances (safe, no polling)
python ralph_tracker.py                          # Start continuous polling (300s default)
python ralph_tracker.py --interval 60            # Custom poll interval
python ralph_tracker.py --history 24h            # View recent signals
python ralph_tracker.py --add-wallet LABEL ADDR  # Add new whale wallet

# === RALPH TREND ANALYSIS ===
python ralph_trend_analysis.py                   # Run trend analysis from log data

# === RALPH GENESIS ===
python ralph_genesis.py                          # Trace token origin / insider detection

# === SETUP ===
pip install -r requirements_ralph.txt            # Install RALPH dependencies
cp .env.example .env                             # Set up environment variables
```

---

## 6) File Authority Map

Each file has a single owner/purpose. When in doubt about where to make a change:

### RALPH Subsystem

| File | Owns | Depends On |
|------|------|------------|
| `ralph_tracker.py` | Polling loop, signal detection, CLI, email alerts | `ralph_config.yaml`, `.env` |
| `ralph_trend_analysis.py` | Multi-day trend analysis, SQLite storage | `ralph_tracker.log`, `ralph_trends.db` |
| `ralph_genesis.py` | Token origin tracing, insider detection | Helius RPC |
| `ralph_config.yaml` | Wallet addresses, RPC URL, email config, settings | `.env` for API keys |

### PLG Subsystem

| File | Owns | Depends On |
|------|------|------------|
| `plg_core.py` | **Shared logic**: constants, CompanyData/VerdictResult, tiered verdict engine (T1-T4), confidence scoring, staleness, research recs, data fetching, DB I/O | — |
| `company_database.json` | **Company data**: all 33 companies with NDR, growth, assessments, Tier 2/3/4 fields | — |
| `plg_batch_analyzer.py` | Batch analysis, summary, CSV/JSON output | `plg_core`, `company_database.json`, yfinance |
| `plg_enhanced_analyzer.py` | Opportunity scoring, valuation overlay, technicals | `plg_core`, `company_database.json`, yfinance |
| `plg_dashboard.py` | Streamlit interactive dashboard (4 views: overview, deep dive, screening, data quality) | `plg_core`, `plg_enhanced_analyzer`, `company_database.json`, streamlit, plotly |
| `test_plg_core.py` | 59 tests for verdict logic, confidence, staleness, tier routing | `plg_core`, `company_database.json` |
| `_archived/plg_prototype.py` | **ARCHIVED** — original single-company test framework | — |

### Design Docs (Read-Only Reference)

| File | Describes |
|------|-----------|
| `plg_verdict_logic.md` | Thesis rules: entry/exit signals, confidence, tiered verdicts |
| `plg_data_schema.md` | Data structures: company, financials, retention, competitive |
| `plg_data_sourcing.md` | Where data comes from, API endpoints, extraction patterns |
| `OPPORTUNITY_SCORING_GUIDE.md` | Valuation + price timing overlay |

---

## 7) Architecture Overview

### RALPH Tracker Pipeline

```
ralph_config.yaml (wallet addresses, settings)
    |
    v
[POLL] Helius RPC: getTokenAccountsByOwner()
    |
    v
[GATE] Level 0: Is balance valid? (not 0 from API error)
    |
    v
[DETECT] SignalDetector: compare to last known state
    |   - Balance increase  -> WHALE_BUY
    |   - Balance decrease  -> WHALE_SELL
    |   - Transfer to CEX   -> WHALE_TO_CEX
    |   - 2+ whales buying  -> ACCUMULATION
    |   - 2+ whales selling -> DISTRIBUTION
    |
    v
[STORE] ralph_tracker_state.json (current balances)
        ralph_tracker.log (event history)
    |
    v
[DISPLAY] Rich CLI output (colored signals)
[ALERT]   Email reports (6-hour intervals)
    |
    v
[TREND] ralph_trend_analysis.py (optional, reads log)
        -> ralph_trends.db (SQLite time-series)
        -> TrendPhase: ACCUMULATION | DISTRIBUTION | CONSOLIDATION
```

### PLG Analysis Pipeline

```
company_database.json (33 companies, NDR + Tier 2/3/4 fields)
    |
    v
plg_core.py:load_company_database()
    |
    v
[FETCH] plg_core.fetch_yfinance_data(): price, market cap, margins
    |
    v
[BUILD] plg_core.build_company_data(): merge DB + live API data
    |
    v
[ROUTE] plg_core._determine_data_tier(): pick verdict path
    |
    v
[VERDICT] plg_core.compute_verdict(): tiered thesis logic
    |   Tier 1: Direct NDR -> 5 entry / 4 exit signals
    |   Tier 2: DBNE/GR/Large Cust NDR -> adjusted thresholds
    |   Tier 3: Implied expansion/RPO -> very conservative (max=WATCH)
    |   Tier 4: Consumer/Marketplace/Transaction or insufficient data
    |   + confidence scoring, staleness, research recommendations
    |
    v
[BATCH]  plg_batch_analyzer.py: all-company run → JSON + CSV
[SCORE]  plg_enhanced_analyzer.py (optional): valuation overlay
    |   Fundamental strength (40 pts)
    |   Valuation P/S (30 pts)
    |   Price momentum (20 pts)
    |   Technicals RSI (10 pts)
    |
    v
[OUTPUT] Console verdicts, JSON details, CSV summary
[TEST]   pytest test_plg_core.py (59 tests)
```

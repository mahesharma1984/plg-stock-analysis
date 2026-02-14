# Developer Guide

**Version:** 1.0
**Updated:** 2026-02-14
**Purpose:** How to make changes safely in this project.

---

## Rule 0: Explicit Failure Gates

Every pipeline, script, or workflow must declare:
- **Hard gates:** Failures that stop execution
- **Soft gates:** Failures that warn and continue

See `CLAUDE.md § 3` for the project-specific gate definitions.

---

## Before Making Changes

### 1. Understand What You're Changing

Before editing:
- **What does this component consume?** (Check File Authority Map in CLAUDE.md § 6)
- **What does it produce?** (outputs, downstream consumers)
- **What depends on it?** (trace the dependency chain)

### 2. Classify Your Tasks (R/P Split)

- **REASONING tasks** (interpretation, judgment) → heuristic code or LLM
- **PRECISION tasks** (extraction, formatting, verification) → code only
- **Mixed tasks** → Split them

### 3. Check Causality (Pattern-First)

- Does this change introduce backwards causality?
- Should this be a new stage or modify existing?
- Are stage boundaries still clean?

---

## Making Changes

### Small Changes (Single File, Clear Scope)

1. Make the change
2. Test with `--snapshot` (RALPH) or single ticker (PLG)
3. Verify output still valid
4. Commit with clear message

### Medium Changes (Multiple Files, Single Feature)

1. Measure baseline (capture current output before changing)
2. Make changes
3. Run tests: `--snapshot` for RALPH, batch run for PLG
4. Compare before/after output
5. Commit with clear message

### Large Changes (Architecture, New Stage, Breaking)

1. Document the change plan (create GitHub Issue)
2. Backup current state (`ralph_tracker_state.json`, `ralph_trends.db`)
3. Make changes incrementally (commit each step)
4. Test after each step
5. Verify against historical data (`ralph_tracker.log`)
6. Update CLAUDE.md and relevant docs in same commit

---

## Testing Guidelines

### RALPH Tracker Testing

| Test | Command | Verifies |
|------|---------|----------|
| Snapshot test | `python ralph_tracker.py --snapshot` | RPC connectivity, balance fetching, display formatting |
| Signal detection | Compare `--snapshot` output across 2 runs | Signals fire correctly on real changes |
| Historical replay | `python ralph_tracker.py --history 24h` | Log parsing, signal reconstruction |
| Trend analysis | `python ralph_trend_analysis.py` | SQLite writes, phase detection |

**Critical test for signal changes:** After modifying `SignalDetector`, verify against `ralph_tracker.log`:
1. Pick 5 known real signals from the log
2. Verify new code would produce same signals
3. Pick 3 known false signals (from API errors)
4. Verify new code correctly filters them

### PLG Analyzer Testing

| Test | Command | Verifies |
|------|---------|----------|
| Single company | `python plg_prototype.py` | Data fetching, verdict logic for MDB |
| Batch run | `python plg_batch_analyzer.py` | All 40 companies, no crashes |
| Specific tickers | `python plg_batch_analyzer.py TWLO ASAN` | Known SELL cases still SELL |
| Enhanced | `python plg_enhanced_analyzer.py` | Opportunity scoring, price data |

**Critical test for verdict changes:** After modifying verdict logic:
1. TWLO (NDR 108%, growth 9%) must still be SELL
2. SNOW (NDR 127%, growth 29%) must still be STRONG_BUY
3. ASAN (NDR 96%, growth 10%) must still be SELL
4. MDB (NDR 119%, growth 24%) must still be BUY

---

## Project-Specific Rules

### RALPH Tracker

1. **Never trust RPC balance of 0 without verification** — distinguish "no tokens" from "API error"
2. **Always test signal changes against historical log** before deploying to continuous polling
3. **Backup `ralph_tracker_state.json` before changes** — this is the "last known good" state
4. **Never modify `ralph_config.yaml` wallet addresses without verifying on-chain** — use Solscan to confirm

### PLG Analyzer

1. **NDR values are manually researched** — only update with earnings call evidence, note the source
2. **COMPANY_DATABASE is the source of truth** for fundamental data — don't derive NDR from APIs
3. **Always include data_tier when adding/modifying companies** — this drives which verdict path runs
4. **Test edge cases**: companies with `ndr=None` (Tier 4), negative growth, consumer models

---

## Documentation Rules

When code changes require doc updates:

1. **Architecture change** → Update `CLAUDE.md` § 6 (File Authority Map) and § 7 (Architecture)
2. **New command/flag** → Update `CLAUDE.md` § 5 (Key Commands)
3. **New failure mode discovered** → Update `docs/DEBUG_RUNBOOK.md`
4. **New workflow** → Update `docs/WORK_ROUTER.md`

**Critical rule:** Update docs in the same commit as code changes.

---

## Commit Messages

Follow the pattern:
```
[type]: [what changed] ([why])

[details if needed]
```

Types: `fix`, `feat`, `refactor`, `docs`, `test`, `chore`

Examples:
- `fix: skip poll when RPC returns 0 balance (false signal prevention)`
- `feat: add Tier 2 verdict fallback for companies with only gross retention`
- `docs: add failure gates to CLAUDE.md`

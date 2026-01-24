# RALPH Tracker Assessment Against DEV GUIDE

**Date:** January 21, 2026
**Assessed By:** Claude
**Status:** PROTOTYPE - NOT PRODUCTION READY

---

## Executive Summary

The RALPH Whale Tracker has significant **Level 0 data integrity issues** that must be fixed before any other improvements. The core problem: **the tracker interprets API failures (balance = 0) as real transactions**, causing false BUY/SELL signals that pollute all trend analysis.

Per DEV GUIDE Part 4.3: **"Level 0 Gates Everything"** - evidence integrity comes first. All trend scores, email alerts, and analyses are built on corrupted data.

---

## Issue Hierarchy

### CRITICAL (Level 0 - Data Integrity)

#### Issue 1: False Transaction Detection from API Failures

**Problem Statement (1 sentence):** The tracker records BUY/SELL signals when the API returns 0 balance due to errors, not actual transactions.

**Evidence from Database:**
```
whale_1 (B93svZr...):
- Jan 20 09:26 | 93.3M | - | Normal (API working)
- Jan 20 20:30 | 0      | SELL 93.3M | FALSE - API returned 0
- Jan 20 20:35 | 93.3M | BUY 93.3M  | FALSE - API recovered
- Jan 20 21:03 | 93.3M | BUY 93.3M  | FALSE - Repeated false signal
- Jan 20 21:59 | 93.3M | BUY 93.3M  | FALSE - Repeated false signal

whale_10 (A12G3UB...):
- Jan 20 09:26 | 13.6M | - | Normal
- Jan 20 20:30 | 0      | SELL 13.6M | Possibly false OR real (stayed 0)
```

**Downstream Corruption:**
- `trend_scores` table shows:
  - 20:30: "BEARISH" score -30 with "Net outflow: 106.8M" (false)
  - 21:59: "BULLISH" score +20 with "1 whale accumulating" (false)
- Email reports sent with false data
- Instant alerts sent for non-existent whale activity

**Root Cause (R/P Analysis):**
- **Precision task** (getting exact balance) is failing silently
- Code at [ralph_tracker.py:280-297](ralph_tracker.py#L280-L297) returns `0` for empty accounts list:
  ```python
  def get_token_balance(self, owner: str, token_mint: str) -> Optional[int]:
      accounts = self.get_token_accounts_by_owner(owner, token_mint)
      if not accounts:
          return 0  # BUG: Can't distinguish "no tokens" from "API failed"
  ```

**Fix Required:**
1. Distinguish between "wallet has 0 tokens" and "API call failed"
2. Add validation: ignore balance changes TO exactly 0 without confirmation
3. Require consecutive polls showing same balance before recording change
4. Add sanity check: flag changes > 50% of total holdings as suspicious

---

### HIGH (Foundational Issues)

#### Issue 2: No Verification of Precision Tasks

**Problem:** Per DEV GUIDE Part 2.5, "You can't tell from the output that it's wrong." The tracker trusts all API responses without verification.

**Current State:**
- RPC calls can fail, return stale data, or timeout
- No checksumming or verification of balance data
- No cross-referencing with transaction signatures

**Fix Required:**
- For any significant balance change, verify by:
  1. Fetching recent transaction signatures for the wallet
  2. Confirming a transaction exists that matches the balance change
  3. Only record if transaction signature confirms the change

#### Issue 3: Backward Causality in Trend Scoring

**Problem:** Per DEV GUIDE Part 5.4, trend scores depend on corrupted wallet history. Fixing wallet history won't retroactively fix trend scores.

**Current State:**
```
wallet_history (corrupted) → TrendAnalyzer → trend_scores (also corrupted)
```

**Fix Required:**
1. Clear corrupted data from database
2. Add data quality flags to distinguish verified vs unverified records
3. Trend scoring should skip/downweight unverified data points

---

### MEDIUM (Design Issues)

#### Issue 4: Missing Checkpoint System

**Problem:** Per DEV GUIDE Part 5.3, stages should have checkpoints for resumption.

**Current State:**
- State file only saves wallet balances
- No checkpoint for trend analysis progress
- No way to resume from partial polling cycle

#### Issue 5: No Measurement Tools

**Problem:** Per DEV GUIDE Part 4.2, "Don't guess what's wrong. Measure."

**Missing:**
- No script to validate data integrity
- No way to compare database balances against on-chain reality
- No metrics dashboard for monitoring false positive rates

---

### LOW (Code Quality)

#### Issue 6: Deprecated datetime.utcnow()

**Problem:** Python warnings about deprecated `datetime.utcnow()`.

**Files Affected:**
- [ralph_tracker.py:528](ralph_tracker.py#L528)
- [ralph_tracker.py:465](ralph_tracker.py#L465)
- [ralph_tracker.py:562](ralph_tracker.py#L562)
- [ralph_tracker.py:927](ralph_tracker.py#L927)
- [ralph_tracker.py:827](ralph_tracker.py#L827)
- [ralph_tracker.py:629](ralph_tracker.py#L629)
- [ralph_tracker.py:949](ralph_tracker.py#L949)

**Fix:** Replace with `datetime.now(datetime.UTC)`

---

## R/P Classification for Current System

| Task | Current Assignment | Should Be | Issue |
|------|-------------------|-----------|-------|
| Fetch wallet balance | Code (RPC) | Code | OK |
| Detect balance = 0 | Code | Code | Missing validation |
| Verify transaction exists | NOT DONE | Code | **MISSING** |
| Calculate % change | Code | Code | OK |
| Classify BUY/SELL | Code | Code | Depends on bad input |
| Calculate trend score | Code | Code | Depends on bad input |
| Generate email content | Code | Code | OK |
| Interpret market conditions | Would need LLM | N/A | Not implemented |

---

## Recommended Fix Order

### Phase 1: Stop the Bleeding (Level 0)

1. **Add balance validation** - Don't record balance changes to 0 without confirmation
2. **Add transaction verification** - Require signature proof for significant changes
3. **Clear corrupted data** - Remove false BUY/SELL records from last 48 hours

### Phase 2: Data Quality (Level 1)

4. **Add data quality flags** - Mark records as verified/unverified
5. **Build measurement tools** - Script to audit data integrity
6. **Add sanity checks** - Flag suspicious changes for review

### Phase 3: Robustness (Level 2)

7. **Implement checkpoint system** - Resume from failures
8. **Add consecutive poll confirmation** - Require 2+ polls before recording change
9. **Fix deprecation warnings** - Clean up code quality issues

---

## GITHUB_ISSUE Template (For Issue 1)

```markdown
# GITHUB ISSUE: Fix False BUY/SELL Signals from API Failures

**Priority:** CRITICAL
**Type:** Bug
**Date:** January 21, 2026
**Depends on:** None

---

## Problem Statement

The tracker records false BUY/SELL signals when the Solana RPC returns 0 balance due to errors/timeouts. This corrupts all downstream trend analysis and sends false email alerts.

## Current State

- `get_token_balance()` returns 0 for both "wallet has no tokens" AND "API failed"
- `detect_balance_change()` treats any change as a real transaction
- Database shows whale_1 "sold" 93.3M then "bought" 93.3M in 5 minutes (impossible)

## Solution

1. Modify `get_token_balance()` to return `None` on API failure, `0` only for confirmed empty
2. Add validation in `detect_balance_change()`:
   - Ignore changes TO 0 without transaction signature confirmation
   - Flag changes > 50% of holdings as suspicious
3. Add transaction verification for any significant balance change

## R/P Classification

| Task | Type | Handled By |
|------|------|------------|
| Distinguish API failure vs real 0 | Precision | Code |
| Fetch transaction signatures | Precision | Code |
| Validate balance change matches tx | Precision | Code |

## Acceptance Criteria

- [ ] API failure returns `None`, not `0`
- [ ] Balance change to 0 requires transaction signature confirmation
- [ ] Changes > 50% are logged for review before recording
- [ ] Existing corrupted data is cleaned from database
- [ ] Test: simulate API failure, verify no false signal recorded

## Files Affected

- `ralph_tracker.py` — SolanaRPCClient.get_token_balance(), SignalDetector.detect_balance_change()
- `ralph_trends.db` — Need to clean corrupted records

## Out of Scope

- Improving trend analysis algorithm
- Adding new features
- Refactoring code structure
```

---

## Conclusion

The RALPH Whale Tracker is a **working prototype** but has **critical data integrity issues** that make it unreliable for production use. The false BUY/SELL signal bug must be fixed before any other improvements.

Per DEV GUIDE: "Don't optimize distribution when quotes are hallucinated. Fix the foundation first."

**Next Step:** Create CURSOR instructions for Issue 1 fix and execute.

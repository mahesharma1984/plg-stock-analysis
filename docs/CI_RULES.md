# CI Rules: Safety Guardrails

**Version:** 1.0
**Updated:** 2026-02-14
**Purpose:** Safety guardrails for code changes, especially AI-assisted ones.

---

## Hard Rules (Never Violate)

1. **Never commit secrets** — No API keys, RPC URLs with keys, SMTP passwords, or wallet private keys
   - Check: `git diff --staged | grep -iE "api.key|secret|password|token|helius-rpc"`
   - Files to watch: `.env`, `ralph_config.yaml`, any `*.yaml` or `*.json`

2. **Never force-push to main** — Protect shared history

3. **Never deploy signal detection changes without historical validation** — Test against `ralph_tracker.log` to verify no new false signals

4. **Never delete `ralph_tracker_state.json` without backup** — This is the "last known good" balance state; losing it causes a full cycle of false signals on next poll

5. **Never modify NDR values without earnings call evidence** — Document the source (transcript URL, date, exact quote) in the `notes` field of `COMPANY_DATABASE`

---

## Files That Must Never Be Committed

| File | Why |
|------|-----|
| `.env` | Contains API keys (Helius RPC, etc.) |
| `ralph_config.yaml` (with real data) | Contains real wallet addresses and RPC URL with API key |
| `ralph_tracker.log` | Large runtime log, contains operational data |
| `ralph_tracker_state.json` | Runtime state, changes every poll |
| `ralph_trends.db` | SQLite database, binary |
| `ralph_launchd.log` | macOS scheduler log |
| `plg_batch_results.json` | Generated output |
| `plg_batch_summary.csv` | Generated output |

Verify `.gitignore` covers all of these before committing.

---

## Change Safety Rules

### Before Committing

- [ ] Tests pass (snapshot mode for RALPH, batch run for PLG)
- [ ] No secrets in diff
- [ ] Changes are scoped to the intended files only
- [ ] Docs updated if behavior changed (CLAUDE.md, DEBUG_RUNBOOK.md)

### Before Pushing

- [ ] Commit messages are clear and descriptive
- [ ] No unintended files included (check `git status`)
- [ ] Branch is up to date with main

### RALPH-Specific Safety

- [ ] Signal detection changes tested against 5+ known real signals from log
- [ ] Signal detection changes verified to filter 3+ known false signals
- [ ] `ralph_tracker_state.json` backed up if making balance-related changes
- [ ] Polling interval not set below 60 seconds (RPC rate limits)

### PLG-Specific Safety

- [ ] Verdict logic changes verified against known test cases (TWLO=SELL, SNOW=STRONG_BUY, ASAN=SELL, MDB=BUY)
- [ ] New companies added with correct `ndr_tier` and `business_model`
- [ ] Data staleness warnings preserved (>100 day threshold)

---

## AI-Assisted Development Rules

When using Claude Code or similar AI tools:

1. **Review all generated code** — AI output is hypothesis until verified
2. **Don't blindly accept refactors** — AI may "improve" working code unnecessarily
3. **Check file operations** — Verify AI isn't modifying unrelated files
4. **Verify deletions** — Confirm removed code is truly unused
5. **Test after AI changes** — Run snapshot/batch even if "the change is simple"
6. **Watch for precision tasks given to LLM** — If Claude is doing extraction, counting, or formatting, move it to code

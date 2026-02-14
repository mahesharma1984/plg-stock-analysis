# Core Documentation Index

**Version:** 1.0
**Updated:** 2026-02-14
**Purpose:** Quick reference for finding documentation. Single source of truth for each concept.

---

## Quick Reference

| Question | Answer | Source |
|----------|--------|--------|
| What does this project do? | Dual system: PLG stock analysis + RALPH whale tracker | `CLAUDE.md` § Project Overview |
| How do I run the PLG analyzer? | `python plg_batch_analyzer.py` | `CLAUDE.md` § 5 |
| How do I run the RALPH tracker? | `python ralph_tracker.py --snapshot` (safe) or `python ralph_tracker.py` (polling) | `CLAUDE.md` § 5 |
| How do I debug an issue? | Follow the triage flow | `docs/DEBUG_RUNBOOK.md` |
| What are the development rules? | See decision rules (R/P Split, Failure Gates, Pattern-First) | `CLAUDE.md` § 3 |
| How do I add a new company? | Add to COMPANY_DATABASE with correct tier | `docs/WORK_ROUTER.md` → Category 2 |
| How do I add a whale wallet? | Edit ralph_config.yaml or use --add-wallet | `docs/WORK_ROUTER.md` → Category 2 |
| What's the PLG thesis logic? | NDR-based entry/exit signals with tiered data | `plg_verdict_logic.md` |
| What data does PLG need? | NDR, revenue growth, competitive position, etc. | `plg_data_schema.md` |
| Where does PLG data come from? | yfinance + SEC EDGAR + manual earnings research | `plg_data_sourcing.md` |
| What are the known bugs? | False signals from RPC returning 0 on error | `docs/RALPH_TRACKER_ASSESSMENT.md` |
| How does opportunity scoring work? | Fundamental (40pts) + Valuation (30pts) + Momentum (20pts) + Technical (10pts) | `OPPORTUNITY_SCORING_GUIDE.md` |
| What's the development methodology? | Exploration-first, R/P Split, Pattern-First, Failure Gates | `docs/DEV_GUIDE_Building_Prototypes_v2.md` |
| How do I launch the dashboard? | `streamlit run plg_dashboard.py` | `CLAUDE.md` § 5 |
| What are the named workflows? | Atomic + composed procedures for PLG and RALPH | `docs/WORKFLOW_REGISTRY.md` |
| Why do we use R/P Split? | LLMs excel at reasoning, fail at precision tasks | `docs/knowledge-base/llm-capability-model.md` |
| Why do we use Pattern-First? | Backwards causality = post-hoc rationalization | `docs/knowledge-base/causality-and-systems.md` |
| Why do we use Failure Gates? | Silent failures are most dangerous | `docs/knowledge-base/failure-theory.md` |

---

## Canonical Sources

Each concept has ONE authoritative document. When information conflicts, defer to the canonical source.

| Concept | Canonical Source | Status |
|---------|-----------------|--------|
| Project overview & architecture | `CLAUDE.md` | **AUTHORITATIVE** |
| Change management rules | `docs/DEVELOPER_GUIDE.md` | **AUTHORITATIVE** |
| Safety guardrails | `docs/CI_RULES.md` | **AUTHORITATIVE** |
| Debugging procedures | `docs/DEBUG_RUNBOOK.md` | **AUTHORITATIVE** |
| Task routing | `docs/WORK_ROUTER.md` | **AUTHORITATIVE** |
| PLG verdict logic | `plg_verdict_logic.md` | **AUTHORITATIVE** |
| PLG data schema | `plg_data_schema.md` | **AUTHORITATIVE** |
| PLG data sourcing | `plg_data_sourcing.md` | **AUTHORITATIVE** |
| Opportunity scoring | `OPPORTUNITY_SCORING_GUIDE.md` | **AUTHORITATIVE** |
| RALPH tracker usage | `docs/ralph-tracker.md` | **AUTHORITATIVE** |
| RALPH signal types | `docs/signals.md` | **AUTHORITATIVE** |
| RALPH config reference | `docs/configuration.md` | **AUTHORITATIVE** |
| Known RALPH issues | `docs/RALPH_TRACKER_ASSESSMENT.md` | **AUTHORITATIVE** |
| Development methodology | `docs/DEV_GUIDE_Building_Prototypes_v2.md` | **AUTHORITATIVE** |
| Named workflows | `docs/WORKFLOW_REGISTRY.md` | **AUTHORITATIVE** |
| Dashboard (interactive analysis) | `plg_dashboard.py` | **AUTHORITATIVE** |
| KB: LLM capabilities | `docs/knowledge-base/llm-capability-model.md` | **AUTHORITATIVE** |
| KB: Task decomposition | `docs/knowledge-base/task-design-theory.md` | **AUTHORITATIVE** |
| KB: Dependency ordering | `docs/knowledge-base/causality-and-systems.md` | **AUTHORITATIVE** |
| KB: Quality verification | `docs/knowledge-base/measurement-theory.md` | **AUTHORITATIVE** |
| KB: Failure modes | `docs/knowledge-base/failure-theory.md` | **AUTHORITATIVE** |

---

## Document Categories

### Navigation (How to find things)
- `CLAUDE.md` — AI assistant instructions, architecture, commands
- `docs/CORE_DOCUMENTATION_INDEX.md` — This file (Q&A lookup)
- `docs/WORK_ROUTER.md` — Symptom-based routing to correct docs

### Architecture & Design (How the system works)
- `CLAUDE.md` § 6-7 — File authority map and architecture diagrams
- `plg_verdict_logic.md` — Full thesis rules with Python pseudocode
- `plg_data_schema.md` — Data structures for all entities
- `plg_data_sourcing.md` — Data source hierarchy, API endpoints, extraction code

### Operations (How to do things)
- `docs/DEVELOPER_GUIDE.md` — Change management, testing, commit rules
- `docs/CI_RULES.md` — Safety guardrails, what never to commit
- `docs/DEBUG_RUNBOOK.md` — Triage and diagnosis for common issues
- `docs/WORK_ROUTER.md` — Step-by-step procedures for common tasks
- `docs/WORKFLOW_REGISTRY.md` — Named atomic + composed workflows

### RALPH Tracker Docs
- `docs/ralph-tracker.md` — Main guide for the whale tracker
- `docs/configuration.md` — Config file reference
- `docs/signals.md` — Signal types and their meanings
- `docs/RALPH_TRACKER_ASSESSMENT.md` — Known issues and data integrity assessment

### PLG Analysis Docs
- `OPPORTUNITY_SCORING_GUIDE.md` — Valuation + timing overlay
- `OPPORTUNITY_SCORING_CHEATSHEET.md` — Quick reference card
- `EXAMPLE_OUTPUT.md` — Sample analysis output
- `BATCH_ANALYZER_GUIDE.md` — Running batch analysis
- `SETUP_INSTRUCTIONS.md` — Getting started (original, for prototype)

### Methodology (Why we do things this way)
- `docs/DEV_GUIDE_Building_Prototypes_v2.md` — Comprehensive methodology guide
- `docs/methodology/rp-split.md` — Reasoning/Precision task allocation
- `docs/methodology/failure-gates.md` — Hard vs soft failure semantics
- `docs/methodology/pattern-first.md` — Schema-before-instances methodology
- `docs/methodology/measurement-driven.md` — Depth/breadth quality cycles
- `docs/methodology/prototype-building.md` — Exploration before execution

### Knowledge Base (Theoretical foundations — why the methodology works)
- `docs/knowledge-base/llm-capability-model.md` — What AI can and cannot do
- `docs/knowledge-base/task-design-theory.md` — How decomposition determines quality
- `docs/knowledge-base/causality-and-systems.md` — Why dependency direction matters
- `docs/knowledge-base/measurement-theory.md` — How to know if something works
- `docs/knowledge-base/failure-theory.md` — How systems break silently

---

## Document Consolidation Notes

The following older docs are **superseded** by newer authoritative sources:

| Old Document | Superseded By | Status |
|--------------|---------------|--------|
| `SETUP_INSTRUCTIONS.md` | `CLAUDE.md` § 5 + `docs/WORK_ROUTER.md` Category 4 | Keep for reference |
| `BATCH_ANALYZER_GUIDE.md` | `CLAUDE.md` § 5 + `docs/WORK_ROUTER.md` Category 2/4 | Keep for reference |
| `plg_prototype.py` | `plg_core.py` + `plg_batch_analyzer.py [TICKER]` | Archived to `_archived/` |
| Inline `COMPANY_DATABASE` | `company_database.json` | Externalized |

### New Files (Post-Rebuild)

| File | Purpose |
|------|---------|
| `plg_core.py` | Shared verdict logic, constants, data classes, confidence scoring, tier routing |
| `company_database.json` | Externalized company data (33 companies with Tier 2/3/4 fields) |
| `test_plg_core.py` | 59 tests covering all tiers, confidence, staleness, integration |
| `plg_dashboard.py` | Streamlit dashboard (4 views: overview, deep dive, screening, data quality) |
| `docs/WORKFLOW_REGISTRY.md` | Named atomic + composed workflows for PLG and RALPH |
| `docs/knowledge-base/*.md` | 5 theoretical foundation documents (from exports) |
| `docs/methodology/*.md` | 5 composable skill modules (from exports) |

When in doubt, prefer the canonical source listed above.

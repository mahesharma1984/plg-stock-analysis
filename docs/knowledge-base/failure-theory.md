# Failure Theory: How Systems Break and How to Contain It

**Read this before:** Failure Gates skill
**Core question:** Why do systems fail silently, and how do you make failures visible and contained?

---

## The Common Assumption

Most developers think about failure as an exception — something that *might* happen, handled with try/catch blocks and error messages. The default mental model is:

1. **Happy path thinking:** "Normally it works; errors are edge cases"
2. **Binary failure:** "Either it works or it throws an error"
3. **Downstream fixing:** "If the output is wrong, fix the output"

In systems with AI components, staged pipelines, or complex data flows, all three assumptions are wrong — and the way they're wrong is specifically dangerous.

---

## The Failure That Reveals the Truth

A multi-stage pipeline processes data through five stages. Stage 3 has a validation rule: "output must contain at least 5 items." The system processes 100 inputs successfully. Quality metrics look good. Score: 0.84 ("STRONG").

Months later, someone audits the pipeline and discovers:
- Stage 3 checks for 5 items but doesn't check whether they're *valid* items
- Stage 4 silently discards invalid items but doesn't report the discards
- Stage 5 produces output from whatever Stage 4 passes through
- The quality metric measures properties of the final output, not process integrity

**Result:** The system scores "STRONG" while only 1 of 4 validation contracts is actually enforced. It produces output that *looks* good from surface metrics but is built on unchecked intermediate results.

**Three failures compounded:**
1. **Incomplete validation** — checking quantity but not quality
2. **Silent failure** — Stage 4 discards bad data without reporting
3. **Surface metrics** — quality score measures output properties, not process integrity

No individual failure was catastrophic. The combination produced silent corruption with a "STRONG" quality label.

---

## The Mental Model: Failure Taxonomy

### Dimension 1: Visibility

| Type | What Happens | Danger Level |
|---|---|---|
| **Loud failure** | Error thrown, pipeline stops, everyone notices | Low — problem is obvious |
| **Quiet failure** | Warning logged, pipeline continues, output degraded | Medium — may be noticed |
| **Silent failure** | Nothing reported, pipeline continues, output looks normal | **High** — not noticed until damage accumulates |

**The most dangerous failures are the ones that don't look like failures.** An LLM that hallucinate data doesn't throw an error — it produces confident, plausible output. A stage that skips validation doesn't crash — it passes unchecked data downstream.

### Dimension 2: Severity

| Type | Impact | Response |
|---|---|---|
| **Data integrity failure** | Output built on fabricated/corrupt data | Everything downstream is invalid |
| **Contract violation** | Component breaks its interface promise | Downstream components may malfunction |
| **Quality degradation** | Output is valid but suboptimal | System works but underperforms |
| **Coverage gap** | Some cases handled, others missed | System works partially |

**These are hierarchical.** Data integrity failures invalidate quality measurements. There's no point measuring quality if the data is fabricated.

### Dimension 3: Location

| Location | Effect | Fix Strategy |
|---|---|---|
| **Upstream** (early in pipeline) | Corrupts everything downstream | Fix at source; don't patch downstream |
| **Midstream** (middle of pipeline) | Corrupts remaining stages | Fix at point of failure |
| **Downstream** (late in pipeline) | Corrupts final output only | Fix at point of failure |

**Fix upstream, not downstream.** If Stage 3 produces bad output because Stage 1's input was wrong, fix Stage 1. Adding special handling in Stage 3 masks the root cause and creates maintenance debt.

---

## The Principle: Hard Gates and Soft Gates

Every component in a pipeline must explicitly declare two categories of failure:

### Hard Gates: Failures That Must Stop Everything

The pipeline cannot produce valid output if these conditions are violated.

**Characteristics:**
- Downstream stages would consume corrupt data
- No reasonable default or fallback exists
- Data integrity is compromised
- Output would be misleading if published

**Examples:**
- Source data doesn't exist or is unreadable
- Required fields missing from intermediate output
- Reference integrity violation (pointer to nonexistent data)
- Evidence verification failed (fabricated data detected)

**Behavior:** Stop execution. Report exactly what failed and why. Do not attempt to continue.

### Soft Gates: Failures That Should Warn But Not Stop

The pipeline can still produce useful output, but quality is reduced.

**Characteristics:**
- Output is degraded but structurally valid
- Reasonable defaults exist
- Downstream stages can handle partial data
- Quality is reduced, not corrupted

**Examples:**
- Coverage below target (80% instead of 95%)
- Quality score below threshold (adequate but not great)
- Optional enrichment failed (skip it)
- Performance exceeded time budget (slow but correct)

**Behavior:** Log warning with context. Continue execution. Include warning in final report.

---

## Why This Distinction Matters

### Without explicit gates:

```
Stage 3 fails validation
  → Developer A thinks: "This is critical, stop everything"
  → Developer B thinks: "This is minor, continue with partial data"
  → Neither is documented
  → Behavior depends on who last modified the code
  → 6 months later, nobody knows the intent
```

### With explicit gates:

```
Stage 3:
  HARD: Input schema must validate       → STOP on failure
  HARD: Reference integrity required      → STOP on failure
  SOFT: Coverage target is 80%            → WARN if below, continue
  SOFT: Processing time target is 30s     → WARN if exceeded, continue
```

Now the failure semantics are explicit, auditable, and independent of who happens to be working on the code.

---

## Five Design Rules for Failure Handling

### Rule 1: Level 0 Gates Everything

Define a foundational check — the most basic validity assertion. If Level 0 fails, skip all other checks.

```
Level 0: Is the data real and intact?
         ↓ (must pass)
Level 1: Is the structure correct?
         ↓ (must pass)
Level 2: Is the quality acceptable?
         ↓ (should pass)
Level 3: Is the output excellent?
         (aspirational)
```

**Why:** If the data is fabricated (hallucinated quotes, corrupt input), measuring "quality" just measures the quality of the fabrication. Level 0 prevents wasted effort on fundamentally invalid data.

### Rule 2: Repair Is a Separate Stage

Don't embed repair logic inside hard gates. If you want auto-repair, make it a separate component with its own gates:

```
WRONG:
  Stage 3: Validate AND repair if invalid

RIGHT:
  Stage 3.0: Validate (hard gate)
  Stage 3.1: Repair (if 3.0 fails, attempt repair, max N tries)
  Stage 3.2: Re-validate (hard gate again after repair)

  If 3.2 still fails → stop (repair didn't work)
```

**Why:** Mixing validation and repair makes it impossible to know whether you're running on original data or repaired data. Separate stages make the repair visible and auditable.

### Rule 3: Soft Gates Accumulate

Individual soft gate failures are acceptable. But track them across the pipeline:

```
Stage 1: 1 soft warning
Stage 2: 0 soft warnings
Stage 3: 2 soft warnings
Stage 4: 3 soft warnings  ← accumulating
Stage 5: 2 soft warnings

Total: 8 soft warnings
Threshold: 5

Alert: Accumulated soft failures exceed threshold.
       Investigation required — systemic issue likely.
```

**Why:** Each individual soft failure is tolerable. But pattern of soft failures across stages may indicate a systemic problem that no individual gate catches.

### Rule 4: Gates Have Explicit Thresholds

Don't hide thresholds in conditionals buried in code. Declare them as named constants:

```python
# Explicit, auditable, changeable
HARD_GATE_MIN_ITEMS = 5
HARD_GATE_DATA_INTEGRITY = 0.90
SOFT_GATE_COVERAGE_TARGET = 0.80
SOFT_GATE_QUALITY_TARGET = 0.70
SOFT_GATE_MAX_PROCESSING_SECONDS = 300
```

**Why:** When a gate fails, you need to know what the threshold was. When thresholds need tuning, you need to find them quickly. Named constants serve both purposes.

### Rule 5: Report Everything, Even Passes

A gate report should include what passed, not just what failed:

```
Stage 3 Gate Report:
  HARD: Schema validation        → PASS
  HARD: Reference integrity      → PASS
  SOFT: Coverage (target: 80%)   → PASS (87%)
  SOFT: Quality (target: 0.70)   → WARN (0.68) ← below threshold
  SOFT: Performance (target: 30s) → PASS (12s)
```

**Why:** When investigating a downstream problem, you need to know that all upstream gates genuinely passed — not just that they didn't fail loudly. "No error" and "verified pass" are different things.

---

## Failure Propagation: The Cascade Problem

Without explicit gates, failures propagate silently:

```
Stage 1: Produces slightly wrong output (no gate)
    ↓
Stage 2: Consumes wrong output, adds its own errors (no gate)
    ↓
Stage 3: Compounding errors, still no visible failure
    ↓
Stage 4: Output is significantly wrong
    ↓
Stage 5: Final output looks plausible but is deeply flawed
    ↓
Quality metric: 0.72 (looks acceptable)
Manual review: "Something feels off but I can't pinpoint what"
```

With explicit gates at each stage:

```
Stage 1: Produces slightly wrong output
    ↓
Stage 2: HARD GATE FAILS — input doesn't match contract
    ↓ (stops here)
Report: "Stage 2 hard gate failed: missing required field 'source_ref'
         in Stage 1 output. Stage 1 likely has a serialization bug."
```

**The failure is caught early, localized, and actionable.**

---

## The Strangler-Fig Pattern for Adding Gates

You don't need to add gates to everything at once. Add them incrementally:

1. **Start with Level 0** — Add data integrity checks. This catches the worst failures.
2. **Add gates where failures have occurred** — Every post-mortem should produce a new gate.
3. **Add gates at stage boundaries** — Validate contracts between stages.
4. **Add gates where metrics are fragile** — If a metric sometimes masks problems, add a process gate.

Each new gate wraps the existing system with additional validation, like a strangler fig growing around a tree. The old system continues working; the new gates catch problems the old system missed.

**From Fowler (2004):** Replace legacy behavior incrementally by wrapping old interfaces with new validation layers, rather than rewriting everything at once.

---

## Connection to Other Knowledge Base Concepts

| Concept | Connection to Failure Theory |
|---|---|
| **LLM Capability Model** | LLMs produce silent failures (hallucination). Hard gates are required for any LLM precision output. |
| **Causality & Systems** | Fix upstream, not downstream. Failure location determines fix location. |
| **Measurement Theory** | Level 0 gates data integrity before quality measurement. Metrics can mask process failures. |
| **Task Design** | Mixed tasks (R/P) produce mixed failures. Decomposition along task types prevents compound failures. |

---

## Test Yourself

Before proceeding to the Failure Gates skill, you should be able to answer:

1. Why are silent failures more dangerous than loud failures?
2. What's the difference between a hard gate and a soft gate?
3. Why should Level 0 (data integrity) gate everything else?
4. Why should repair logic be a separate stage from validation?
5. What does "fix upstream, not downstream" mean in practice?
6. How does the strangler-fig pattern apply to adding failure handling?

If these feel clear, proceed to [Failure Gates](../skills/failure-gates.md).

---

## References

- Fowler, M. (2004). "StranglerFigApplication" — Incremental replacement pattern
- Perrow, C. (1984). "Normal Accidents" — How complex systems fail through interaction of small failures
- Cook, R. (2000). "How Complex Systems Fail" — 18 observations about failure in complex systems
- Allspaw, J. (2012). "Fault Injection in Production" — Making failures visible before they compound
- Meyer, B. (1988). "Object-Oriented Software Construction" — Contract-based failure semantics
- This repository's measurement data: Contract violation detection, gate enforcement audit, silent corruption discovery

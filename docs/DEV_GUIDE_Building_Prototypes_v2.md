# DEV GUIDE: Building Prototypes

**Version:** 2.0
**Date:** January 16, 2026
**Purpose:** Complete methodology for exploration → handoff
**Replaces:** Exploration-First v2.0, LLM Capabilities v1.0, Iterative Fix v1.0, Pattern-First v2.0
**Complements:** RALPH Readiness Assessment v3.0 (Stage 2: prototype → production)

---

## OVERVIEW

This guide covers Stage 1: Building Prototypes — all exploration and development work before automation.

```
┌─────────────────────────────────────────────────────────────┐
│ STAGE 1: BUILDING PROTOTYPES (this guide)                   │
│ ├── Explore the problem                                     │
│ ├── Test on real cases                                      │
│ ├── Confirm the pattern                                     │
│ ├── Build and iterate                                       │
│ └── Create handoff docs                                     │
│                                                             │
│ ══════════════════════════════════════════════════════════  │
│                                                             │
│ STAGE 2: PROTOTYPE → PRODUCTION (RALPH Assessment v3.0)     │
│ ├── Validate readiness                                      │
│ ├── Run autonomous loops                                    │
│ └── Ship to users                                           │
└─────────────────────────────────────────────────────────────┘
```

**Use this guide when:**
- Starting something new
- Problem is unfamiliar or ambiguous
- Building or modifying code
- Debugging failures
- Prior attempts went in circles

---

## PART 1: CORE PRINCIPLES

### 1.1 Real Case First

Never build in the abstract. Start with one real case.

| Wrong | Right |
|-------|-------|
| "Design a diagnostic system" | "Score this one essay, then figure out the system" |
| "Build a content pipeline" | "Convert this one kernel to HTML, then extract the pattern" |
| "Create a validation framework" | "Check if this one quote exists, then generalize" |

The real case forces concrete decisions, reveals hidden assumptions, provides test data, and prevents over-engineering.

### 1.2 One Problem Per Chat

Each chat = one bounded piece of work.

- State the problem at the start
- Don't branch into side problems (log them for later)
- End with clear output or decision
- Use handoff docs for continuity

Long chats drift. Bounded chats stay focused.

### 1.3 Exploration Before Execution

Don't build until the pattern is confirmed.

```
EXPLORATION (must complete first):
1. Problem Definition    → Can you state it in one sentence?
2. Decomposition         → What are the sub-problems?
3. Pattern Recognition   → What approach will work?
4. Abstraction           → Can you describe it generally?
─────────────────────────────────────────────────────────────
EXECUTION (only after exploration):
5. Build                 → Follow the confirmed pattern
```

If you're building and can't clearly state 1-4, stop and go back.

### 1.4 Structure Before Content

Define the pattern/schema/structure before populating it.

| Wrong (Rationalization) | Right (Structure-First) |
|------------------------|------------------------|
| Select devices → invent pattern | Derive pattern → select devices |
| Create worksheets → map progression | Define progression → fill worksheets |
| Find quotes → validate device | Define device criteria → find matching quotes |
| Write content → extract structure | Define structure → fill sections |

The pattern: Always define the schema before populating instances.

### 1.5 Claude's Output Is Hypothesis

"This should work" from Claude means:
- The logic seems sound
- The code looks correct
- It has not been tested

Treat every Claude output as hypothesis until verified by running actual code on actual data.

---

## PART 2: THE REASONING/PRECISION SPLIT

### 2.1 The Fundamental Problem

LLMs say "yes" to everything. They'll attempt any task. This creates a trap: you design systems assuming Claude can do X, then spend months debugging failures that stem from X being impossible.

The first question isn't "build me this." It's "what are you good at?"

### 2.2 Two Modes of Operation

**Reasoning (LLMs excel):**

| Task Type | Examples | Reliability |
|-----------|----------|-------------|
| Classification | "Is this POV first-person or third-person?" | High |
| Interpretation | "What does this metaphor suggest?" | High |
| Synthesis | "How do these codes combine into a pattern?" | High |
| Explanation | "Why does this device create tension?" | High |
| Judgment | "Which chapter contains the climax?" | High |

Characteristics: Answers "what" and "why" questions. Output is semantic, conceptual. Multiple valid answers possible. Evaluation is qualitative.

**Precision (LLMs fail):**

| Task Type | Examples | Reliability |
|-----------|----------|-------------|
| Exact extraction | "Copy these exact 10 words from the text" | Low |
| Counting | "How many chapters are there?" | Low |
| Calculation | "What percentage is 4 out of 23?" | Low |
| Format compliance | "Output valid JSON with no errors" | Medium |
| Position tracking | "What's at line 547?" | Low |

Characteristics: Answers "where exactly" and "how many" questions. Output must match ground truth exactly. Only one correct answer exists. Evaluation is binary (right/wrong).

### 2.3 The Principle

**Claude reasons. Code handles precision.**

| If the task is... | Give it to... |
|-------------------|---------------|
| Identifying, classifying, interpreting | Claude |
| Counting, calculating, extracting exact text | Code |
| Explaining, synthesizing, judging | Claude |
| Formatting output, validating structure | Code |

Never ask Claude to do both in one call. Mixed calls get mixed results.

### 2.4 Applying the Split

**API Call Design:**

Before (mixed — fails):
```
Find 6-8 devices in this text.
For each, provide:
- name (reasoning)
- exact 5-10 word quote (precision)
- effect (reasoning)
Return as JSON array (precision)
```

After (split — works):
```
Call 1 (Claude): "What devices do you see? Describe roughly where."
Step 2 (Code): Search text for described passages, extract exact quotes
Call 3 (Claude): "Given this quote, explain its effect."
Step 4 (Code): Assemble JSON from verified parts
```

**Prompt Design:**

Before (precision request — fails):
```
CRITICAL: Output ONLY valid JSON. No additional text.
```

After (reasoning request — works):
```
Describe your analysis in plain text with clear labels.
```

Then code parses the plain text into JSON.

### 2.5 The Trap

LLMs are confident. They don't say "I can't extract exact quotes reliably." They say "Here are the quotes:" and give you plausible-looking output.

You can't tell from the output that it's wrong. A hallucinated quote looks exactly like a real one.

The only way to know is:
1. Understand the capability limits beforehand
2. Design systems that don't rely on precision from LLMs
3. Verify precision outputs with code

### 2.6 R/P Checklist

Before any LLM API call:
- [ ] Listed all tasks in this call
- [ ] Categorized each as reasoning or precision
- [ ] Moved precision tasks to code
- [ ] Claude outputs plain text (not JSON)
- [ ] Code handles parsing/formatting
- [ ] Verification step for any extracted content

---

## PART 3: THE EXPLORATION STAGES

### 3.1 Stage 1: Problem Definition

**Question:** What are we actually trying to solve?

**Do:**
- State the problem in one sentence
- Identify who the user is
- Define what success looks like
- Get a real case to test against

**Don't:**
- Jump to solutions
- Accept vague requirements ("make it better")
- Start with technical architecture

**Checkpoint:** Can you state the problem in one sentence?

**Output:** One-sentence problem statement + real test case

### 3.2 Stage 2: Decomposition

**Question:** What are the component parts?

**Do:**
- List sub-problems or questions
- Identify what you need to know before solving
- Name assumptions you're making
- Find the simplest version of the problem

**Don't:**
- Decompose into technical components before understanding user needs
- Treat everything as equally important
- Skip to architecture

**Checkpoint:** Do you have a list of sub-problems?

**Output:** List of sub-problems + dependencies

### 3.3 Stage 3: Pattern Recognition

**Question:** What approach will work?

**Do:**
- Check if you've solved something similar before
- Identify what approaches exist
- Test approach against real case
- Note what worked and what didn't

**Don't:**
- Invent new approach when existing one works
- Copy approach without understanding why it works
- Declare pattern found without testing

**Checkpoint:** Can you describe the pattern or approach?

**Output:** Approach description + evidence it works on real case

### 3.4 Stage 4: Abstraction

**Question:** Can we describe this generally?

**Do:**
- Explain approach to someone else
- Identify what's reusable vs case-specific
- Predict when approach will fail
- Classify tasks as reasoning or precision

**Don't:**
- Abstract before pattern is confirmed
- Over-generalize from one case
- Skip R/P classification

**Checkpoint:** Can you state the solution approach in general terms?

**Output:** General description + R/P classification for all tasks

### 3.5 Stage 5: Execution

**Only now:** Build the thing.

**Do:**
- Follow the confirmed pattern
- Test against the original real case
- Test against 2+ additional cases
- Save checkpoints for resumption

**Don't:**
- Improvise or expand scope
- Skip verification
- Build without testing

**Checkpoint:** Does the output solve the problem stated in Stage 1?

---

## PART 4: THE ITERATIVE FIX LOOP

### 4.1 The Loop

```
MEASURE → DIAGNOSE → FIX → VERIFY → (repeat)
```

Don't guess what's wrong. Measure. Don't assume fix worked. Verify.

### 4.2 Measure First

Before fixing anything:

1. **Build measurement tools** — Scripts that check actual output against ground truth
2. **Establish baseline** — Numbers before you touch anything
3. **Define success** — What metrics need to change, by how much

| Anti-pattern | Pattern |
|--------------|---------|
| "I think it's working better now" | "QVR went from 33% to 92%" |

### 4.3 Level 0 Gates Everything

Evidence integrity comes first. If the data is fabricated, all other metrics describe the fabrication.

```
Level 0: Can we verify claims against reality?
         ↓ (must pass)
Level 1+: Everything else
```

Don't optimize distribution when quotes are hallucinated. Fix the foundation first.

### 4.4 Precision Tasks Done Once

Precision tasks produce varying results when repeated:
- PDF extraction → different artifacts each time
- Quote extraction → different hallucinations each time
- API calls → different responses each time

**Principle:** Do precision work once, save result, reuse everywhere.

```
WRONG:
  Stage 2: Extract PDF → "necessa ry"
  Measurement: Extract PDF → "necessary"
  Result: Quotes don't match

RIGHT:
  Stage 1: Extract PDF → save to .txt
  Stage 2: Read .txt
  Measurement: Read .txt
  Result: Same text everywhere
```

### 4.5 R/P as Recursive Diagnostic

When something fails, ask: "Is this reasoning or precision?"

Keep asking at each level until you find the misallocated task.

```
Stage 5 produces 0 devices
  → Phase B search fails
    → Is Phase B R or P? → Precision (code) ✓
    → Why does it fail? → Keywords don't match text
      → Where do keywords come from? → Phase A
        → Is "describe the text" R or P? → Precision (asking for specific words)
        → ROOT CAUSE: Precision task given to Claude in Phase A prompt
```

The failure is often one or two levels deeper than it appears.

### 4.6 Sub-Issue Pattern

When a fix doesn't work, don't rewrite everything. Create a targeted sub-issue.

```
ISSUE_Stage5_RP_Split.md (parent)
  └── SUB_ISSUE_Fix_Phase_A_Prompt.md (specific failure)
  └── SUB_ISSUE_Single_Source_Text_Extraction.md (specific failure)
```

Each sub-issue:
- States the specific failure
- Traces to root cause using R/P analysis
- Proposes minimal fix
- Defines success criteria

Scope stays small. Iteration stays fast.

### 4.7 Fix Checklist

**Before implementing:**
- [ ] Measured current state with actual tools
- [ ] Identified failing metric
- [ ] Traced to root cause using R/P analysis
- [ ] Scoped fix to single sub-issue
- [ ] Defined success criteria

**After implementing:**
- [ ] Re-ran measurement tools
- [ ] Compared before/after metrics
- [ ] If improved: document and move on
- [ ] If not improved: create new sub-issue, trace deeper

---

## PART 5: STAGE BOUNDARIES AND CHECKPOINTS

### 5.1 Why Stages Matter

Clear stage boundaries prevent:
- Backwards causality (later stages affecting earlier ones)
- Scope creep (one stage absorbing another's work)
- Resume failures (can't restart from middle)

### 5.2 Stage Design Principles

Each stage should have:

| Element | Description |
|---------|-------------|
| Clear inputs | What does this stage consume? |
| Clear outputs | What does this stage produce? |
| Checkpoint | Saved state for resumption |
| Validation | How to verify stage succeeded |
| Independence | Can run without later stages |

### 5.3 Checkpoint System

Save intermediate state to enable resumption:

```python
def stage_2_optimization(self):
    # Try to load checkpoint
    cached = self._load_checkpoint('stage_2')
    if cached:
        print("✓ Loaded Stage 2 from checkpoint")
        return cached

    # Do expensive work
    result = do_expensive_work()

    # Save for future runs
    self._save_checkpoint('stage_2', result)
    return result
```

Benefits:
- Resume from failure without re-running everything
- Incremental testing of each stage
- Version compatibility (old checkpoints work with new code)

### 5.4 Causality Auditing

Check dependency directions. Fix backwards flows.

**The Audit Template:**

```
DEPENDENCY ANALYSIS:

Thing A: [e.g., pattern derivation]
Thing B: [e.g., device selection]
Thing C: [e.g., chapter optimization]

Current order: A → B
Proposed: C → A → B

Questions:
1. Does A need information from B to work properly?
2. Does A need information from C to work properly?
3. Is B a rationalization of A, or a constraint on A?
4. Is A a rationalization of C, or an optimization using C?
5. If we change A, must we change B?
6. If we change C, must we change A?

If 1=Yes or 3=constraint → B should come FIRST
If 2=Yes or 4=optimization → C should come FIRST
If 5=Yes → Current A→B order is wrong
If 6=Yes → C→A order is correct
```

**Test:** Can you run Stage N without running Stage N+1? If no, you have backwards causality.

### 5.5 Anti-Patterns to Watch For

**Post-Hoc Naming:**
- BAD: Generate output → Name it based on output
- GOOD: Define name/schema → Generate conforming output

**Iterative Rationalization:**
- BAD: Make change → Discover it breaks something → Fix that → Repeat
- GOOD: Trace dependencies → Show impact map → Make all changes at once

**Selection Without Criteria:**
- BAD: Pick items → Invent reason they fit
- GOOD: Define criteria → Select items matching criteria

**Documentation After Implementation:**
- BAD: Write code → Document what it does
- GOOD: Write spec → Implement to spec → Validate

### 5.6 Refactoring Checklist

When modifying existing code:
- [ ] Does this change introduce backwards causality?
- [ ] Should this be a new stage or modify existing?
- [ ] Does checkpoint system need updating?
- [ ] Are stage boundaries still clean?
- [ ] Did we trace ALL dependencies?
- [ ] Can we resume from failure?

---

## PART 6: RABBIT HOLE DETECTION

### 6.1 Signs You're In a Rabbit Hole

| Signal | What's Happening |
|--------|------------------|
| Elaborating something already documented | Rediscovering, not discovering |
| "This changes everything" | Probably doesn't |
| 1000+ words explaining a simple fix | Over-engineering |
| Can't test it against real case | Too abstract |
| Same problem reframed 3+ times | Lost the thread |
| Building infrastructure for hypothetical use | Premature optimization |
| Chat is 20+ exchanges with no output | Blocked on something |

### 6.2 Reframe Triggers

When you see these, stop and reframe:

| Trigger | Reframe To |
|---------|------------|
| "We need to restructure the whole system" | What's the ONE thing broken? |
| "This is more complex than I thought" | What's the simplest version? |
| "Let me explain the theory first" | What's the concrete test case? |
| "This should work now" | Did you actually run it? |
| "I need to build X before I can do Y" | Can I do Y manually first? |

### 6.3 How to Reframe

1. State the original problem in one sentence
2. State what you've tried and why it failed
3. Ask: "What's the simplest thing that could work?"
4. Get a real case and test against it
5. If still stuck, start a new chat with fresh framing

---

## PART 7: SESSION PROTOCOL

### 7.1 Starting a Chat

```markdown
## Session Check-In

**Problem:** [One sentence]

**Real case:** [What specific example am I testing against?]

**Stage:**
□ Problem definition — need to clarify
□ Decomposition — breaking it down
□ Pattern recognition — looking for approach
□ Abstraction — confirming the pattern
□ Execution — ready to build

**One next step:** [Single thing to do next]
```

### 7.2 Mid-Chat Check-In

Use when stuck or going in circles:

```markdown
## Mid-Chat Check

1. Can I state the problem clearly?
   □ No → Go back to problem definition
   □ Yes → Continue

2. Am I jumping to solutions?
   □ Yes → Go back to decomposition
   □ No → Continue

3. Is the pattern confirmed?
   □ No → Don't build yet
   □ Yes → Proceed to execution

4. Am I testing against a real case?
   □ No → Get a real case
   □ Yes → Continue

5. Have I classified R/P for all tasks?
   □ No → Do R/P split
   □ Yes → Continue
```

### 7.3 Ending a Chat

Every chat should end with one of:

| Outcome | What to Create |
|---------|----------------|
| Problem clarified, ready to decompose | Note for next chat |
| Pattern confirmed, ready to build | GITHUB_ISSUE + CURSOR docs |
| Built and tested, pattern works | Version the methodology |
| Stuck, need to reframe | Note what failed + new angle |

---

## PART 8: HANDOFF DOCUMENTS

### 8.1 Handoff Checklist

Before creating GITHUB_ISSUE and CURSOR docs:

**Exploration Complete?**
- [ ] Problem stated in one sentence
- [ ] Decomposed into sub-problems
- [ ] Pattern/approach tested on real case
- [ ] Can describe approach in general terms

**R/P Split Done?**
- [ ] Every task classified as reasoning or precision
- [ ] Precision tasks assigned to code
- [ ] Reasoning tasks isolated to specific prompts

**Ready for Build?**
- [ ] Know what files need to be created/modified
- [ ] Know acceptance criteria (specific, testable)
- [ ] Know how to verify success
- [ ] Scope is reasonable (< 1 day of work)

### 8.2 GITHUB_ISSUE Template

```markdown
# GITHUB ISSUE: [Short Title]

**Priority:** [High/Medium/Low]
**Type:** [Feature/Bug/Refactor]
**Date:** [Today]
**Depends on:** [Prior work, if any]

---

## Problem Statement

[One paragraph: What's broken or missing? Why does it matter?]

## Current State

[What exists now? What's the gap?]

## Solution

[High-level approach — what will we build?]

## R/P Classification

| Task | Type | Handled By |
|------|------|------------|
| [Task 1] | Reasoning | Claude |
| [Task 2] | Precision | Code |

## Acceptance Criteria

- [ ] [Specific, testable criterion 1]
- [ ] [Specific, testable criterion 2]

## Files Affected

- `path/to/file.py` — [what changes]

## Out of Scope

- [What we're explicitly NOT doing]
```

### 8.3 CURSOR Template

```markdown
# CURSOR INSTRUCTIONS: [Short Title]

**Issue:** [Link to GITHUB_ISSUE]
**Task:** [One sentence]

---

## OVERVIEW

**Current:** [What exists now]
**Target:** [What we're building]

---

## STEPS

### Step 1: [Name]

[Specific instructions]

### Step 2: [Name]

[Instructions]

---

## VERIFICATION

```bash
# Commands to verify
python script.py input.json
```

**Expected:** [What success looks like]

## CHECKLIST

- [ ] Step 1 complete
- [ ] Step 2 complete
- [ ] Verification passed
```

---

## PART 9: COMMON PATTERNS

### 9.1 New Feature

1. Get real case (one example)
2. Solve manually in chat (explore stages 1-4)
3. Extract the pattern (what did you do?)
4. Classify R/P (reasoning vs precision)
5. Create GITHUB_ISSUE + CURSOR docs
6. Build in Cursor
7. Test on original + 2 more cases
8. If works → version methodology

### 9.2 Bug Fix

1. Get failing case
2. Measure (what's the actual output vs expected?)
3. Diagnose (R/P recursive — where's the real problem?)
4. Propose minimal fix
5. Create CURSOR doc (or fix inline if trivial)
6. Verify fix
7. Test on 2 more cases

### 9.3 Refactor

1. Identify the pain (what's hard?)
2. Map current structure
3. Propose new structure (structure-first)
4. Identify changes vs preserved
5. Create GITHUB_ISSUE + CURSOR docs
6. Build incrementally
7. Test after each change

---

## PART 10: QUICK REFERENCE

### Starting Work

- [ ] State problem in one sentence
- [ ] Have a real case to test against
- [ ] Identify exploration stage (1-4) or execution (5)

### During Exploration

- [ ] Test ideas against real case
- [ ] Don't build until pattern confirmed
- [ ] Watch for rabbit hole signals
- [ ] Classify R/P before handoff

### Building

- [ ] Follow confirmed pattern
- [ ] Precision in code, reasoning in prompts
- [ ] Save checkpoints
- [ ] Test on original + 2 more cases

### Debugging

- [ ] Measure first (numbers, not vibes)
- [ ] Apply R/P recursive diagnostic
- [ ] Scope fix to single sub-issue
- [ ] Verify fix with measurement

### Handoff

- [ ] Exploration stages 1-4 complete
- [ ] R/P split done
- [ ] Create GITHUB_ISSUE + CURSOR docs
- [ ] If automatable → run RALPH Assessment

---

## VERSION HISTORY

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 16, 2026 | Initial guide — exploration to handoff |
| 2.0 | Jan 16, 2026 | Consolidated: absorbs Exploration-First, LLM Capabilities, Iterative Fix, Pattern-First |

**Replaces:**
- DEV_GUIDE_ADDENDUM_Exploration_First_v2_0.md
- DEV_GUIDE_ADDENDUM_LLM_Capabilities_v1_0.md
- DEV_GUIDE_ADDENDUM_Iterative_Fix_Protocol_v1_0.md
- Pattern-First_Development_v2_0.md

---

**END OF GUIDE**

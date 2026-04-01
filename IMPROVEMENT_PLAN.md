# Self-Developing Agents Framework — Improvement Plan

Based on a detailed comparison of the PMO project's actual development practices (CLAUDE.md rules 1-18, 170+ sprints, GL-TDD/RDD/ERROR-LOGGING) against the SDA framework's codified practices, this plan addresses the gaps identified.

## Priority 1: Add Inline Resolution Documentation to Sprint Plan Template

### Problem
The PMO's real sprint plans (SP_170-SP_174) document every CRITICAL/HIGH finding with short identifiers (C-1, H-1) and their resolutions inline in the Review Log. This is the most valuable artifact for context recovery — an agent resuming work after context loss can reconstruct WHY decisions were made without re-running reviews.

The SDA's `templates/SPRINT_PLAN.md` Review Log section only records iteration counts and severity breakdowns. The resolution trail is lost.

### What to Change

**File:** `templates/SPRINT_PLAN.md`

Update the Review Log section to include a resolution block after each iteration. The format should match what the PMO actually writes:

```markdown
### Pre-Implementation Review
- **Iteration 1** (YYYY-MM-DD): [Reviewers] found N total — X CRITICAL, Y HIGH, Z MEDIUM, W LOW. Files reviewed: [list]
- **Iteration 2** (YYYY-MM-DD): [Reviewers] found N total — X CRITICAL, Y HIGH. Files reviewed: [list]

**Resolution — All CRITICAL and HIGH addressed:**
1. **C-1 (short identifier)**: [What was wrong] → [What was changed and why]
2. **H-1 (short identifier)**: [What was wrong] → [What was changed and why]
3. **H-2 (short identifier)**: [What was wrong] → [What was changed and why]
```

The same pattern applies to the Post-Implementation Review Log section.

### Why This Matters
After context compaction (LLM context window shrinks mid-session), the agent re-reads the sprint plan. Without inline resolutions, it sees "2 CRITICAL fixed" but has no idea what they were or why the plan changed. With resolutions, it can resume intelligently.

### Validator Impact
`validate_sprint.py` currently checks for iteration entries with severity counts and "Files reviewed:" annotation. It does NOT check for a resolution block. No validator change is needed — the resolution block is a documentation improvement, not a validation target.

---

## Priority 2: Add Running Test Total to PROGRESS.md Template

### Problem
The PMO's actual PROGRESS.md entries include running test totals: `+23 new tests (6,283 total)`. This lets any agent instantly know the project's test count without running pytest. The SDA template only has `**Tests added**: +N new tests` — no cumulative total.

### What to Change

**File:** `templates/PROGRESS.md`

Change the Sprint History entry format from:
```markdown
- **Tests added**: [+N new tests]
```
to:
```markdown
- **Tests added**: [+N new tests (NNNN total)]
```

Update the commented-out example to show the format with a realistic total.

### Why This Matters
When a Coding Agent starts a new sprint, knowing the current test count is essential for assessing project maturity, setting coverage targets, and writing accurate sprint summaries. Without a running total, the agent must run `pytest --co -q | tail -1` to discover the count.

---

## Priority 3: Add Context Compaction Rule to GL-CONTEXT-MANAGEMENT.md

### Problem
PMO CLAUDE.md Rule 17 specifically addresses mid-session context compaction. GL-CONTEXT-MANAGEMENT.md already mentions compaction in Rule 2 ("Context compaction" is listed as a trigger event) and the Anti-Patterns section ("NEVER continue work after compaction without re-reading the sprint plan"). However, while the topic is covered, the existing guidance lacks a concrete step-by-step recovery procedure specific to mid-session compaction. The session-start recovery procedure (Orient→Assess→Resume) is detailed, but the mid-session case only says "re-read the sprint plan" without enumerating the full recovery sequence.

### What to Change

**File:** `practices/GL-CONTEXT-MANAGEMENT.md`

Expand Rule 2 with a structured recovery procedure and add a "Signs of Context Compaction" subsection. Insert near the existing compaction mention, not as a wholly new topic but as a more actionable version of what's already there:

```markdown
## Mid-Session Context Compaction

When the agent platform compresses or truncates the conversation history mid-session
(common in long implementation sessions), the agent must:

1. Stop current work immediately — do not continue coding from partial memory
2. Re-read the active sprint plan file from disk (it was saved before implementation began)
3. Re-read MEMORY.md for cross-session state
4. Re-read PROGRESS.md for active sprint confirmation
5. Assess current stage: compare what the sprint plan says should be done vs what
   files exist on disk (run validators to detect current state)
6. Resume from the identified stage — do not restart from Stage 1

The sprint plan file is the authoritative context anchor. If the agent's memory of
what it was doing conflicts with what the sprint plan says, trust the sprint plan.

Signs of context compaction:
- The agent cannot recall earlier conversation turns
- The agent asks about decisions that were already made
- The agent proposes changes that were already implemented
- The agent repeats a review iteration that was already completed

Recovery takes priority over speed. A 2-minute re-read prevents hours of
re-work from a corrupted context state.
```

### Why This Matters
Context compaction happens in every long session. Without explicit instructions, the agent continues working from partial memory, producing code that contradicts earlier decisions. The PMO learned this the hard way — Rule 17 exists because agents were making contradictory changes after compaction.

---

## Priority 4: Fix 3 Known Bugs (From Latest Audit)

These are real bugs confirmed by the debugger agent in the latest audit. They should be fixed alongside the improvements above.

### Bug 1: Delivery report filename inconsistency

**Files to fix:**
- `architecture/SYSTEM_DESIGN.md` — lines 141 and 277 use `TASK_XXX_REPORT.md`
- `architecture/ROUTING_RULES.md` — line 155 uses `TASK_XXX_REPORT.md`

**Fix:** Change all `_REPORT.md` references to `_DELIVERY.md` to match the canonical name used in `skills/dev-bootstrap/templates/AGENTS.md` (the Coding Agent's behavioral rules).

### Bug 2: {{MAIN_AGENT_ID}} in IDENTITY.md never substituted

**File to fix:** `install.sh`

The `deploy/openclaw/templates/IDENTITY.md` contains `{{MAIN_AGENT_ID}}` on line 6. When `install.sh` copies this file to the workspace in Step 2, it does not run `sed` to substitute the placeholder. The Coding Agent's IDENTITY.md will contain the raw template variable.

**Fix:** After copying IDENTITY.md in install.sh Step 2 (the workspace setup section for `--mode new`), add:
```bash
if [[ -n "$MAIN_WORKSPACE" ]]; then
    MAIN_AGENT_BASENAME=$(basename "$MAIN_WORKSPACE")
    sed -i "s|{{MAIN_AGENT_ID}}|$MAIN_AGENT_BASENAME|g" "$AGENT_WORKSPACE/IDENTITY.md"
fi
```

The root `install.sh` does NOT have this sed (verified — zero matches for "MAIN_AGENT_ID" in the entire file). The fix must be added.

### Bug 3: Task format missing from ROUTING_RULES.md

**File to fix:**
- `architecture/ROUTING_RULES.md` — the task format section (around lines 72-95) is missing the operational metadata fields that SYSTEM_DESIGN.md requires: `**ID:**`, `**Status:**`, `**Target workspace:**`, `**Created:**`, `**Timeout hours:**`, `**Priority:**`

Note: `deploy/openclaw/templates/MAIN_AGENT_ROUTING.md` already has all these fields — no fix needed there.

**Fix:** Add the bold-label metadata fields to the task format in ROUTING_RULES.md, matching what SYSTEM_DESIGN.md Pattern 2 specifies:
```markdown
**ID:** TASK_XXX
**Status:** NEW
**Requested by:** [agent ID]
**Target workspace:** [path to the agent workspace where built skills should be deployed]
**Created:** [ISO timestamp]
**Timeout hours:** [number]
**Priority:** high | medium | low
```

Without `**Target workspace:**`, the Coding Agent has no way to know where to deploy the built skills.

---

## Priority 5: Strengthen Single-Agent Mode Documentation

### Problem
PMO CLAUDE.md Rule 5 is strict: "The agent that built the code must NOT be the same context that reviews it." The SDA framework's Single-Agent Mode (in `skills/dev-bootstrap/templates/AGENTS.md`) allows the same agent to review its own work by taking a "context break." This is a necessary fallback for platforms without sub-agent support, but the current documentation doesn't adequately communicate the trade-off.

### What to Change

**File:** `skills/dev-bootstrap/templates/AGENTS.md`

In the "Review Protocol (Primary — Single-Agent Mode)" section, add an explicit warning:

```markdown
**Important limitation:** Single-agent review with context breaks is significantly
less effective than true sub-agent isolation. The agent cannot fully forget its own
intent — cognitive biases (confirmation bias, anchoring, curse of knowledge) persist
across context breaks. Strongly prefer sub-agent mode when available.

When using single-agent mode:
- Expect to catch materially fewer bugs than sub-agent mode
- Compensate by running MORE iterations (3-4 minimum instead of 2)
- Be especially vigilant for "looks good to me" bias — if a review finds zero
  issues on the first pass, that itself is suspicious and warrants a harder second look
```

### Why This Matters
Without this warning, an agent on a sub-agent-capable platform might use Single-Agent Mode out of convenience (it's simpler, faster). The documentation should make clear that the convenience comes at a real quality cost.

---

## Implementation Order

Priorities above are ordered by **value impact**. Implementation order below is ordered by **dependency** (bugs before enhancements, blockers before nice-to-haves). Steps 4-7 are independent and can be done in parallel.

1. Fix Bug 3 (task format in ROUTING_RULES.md) — blocks correct inter-agent communication
2. Fix Bug 1 (delivery filename) — prevents Main Agent from finding delivery reports
3. Fix Bug 2 (IDENTITY.md substitution) — cosmetic but visible
4. Priority 1 (inline resolutions in SPRINT_PLAN.md template)
5. Priority 2 (running test total in PROGRESS.md template)
6. Priority 3 (context compaction in GL-CONTEXT-MANAGEMENT.md)
7. Priority 5 (single-agent mode warning in AGENTS.md)

## Verification

After implementing:
- All existing tests must still pass (run `pytest HOW_ITS_DONE/SELF_DEVELOPING_AGENTS/ -q` to verify)
- `validate_sprint.py` must still parse the updated SPRINT_PLAN.md template format
- No new project-specific references introduced (grep for Baserow/OpenClaw/Uroboros/Callisto/PMO in non-deploy files)
- The ROUTING_RULES.md and MAIN_AGENT_ROUTING.md task formats must match SYSTEM_DESIGN.md Pattern 2
- All `_REPORT.md` references must be replaced with `_DELIVERY.md`

## Files Changed (Summary)

| File | Change |
|---|---|
| `templates/SPRINT_PLAN.md` | Add inline resolution block to Review Log |
| `templates/PROGRESS.md` | Add running test total format |
| `practices/GL-CONTEXT-MANAGEMENT.md` | Add mid-session compaction section |
| `skills/dev-bootstrap/templates/AGENTS.md` | Add single-agent mode limitation warning |
| `architecture/SYSTEM_DESIGN.md` | Fix `_REPORT.md` → `_DELIVERY.md` (2 occurrences) |
| `architecture/ROUTING_RULES.md` | Fix `_REPORT.md` → `_DELIVERY.md` + add task metadata fields |
| `install.sh` | Add IDENTITY.md `{{MAIN_AGENT_ID}}` substitution (verify if already present) |

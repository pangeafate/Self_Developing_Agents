# Coding Agent — Behavioral Rules

This file defines the Coding Agent's operating rules. It is the bridge between the framework's methodology (practices/GL-*.md) and the executable skills (skills/dev-*).

Each skill has a SKILL.md with exact commands and parameters. Read the SKILL.md before using a skill for the first time.

---

## Task Lifecycle

You are a headless worker. You do not interact with humans directly. You receive tasks from the Main Agent via file-based dispatch and deliver built capabilities back to the Main Agent's workspace.

### Polling for Tasks

On every heartbeat, run the `poll-tasks` action from the **dev-deploy** skill to check `workspace/tasks/` for NEW tasks.

If `pending_count > 0`, pick the highest-priority NEW task (returned as `next_task` in the JSON output) and begin the Development Lifecycle Protocol below.

### Status Updates

When you pick up a task:
1. Update the task file's `**Status:**` from `NEW` to `IN_PROGRESS`
2. Execute the 7-stage Development Lifecycle Protocol
3. On success: update `**Status:**` to `DELIVERED` and write a delivery report to `workspace/delivery/TASK_XXX_DELIVERY.md`
4. On failure: update `**Status:**` to `FAILED` and write a failure report to `workspace/delivery/TASK_XXX_DELIVERY.md` explaining what went wrong

### One Task at a Time

Process only one task at a time. Do not pick up a new task until the current task reaches DELIVERED or FAILED status.

---

## Development Lifecycle Protocol

When you find a NEW task in `workspace/tasks/`, follow these stages exactly. Do not skip stages.

### Stage 1 — Task Recognition

Read the task file. Determine whether the request requires new code, a bug fix, a configuration change, or documentation only. If it requires code changes, proceed to Stage 2.

### Stage 2 — Sprint Planning

Use the **dev-sprint** skill, `create-plan` action to generate a sprint plan skeleton. Read `dev-sprint/SKILL.md` for exact parameters.

Then manually fill in:
- **Current State** — what exists now
- **Desired End State** — what should exist after
- **Technical Approach** — how you will build it
- **Testing Strategy** — what tests you will write
- **Success Criteria** — how you know it's done

Update PROGRESS.md with: `**Current:** SP_XXX`

Save the plan to disk before proceeding.

### Stage 3 — Plan Review (minimum 2 iterations)

Use the **dev-critique** skill to prepare review context and parse results.

**Protocol:**
1. Run `gather-context` action with `--role architect-reviewer --stage 3 --sprint-plan <plan_path> --files <referenced_files>`
2. Read the JSON output — it contains `system_prompt`, `review_prompt`, and `context_files`
3. Perform the review (see Review Protocol below)
4. Run `parse-findings` action — pipe the review output through it
5. Read the JSON result: if `deployment_blocked: true`, fix the plan and repeat
6. Repeat with `--role code-reviewer`
7. Minimum 2 iterations total, even if first is clean

### Pre-Implementation Gate (MANDATORY)

Before writing ANY code, run the pre-implementation gate:

```
python validators/validate_sprint.py <project-root> --gate pre-impl
```

This checks:
1. Sprint plan file exists on disk
2. Sprint plan has required sections (Goal, Approach, Testing, Criteria)
3. Review Log has at least 2 iterations with severity counts and files-reviewed

**If this gate fails, do NOT write any code.** Fix the sprint plan first. This is the enforcement mechanism — no plan, no review, no code.

### Stage 4 — Implementation

Follow GL-TDD.md strictly:
1. Write a failing test (RED)
2. Write minimal code to pass the test (GREEN)
3. Refactor while keeping tests green (REFACTOR)
4. Repeat for each feature

### Stage 5 — Post-Implementation Review (minimum 2 iterations, up to 5)

Use the **dev-critique** skill for gap analysis.

**CRITICAL: do NOT pass `--sprint-plan` at Stage 5.** The review must see only code and tests — not the plan. The `gather-context` action enforces this (exits with error if you try).

1. Run `gather-context` action with `--role debugger --stage 5 --files <new_and_modified_files>`
2. Perform the review (see Review Protocol below)
3. Run `parse-findings` action
4. If `deployment_blocked: true`, fix issues, re-run tests, iterate
5. If iteration 5 still has CRITICAL/HIGH, update task status to FAILED and write a failure report

Rotate reviewers across iterations: debugger, code-reviewer, architect-reviewer. Add security-auditor if touching auth/user-input.

### Stage 6 — Deployment

Use the **dev-deploy** skill, `deploy-to-agent` action to copy built skills to the target workspace specified in the task file. Read `dev-deploy/SKILL.md` for exact parameters.

The `deploy-to-agent` action:
- Copies skills to the target agent's workspace
- Registers new skills in the target agent's configuration (patches the agent config file if present)
- Creates backups before overwriting
- Does NOT restart the gateway (the delivery report will indicate if a restart is needed)

Deployment is blocked if any validator fails. Fix failures before retrying.

### Stage 7 — Documentation and Delivery

Use the **dev-sprint** skill, `update-docs` action to update PROGRESS.md with sprint completion.

Also manually update:
- ARCHITECTURE.md (if system design changed)
- DATA_SCHEMA.md (if database changed)
- CODEBASE_STRUCTURE.md (if new files/directories created)

Write the delivery report to `workspace/delivery/TASK_XXX_DELIVERY.md` with:
- What was built (skills, scripts, files)
- Whether the gateway needs restarting
- Test count and pass status
- Any known limitations or follow-up work

Update the task file's `**Status:**` to `DELIVERED`.

---

## Review Protocol (Primary — Single-Agent Mode)

This protocol works on any platform. For platforms with sub-agent support, see Enhanced Review Protocol below.

When you need to review code or plans:

1. **Prepare**: Run the `gather-context` action from the **dev-critique** skill. It outputs JSON containing a `system_prompt` (the reviewer's role), a `review_prompt` (what to look for), and `context_files` (the code to review).

2. **Context break**: Before reviewing, explicitly acknowledge: "I am now switching to reviewer mode. I will evaluate the code on its own merits without considering my intent when I wrote it."

3. **Review**: Read the `review_prompt` and `context_files` from the JSON output. For Stage 5, do NOT re-read the sprint plan — evaluate the code as if you are seeing it for the first time. Produce findings using severity format: `**CRITICAL**`, `**HIGH**`, `**MEDIUM**`, `**LOW**`.

4. **Parse**: Pipe your findings through the `parse-findings` action. Read the structured JSON result.

5. **Switch back**: "I am switching back to builder mode." Act on the findings.

6. **Iterate**: Repeat with a different reviewer role for the next iteration. Minimum 2 iterations per stage.

### Enhanced Review Protocol (Sub-Agent Platforms)

If your platform supports spawning isolated sub-agents (e.g., Claude Code's Agent tool):

1. Run `gather-context` action — same as above
2. Spawn a **new, isolated agent** with the `system_prompt` as its system instructions and `review_prompt` + `context_files` as its task
3. The sub-agent reviews independently and outputs markdown findings
4. Pipe the sub-agent's output through `parse-findings`
5. This provides true context isolation — the reviewer has zero knowledge of your intent

### Available Reviewer Roles

| Role | Best For | Stage |
|------|----------|-------|
| architect-reviewer | Architecture risks, SOLID, backward compatibility | 3, 5 |
| code-reviewer | Factual accuracy, code quality, correctness | 3, 5 |
| debugger | Error investigation, test failures, logical gaps | 5 |
| security-auditor | Vulnerabilities, injection, auth bypass, secrets | 5 |
| performance-reviewer | Bottlenecks, O(n^2), missing caches | 5 |

### Context Isolation Rules

- **Stage 3**: Reviewers DO see the sprint plan (that's what they're reviewing)
- **Stage 5**: Reviewers NEVER see the sprint plan — only code + tests
- **Each iteration**: Use a different reviewer role when possible
- In single-agent mode: take an explicit context break between builder and reviewer phases
- In sub-agent mode: each reviewer runs in a completely fresh context

---

## Context Recovery

On session start or after context loss:

1. Read `MEMORY.md` for cross-session state
2. Read `PROGRESS.md` for active sprint
3. Read the active sprint plan file
4. Resume from the current stage (noted in MEMORY.md)

---

## Self-Improvement Rules

**Autonomous** (no approval needed):
- Changes to workspace files (MEMORY.md, validator configs)
- Development tooling improvements (test fixtures, CI config)
- Documentation updates and clarifications

**Requires full sprint cycle** (Stages 2-7):
- Production code changes
- Database schema changes
- External service integrations
- New skills or capabilities

After any autonomous change, append a one-line entry to the Self-Improvement Log in MEMORY.md.

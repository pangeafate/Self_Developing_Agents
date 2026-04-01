# System Design: 3-Tier Agent Architecture

## Overview

The Self-Developing Agents Framework uses a strict 3-tier architecture that separates concerns across domain expertise, engineering discipline, and specialized analysis. Each tier has clearly defined responsibilities and hard boundaries on what it must never do.

This architecture is project-agnostic. It applies to any system where an AI agent manages a domain and needs to extend its own capabilities through code.

---

## Tier 1: Main Agent

### Role

The Main Agent is the domain expert and human-facing interface. It understands the problem domain deeply, routes human requests, and verifies that delivered features match what was asked for.

### Responsibilities

- **Route human requests**: Recognize when a request requires code changes and delegate to the Coding Agent
- **Domain expertise**: Maintain deep understanding of the application domain, data model, business rules, and user needs
- **Sprint plan review (Stage 3)**: Review sprint plans for domain correctness -- does the plan solve the right problem? Are the acceptance criteria correct? Does it align with the domain model?
- **Feature verification**: After the Coding Agent delivers, verify the feature works as intended from a domain perspective
- **Report to human**: Communicate results, ask clarifying questions, manage the human relationship

### Hard Boundaries -- What the Main Agent Must NEVER Do

- **NEVER write code.** Not even "small fixes." All code changes go through the Coding Agent.
- **NEVER review implementation code (Stage 5).** The Main Agent lacks the engineering context to evaluate code quality, and mixing domain review with code review dilutes both.
- **NEVER make architectural decisions.** Architecture is the Coding Agent's domain.
- **NEVER spawn quality-review sub-agents directly.** Review orchestration belongs to the Coding Agent.

### What the Main Agent Sees

- Human requests (natural language)
- Sprint plans (for domain review in Stage 3)
- Delivery reports from the Coding Agent
- Test results (pass/fail summary, not test code)

---

## Tier 2: Coding Agent (Dedicated Context)

### Role

The Coding Agent owns the entire engineering discipline. It operates in a dedicated context, separate from the Main Agent's conversation with the human. It is the architect, implementer, and orchestrator of all development work. In the default deployment, it runs as a **headless worker** — no Telegram binding, no direct human interaction. It receives tasks via file-based dispatch (Pattern 2) and delivers results via delivery reports.

### Responsibilities

- **Stage 2 -- Sprint Planning**: Analyze the task, research the codebase, write the sprint plan
- **Stage 3 -- Plan Review Orchestration**: Run parallel self-critique iterations via sub-agents, solicit domain review from Main Agent, consolidate findings, update the plan
- **Stage 4 -- Implementation**: Write code following TDD (test first, then implementation), following all GL-*.md engineering guidelines
- **Stage 5 -- Post-Implementation Review Orchestration**: Spawn context-isolated quality agents to review the delivered code (see Tier 3). Consolidate their findings and fix issues. Run iterative gap analysis rounds via sub-agents until a clean iteration (zero issues found). The Coding Agent itself NEVER validates its own code.
- **Stage 6 -- Deployment**: Push via CI/CD, verify deployment succeeded, handle failures
- **Stage 7 -- Documentation**: Update all affected docs (PROGRESS.md, PROJECT_ROADMAP.md, FEATURE_LIST.md, USER_STORIES.md, etc.)

### Hard Boundaries -- What the Coding Agent Must NEVER Do

- **NEVER validate its own code.** All review and quality checks are delegated to context-isolated sub-agents (Tier 3).
- **NEVER interact with the human directly.** All human communication goes through the Main Agent.
- **NEVER make domain decisions.** When domain questions arise, escalate to the Main Agent via the communication protocol.
- **NEVER skip the review stage.** Every sprint goes through Stage 5 review, no matter how small the change.

### Engineering Practices Owned by the Coding Agent

The Coding Agent is the sole owner and enforcer of:

- GL-TDD.md -- Test-driven development guidelines
- GL-RDD.md -- Documentation-first development and module splitting
- GL-ERROR-LOGGING.md -- Error handling and logging standards
- All architecture documents
- Sprint workspace management
- Module boundary enforcement

### Source Control Integration

On Day 1 of a new project, the Coding Agent should suggest that the human create a private GitHub repository (or equivalent). Benefits:

- Version history for all changes
- CI/CD pipeline for automated testing and deployment
- Pull request workflow for change tracking
- Rollback capability

If the human declines source control, the Coding Agent tracks all changes via sprint files in the workspace directory, maintaining a manual change log.

---

## Tier 3: Helper Agents (Context-Isolated)

Helper agents are short-lived, single-purpose agents spawned by the Coding Agent to perform specific tasks. They fall into two categories with different isolation requirements.

### Research Agents (Shared Context Permitted)

Research agents assist the Coding Agent with information gathering and analysis. They MAY share context with the Coding Agent because their output feeds into the Coding Agent's decision-making, not into quality evaluation.

| Agent | Purpose |
|-------|---------|
| **Researcher** | Search the codebase, find relevant files, understand existing patterns |
| **Analyzer** | Analyze data structures, trace execution paths, map dependencies |

Research agents receive the Coding Agent's current context (what it is building, why, relevant files) because this context makes their research more targeted and useful.

### Quality Agents (Strict Isolation Required)

Quality agents perform review and validation. They MUST be context-isolated from the Coding Agent's build intent to prevent confirmation bias. See [CONTEXT_ISOLATION.md](CONTEXT_ISOLATION.md) for the full rationale.

| Agent | Purpose | What It Receives |
|-------|---------|-----------------|
| **Architect-Reviewer** | Evaluate architecture risks, backward compatibility, deployment ordering, scope creep, performance | The code files to review + relevant existing architecture docs. During Stage 3: the sprint plan. During Stage 5: NEVER the sprint plan. |
| **Code-Reviewer** | Verify factual claims, check that referenced functions/fields/signatures exist, find practical implementation issues | The code files to review + the actual source files they reference. During Stage 3: the sprint plan. During Stage 5: NEVER the sprint plan. |
| **Debugger** | Investigate test failures, trace bugs, propose fixes | Failing test output + relevant source files. Never the sprint plan or build intent. |
| **Security-Auditor** | Check for security vulnerabilities, credential exposure, injection risks | The code files to review. Never the sprint plan or build intent. |
| **Performance-Reviewer** | Identify performance bottlenecks, unnecessary allocations, N+1 queries | The code files to review + relevant data model docs. Never the sprint plan or build intent. |

### Lifecycle of a Helper Agent

1. **Spawn**: Coding Agent creates the helper with a structured task prompt and the specific files/context it needs
2. **Execute**: Helper performs its task in complete isolation
3. **Report**: Helper writes findings to a result file or returns them directly
4. **Terminate**: Helper context is discarded. It is never reused for a subsequent iteration.

Each review iteration starts a fresh agent context. A reviewer that ran in Iteration 1 of gap analysis is never reused for Iteration 2. This prevents accumulated bias.

---

## Communication Protocols

Two communication mechanisms support different deployment scenarios. A project should choose one based on its platform capabilities.

### Pattern 1: Sub-Agent Spawn (Same Platform)

Used when the Main Agent and Coding Agent run on the same platform and the platform supports spawning sub-agents programmatically.

```
Human -> Main Agent: "I need the system to handle recurring tasks"
                          |
                          | [spawns Coding Agent with structured task prompt]
                          v
                    Coding Agent
                          |
                          | [spawns Helper Agents as needed]
                          | [writes results to delivery/TASK_XXX_REPORT.md]
                          v
                    Main Agent [reads delivery report]
                          |
                          | [verifies domain correctness]
                          v
                    Human: "Done. Here's what was built..."
```

**Flow**:
1. Main Agent recognizes a coding task (see [ROUTING_RULES.md](ROUTING_RULES.md))
2. Main Agent spawns Coding Agent with a structured task prompt containing:
   - What the human asked for (verbatim or summarized)
   - What functionality is missing
   - Acceptance criteria
   - Domain context (relevant entities, business rules)
3. Coding Agent executes the full development cycle (Stages 2-7: planning, review, implementation, post-implementation review, deployment, documentation)
4. Coding Agent writes results to a delivery file
5. Main Agent reads the delivery file and verifies
6. Main Agent reports to the human

### Pattern 2: File-Based Task Dispatch (Cross-Platform)

Used when the Main Agent and Coding Agent run on different platforms, different machines, or cannot spawn each other directly. In the default configuration, the Coding Agent operates as a **headless worker** — it has no Telegram binding and no direct human interaction. It receives all work via task files and delivers results via delivery reports.

```
workspace-dev-agent/
  tasks/
    TASK_001_add_email_skill.md    # Status: IN_PROGRESS (in-file)
    TASK_002_fix_login_bug.md      # Status: NEW (in-file)
  delivery/
    TASK_001_DELIVERY.md           # Delivery report
```

**Status Enum** (v1 — simplified):

| Status | Set By | Meaning |
|--------|--------|---------|
| `NEW` | Main Agent | Task created, awaiting pickup |
| `IN_PROGRESS` | Coding Agent | Coding Agent is working on this task |
| `DELIVERED` | Coding Agent | Work complete, delivery report written |
| `FAILED` | Coding Agent | Work failed, failure report written |

> **Note:** `REVIEW_REQUESTED` and `VERIFIED` are deferred to a future version. In v1, the lifecycle ends at `DELIVERED`. The Main Agent reads the delivery report and implicitly verifies by restarting the gateway and testing the new capability.

**Task File Format** (written by Main Agent, status updated in-place by Coding Agent):

```markdown
# Task: [Title]

**ID:** TASK_XXX
**Status:** NEW
**Requested by:** [Main Agent ID]
**Target workspace:** [Main Agent workspace path]
**Created:** [ISO timestamp]
**Timeout hours:** 24
**Priority:** high | medium | low

## What the Human Asked For
[The original request from the human]

## What Functionality Is Missing
[Technical description of the gap — what skill, script, or service needs to be built]

## Acceptance Criteria
- [ ] Criterion 1
- [ ] Criterion 2

## Domain Context
[Which existing skills, tables, or services this relates to. Include file paths if known.]
```

Task metadata uses **bold labels** (`**Status:** NEW`) rather than headings (`## Status: NEW`). This keeps the document structure flat and makes in-place status updates straightforward with simple text replacement.

**Delivery Report Format** (`delivery/TASK_XXX_DELIVERY.md`):

```markdown
# Delivery: TASK_XXX — [Title]

**Status:** DEPLOYED | FAILED
**Sprint:** SP_XXX
**Completed:** [ISO timestamp]
**Skills deployed:** [list]
**Tests added:** [count]
**Files changed:** [list]

## What Was Built
[Summary]

## Deployment Details
- Target workspace: [path]
- Skills copied: [list]
- Agent config registered: yes/no
- Gateway restart needed: yes/no (platform-specific restart command may be required)

## Known Limitations
[Any caveats or follow-up work needed]
```

**Flow**:
1. Main Agent writes a task file to the Coding Agent's `tasks/` directory with `**Status:** NEW`
2. Coding Agent polls `tasks/` on heartbeat (every 10 minutes) via `poll-tasks.py`
3. Coding Agent picks up the highest-priority NEW task, updates `**Status:**` to `IN_PROGRESS`
4. Coding Agent executes the full 7-stage development cycle
5. Coding Agent deploys built skills to the Main Agent's workspace via `deploy-to-agent.py`
6. Coding Agent writes `delivery/TASK_XXX_DELIVERY.md`, updates task `**Status:**` to `DELIVERED`
7. Main Agent reads the delivery report on its next heartbeat and acts on it (restart gateway if needed)

---

## Stage Summary

| Stage | Owner | Description |
|-------|-------|-------------|
| 1 | Main Agent | Task Recognition: receive human request, recognize coding need, create task |
| 2 | Coding Agent | Sprint Planning: research codebase, write sprint plan |
| 3 | Coding Agent + Main Agent | Plan Review: Coding Agent runs self-critique sub-agents, Main Agent reviews for domain correctness |
| 4 | Coding Agent | Implementation: TDD (tests first, then code) |
| 5 | Coding Agent (via Quality Agents) | Post-Implementation Review: context-isolated reviewers + iterative gap analysis until clean |
| 6 | Coding Agent | Deployment: push via CI/CD, verify, handle failures |
| 7 | Coding Agent | Documentation: update PROGRESS.md, roadmap, features, user stories |

---

## Workspace Structure

The Coding Agent maintains a structured workspace for all development artifacts:

```
<agent-workspace>/
  tasks/
    TASK_XXX.md                   # Task definitions (file-based dispatch)
  delivery/
    TASK_XXX_DELIVERY.md          # Delivery reports
  sprints/
    SP_XXX_Description.md         # Sprint plans
  skills/
    dev-bootstrap/                # Bootstrapping skill
    dev-sprint/                   # Sprint planning skill
    dev-critique/                 # Self-critique skill
    dev-deploy/                   # Deployment skill
  AGENTS.md                       # Behavioral rules
  HEARTBEAT.md                    # Periodic maintenance
  MEMORY.md                       # Cross-session state
```

---

## Design Principles

1. **Separation of concerns**: Domain knowledge, engineering discipline, and quality review are never mixed in a single agent context.
2. **Context isolation for quality**: Reviewers that never saw the build intent catch fundamentally different classes of bugs than reviewers who did. See [CONTEXT_ISOLATION.md](CONTEXT_ISOLATION.md).
3. **Single responsibility per agent**: Each agent does one thing well. The Main Agent routes. The Coding Agent builds. Helper agents analyze or review.
4. **Fresh contexts for each iteration**: No agent accumulates state across review iterations. Each iteration starts clean.
5. **File-based contracts**: All inter-agent communication uses structured files with defined formats. No implicit state passing.

# Agent Instructions

This is the operating rulebook for any agent using the Self-Developing Agents Framework. Every rule listed here is mandatory and non-negotiable. Violations cause validators to fail and block deployment.

These rules are project-agnostic. Project-specific configuration (database details, platform credentials, deployment targets) belongs in your project's own instruction file, not here.

**Development cycle reference**: All work follows the 7-stage self-improvement cycle defined in `architecture/SYSTEM_DESIGN.md`: (1) Task Recognition, (2) Sprint Planning, (3) Plan Review, (4) Implementation, (5) Post-Implementation Review, (6) Deployment, (7) Documentation. No stage may be skipped. Validators in `validators/` enforce this.

**Cross-cutting practices**: `practices/GL-CONTEXT-MANAGEMENT.md` applies at every stage transition -- re-read the sprint plan, persist intermediate state, provide full context to sub-agents. `practices/GL-TEMPLATE-ENFORCEMENT.md` applies whenever output is generated -- read the template before producing output, never freestyle. `practices/GL-DOC-RECONCILIATION.md` applies at Stage 7 -- reconcile meta-docs with shipped reality before the sprint closes.

---

## The 16 Rules

### 1. Test-Driven Development is Non-Negotiable

Never write code before writing a failing test. Follow `practices/GL-TDD.md` for the full RED/GREEN/REFACTOR cycle, coverage thresholds, and anti-patterns. Automated tests are required for all production code: scripts, services, and library modules. No exceptions.

### 2. Documentation-First Development

Follow `practices/GL-RDD.md` for documentation-first development and module splitting guidelines. Document the interface before implementing it. When a module exceeds complexity thresholds (cyclomatic complexity >10, cognitive complexity >15, >8 imports, >4 parameters), split it. SRP trumps pattern cohesion.

### 3. Error Handling and Logging Standards

Follow `practices/GL-ERROR-LOGGING.md` for error handling and logging standards. Use the five severity levels (DEBUG, INFO, WARNING, ERROR, CRITICAL) and the five error type categories (domain, infrastructure, integration, runtime, security). Follow the exit code convention: 0=success, 1=recoverable, 2=fatal, 3=configuration. Never swallow exceptions. Never log secrets.

### 4. Layer Boundaries

Maintain clear layer boundaries. The canonical layers are:

- **Capabilities** -- execution entry points (what the agent can do)
- **Shared logic** -- reusable business logic and services
- **Models** -- data structures, enums, domain objects
- **Infrastructure** -- setup, configuration, deployment scripts

Dependencies flow inward: capabilities depend on shared logic, shared logic depends on models, infrastructure is standalone. Never allow a model to import from a capability. Never allow shared logic to import from infrastructure.

### 5. Context Isolation

All review, gap analysis, and debugging work MUST be done by dedicated sub-agents. The agent that built the code must NOT be the same context that reviews it. This prevents confirmation bias and context contamination between builder and reviewer.

Specific isolation rules:
- The Coding Agent never validates its own code.
- Quality agents (architect-reviewer, code-reviewer, debugger) never see the sprint plan during post-implementation review (Stage 5). They receive only code, tests, and a neutral review prompt. During plan review (Stage 3), they do see the plan because that is what they are reviewing.
- Each review iteration starts a fresh agent context with no accumulated bias.
- Research agents may share context with the Coding Agent. Quality agents must not.

See `architecture/CONTEXT_ISOLATION.md` for the full rationale and anti-patterns.

### 6. Pre-Feature Discipline

Before building any feature:
1. Check `PROJECT_ROADMAP.md` (create it if it does not exist).
2. Create the sprint plan in `workspace/sprints/` using naming `SP_XXX_Description.md` (zero-padded sequential number).
3. Update `PROGRESS.md` with a condensed sprint description.
4. If the sprint produces multiple files, create a `SP_XXX_Description/` subfolder under `workspace/sprints/`.

See `practices/GL-SPRINT-DISCIPLINE.md` for the full checklist.

### 7. Post-Implementation Documentation

After implementation, update all affected documentation:
- `PROGRESS.md` -- mark sprint complete with summary.
- `PROJECT_ROADMAP.md` -- update milestone status.
- `FEATURE_LIST.md` -- mark features as implemented.
- `USER_STORIES.md` -- update story status.
- `CODEBASE_STRUCTURE.md` -- if new files or directories were created.
- `ARCHITECTURE.md` -- if system design changed.
- `DATA_SCHEMA.md` -- if database schema changed.

This is Stage 7 of the development cycle. It is not optional. See also Rule 16 for the reconciliation checklist and the `last-reconciled` frontmatter contract.

### 8. Sprint Plan Self-Critique

After writing and saving a sprint plan, run a minimum of 2 parallel review iterations using dedicated sub-agents before starting implementation (Stage 3):

- **Iteration 1 (architect-reviewer)**: Evaluate architecture risks, backward compatibility, deployment ordering, scope creep, TDD compliance, missing edge cases, and performance. Rank issues by severity: CRITICAL, HIGH, MEDIUM, LOW.
- **Iteration 2 (code-reviewer)**: Independently verify factual claims against the actual codebase. Check that referenced functions, field names, and signatures actually exist. Find issues the first reviewer missed. Focus on practical implementation details.
- Both reviewers must read the sprint plan in full plus all source files it references.
- Consolidate findings and update the plan to address all CRITICAL and HIGH issues.
- Continue iterating until zero CRITICAL/HIGH issues remain. Minimum 2 iterations even if the first comes back clean.

### 9. Post-Sprint Gap Analysis

After each sprint's tests pass and BEFORE deployment (Stage 6), run a minimum of 2 sequential gap analysis iterations using dedicated sub-agents (part of Stage 5). Continue up to 5 iterations:

- Each iteration reviews all new files for: logical gaps, missing edge cases, inconsistencies between modules, broken cross-references, untested paths, import errors, schema-to-model sync, error path coverage, and cross-module contract consistency.
- Fix any bugs found and re-run tests before the next iteration.
- Stop early (fewer than 5 iterations) ONLY if an iteration finds zero issues.
- Minimum 2 iterations even if the first comes back clean.
- **Hard stop**: If iteration 5 still has CRITICAL or HIGH issues, do NOT proceed to Stage 6 (Deployment). Block deployment and report unresolved issues to the human for guidance.

See `practices/GL-SELF-CRITIQUE.md` for the full review protocol and checklists.

### 10. Sprint Plan Persistence

Save sprint plans to disk before implementation begins. After any context loss (compaction, session break, token limit), re-read the sprint plan file as the first action to restore context. The sprint plan file on disk is the authoritative context anchor, not memory and not conversation history.

See `practices/GL-CONTEXT-MANAGEMENT.md` for context restoration patterns and sub-agent context passing.

### 11. CI/CD-First Deployment

Deploy via CI/CD (git push). Direct server access (SSH, remote shell) is emergency-only, used when CI/CD itself is broken. Every deployment must be version-controlled and traceable.

Post-deploy: verify the deployment succeeded. If deployment fails, do NOT proceed to Stage 7. Report the failure to the human.

See `practices/GL-DEPLOYMENT.md` for the full deployment protocol and security boundaries.

### 12. Version-Controlled Workspace

All workspace files must be pushed via version control. This includes MEMORY.md, agent configuration, validator configs, sprint plans, progress tracking, and all documentation. Nothing lives only on a server or only in an agent's memory. If it matters, it is in git.

### 13. Pre-Deploy Validation

Run `validators/run_all.py` before every deployment. The validators catch skipped stages, missing tests, undocumented modules, structural violations, and credential leaks. A validator failure blocks deployment. Fix the issue, do not bypass the validator.

### 14. Sub-Agents for External Tool Calls

Use dedicated sub-agents when invoking MCP tools or any external service integration. This keeps the main execution context clean and prevents tool-specific errors from contaminating the primary workflow.

### 15. Self-Improvement Scope

The agent may make certain changes autonomously without a full sprint cycle:

**No approval required**:
- Changes to the agent's own workspace files (MEMORY.md, validator configs, practice clarifications).
- Development tooling (test fixtures, CI configuration, helper scripts).
- Documentation updates and corrections.

**Standard 7-stage sprint cycle required**:
- Production code changes.
- Database schema changes.
- External service integrations.

**Audit trail**: After any autonomous self-improvement, append a one-line entry to a self-improvement log so the human has visibility into what changed and why.

**Override**: When told to present a proposal first, do that instead of making the change directly.

### 16. Documentation Reconciliation

Before Stage 6 (Deployment), run `validators/validate_doc_reality.py <project_root>`; a failure blocks deployment. At Stage 7 (Documentation), complete the reconciliation checklist: for every meta-doc whose subject-matter was touched by this sprint, update content and bump `last-reconciled`.

Rule 15's autonomous-update clause remains in effect for docs-only changes: such changes must still bump `last-reconciled` and may be validated post-hoc, but they do not require the full Stage-7 reconciliation pass.

See `practices/GL-DOC-RECONCILIATION.md` for the frontmatter convention, the single-source rule and the `@inherits:` directive, vision-doc quarantine, and the TBD-by decay rule.

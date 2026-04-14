# Deployment Rules

_Safe deployment practices for self-developing agent projects_

**Version**: 1.0
**Status**: Active Development Guidelines

---

## Philosophy

Deployment is the highest-risk phase of any sprint. A single bad push can break a running system. Self-developing agents must follow strict deployment protocols because they lack the intuitive caution that experienced human developers bring to production operations. Every rule here exists because an agent (or human) made the mistake it prevents.

## Core Deployment Principles

### 1. CI/CD via Git Push -- Always Preferred

The standard deployment path is:

```
git push -> CI/CD pipeline -> automated deploy
```

This is the ONLY deployment method for normal operations. It provides:
- Audit trail (git history)
- Automated testing (CI runs tests before deploy)
- Rollback capability (revert the commit)
- Review opportunity (PR gates, if configured)

### 2. Direct Server Access -- Emergency Only

SSH or direct server commands are reserved for emergencies:
- Production is down and CI/CD pipeline is broken
- Security incident requiring immediate intervention
- Infrastructure failure that blocks the normal pipeline

**Every emergency deploy must be:**
- Logged (what was changed, why, by whom/what agent)
- Followed up with a proper git commit that captures the changes
- Reviewed by a human or security-auditor agent after the fact

### 3. No Docker for Application Code

Docker containers are appropriate for infrastructure services (databases, message queues, reverse proxies). Application code -- agent capabilities, shared libraries, models -- deploys directly.

**Why**: Agent application code changes frequently and benefits from fast iteration cycles. Container build/push/pull adds latency and complexity that is not justified for scripts and libraries.

**Exception**: If the project's architecture specifically requires containerized application deployment (e.g., Kubernetes-based systems), document the rationale in ARCHITECTURE.md and adjust these guidelines accordingly.

## Pre-Deploy Lockfile Requirement

Stage 7 (Deployment) MUST NOT begin until Stage 6 (Documentation) has produced a valid `.docs_reconciled` lockfile at the project root. Verify:

1. The file `.docs_reconciled` exists at `<project_root>/.docs_reconciled`.
2. It parses as JSON with `schema_version: 1`.
3. Its `sprint_id` equals the active sprint ID from `PROGRESS.md`.

Any check failing → refuse deploy; return to Stage 6.

The lockfile is written by `validators/validate_doc_freshness.py` on a clean run. Its presence is the machine-readable receipt that documentation was reconciled against the sprint's git diff. Do not hand-write the lockfile; if validation won't produce it, fix the validator findings first.

The lockfile is gitignored (local build artifact, not committed state). Each sprint overwrites the previous sprint's lockfile.

## Bootstrap File Size Limits

Most agent platforms load certain files at session start: identity files, instruction documents, workspace configuration. These files are loaded into the agent's context window on every session, consuming tokens before any work begins.

### The Problem

A bootstrap file that grows unchecked eventually:
- Crowds out working context for actual tasks
- Increases session start latency
- May hit platform-specific size limits that cause silent truncation

### Configuration

Define size limits in a `.validators.yml` file at the project root (or equivalent configuration):

```yaml
bootstrap_files:
  hard_limit_bytes: 20000      # Files above this BLOCK deployment
  warning_limit_bytes: 18000   # Files above this emit a WARNING

  monitored_files:
    - workspace/AGENTS.md
    - workspace/IDENTITY.md
    - workspace/SOUL.md
    - workspace/HEARTBEAT.md
    - workspace/TEMPLATES.md
    # Add any file loaded at agent session start
```

### Enforcement

**Pre-deploy check** (add to CI/CD or pre-push hook):

```python
import os
import yaml

def check_bootstrap_sizes(config_path=".validators.yml"):
    with open(config_path) as f:
        config = yaml.safe_load(f)

    bs = config["bootstrap_files"]
    hard = bs["hard_limit_bytes"]
    warn = bs["warning_limit_bytes"]
    violations = []

    for path in bs["monitored_files"]:
        if not os.path.exists(path):
            continue
        size = os.path.getsize(path)
        if size > hard:
            violations.append(f"BLOCK: {path} is {size} bytes (limit: {hard})")
        elif size > warn:
            violations.append(f"WARNING: {path} is {size} bytes (warning at: {warn})")

    return violations
```

### When a File Exceeds the Limit

1. **Identify what grew**: Usually accumulated rules, examples, or known issues
2. **Extract to reference files**: Move detailed content to `references/` or `docs/` -- the agent reads these on-demand rather than loading them at startup
3. **Archive old content**: Move superseded rules to an archive file
4. **Never truncate silently**: If content must be removed, ensure it is preserved elsewhere

## Version Control Requirements

### All Workspace Files Must Be Version-Controlled

Every file that affects agent behavior must be in git:
- Capability specs (SPEC.md / SKILL.md)
- Workspace instructions (AGENTS.md, IDENTITY.md, HEARTBEAT.md)
- Templates (TEMPLATES.md, references/*.md)
- Configuration (cron schedules, model settings)
- Deployment scripts

**Exception**: Credentials and secrets. These NEVER go in version control (see Security Boundaries below).

### Commit Before Deploy

The agent must not deploy code that is not committed. Uncommitted changes:
- Cannot be rolled back via git
- Are invisible to CI/CD
- May be lost if the server is reprovisioned

## Deployment Failure Protocol

When deployment (Stage 7) fails (CI/CD error, test failure in pipeline, infrastructure issue):

1. **Do NOT mark the sprint as complete in PROGRESS.md** — Stage 6 (Documentation) already happened on the assumption deploy would follow. If deploy fails permanently, either revert the Stage 6 doc bumps or open a follow-up sprint to reconcile.
2. **Do NOT delete `.docs_reconciled`** — it is the receipt for this attempt's docs state. A retry of deploy reuses it; a new Stage 6 run would overwrite it.
3. **Diagnose the failure**: Read CI/CD logs, identify root cause
4. **Fix and re-deploy** if the fix is straightforward
5. **Report to human** if the failure is:
   - Infrastructure-related (server down, credentials expired)
   - Caused by environment differences (works locally, fails in CI)
   - Intermittent or non-deterministic
   - Not diagnosable from available logs

## Security Boundaries

### Credentials NEVER in Version-Controlled Files

- API keys, tokens, passwords: environment variables or secret managers only
- Database connection strings: environment variables
- SSH keys: never committed, managed separately
- `.env` files: add to `.gitignore`, document required variables in `.env.example`

### Emergency Deploy Logging

Every direct server access must be logged with:
- Timestamp
- Who/what agent initiated it
- What was changed
- Why the normal pipeline was bypassed
- When the follow-up git commit was made

### Destructive Commands Require Human Confirmation

The following operations should NEVER be executed by an autonomous agent without human approval:

- `git push --force` (rewrites history)
- `git reset --hard` (discards uncommitted work)
- Database schema drops or truncates
- Deleting production files or directories
- Restarting production services
- Modifying firewall rules or network configuration

### Security-Auditor Reviews

In multi-agent setups, designate a security-auditor reviewer role that:
- Reviews all SSH operations in emergency deploys
- Validates that no credentials leaked into git history
- Checks file permissions on deployed code
- Verifies that emergency changes were properly committed afterward

## Pre-Deploy Checklist

```
[ ] All tests passing (unit + integration)
[ ] Coverage meets thresholds (GL-TDD.md)
[ ] Post-implementation review passed (GL-SELF-CRITIQUE.md Stage 5)
[ ] No CRITICAL or HIGH issues outstanding
[ ] All changes committed to git
[ ] Bootstrap file sizes within limits
[ ] No credentials in committed files
[ ] PROGRESS.md updated
[ ] Ready to push
```

## Post-Deploy Verification

After a successful deploy:

1. **Verify the deployment took effect**: Check that new capabilities are available, updated behavior is observable
2. **Run a smoke test** if available: A minimal end-to-end check that the system is functional
3. **Monitor for errors**: Check logs for the first few minutes after deploy
4. **Update documentation**: Complete the post-feature checklist (GL-SPRINT-DISCIPLINE.md)

## Rollback Procedure

If a deployment causes issues in production:

1. **Revert the commit**: `git revert <commit-hash>` (creates a new commit, preserves history)
2. **Push the revert**: Let CI/CD deploy the rollback
3. **Do NOT use `git push --force`** unless the commit contains leaked secrets
4. **Investigate**: Determine why the issue was not caught by tests or review
5. **Create a fix sprint**: If the revert removes desired functionality, plan a new sprint to re-implement with the fix

---

_This framework ensures that deployments are safe, auditable, and reversible. Every rule exists to prevent a specific class of failure._

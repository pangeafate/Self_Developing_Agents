---
name: dev-deploy
description: Pre-deploy validation, git push deployment, task polling, and cross-agent skill deployment
version: 2.0.0
---

# Dev Deploy — Validation, Deployment, and Inter-Agent Bridge

Run all validators before deployment, push to version control, poll for incoming tasks, and deploy built skills to target agent workspaces.

## When to Use

- **Stage 7 (Deployment)**: After Stage 6 Documentation completes and `.docs_reconciled` lockfile exists — validate and deploy
- **Anytime**: Run validators without pushing (`--action validate`) as a health check
- **Heartbeat**: Poll for new tasks from the Main Agent (`poll-tasks.py`)
- **Cross-agent deployment**: Copy built skills to the Main Agent's workspace (`deploy-to-agent.py`)

## Available Scripts

### deploy.py — Validate and deploy

**Usage:**
```bash
# Dry run — validate only, no push
python scripts/deploy.py --action validate --project-root .

# Full deploy — validate + git add/commit/push
python scripts/deploy.py --action push --project-root . --message "SP_042: Add user auth"
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--action` | Yes | `validate` (dry run) or `push` (validate + git push) |
| `--project-root` | Yes | Project root directory |
| `--message` | For push | Git commit message (required when action=push) |
| `--validators-dir` | No | Path to validators directory (default: `<project-root>/validators/`) |
| `--skip-validators` | No | Comma-separated validator names to skip |

**Output (JSON to stdout):**
```json
{
  "status": "pushed",
  "validators_passed": true,
  "validator_results": {"structure": "PASS", "workspace": "PASS", "tdd": "PASS", "rdd": "PASS", "sprint": "PASS"},
  "commit_hash": "a1b2c3d",
  "files_committed": 5
}
```

**Exit Codes:**
| Code | Meaning |
|------|---------|
| 0 | Success (validated, or validated + pushed) |
| 1 | Validators failed — deployment blocked |
| 2 | Git error (fatal — commit or push failed) |
| 3 | Configuration error (validators directory not found) |

**Deployment is blocked if any validator fails.** The script will NOT push code that fails validation.

---

### poll-tasks.py — Check for pending tasks

Scans a tasks directory for markdown files with `**Status:** NEW` and returns a summary of pending work. Designed to be called on every heartbeat.

**Usage:**
```bash
# Check for new tasks
python scripts/poll-tasks.py --tasks-dir /path/to/tasks/
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--tasks-dir` | Yes | Path to the directory containing task markdown files |

**Output (JSON to stdout):**
```json
{
  "pending_count": 2,
  "task_ids": ["TASK_003", "TASK_007"],
  "next_task": {
    "id": "TASK_003",
    "file": "TASK_003_add_email_skill.md",
    "title": "Add Email Skill",
    "priority": "high",
    "status": "NEW",
    "created": "2026-04-01T10:00:00Z",
    "timeout_hours": 24
  }
}
```

When no tasks are pending:
```json
{
  "pending_count": 0,
  "task_ids": [],
  "next_task": null
}
```

**Exit Codes:**
| Code | Meaning |
|------|---------|
| 0 | Success (tasks found or none pending) |
| 1 | Error reading tasks directory (missing, permissions) |

**Behavior:**
- Only counts files with `**Status:** NEW` as pending
- Ignores files with status IN_PROGRESS, DELIVERED, or FAILED
- Sorts pending tasks by priority: high > medium > low
- Tasks without a priority field default to `medium`
- Skips malformed files (missing required fields) with a warning on stderr

---

### deploy-to-agent.py — Deploy skills to target agent workspace

Copies a built skill directory to a target agent's workspace and registers it in the target's openclaw.json. Includes backup, atomic JSON patching, dry-run, and rollback capabilities.

**Usage:**
```bash
# Deploy a skill to the Main Agent's workspace
python scripts/deploy-to-agent.py \
  --source-dir /path/to/built/skill/ \
  --target-workspace /path/to/main-agent/workspace/ \
  --skill-name my-new-skill

# Deploy with config patching
python scripts/deploy-to-agent.py \
  --source-dir /path/to/built/skill/ \
  --target-workspace /path/to/main-agent/workspace/ \
  --skill-name my-new-skill \
  --config-file /home/openclaw/.openclaw/openclaw.json

# Dry run — show what would happen without making changes
python scripts/deploy-to-agent.py \
  --source-dir /path/to/built/skill/ \
  --target-workspace /path/to/main-agent/workspace/ \
  --skill-name my-new-skill \
  --dry-run

# Rollback a previously deployed skill
python scripts/deploy-to-agent.py \
  --target-workspace /path/to/main-agent/workspace/ \
  --skill-name my-new-skill \
  --rollback
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--source-dir` | Yes (deploy) | Path to the built skill directory to copy |
| `--target-workspace` | Yes | Path to the target agent's workspace |
| `--skill-name` | Yes | Name of the skill (used for directory name and config registration) |
| `--config-file` | No | Path to the target's openclaw.json (if provided, registers the skill) |
| `--dry-run` | No | Show what would happen without making changes |
| `--rollback` | No | Restore the skill from its `.bak/` backup (ignores `--source-dir`) |

**Output (JSON to stdout):**
```json
{
  "status": "deployed",
  "skill_name": "my-new-skill",
  "target_workspace": "/path/to/main-agent/workspace/",
  "files_copied": 5,
  "backup_created": true,
  "backup_path": "/path/to/main-agent/workspace/skills/my-new-skill.bak/",
  "config_patched": true,
  "gateway_restart_needed": true
}
```

**Exit Codes:**
| Code | Meaning |
|------|---------|
| 0 | Success (deployed or rolled back) |
| 1 | Validation failed (source dir missing required files) |
| 2 | Fatal error (target workspace missing, copy failed) |
| 3 | Configuration error (malformed openclaw.json, JSON patch failed) |

**Safety Measures:**
1. **Backup**: Before overwriting, copies the existing skill directory to `<skill-name>.bak/`
2. **Atomic JSON patch**: Reads openclaw.json, patches in memory, validates with `json.loads()`, writes to `.tmp`, then renames
3. **Python json module**: Uses Python's `json` module (not jq subprocess) for reliable JSON manipulation
4. **Domain skill registration**: Registers as `skills.entries[name] = {}` (no `SDA_FRAMEWORK_ROOT` — domain skills do not import framework modules)
5. **No gateway restart**: The script does NOT restart the gateway. It outputs `"gateway_restart_needed": true` in the JSON report. The human or CI pipeline handles the restart.
6. **Rollback**: `--rollback` restores from the `.bak/` directory created during the last deployment
7. **Dry run**: `--dry-run` reports what would change without modifying any files
8. **Permission model**: Sets `openclaw:openclaw` ownership, `550` for `.py` files, `440` for `.md` files

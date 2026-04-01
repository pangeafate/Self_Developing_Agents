---
name: dev-bootstrap
description: Automate Day 1 workspace setup for new projects
version: 1.0.0
---

# Dev Bootstrap — Day 1 Workspace Setup

Automates the mechanical steps of BOOTSTRAP.md — creates directories, copies templates, practices, validators, and workspace files into the target project.

## When to Use

- **Day 1**: When setting up a new project with the Self-Developing Agents Framework
- **Verification**: When checking if an existing workspace is correctly configured

## Available Scripts

### bootstrap.py — Automate workspace setup

Handles Steps 2-5 of BOOTSTRAP.md programmatically. Does NOT replace the full BOOTSTRAP.md workflow — the human still needs to handle Step 1 (GitHub repo setup) and Step 6 (readiness report).

**Usage:**
```bash
# Full Day 1 setup
python scripts/bootstrap.py --action setup --project-root /path/to/project

# Verify existing setup
python scripts/bootstrap.py --action verify --project-root /path/to/project

# Setup without running validators
python scripts/bootstrap.py --action setup --project-root /path/to/project --skip-validation
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--action` | Yes | `setup` (create workspace) or `verify` (check existing workspace) |
| `--project-root` | Yes | Target project root directory |
| `--framework-root` | No | Path to framework (auto-detected by walking up from script location) |
| `--skip-validation` | No | Skip running validators after setup |

**What `setup` does:**
1. Creates workspace directory structure (workspace/, test/unit/, test/integration/, test/fixtures/, workspace/sprints/)
2. Copies template files from `templates/` into `workspace/`
3. Copies practice files (`practices/GL-*.md`) into `workspace/`
4. Copies validators (`validators/`) into `<project-root>/validators/`
5. Copies workspace behavioral templates (AGENTS.md, HEARTBEAT.md, MEMORY.md) into `workspace/`
6. Runs `validators/run_all.py --bootstrap` (unless --skip-validation)

**Output (JSON to stdout):**
```json
{
  "status": "setup_complete",
  "dirs_created": ["workspace/", "workspace/sprints/", "test/unit/", "test/integration/", "test/fixtures/"],
  "files_copied": 22,
  "validation_result": "passed"
}
```

**Exit Codes:**
| Code | Meaning |
|------|---------|
| 0 | Success — workspace fully set up |
| 1 | Partial — setup complete but validation had warnings |
| 2 | Fatal — cannot create directories or copy files |
| 3 | Configuration — framework root not found |

**What `verify` does:**
Checks that all expected workspace files and directories exist. Reports missing items. Does NOT create anything.

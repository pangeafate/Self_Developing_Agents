---
name: dev-sprint
description: Sprint lifecycle management — create plans and update documentation
version: 1.0.0
---

# Dev Sprint — Sprint Lifecycle Management

Create sprint plan files from requirements and update tracking documentation after sprint completion.

## When to Use

- **Stage 2 (Sprint Planning)**: Create a new sprint plan skeleton
- **Stage 7 (Documentation)**: Update PROGRESS.md, PROJECT_ROADMAP.md, FEATURE_LIST.md after completing a sprint

## Available Scripts

### create-plan.py — Create a sprint plan from requirements

Reads the SPRINT_PLAN.md template, fills in the sprint ID, goal, and today's date, and writes the skeleton to the output directory. The agent fills in substantive sections (Technical Approach, Testing Strategy, etc.) manually after creation.

**Usage:**
```bash
python scripts/create-plan.py \
  --sprint-id SP_042 \
  --goal "Add user authentication" \
  --output-dir workspace/sprints/
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--sprint-id` | Yes | Sprint identifier (e.g., `SP_042`) |
| `--goal` | Yes | One-line sprint goal |
| `--output-dir` | Yes | Directory to write the plan file |
| `--template` | No | Path to custom template (defaults to framework's `templates/SPRINT_PLAN.md`) |

**Output (JSON to stdout):**
```json
{"sprint_id": "SP_042", "file_path": "workspace/sprints/SP_042_Add_User_Authentication.md", "created_at": "2026-03-31"}
```

**Exit Codes:** 0=created, 2=fatal (template not found, output dir creation failed)

### update-docs.py — Update tracking docs after sprint completion

Moves the sprint from "Active Sprint" to "Sprint History" in PROGRESS.md and adds a summary entry.

**Usage:**
```bash
python scripts/update-docs.py \
  --sprint-id SP_042 \
  --status complete \
  --summary "Added JWT auth with login/logout endpoints and middleware" \
  --tests-added 23
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--sprint-id` | Yes | Sprint identifier |
| `--status` | Yes | `complete`, `abandoned`, or `superseded` |
| `--summary` | Yes | One-line description of what was delivered |
| `--progress-file` | No | Path to PROGRESS.md (auto-detected at project root) |
| `--tests-added` | No | Number of new tests added |

**Output (JSON to stdout):**
```json
{"files_updated": ["PROGRESS.md"], "sprint_id": "SP_042", "status": "complete"}
```

**Exit Codes:** 0=updated, 1=sprint not found in PROGRESS.md, 2=fatal

**Important:** Writes Active Sprint section using `**Current:** SP_XXX` format (required by validate_sprint.py), not the template's `- **Sprint**:` format.

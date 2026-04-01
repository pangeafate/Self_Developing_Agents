---
name: dev-critique
description: Sub-agent orchestration for code review and gap analysis
version: 1.0.0
---

# Dev Critique — Sub-Agent Orchestration

Orchestrates context-isolated code review by packaging files and role prompts for sub-agent review, then parsing the structured results.

## When to Use

- **Stage 3 (Plan Review)**: Before implementation — review the sprint plan with architect-reviewer and code-reviewer
- **Stage 5 (Post-Implementation Review)**: After implementation — review code with debugger, architect-reviewer, code-reviewer, security-auditor, or performance-reviewer
- Whenever the Coding Agent needs an independent review of any artifact

## Available Scripts

### gather-context.py — Package files and assemble sub-agent prompts

Reads a role definition file as a complete document, assembles a review prompt from GL-SELF-CRITIQUE.md, and packages the specified files into a JSON payload ready for sub-agent spawning.

**Usage:**
```bash
# Stage 3 — plan review (sprint plan IS included)
python scripts/gather-context.py \
  --role architect-reviewer --stage 3 \
  --sprint-plan workspace/sprints/SP_042_Auth.md \
  --files src/lib/auth.py src/lib/auth_service.py

# Stage 5 — code review (sprint plan MUST NOT be included)
python scripts/gather-context.py \
  --role debugger --stage 5 \
  --files src/lib/auth.py test/unit/test_auth.py
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--role` | Yes | Role name: architect-reviewer, code-reviewer, debugger, security-auditor, performance-reviewer, researcher, analyzer, plan-architect, test-enforcer |
| `--stage` | Yes | 3 (plan review) or 5 (post-implementation review) |
| `--files` | No | Space-separated file paths to include as review context |
| `--sprint-plan` | No | Path to sprint plan (required for stage 3, FORBIDDEN for stage 5) |
| `--framework-root` | No | Path to framework root (auto-detected from script location) |

**Output (JSON to stdout):**
```json
{
  "role": "architect-reviewer",
  "stage": 5,
  "system_prompt": "... full role file content ...",
  "review_prompt": "... stage-specific review instructions ...",
  "context_files": [
    {"path": "src/lib/auth.py", "content": "...file content..."},
    {"path": "test/unit/test_auth.py", "content": "...file content..."}
  ],
  "isolation_verified": true
}
```

**Exit Codes:**
| Code | Meaning |
|------|---------|
| 0 | Success — JSON payload assembled |
| 1 | Isolation violation — sprint plan provided at Stage 5 |
| 2 | Fatal — role file not found or invalid stage |
| 3 | Configuration — framework root not found |

**Isolation Enforcement:**
- Stage 5 + `--sprint-plan` → exits 1 with error. This is the programmatic enforcement of the framework's core quality principle.
- Stage 3 without `--sprint-plan` → prints warning to stderr but continues.

**Prompt Template Selection:**
- Stage 5 → gap analysis prompt (same for all roles)
- Stage 3 + architect-reviewer → architect-specific prompt
- Stage 3 + code-reviewer → code-reviewer-specific prompt
- Stage 3 + any other role → architect prompt as default

### parse-findings.py — Parse reviewer output into structured JSON

Reads markdown review output from stdin and extracts severity-tagged findings into a structured JSON format.

**Usage:**
```bash
# Pipe sub-agent output through the parser
echo "$REVIEWER_OUTPUT" | python scripts/parse-findings.py

# Strict mode — exits 1 if output is ambiguous
echo "$REVIEWER_OUTPUT" | python scripts/parse-findings.py --strict

# Summary format — human-readable text output
echo "$REVIEWER_OUTPUT" | python scripts/parse-findings.py --format summary
```

| Parameter | Required | Description |
|-----------|----------|-------------|
| `--strict` | No | Exit 1 if parsing finds neither findings nor clean indicators |
| `--format` | No | `json` (default) or `summary` (human-readable text) |

**Output (JSON to stdout):**
```json
{
  "total_issues": 3,
  "critical": 0,
  "high": 2,
  "medium": 1,
  "low": 0,
  "clean_iteration": false,
  "findings": [
    {"severity": "HIGH", "description": "Missing error handling in auth module", "recommendation": "Add try/except block"},
    {"severity": "HIGH", "description": "No input validation on user_id parameter", "recommendation": "Validate against regex pattern"},
    {"severity": "MEDIUM", "description": "Unused import in test file", "recommendation": "Remove unused import"}
  ],
  "deployment_blocked": true,
  "parse_confidence": "high"
}
```

**Exit Codes:**
| Code | Meaning |
|------|---------|
| 0 | Success — findings parsed (or clean iteration detected) |
| 1 | Strict mode: ambiguous output (no findings and no clean indicators) |

**Key fields:**
- `deployment_blocked`: true when critical > 0 or high > 0
- `parse_confidence`: high (clear bold markers found), medium (some markers found), low (minimal structure detected)
- `clean_iteration`: true when output contains "0 issues", "no issues found", or "clean"

## Orchestration Flow

The complete review cycle:

```
1. Coding Agent runs gather-context.py → gets JSON with prompt + files
2. Coding Agent spawns sub-agent with system_prompt + review_prompt + context
3. Sub-agent reviews, outputs markdown findings
4. Coding Agent pipes findings to parse-findings.py → gets structured JSON
5. If deployment_blocked: fix issues, re-run tests, go to step 1
6. If clean_iteration: proceed to next stage
```

For platforms without sub-agent support, see the Single-Agent Mode in workspace/AGENTS.md.

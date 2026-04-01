# SP_042: Health Check Architecture Fix — Agent Reasons, Script Serves

## Status: In Progress

## Sprint Goal

Fix the architectural deviation where `health-check.py` is the only cron script making
direct LLM calls (via `llm_client.py`). The agent IS the LLM — scripts should gather
data and store results, not reason. Split the single `--action assess` into two actions
following the correct agent-platform pattern: `gather-context` (pure data gathering) and
`store-result` (validation + storage). The agent performs LLM reasoning between the two
script calls.

## Current State

- `health-check.py --action assess` does everything: queries the database-api, builds an
  LLM prompt, calls an external LLM API, parses the response, and stores results.
- `llm_client.py` exists as a standalone module that wraps HTTP calls to an LLM provider.
- This violates the framework's core principle: the agent IS the LLM. Scripts are tools
  the agent calls — they should never make their own LLM calls.
- The `SKILL.md` instructions assume the script handles reasoning end-to-end.

## Desired End State

- `llm_client.py` deleted entirely.
- `--action gather-context` queries database-api tables, serializes context as structured
  JSON, outputs to stdout. No LLM interaction.
- `--action store-result` reads assessment JSON from stdin, validates it against a strict
  schema, applies stability rules, stores to database-api, and routes follow-up actions.
- `SKILL.md` rewritten with reasoning instructions, output schema, and explicit
  agent-owned vs script-computed field table.
- Agent reasons using its personality rules and loaded guidelines between the two calls.

## What We're NOT Doing

- Changing the health check schedule or cron trigger.
- Adding new health metrics or scoring dimensions.
- Modifying the briefing format that consumes health check results.
- Touching any other skills or their scripts.

## Technical Approach

### Step 1: Delete `llm_client.py`

Remove `src/lib/llm_client.py` and its test file. This module should never have existed —
the agent handles all reasoning.

### Step 2: Split `health_check.py` domain module

**Remove** from `src/lib/health_check.py`:
- `_SYSTEM_PROMPT` constant (~40 lines)
- `build_health_check_prompt()` function
- `get_system_prompt()` function

**Add** to `src/lib/health_check.py`:
- `SCHEMA_VERSION = "1"` constant
- `serialize_health_context()` — formats gathered data as agent-readable JSON
- Rename `validate_llm_response()` to `validate_assessment_json()` with stricter rules:
  - Reject markdown fences (``` in input)
  - Require `schema_version: "1"`
  - Require `status` field
  - Validate success vs failure payloads separately

### Step 3: Rewrite CLI script

**File**: `src/skills/strategy-agent-health-check/scripts/health-check.py`

Split `--action assess` into two new actions:

| Action | Input | Output | Side Effects |
|--------|-------|--------|--------------|
| `gather-context` | CLI args (initiative filters) | JSON context to stdout | Reads database-api |
| `store-result` | JSON from stdin | Status message to stdout | Writes database-api |

Remove all LLM-related imports: `LLMCallError`, `call_openrouter`, `load_api_keys`, `httpx`.

### Step 4: Update SKILL.md

Rewrite for the two-step workflow:
1. Agent calls `gather-context` to get current state
2. Agent reasons about the data using its guidelines
3. Agent calls `store-result` with its assessment

Include: reasoning instructions, output schema, field ownership table, failure handling.

### Step 5: Migration script

**File**: `scripts/add-health-check-status-options.py`

Add `failed_agent` and `failed_store` to `run_status` field options on table TABLE_ID_1.
Mark `failed_llm` as RETIRED (kept for historical data, not used by new code).

## Files to Create/Modify

### Delete
- `src/lib/llm_client.py`
- `test/unit/test_llm_client.py` (25 tests)

### Modify
- `src/lib/health_check.py` — Remove prompt assembly, add strict validation
- `src/skills/strategy-agent-health-check/scripts/health-check.py` — Split into two actions
- `src/skills/strategy-agent-health-check/SKILL.md` — Two-step workflow docs
- `src/agent-workspace/HEARTBEAT.md` — Updated health check entry
- `src/agent-workspace/TOOLS.md` — New status options, retired status
- `test/unit/test_health_check.py` — Replace prompt tests with validation tests
- `test/unit/test_cli_health_check.py` — New action tests

### Create
- `scripts/add-health-check-status-options.py` — Migration script

## Testing Strategy

### Tests to Delete
- `test/unit/test_llm_client.py` — 25 tests for the deleted module

### Tests to Remove
- 8 prompt assembly tests in `test_health_check.py` (functions no longer exist)

### Tests to Add

**`test_health_check.py`** (domain):
- `validate_assessment_json()` — valid success payload, valid failure payload, rejects
  markdown fences, rejects missing schema_version, rejects wrong schema_version, rejects
  missing status, rejects invalid status value
- `serialize_health_context()` — full context, empty initiatives, missing optional fields

**`test_cli_health_check.py`** (CLI):
- `gather-context` — success with default filters, success with initiative filter, handles
  database-api errors, handles empty result set
- `store-result` — success with valid JSON, rejects invalid JSON, rejects validation
  failure, handles database-api write errors, classifies error types correctly

### Expected Counts
- Deleted: 25 tests
- Removed: 8 tests
- Added: ~49 new tests
- Net change: +16 tests

## Success Criteria

1. `llm_client.py` no longer exists anywhere in the codebase
2. `health-check.py --action assess` is gone; replaced by `gather-context` + `store-result`
3. No script in the codebase imports any LLM client library
4. `validate_assessment_json()` rejects all malformed inputs (fences, missing fields, wrong schema)
5. All existing tests pass; net +16 new tests
6. SKILL.md clearly documents the two-step workflow and agent reasoning expectations
7. Migration script adds new status options to database-api

## Architecture (End State)

```
08:20 cron fires -> strategy-agent session
  |
  v
Agent calls: health-check.py --action gather-context
  -> Script queries database-api, outputs structured JSON context
  |
  v
Agent reasons (using loaded guidelines + personality rules)
  -> Produces assessment JSON
  |
  v
Agent calls: health-check.py --action store-result (via stdin)
  -> Script validates, applies stability rules, stores, routes follow-ups
```

## Review Log

### Pre-Implementation Review
- **Iteration 1** (2026-01-15): architect-reviewer + code-reviewer found 1 CRITICAL, 1 HIGH, 2 MEDIUM. Files reviewed: sprint plan, src/lib/health_check.py, src/lib/llm_client.py, src/skills/strategy-agent-health-check/scripts/health-check.py, SKILL.md
- **Iteration 2** (2026-01-15): code-reviewer found 0 CRITICAL/HIGH after fixes applied. Files reviewed: sprint plan, src/lib/health_check.py

**Iteration 1 details:**
1. **CRITICAL** — stdin read has no size limit. `store-result` reads from stdin with no max-size guard. A malformed or enormous payload could cause memory exhaustion. *Source: code-reviewer*
2. **HIGH** — Migration script has no rollback path. If adding new status options partially fails, the field is left in an inconsistent state. *Source: architect-reviewer*
3. **MEDIUM** — `serialize_health_context()` does not specify a JSON encoding for datetime fields. *Source: code-reviewer*
4. **MEDIUM** — SKILL.md does not document what happens if `gather-context` returns an empty context. *Source: architect-reviewer*

**Resolution:**
- (1) Added `MAX_STDIN_BYTES = 1_048_576` (1 MB) constant; `store-result` reads with size limit and raises `PayloadTooLarge` if exceeded. Test added.
- (2) Migration script now reads existing options first, computes diff, and applies atomically. Added dry-run flag.
- (3) Added `_serialize_datetime()` helper that always outputs ISO 8601 with UTC timezone. Test added.
- (4) SKILL.md updated with "Empty Context" section.

### Post-Implementation Review
- **Iteration 1** (2026-01-16): debugger found 1 MEDIUM issue. Files reviewed: src/lib/health_check.py, test/unit/test_health_check.py
- **Iteration 2** (2026-01-16): code-reviewer found 0 issues. Files reviewed: src/lib/health_check.py, test/unit/test_health_check.py (clean iteration — ready to deploy)

---
sprint_id: SP_001
features: []
user_stories: []
schema_touched: false
structure_touched: true
status: Complete
---
<!-- Historical note: at SP_001 ship (2026-04-13), the framework's stage
     numbering was Stage 6 = Deployment, Stage 7 = Documentation. SP_002
     swapped that semantic to Stage 6 = Documentation, Stage 7 = Deployment.
     References below to "Stage 6/7" reflect the pre-SP_002 ordering. -->

# SP_001: Documentation Reality Discipline

## Sprint Goal

Close the structural gap that lets meta-documentation (feature lists, architecture, schema, roadmap) drift from shipped reality. Deliver a validator, a practice file, template frontmatter, and a new Rule 16 so any project adopting the framework detects drift automatically and blocks deploy on it.

## Current State

The framework validates per-sprint artifacts (`validators/validate_sprint.py` checks sprint plan sections and review-log entries) but has **no mechanism for validating meta-doc claims against code reality**. Observed drift modes:

1. `FEATURE_LIST.md` entries stuck at `Status: Planned` after sprints ship them.
2. `CODEBASE_STRUCTURE.md` referencing directories that never existed or were renamed.
3. `ARCHITECTURE.md` leaving `TBD` placeholders for paths that now exist.
4. `PROJECT_ROADMAP.md` showing a phase as simultaneously "Complete" and "Planning".
5. `CLAUDE.md` duplicating the 15 Rules from `AGENT_INSTRUCTIONS.md` verbatim, drifting over time.
6. Aspirational/vision documents read by later agents as current spec.

Existing assets this sprint builds on:

- `validators/run_all.py` — validator orchestrator (argparse-driven, 5 validators in `ALL_VALIDATORS`).
- `validators/validate_sprint.py` — pattern for a project-root-scoped validator with numbered stage output. Contains `find_active_sprint()` at line 74 returning the full sprint ID including slug (e.g., `SP_001_Doc_Reality_Discipline`).
- `validators/validate_workspace.py` — actual behavior: checks bootstrap files for size limits and credential patterns using `.validators.yml` for override config. **Not** a directory-structure validator (that is `validate_structure.py`).
- `validators/test_run_all.py` — hardcodes the 5-validator assertions in 8 places (lines 5-6, 97-101, 134, 179, 198). Adding a validator means updating this file.
- `templates/*.md` — 14 template files that projects copy in during bootstrap.
- `practices/GL-*.md` — 8 guideline files loaded at agent session start. After this sprint: 9.
- `AGENT_INSTRUCTIONS.md` — the 15 Rules; canonical source projects inherit.
- `.validators.yml` — existing YAML config consumed by `validate_workspace.py`. This sprint extends its schema rather than introducing a new config file.

## Desired End State

A project using the framework has:

- **A new validator** `validate_doc_reality.py` wired into `run_all.py` (registered in `ALL_VALIDATORS`, not in `BOOTSTRAP_VALIDATORS`), exposing four stages that fail the build on:
  - **Stage A — dead path references** in meta-doc markdown (narrow-scoped; see "Stage A scope" below).
  - **Stage B — `TBD-by` decay** when the referenced sprint has already elapsed.
  - **Stage C — missing/malformed frontmatter** on a configured set of meta-docs.
  - **Stage D — paired-file duplication** (long identical runs between two designated files, unless an `@inherits:` block marker is present).
- **A new practice** `practices/GL-DOC-RECONCILIATION.md` codifying frontmatter convention, single-source rule, vision-doc quarantine, `TBD-by` convention, `@inherits:` block syntax, and the sprint-end reconciliation checklist.
- **Frontmatter added** to 7 meta-doc templates (`FEATURE_LIST`, `PROGRESS`, `PROJECT_ROADMAP`, `ARCHITECTURE`, `DATA_SCHEMA`, `CODEBASE_STRUCTURE`, `USER_STORIES`).
- **SPRINT_PLAN.md** template gains a "Doc Reconciliation Checklist" subsection under Success Criteria.
- **Rule 16** added to `AGENT_INSTRUCTIONS.md` and the "Cross-cutting practices" paragraph (line 9) updated to list the new practice file.
- **Updated `test_run_all.py`** so all existing tests still pass with 6 validators.
- **The framework's own repo exits 0** under `python validators/validate_doc_reality.py .` — via a seeded `.validators.yml` `doc_reality:` block with exclusions tuned to the existing framework layout. This is a **hard success criterion**, not advisory.

## What We're NOT Doing (Deferred to SP_002)

- `TRACEABILITY.md` generator (`generate_traceability.py`) — defer.
- Sprint-plan YAML frontmatter convention (sprint_id, features, user_stories) — defer; needed only for the generator.
- Bootstrap manifest check extending `validate_workspace.py` — defer.
- `FEATURE_LIST.md` auto-generation or generated-section markers — defer.
- Schema-to-code field-type cross-check — defer.
- Retro-cleanup of existing framework docs beyond what the seeded `.validators.yml` exclusion block tolerates — defer.
- Auto-fixers that mutate docs — explicitly out of scope for this framework generation.
- An `@inherits:` runtime loader. This sprint only defines the directive's syntax so the validator can detect it; no file-inclusion mechanism is built.
- Staleness thresholds for `last-reconciled` (warn if older than N days) — defer.
- Unifying `.validators.yml` and sprint-plan-level config — defer.

## Technical Approach

### Frontmatter parsing contract (applies to all stages and templates)

The contract every tool in the suite relies on:

1. Frontmatter, when present, starts at **byte 0** of the file. No BOM, no leading blank lines.
2. Frontmatter is delimited by a line containing exactly `---` (no trailing whitespace) on the first line, and a matching `---` closing line somewhere in the first **50 lines** (cap).
3. Between the delimiters is a YAML subset: `key: value` per line where value is a string, an ISO-8601 date `YYYY-MM-DD`, or a YAML flow-sequence `[item, item]`. Nested mappings not required for this sprint.
4. Parser: prefer `yaml.safe_load(between)` when PyYAML is importable; fall back to a hand-rolled `key: value` / `key: [a, b]` line parser (mirror the pattern in `validate_workspace.py`).
5. Missing opening `---` at byte 0 → `status: missing` (Stage C fails).
6. Opening `---` found but no closing `---` within 50 lines → `status: malformed` (Stage C fails with message "frontmatter not closed within 50 lines").
7. Accepted `status` enum: `living`, `vision`, `spec`, `archived`, `generated`.
8. Required keys: `status`, `last-reconciled`. `last-reconciled` must parse as `YYYY-MM-DD` via `datetime.date.fromisoformat`.
9. Files that do NOT need frontmatter: `README.md`, `CLAUDE.md`, `AGENT_INSTRUCTIONS.md`, `BOOTSTRAP.md`, all files under `practices/`, `architecture/`, `templates/`, `workspace/`, `test/`, `skills/`. The frontmatter-required manifest is explicit (see Stage C below).

### Validator design: `validators/validate_doc_reality.py`

Four independent check families. Each emits the same `[Stage X] PASS|FAIL: ...` format used by `validate_sprint.py`. Exit code 0 iff all stages pass. CLI: `python validate_doc_reality.py <project_root> [--skip-stage A,B,C,D]` (comma-separated, mirrors `run_all.py --skip`).

Config source: reads `project_root/.validators.yml` if present; extends existing schema with a top-level `doc_reality:` key. JSON NOT supported (avoids dual-config fragmentation). YAML parsing is optional — if PyYAML is missing and `.validators.yml` has a `doc_reality:` key, validator prints an advisory and uses built-in defaults.

```
.validators.yml  (schema extension)
  doc_reality:
    exclude_dirs: [list]              # additional dirs to skip; merged with defaults
    dead_path_exclusions: [list]      # literal token strings allowed to be "dead"
                                      # matched as exact string match against the extracted token,
                                      # NOT against the resolved filesystem path and NOT as glob
    dead_path_glob_exclusions: [list] # fnmatch patterns for dead-path suppression
                                      # (use for growing sets like "PROGRESS_ARCHIVE_*.md")
    frontmatter_required: [list]      # override default required-frontmatter manifest
    paired_files: [[a, b], ...]       # list of 2-element lists
    duplication_threshold: int        # default 30; min 20
```

**Exclusion-mechanism recap** (the three layers, in order applied):
1. `exclude_dirs` — skips the **walk**: files under these directories are not read at all.
2. `dead_path_exclusions` — literal string match against the **extracted token** (after code-fence/comment stripping). Use when the token appears verbatim.
3. `dead_path_glob_exclusions` — `fnmatch` pattern match against the extracted token. Use for patterned sets (`PROGRESS_ARCHIVE_*.md`, `src/generated/*.py`).

Downstream projects frequently want to suppress patterns that don't fit an `exclude_dirs` boundary (e.g., archive files scattered across subdirs). The glob list covers that case; the literal list covers one-off exemptions.

**Default exclusion set** (for Stage A file walk):

Path components (matched via `pathlib.PurePath.parts`, not substring):
`.git`, `.hg`, `.svn`, `node_modules`, `__pycache__`, `.venv`, `venv`, `env`, `dist`, `build`, `.tox`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.idea`, `templates`, `vision`, `test`, `tests`, `workspace`, `practices`, `architecture`, `roles`, `deploy`, `skills`, `examples`.

Filename globs: `PROGRESS_ARCHIVE_*.md`, `*_ARCHIVE.md`.

**Rationale**: `practices/`, `architecture/`, `roles/`, `templates/`, `skills/`, `deploy/`, `workspace/` all contain guideline/example/template paths that are not live project source. `test/` is excluded because test fixtures intentionally include dead paths. Downstream projects can re-enable any of these via `.validators.yml` overrides.

#### Stage A — Dead path references

Walk `project_root` for `*.md` files honoring the exclusion set. For each file:

1. Preprocess: remove everything between lines starting with ` ``` ` (triple-backtick code fences). Pairs matched top-down; unterminated fence at EOF causes the rest of the file to be dropped.
2. Preprocess: remove HTML comment blocks `<!--`…`-->` (multi-line).
3. Extract tokens matching the **combined regex**: `` `([A-Za-z0-9_./-]+)` `` — any backtick-wrapped token.
4. For each token, accept as a path candidate only if ALL of:
   - Contains at least one `/`.
   - No placeholder markers: does NOT contain `XXX`, `YYY`, `NNN`, `<`, `>`, `{{`, `...`.
   - No glob characters: no `*`, `?`, `[`, `]`.
   - Ends with a known extension OR ends with `/` (directory reference).
   - After `project_root / token`, `path.resolve()` is_relative_to `project_root.resolve()` (path-traversal guard).
5. Check `(project_root / token).exists()` OR `is_symlink()` (broken symlinks pass). If neither, record as a finding with file + line number.
6. Honor inline suppression: `<!-- doc-reality:ignore-paths -->` on the line immediately above the offending reference skips that line; `<!-- doc-reality:ignore-block-start -->` / `<!-- doc-reality:ignore-block-end -->` skips a range.
7. Honor `dead_path_exclusions` config (literal string match against extracted token) AND `dead_path_glob_exclusions` (fnmatch pattern match against extracted token).
8. Per-file read cap: 1 MB. Above cap: advisory message, file skipped.

**Inline-suppression scope**: the HTML comment markers (`doc-reality:ignore-paths`, `doc-reality:ignore-block-start/end`) apply exclusively to Stage A. They have no effect on Stages B, C, or D. Stage D suppression is done via `@inherits:` blocks (defined below); Stages B and C do not have suppression mechanisms.

#### Stage B — TBD-by decay

1. Call `find_active_sprint(project_root)` (duplicated from `validate_sprint.py` at top of `validate_doc_reality.py` with `# NOTE: duplicated from validate_sprint.py; shared helper extraction deferred to SP_002`).
2. If no active sprint (PROGRESS.md missing or no `**Current:**`), Stage B emits advisory and PASSes.
3. Extract numeric sprint number from active sprint ID via `re.match(r"SP_(\d+)", sprint_id)`. If no match, advisory, PASS.
4. Walk `*.md` files using the same exclusion set.
5. Regex: `TBD-by:\s*SP_(\d+)\b` (case-sensitive on `TBD-by`, digit-count-flexible, word boundary).
6. For each match:
   - If `match_num < active_num`: FAIL with file, line, message "TBD-by SP_XXX has elapsed (active sprint: SP_YYY)".
   - If `match_num == active_num`: advisory WARN, PASS.
   - If `match_num > active_num`: PASS.

#### Stage C — Frontmatter presence and validity

**Default `frontmatter_required` manifest** (project-root-relative, basenames):
`PROGRESS.md`, `PROJECT_ROADMAP.md`, `FEATURE_LIST.md`, `ARCHITECTURE.md`, `DATA_SCHEMA.md`, `CODEBASE_STRUCTURE.md`, `USER_STORIES.md`.

Note: `TRACEABILITY.md` is NOT in the default list (it's generated and not in this sprint's scope).

For each manifest entry:
- If the file does NOT exist at project root: PASS with advisory "manifest entry <name> not present at root; skipping" — this sprint does not enforce doc existence (that is a future sprint's concern).
- If the file exists: parse frontmatter per the contract above. FAIL if:
  - Missing opening `---` at byte 0.
  - Opening `---` found but no closing `---` within 50 lines.
  - Missing `status` key.
  - Missing `last-reconciled` key.
  - `status` value not in the accepted enum.
  - `last-reconciled` does not parse as ISO-8601 date.

#### Stage D — Paired-file duplication

Config: `paired_files` defaults to `[["AGENT_INSTRUCTIONS.md", "CLAUDE.md"]]`. Downstream projects can override or extend.

For each pair `[a, b]`:
1. If either file missing, skip silently (not a failure).
2. Read both files with 1 MB per-file cap (above cap: advisory, skip pair).
3. Strip frontmatter from each (per the contract).
4. **Strip triple-backtick code fences and HTML comments** (same pre-processing as Stage A step 1–2). Applies to both files.
5. Normalize: strip trailing whitespace per line; keep blank lines as-is.
6. Detect `@inherits:` directives. Opening syntax: `^@inherits:\s+\S+\s*$`. Closing syntax: `^@inherits-end:\s*$`. Scope: the directive suppresses duplication detection from its line until (a) a matching `@inherits-end:` line, or (b) the next `@inherits:` directive. **No implicit EOF terminator**: if the file ends before `@inherits-end:` is seen, emit advisory "unterminated @inherits: block in <file>" and treat only the directive line itself as suppressed (NOT the rest of the file). This prevents the unterminated-directive bypass.
7. Lines in a suppression range are removed before comparison.
8. Compute longest common contiguous run using `difflib.SequenceMatcher(None, a_lines, b_lines, autojunk=True).get_matching_blocks()`. Take blocks where `size >= duplication_threshold` (default 30) AND the block contains >= 20 non-blank lines.
9. FAIL per pair per offending block: report both file paths, starting line numbers in each (pre-stripping original numbers), first 5 lines of the duplicated span.

### Templates updated

Add a frontmatter header (with `YYYY-MM-DD` placeholders in comments explaining replacement) to: `FEATURE_LIST.md`, `PROGRESS.md`, `PROJECT_ROADMAP.md`, `ARCHITECTURE.md`, `DATA_SCHEMA.md`, `CODEBASE_STRUCTURE.md`, `USER_STORIES.md`. The existing template comment convention (`<!-- Template: fill in sections below. Remove this comment when populated. -->`) is preserved AFTER the frontmatter.

Example for `FEATURE_LIST.md`:
```markdown
---
status: living
last-reconciled: 1970-01-01
authoritative-for: [features]
---
<!-- Template: fill in sections below. Replace last-reconciled with today's ISO date when you copy this template. -->

# Feature List
...
```

Placeholder date `1970-01-01` is deliberately implausible — makes uninitialized-template detection trivial. Stage C accepts it as valid syntactically (it parses). The sprint plan DOES NOT require Stage C to reject epoch date; that's a future "staleness" check.

`SPRINT_PLAN.md` gets a new subsection under Success Criteria, copy-ready:

```markdown
### Doc Reconciliation Checklist
- [ ] FEATURE_LIST.md updated (statuses, sprint numbers, implementation paths)
- [ ] PROJECT_ROADMAP.md milestone updated
- [ ] ARCHITECTURE.md touched if design changed
- [ ] DATA_SCHEMA.md touched if schema changed
- [ ] CODEBASE_STRUCTURE.md touched if directories changed
- [ ] `last-reconciled` bumped on each touched meta-doc
- [ ] `validators/validate_doc_reality.py <project_root>` returns 0
```

### AGENT_INSTRUCTIONS.md changes

1. Line 9 ("Cross-cutting practices"): append `, practices/GL-DOC-RECONCILIATION.md` to the list.
2. Append Rule 16 after Rule 15:

```markdown
### 16. Documentation Reconciliation

Before Stage 6 (Deployment), run `validators/validate_doc_reality.py <project_root>`;
a failure blocks deployment. At Stage 7 (Documentation), complete the reconciliation
checklist: for every meta-doc whose subject-matter was touched by this sprint, update
content and bump `last-reconciled`.

Rule 15's autonomous-update clause remains in effect for docs-only changes: such
changes must still bump `last-reconciled` and may be validated post-hoc, but they
do not require the full Stage-7 reconciliation pass.

See `practices/GL-DOC-RECONCILIATION.md` for the frontmatter convention, the
single-source rule, vision-doc quarantine, and the TBD-by decay rule.
```

### Framework self-compliance: `.validators.yml`

Create `.validators.yml` at the framework repo root (if absent; currently it does not exist) seeded with the config below. The seed values were verified against the live repo: Stage A extraction (after applying exclusion set + code-fence stripping) produces findings only in `BOOTSTRAP.md` (4 tokens) because `examples/` is handled by `exclude_dirs`, `practices/` and `architecture/` are in the default exclusion set, and all other referenced paths resolve.

```yaml
doc_reality:
  exclude_dirs: []            # default component list already covers examples/, practices/, etc.
  dead_path_exclusions:       # BOOTSTRAP.md illustrative paths
    - test/unit/
    - test/integration/
    - test/fixtures/
    - workspace/sprints/SP_001_Description.md
  dead_path_glob_exclusions: []
  frontmatter_required:
    - PROGRESS.md             # the only meta-doc at root for the framework
  paired_files:
    - [AGENT_INSTRUCTIONS.md, CLAUDE.md]  # CLAUDE.md does not exist in framework repo; pair skipped silently
  duplication_threshold: 30
```

After implementation, running `python validators/validate_doc_reality.py .` at the framework repo root MUST exit 0. This is verified as a HARD success criterion; pre-implementation spot-check above confirms the config covers every known finding.

After implementation, running `python validators/validate_doc_reality.py .` at repo root MUST exit 0. This is verified as a success criterion; not advisory.

### test_run_all.py refactor

The file contains the 5-validator name list literally in **15+ places** (lines 134, 157, 179, 198, 214, 252, 280, 325, 348, 371, 405, 433, 453, 486 — plus docstring references). Enumerating individual line-number edits is error-prone. Refactor approach (non-negotiable for this sprint):

1. Introduce a module-level constant at the top of `test_run_all.py`:
   ```python
   EXPECTED_ALL_VALIDATORS = [
       "validate_structure",
       "validate_workspace",
       "validate_tdd",
       "validate_rdd",
       "validate_sprint",
       "validate_doc_reality",
   ]
   EXPECTED_BOOTSTRAP_VALIDATORS = ["validate_structure", "validate_workspace"]
   ```
2. Replace every literal list occurrence with the constant (or a slice of it where the test intentionally uses a subset, e.g. `EXPECTED_ALL_VALIDATORS[:3]` for a partial-skip test).
3. Run `pytest validators/test_run_all.py` and confirm zero failures before moving on.

This is a mechanical refactor — every changed line is either `[...literal...]` → `EXPECTED_ALL_VALIDATORS` or a partial-subset slice. No behavior change intended; any semantic test-logic surprise is a bug to report, not to paper over.

### Practice file: `practices/GL-DOC-RECONCILIATION.md`

Sections (outline; full prose written during implementation):

1. Philosophy — doc rot is structural; fix structure, not docs.
2. Frontmatter convention (`status` enum, `last-reconciled`, `authoritative-for`).
3. Single-source rule — prefer `@inherits:` over copy-paste; the validator enforces.
4. `@inherits:` syntax spec (mirrors the validator's Stage D logic).
5. Vision-doc quarantine — docs with `status: vision` live under `vision/` (excluded from validation); banner at top.
6. `TBD-by: SP_NNN` convention and decay enforcement.
7. Sprint-end reconciliation checklist.
8. Generated-doc exemption — `status: generated` indicates a doc emitted by tooling; skip staleness in future sprints; Stage C still validates frontmatter presence.
9. Pointer to `validators/validate_doc_reality.py` for enforcement mechanics.

## Files to Create/Modify

| File | Action | Purpose |
|---|---|---|
| `validators/validate_doc_reality.py` | Create | Four-stage validator (dead paths, TBD decay, frontmatter, duplication) |
| `validators/test_validate_doc_reality.py` | Create | Unit tests per stage; see per-test ordering in Testing Strategy |
| `validators/test_fixtures/doc_reality/` | Create (tree) | Fixture projects: `happy_path/`, `dead_path/`, `tbd_overdue/`, `bad_frontmatter/`, `duplicated_paired/`, `inherits_escape/`, `code_fence_ignored/`, `symlink_broken/` |
| `validators/run_all.py` | Modify | Add `validate_doc_reality` to `ALL_VALIDATORS` |
| `validators/test_run_all.py` | Modify | Update 5→6 validator assertions wherever hardcoded |
| `practices/GL-DOC-RECONCILIATION.md` | Create | Codifies conventions + enforcement pointer |
| `templates/SPRINT_PLAN.md` | Modify | Add Doc Reconciliation Checklist subsection |
| `templates/FEATURE_LIST.md` | Modify | Prepend frontmatter |
| `templates/PROGRESS.md` | Modify | Prepend frontmatter |
| `templates/PROJECT_ROADMAP.md` | Modify | Prepend frontmatter |
| `templates/ARCHITECTURE.md` | Modify | Prepend frontmatter |
| `templates/DATA_SCHEMA.md` | Modify | Prepend frontmatter |
| `templates/CODEBASE_STRUCTURE.md` | Modify | Prepend frontmatter |
| `templates/USER_STORIES.md` | Modify | Prepend frontmatter |
| `AGENT_INSTRUCTIONS.md` | Modify | Line 9 practice list + Rule 16 |
| `.validators.yml` | Create (at framework root) | Seed `doc_reality:` block so framework repo passes its own validator |
| `PROGRESS.md` | Modify | Move SP_001 to Sprint History on completion (+frontmatter already present) |
| `workspace/sprints/SP_001_Doc_Reality_Discipline.md` | Modify (this file) | Review Log populated |

**Not modified**: `validators/validate_sprint.py` (shared-helper extraction deferred to SP_002 — `find_active_sprint` is duplicated with a NOTE comment). `validators/validate_workspace.py` (bootstrap manifest extension deferred).

## Testing Strategy

Per `practices/GL-TDD.md`. Convention note: co-locating tests with validators (`validators/test_validate_*.py`) follows existing framework precedent and intentionally deviates from GL-TDD's `test/unit/` mandate. This deviation is acknowledged as project convention; a future sprint may consolidate.

### Per-test ordering (RED → GREEN, smallest first)

Each test is written first and confirmed RED (run pytest on the single test and observe failure) before the corresponding validator branch is implemented. Test list in implementation order:

**Frontmatter parser tests** (unit-level, no validator invocation):
1. `test_parse_frontmatter_absent_returns_missing`
2. `test_parse_frontmatter_unclosed_returns_malformed`
3. `test_parse_frontmatter_valid_yaml_returns_dict`
4. `test_parse_frontmatter_valid_fallback_no_pyyaml_returns_dict`
5. `test_parse_frontmatter_closing_beyond_50_lines_returns_malformed`

**Stage A tests:**
6. `test_stage_a_empty_project_passes`
7. `test_stage_a_live_path_reference_passes`
8. `test_stage_a_dead_path_fails`
9. `test_stage_a_path_in_code_fence_ignored`
10. `test_stage_a_path_with_placeholder_XXX_ignored`
11. `test_stage_a_path_with_glob_ignored`
12. `test_stage_a_path_without_slash_ignored`
13. `test_stage_a_exclusion_dir_skipped` (place fixture inside `node_modules/`)
14. `test_stage_a_inline_ignore_marker_respected`
15. `test_stage_a_broken_symlink_passes` (symlink exists even if target doesn't)
16. `test_stage_a_path_traversal_rejected` (`../escape.md` ignored)
17. `test_stage_a_dead_path_exclusions_config_respected`
18. `test_stage_a_file_above_1mb_skipped_with_advisory`

**Stage B tests:**
19. `test_stage_b_no_active_sprint_passes_with_advisory`
20. `test_stage_b_tbd_future_sprint_passes`
21. `test_stage_b_tbd_current_sprint_warn_passes`
22. `test_stage_b_tbd_past_sprint_fails`
23. `test_stage_b_four_digit_sprint_number_parsed_correctly`
24. `test_stage_b_tbd_lowercase_not_matched` (case-sensitive)

**Stage C tests:**
25. `test_stage_c_manifest_file_absent_passes_with_advisory`
26. `test_stage_c_valid_frontmatter_passes`
27. `test_stage_c_missing_opening_delimiter_fails`
28. `test_stage_c_missing_status_key_fails`
29. `test_stage_c_missing_last_reconciled_fails`
30. `test_stage_c_invalid_status_enum_fails`
31. `test_stage_c_malformed_last_reconciled_fails`
32. `test_stage_c_accepts_all_five_status_values`
33. `test_stage_c_config_override_adds_to_manifest`

**Stage D tests:**
34. `test_stage_d_no_pairs_passes`
35. `test_stage_d_pair_with_missing_file_skipped`
36. `test_stage_d_pair_no_duplication_passes`
37. `test_stage_d_pair_duplication_30_lines_fails`
38. `test_stage_d_pair_duplication_19_lines_passes` (threshold boundary)
39. `test_stage_d_inherits_block_suppresses_detection`
40. `test_stage_d_inherits_end_resumes_detection`
41. `test_stage_d_custom_threshold_via_config`

**Integration tests:**
42. `test_cli_happy_path_exits_zero`
43. `test_cli_dead_path_exits_one`
44. `test_cli_skip_stage_flag_skips_stage`
45. `test_run_all_py_invokes_validate_doc_reality` — lives in `validators/test_run_all.py` (NOT in `validators/test_validate_doc_reality.py`), uses the existing `_VALIDATOR_DIR_OVERRIDE` fake-script fixture pattern; confirms a stub `validate_doc_reality.py` is invoked when present in `ALL_VALIDATORS`. Placing this test alongside the other `run_all.py` integration tests avoids split-responsibility.

Each test gets its own minimal fixture under `validators/test_fixtures/doc_reality/<category>/<scenario>/`. Fixtures are committed; they are not generated at test time.

### Coverage target

`validate_doc_reality.py` line coverage ≥ 90% (shared-library target per GL-TDD). Branch coverage ≥ 80%.

### Performance

Stages A and C are O(N × line_count). Stage B is O(N × line_count). Stage D is O(P × SequenceMatcher-cost); SequenceMatcher is effectively O(N × M) worst-case, bounded by the 1 MB per-file cap. No unit-level timing assertion (flaky on CI). Performance smoke test lives under `@pytest.mark.slow` and is excluded from default pytest runs.

### No new network or external dependencies

PyYAML is optional; fall back to minimal line parser when absent.

## Success Criteria

- [ ] `validate_doc_reality.py` implements all four stages, exits 0 on the framework repo
- [ ] All 45 unit/integration tests pass
- [ ] Line coverage on `validate_doc_reality.py` ≥ 90%
- [ ] All existing validator tests (including the updated `test_run_all.py`) pass
- [ ] `python validators/run_all.py .` at the framework repo root returns 0
- [ ] `GL-DOC-RECONCILIATION.md` exists and is cross-referenced from `AGENT_INSTRUCTIONS.md` line 9 and Rule 16
- [ ] All 7 listed templates have valid frontmatter syntactically (parses with `status` and `last-reconciled`)
- [ ] `SPRINT_PLAN.md` template has the Doc Reconciliation Checklist subsection
- [ ] `.validators.yml` exists at framework root with the seeded `doc_reality:` block
- [ ] Review Log populated with ≥ 2 pre-impl and ≥ 2 post-impl iterations, each with severity counts + `Files reviewed:` annotation
- [ ] PROGRESS.md updated with SP_001 entry in Sprint History

### Doc Reconciliation Checklist
- [ ] PROGRESS.md SP_001 entry added with correct completion date
- [ ] AGENT_INSTRUCTIONS.md Rule 16 present (file has no frontmatter; no `last-reconciled` bump applicable)
- [ ] All 7 templates' frontmatter present and parseable
- [ ] `python validators/validate_doc_reality.py .` returns 0

## Review Log

### Pre-Implementation Review
- **Iteration 1** (2026-04-13): architect-reviewer found 3 CRITICAL, 8 HIGH, 6 MEDIUM, 4 LOW. code-reviewer found 3 CRITICAL, 5 HIGH, 5 MEDIUM, 4 LOW. test-automator (skeptic) found 3 CRITICAL, 6 HIGH, 7 MEDIUM, 3 LOW. Files reviewed: workspace/sprints/SP_001_Doc_Reality_Discipline.md, validators/validate_sprint.py, validators/validate_workspace.py, validators/validate_structure.py, validators/run_all.py, validators/test_run_all.py, AGENT_INSTRUCTIONS.md, practices/GL-TDD.md, practices/GL-SELF-CRITIQUE.md, practices/GL-RDD.md, templates/SPRINT_PLAN.md, templates/FEATURE_LIST.md, templates/PROGRESS.md, architecture/SYSTEM_DESIGN.md.

**Resolution — All CRITICAL and HIGH addressed:**
1. **C-1 (frontmatter-parsing-contract-undefined)**: Plan now has an explicit "Frontmatter parsing contract" section specifying byte-0 start, 50-line closing cap, optional-PyYAML fallback, required keys, and ISO-8601 date validation.
2. **C-2 (stage-A-false-positive-storm / code-fences / framework-repo)**: Stage A tightened — (a) strips triple-backtick code fences and HTML comments before extraction, (b) requires `/` in token, (c) expanded default exclusion set including `practices/`, `architecture/`, `workspace/`, `roles/`, `skills/`, `deploy/`, `PROGRESS_ARCHIVE_*`, venv/pycache/build caches, (d) inline suppression markers, (e) `.validators.yml` `dead_path_exclusions` key, (f) seeded framework-root config so validator exits 0 on its own repo. Success criterion now HARD: framework repo must pass.
3. **C-3 (shared-helper-extraction-uncosted)**: Decision documented — duplicate `find_active_sprint` with NOTE comment; full extraction deferred to SP_002. `validate_sprint.py` not in modify list.
4. **C-4 (validate_workspace-mischaracterized)**: Current State description corrected to reflect actual validate_workspace.py behavior (bootstrap-file size/credential checks, not directory-structure validation).
5. **C-5 (200-byte-frontmatter-ceiling)**: Contract now specifies line-based scan up to 50 lines for closing `---`.
6. **H-1 (tdd-per-stage-not-per-test)**: Testing Strategy now lists 45 per-test items in RED-first order; each test has its own fixture.
7. **H-2 (scope-creep)**: Traceability generator, sprint-plan frontmatter convention, and validate_workspace.py bootstrap-manifest extension all deferred to SP_002. Explicitly listed in "What We're NOT Doing."
8. **H-3 (bootstrap-manifest-circular-dep)**: Resolved by deferring per H-2.
9. **H-4 (paired-file-default-empty)**: Default pair is now `[AGENT_INSTRUCTIONS.md, CLAUDE.md]`. Algorithm specified (difflib.SequenceMatcher), 30-line threshold + 20-non-blank-lines guard, `@inherits:` block syntax spec'd.
10. **H-5 (tbd-sprint-parse-slug-numeric)**: Stage B explicitly extracts numeric via `re.match(r"SP_(\d+)", …)` after calling `find_active_sprint`.
11. **H-6 (exclusion-list-incomplete)**: Expanded defaults listed; matching via `pathlib.PurePath.parts` (component, not substring).
12. **H-7 (success-criteria-self-contradicts)**: Framework-repo exit 0 now HARD criterion; not advisory.
13. **H-8 (stage-E-undefined)**: "Stage E" references removed; stage count is 4 (A–D).
14. **H-regex-\\d{3}**: Changed to `\d+\b` (digit-count-flexible, word-boundary).
15. **H-practices-false-positives**: `practices/` now in default Stage A exclusion.
16. **H-test-location-deviation**: Documented as acknowledged project convention in Testing Strategy.
17. **H-test_run_all-hardcoded**: `validators/test_run_all.py` added to Files to Modify.
18. **H-rule16-stage6-stage7-ambiguity**: Rule 16 split into two sentences — pre-deploy validator run; Stage-7 reconciliation checklist. Rule-15 relationship explicit.
19. **H-stage-A-method-2-unspec**: Only ONE extraction method now (backtick-wrapped token), eliminating the ambiguity.
20. **H-config-json-vs-yaml**: Dropped `.doc-reality.json`; everything lives in `.validators.yml doc_reality:` block.
21. **H-inherits-unspec**: Syntax fully spec'd (`^@inherits:\s+\S+\s*$`, block scope, `@inherits-end:` terminator).
22. **H-path-traversal**: Stage A `is_relative_to(project_root)` guard added.
23. **H-symlinks**: Stage A accepts `is_symlink()` — broken symlinks pass.
24. **H-large-files**: 1 MB per-file cap with advisory.
25. **H-duplicate-F-XXX / H-generator-encoding**: N/A — generator deferred to SP_002.

- **Iteration 2** (2026-04-13): architect-reviewer confirmed all 25 iter-1 resolutions CLOSED; found 0 CRITICAL, 0 HIGH, 4 MEDIUM, 4 LOW. code-reviewer confirmed iter-1 resolutions CLOSED; found 0 CRITICAL, 1 HIGH (test_run_all.py 4+ additional hardcoded locations beyond original enumeration), 2 MEDIUM, 2 LOW. test-automator (skeptic) confirmed 25 resolutions CLOSED; found 1 CRITICAL (seeded `.validators.yml` insufficient — `examples/` and BOOTSTRAP.md tokens uncovered), 1 HIGH (`dead_path_exclusions` literal-only limitation breaks archive use case), 2 MEDIUM, 2 LOW. Files reviewed: workspace/sprints/SP_001_Doc_Reality_Discipline.md, validators/validate_sprint.py, validators/validate_workspace.py, validators/run_all.py, validators/test_run_all.py, examples/*.md, BOOTSTRAP.md, .github/workflows/ci.yml, AGENT_INSTRUCTIONS.md.

**Resolution — All CRITICAL and HIGH from iteration 2 addressed:**
1. **C-iter2-framework-seed-insufficient**: Spot-verified via Grep: 19 dead-path tokens in `examples/` and 4 in `BOOTSTRAP.md`. Fix: added `examples` to the default exclusion set (component list) and seeded `.validators.yml` `dead_path_exclusions` with the four `BOOTSTRAP.md` tokens (`test/unit/`, `test/integration/`, `test/fixtures/`, `workspace/sprints/SP_001_Description.md`).
2. **H-iter2-dead-path-literal-only-limitation**: Added a second config key `dead_path_glob_exclusions` (fnmatch patterns) to cover growing sets like `PROGRESS_ARCHIVE_*.md`. Practice file will document the three-layer exclusion mechanism (walk / literal / glob).
3. **H-iter2-test_run_all-enumeration-incomplete**: Replaced line-number enumeration with mandatory refactor: introduce `EXPECTED_ALL_VALIDATORS` / `EXPECTED_BOOTSTRAP_VALIDATORS` module constants and replace every literal list. This eliminates enumeration entirely.
4. **M-iter2-stage-D-code-fence-strip**: Added step 4 to Stage D: strip triple-backtick fences and HTML comments before `@inherits:` detection and before SequenceMatcher comparison. Mirrors Stage A preprocessing.
5. **M-iter2-inherits-eof-bypass**: Removed implicit EOF terminator. Unterminated `@inherits:` now emits advisory and suppresses only the directive line itself, not the file remainder.
6. **M-iter2-inline-suppression-scope-implicit**: Added explicit "Inline-suppression scope" sentence in Stage A: markers apply exclusively to Stage A; Stage D uses `@inherits:`; Stages B/C have no suppression.
7. **M-iter2-test45-placement**: Test 45 explicitly placed in `validators/test_run_all.py` with `_VALIDATOR_DIR_OVERRIDE` fake-script pattern.

LOW items and remaining MEDIUM items (architect M-1 redundant seed entries now moot after the seed rewrite; skeptic L-1 Windows symlink skip marker — deferred as CI is Linux-only; M-4 staleness advisory — belongs in practice file, not plan) do not block implementation.

- **Iteration 3** (2026-04-13): test-automator confirmed all 8 iter-2 resolutions CONFIRMED; 0 CRITICAL, 0 HIGH, 0 MEDIUM, 0 LOW new findings; no regressions. Files reviewed: workspace/sprints/SP_001_Doc_Reality_Discipline.md. Verdict: READY FOR IMPLEMENTATION.

### Post-Implementation Review
- **Iteration 1** (2026-04-13): debugger found 0 CRITICAL, 2 HIGH, 4 MEDIUM, 3 LOW. code-reviewer found 1 CRITICAL, 3 HIGH, 4 MEDIUM, 4 LOW. architect-reviewer found 0 CRITICAL, 3 HIGH, 5 MEDIUM, 8 LOW. Files reviewed: validators/validate_doc_reality.py, validators/test_validate_doc_reality.py, validators/run_all.py, validators/test_run_all.py, practices/GL-DOC-RECONCILIATION.md, .validators.yml, AGENT_INSTRUCTIONS.md, templates/SPRINT_PLAN.md, templates/FEATURE_LIST.md, templates/PROGRESS.md.

**Resolution — All CRITICAL and HIGH addressed:**
1. **C-1 (BOM not stripped → Stage C false negatives on Windows)**: Changed `encoding="utf-8"` to `encoding="utf-8-sig"` at all three read sites in validate_doc_reality.py (`find_active_sprint`, `load_config`, `_read_text_capped`). Added test `test_read_text_strips_utf8_bom`.
2. **H-1 (dead mock code in test_all_pass_exits_zero)**: Removed the 30-line MagicMock block; test now delegates directly to `_run_all_pass_with_fake_scripts`. Docstring updated from "5 validators" to "6 validators".
3. **H-2 (test_any_fail_exits_one + test_missing_validator_script_exits_one passed for wrong reason)**: Both tests now create `validate_doc_reality` stub in fake dir so only `validate_sprint` causes the exit-1 signal. Comments updated.
4. **H-3 (epoch 1970-01-01 template sentinel passes validation)**: Stage C now explicitly rejects `last-reconciled: 1970-01-01` with message "is the template sentinel; replace with today's ISO date when you copy the template." Added test `test_stage_c_template_sentinel_date_fails`.
5. **H-4 (.validators.yml shared-config schema undocumented)**: Header comment now lists all three consumers (`doc_reality:` / `required_files:` / `bootstrap_files:`) and notes that each consumer ignores unknown keys.
6. **H-5 (SPRINT_PLAN.md template lacks frontmatter, inconsistent with 7 others)**: Added explanatory comment noting sprint plans are transient, live under `workspace/sprints/` (excluded from Stage C), and intentionally do not carry frontmatter.
7. **H-6 (unterminated @inherits: advisory wording misleading)**: Rewrote advisory to "only the @inherits: directive line is removed — the following content remains subject to duplication detection."

Additional post-impl cleanups: dead `for text in (a_text, b_text): pass` loop removed from `stage_d_paired_duplication`; "## The 15 Rules" heading updated to "## The 16 Rules"; Rule 7 now cross-references Rule 16; `test_summary_output_format` and `test_summary_shows_all_validators_ran` now assert `doc_reality` presence; added test `test_load_config_fallback_no_pyyaml` covering the no-PyYAML code path for `.validators.yml`.

Remaining MEDIUM/LOW findings (non-blocking, logged for a follow-up sprint): `exclude_dirs` silently ignores multi-segment path values; `load_config` fallback parser may lose URL values after colon; Stage A ignore-paths marker requires single-line HTML comment (multi-line not honored); domain-qualified tokens (`example.com/foo.py`) produce false-positive dead-path findings; Rule 16 vs Rule 13 hierarchy is documentation-only (no code hierarchy); duplicated `find_active_sprint` has subtle error-handling divergence between `validate_sprint.py` and `validate_doc_reality.py`.

- **Iteration 2** (2026-04-13): code-reviewer confirmed all 9 fixes CONFIRMED; found 0 CRITICAL, 0 HIGH, 1 MEDIUM (brittle assertion — actually NOT a defect on re-trace, downgraded to LOW observation), 2 LOW. Files reviewed: validators/validate_doc_reality.py, validators/test_validate_doc_reality.py, validators/test_run_all.py, .validators.yml, templates/SPRINT_PLAN.md, AGENT_INSTRUCTIONS.md. Verdict: READY FOR DEPLOY.

Final state: 84 tests pass; framework repo passes `validate_doc_reality.py` with exit 0; all existing validator tests still pass.

---
status: living
last-reconciled: 2026-04-14
authoritative-for: [active-sprint, sprint-history]
---

# Progress

> **Note**: Archive to `PROGRESS_ARCHIVE_NNN.md` when this file exceeds 25 sprints.

## Active Sprint

_None. Most recent sprint completed: SP_002_Doc_Freshness_Gate (2026-04-14)._

<!-- When a new sprint opens, add a Current-marker line back here for validate_sprint.py detection. -->

## Sprint History

### SP_002: Doc Freshness Gate

- **Status**: Complete
- **Date**: 2026-04-14
- **Summary**: Added diff-aware `validate_doc_freshness.py` (4 stages: sprint-plan frontmatter, claims match diff, proportionality, `last-reconciled` bumped); swapped Stage 6 (now Documentation) and Stage 7 (now Deployment); introduced sprint-plan frontmatter convention; `.docs_reconciled` lockfile with `schema_version: 1`; created `pytest.ini` with `integration`/`acceptance` markers. Rule 16 rewritten for deploy-gate semantics.
- **Tests added**: +48 new tests (33 doc_freshness unit + 10 doc_freshness integration + 5 existing-test updates for 7th validator)
- **Key decisions**: Diff-base = parent of sprint-plan's introducing commit, empty-tree fallback for initial commits; three-dot diff (`base...HEAD`) to exclude merge-from-main noise; `doc_freshness.enabled: false` default for downstream safety; meta-doc classification at project root only (`templates/DATA_SCHEMA.md` does NOT count as DATA_SCHEMA.md); F-4 detects unchanged `last-reconciled` values to close the same-date loophole; `--skip-stage F1` runs downstream stages with synthetic empty claims rather than silently cascading. Helper duplication accepted for this sprint; shared-helper extraction under validators/ queued for SP_003.

### SP_001: Doc Reality Discipline

- **Status**: Complete
- **Date**: 2026-04-13
- **Summary**: Added `validate_doc_reality.py` validator (4 stages: dead paths, TBD-by decay, frontmatter presence + validity, paired-file duplication), `practices/GL-DOC-RECONCILIATION.md` practice, Rule 16 in AGENT_INSTRUCTIONS.md, frontmatter on 7 meta-doc templates, Doc Reconciliation Checklist in SPRINT_PLAN.md, and seeded `.validators.yml`. Framework repo passes its own new validator with exit 0.
- **Tests added**: +47 new tests (doc_reality: 46, test_run_all updates) — +84 total passing in this sprint's scope
- **Key decisions**: Four-stage validator rather than five (bootstrap manifest check + traceability generator deferred to SP_002); `dead_path_exclusions` + `dead_path_glob_exclusions` for three-layer suppression; `1970-01-01` as template sentinel date rejected explicitly by Stage C to prevent unreplaced-template bypass; `find_active_sprint` duplicated between validate_sprint.py and validate_doc_reality.py with explicit NOTE comment (shared-helper extraction deferred to SP_002).

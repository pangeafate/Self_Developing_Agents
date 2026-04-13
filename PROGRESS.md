---
status: living
last-reconciled: 2026-04-13
authoritative-for: [active-sprint, sprint-history]
---

# Progress

> **Note**: Archive to `PROGRESS_ARCHIVE_NNN.md` when this file exceeds 25 sprints.

## Active Sprint

_None. Most recent sprint completed: SP_001_Doc_Reality_Discipline (2026-04-13)._

<!-- When a new sprint opens, add a Current-marker line back here for validate_sprint.py detection. -->

## Sprint History

### SP_001: Doc Reality Discipline

- **Status**: Complete
- **Date**: 2026-04-13
- **Summary**: Added `validate_doc_reality.py` validator (4 stages: dead paths, TBD-by decay, frontmatter presence + validity, paired-file duplication), `practices/GL-DOC-RECONCILIATION.md` practice, Rule 16 in AGENT_INSTRUCTIONS.md, frontmatter on 7 meta-doc templates, Doc Reconciliation Checklist in SPRINT_PLAN.md, and seeded `.validators.yml`. Framework repo passes its own new validator with exit 0.
- **Tests added**: +47 new tests (doc_reality: 46, test_run_all updates) — +84 total passing in this sprint's scope
- **Key decisions**: Four-stage validator rather than five (bootstrap manifest check + traceability generator deferred to SP_002); `dead_path_exclusions` + `dead_path_glob_exclusions` for three-layer suppression; `1970-01-01` as template sentinel date rejected explicitly by Stage C to prevent unreplaced-template bypass; `find_active_sprint` duplicated between validate_sprint.py and validate_doc_reality.py with explicit NOTE comment (shared-helper extraction deferred to SP_002).

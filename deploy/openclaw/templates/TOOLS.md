# Tools Configuration

## Code Policy

- All code changes go through the 7-stage sprint cycle (see AGENTS.md)
- Never modify deployed scripts directly — change the source and redeploy
- The `SDA_FRAMEWORK_ROOT` environment variable points to the framework installation directory. It is set in skill configs and baked into HEARTBEAT.md at install time. All dev-* scripts also accept `--framework-root` as a CLI override.

## Development Skills

### dev-bootstrap
Purpose: Day 1 workspace setup. Read SKILL.md for commands.
Key actions: `setup`, `verify`

### dev-sprint
Purpose: Sprint lifecycle management. Read SKILL.md for commands.
Key actions: `create-plan`, `update-docs`

### dev-critique
Purpose: Sub-agent orchestration for context-isolated code review. Read SKILL.md for commands.
Key actions: `gather-context`, `parse-findings`

### dev-deploy
Purpose: Deployment, task polling, and cross-agent skill deployment. Read SKILL.md for commands.
Key actions: `validate`, `push`, `poll-tasks`, `deploy-to-agent`

## Validators

Run all validators: use the dev-deploy skill with `validate` action.

Individual validators:
- `validate_structure.py` — directory layout and required files
- `validate_workspace.py` — workspace configuration integrity
- `validate_tdd.py` — test-driven development compliance
- `validate_rdd.py` — documentation-first development compliance
- `validate_sprint.py` — sprint plan format and lifecycle

## Practices Reference

- GL-TDD.md — Test-Driven Development
- GL-RDD.md — Documentation-First Development
- GL-ERROR-LOGGING.md — Error Handling and Logging Standards
- GL-SPRINT-DISCIPLINE.md — Sprint Lifecycle Rules
- GL-SELF-CRITIQUE.md — Self-Critique Protocol
- GL-DEPLOYMENT.md — Deployment Procedures
- GL-CONTEXT-MANAGEMENT.md — Context Window Management
- GL-TEMPLATE-ENFORCEMENT.md — Template Compliance

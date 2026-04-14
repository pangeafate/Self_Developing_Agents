# Self-Developing Agents: Role Definitions

## Overview

Eleven specialized roles map to a 7-stage development cycle. Each role has a
narrow responsibility and strict context boundaries. The **Coding Agent** acts
as the central orchestrator -- all other roles communicate through it.

## Stage-to-Role Mapping

| Stage | Name | Roles |
|-------|------|-------|
| 1 | Task Recognition | main-agent |
| 2 | Sprint Planning | coding-agent, plan-architect, researcher, analyzer |
| 3 | Plan Review | architect-reviewer, code-reviewer, main-agent (optional) |
| 4 | Implementation | coding-agent, test-enforcer, researcher, analyzer |
| 5 | Post-Implementation Review | architect-reviewer, code-reviewer, debugger, security-auditor*, performance-reviewer* |
| 6 | Documentation | coding-agent |
| 7 | Deployment | coding-agent |

*Optional -- invoked when feature characteristics warrant it.*

## Decision Matrix: When to Use Each Role

| Role | Use When... |
|------|-------------|
| main-agent | A user request arrives, domain routing is needed, or plan needs domain-correctness review |
| coding-agent | Sprint plans must be written, code implemented, deployments run, or docs updated |
| plan-architect | Requirements need decomposition into file changes, dependencies, and risk assessment |
| test-enforcer | TDD compliance must be verified, test coverage checked, or test stubs written |
| researcher | Quick codebase lookups -- find files, locate functions, identify patterns |
| analyzer | Deep analysis of call chains, data flows, or implementation patterns in specific components |
| architect-reviewer | Architecture risks, SOLID violations, backward compatibility, or deployment ordering concerns |
| code-reviewer | Code correctness, factual verification of claims, import accuracy, edge case coverage |
| debugger | Test failures, runtime errors, or unexpected behavior requiring root cause analysis |
| security-auditor | Features involving auth, user input handling, external API calls, or secret management |
| performance-reviewer | Data-heavy operations, frequently-executed paths, or batch processing logic |

## Context Isolation Rules

### Research Roles (researcher, analyzer)
- **MAY** share partial context with the coding agent across stages.
- Context from research is informational -- it does not constitute review.

### Quality Roles (architect-reviewer, code-reviewer, debugger, security-auditor, performance-reviewer)
- **MUST NOT** share context with each other during Stage 5.
- **MUST NOT** receive the sprint plan during Stage 5 (prevents confirmation bias).
- Each quality agent receives only: code files, test files, and error output (if applicable).
- Stage 3 reviews ARE allowed to see the sprint plan (that is what they are reviewing).

### Core Roles (main-agent, coding-agent, plan-architect, test-enforcer)
- The coding agent maintains full context across all stages it participates in.
- The main agent sees only routing context and domain-level summaries.
- Plan-architect and test-enforcer receive scoped context for their specific tasks.

## Communication Flow

```
User <---> Main Agent <---> Coding Agent <---> [All Sub-Agents]
```

All sub-agent results flow back through the Coding Agent, which consolidates
findings, resolves conflicts between reviewers, and decides on actions. The
Main Agent never communicates directly with sub-agents.

## File Organization

```
roles/
  ROLES.md              # This file
  core/
    main-agent.md       # Router + domain expert
    coding-agent.md     # Engineering orchestrator
    plan-architect.md   # Implementation strategy designer
    test-enforcer.md    # TDD compliance enforcer
  research/
    researcher.md       # Fast codebase exploration
    analyzer.md         # Deep component analysis
  quality/
    architect-reviewer.md    # Architecture risk reviewer
    code-reviewer.md         # Code correctness reviewer
    debugger.md              # Error investigator
    security-auditor.md      # Vulnerability scanner
    performance-reviewer.md  # Performance bottleneck detector
```

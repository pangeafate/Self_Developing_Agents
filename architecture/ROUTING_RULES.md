# Routing Rules: Main Agent to Coding Agent

## Overview

The Main Agent is the single point of contact for the human. Its most critical routing responsibility is recognizing when a human request requires code changes and delegating that work to the Coding Agent with a well-structured task description.

This document defines the recognition patterns, task format, response flow, and communication mechanisms that govern this routing.

---

## Recognition Patterns

The Main Agent must route to the Coding Agent when it recognizes any of the following situations.

### Explicit Capability Gaps

The human asks for something the system cannot currently do:

- "Can you track my workouts?" (no workout functionality exists)
- "I need the report to include risk scores" (risk scoring not implemented)
- "Add a notification when deadlines are missed" (no deadline notification system)

**Recognition signal**: The Main Agent searches its known capabilities and finds no match. The response would be "I don't have this functionality" -- that is the trigger to route.

### Behavioral Defects

The human reports something that should work but does not:

- "The status shows wrong after I update it"
- "It's not sending me the weekly summary anymore"
- "The search returns duplicates"

**Recognition signal**: The Main Agent can confirm the expected behavior exists in principle but is broken. This requires a bug-fix sprint.

### Enhancement Requests

The human asks for an existing feature to work differently:

- "Can the briefing also show overdue items?"
- "I want to filter tasks by priority"
- "Make the summary shorter and include action items"

**Recognition signal**: The capability exists but needs modification. The Main Agent understands the domain change required but cannot implement it.

### Performance or Scale Issues

The human reports slowness or capacity problems:

- "It's taking too long to generate the report"
- "It crashes when I have more than 100 items"

**Recognition signal**: The system works but not well enough. Requires engineering analysis and optimization.

### Self-Identified Gaps

The Main Agent itself recognizes during normal operation that it lacks needed functionality:

- While processing a request, discovers a missing data field
- While generating output, realizes a calculation is wrong
- While handling an edge case, finds no code path for it

**Recognition signal**: The Main Agent's own execution reveals a gap. It should create a task for the Coding Agent proactively and inform the human.

---

## Task Format

When the Main Agent routes to the Coding Agent, it must provide a structured task description. Ambiguous or incomplete task descriptions lead to incorrect implementations.

### Required Fields

```markdown
# Task: [Short descriptive title]

## What the Human Asked For
[The human's request, quoted verbatim when possible, with additional
context from the conversation if the request was conversational]

## What Functionality Is Missing
[The Main Agent's assessment of what the system currently lacks.
This is where domain expertise matters -- the Main Agent translates
the human's language into a precise description of the gap]

## Acceptance Criteria
- [ ] [Specific, testable criterion 1]
- [ ] [Specific, testable criterion 2]
- [ ] [Specific, testable criterion 3]

## Domain Context
[Relevant information the Coding Agent needs to understand the domain:
- Related entities and their relationships
- Business rules that constrain the solution
- Edge cases the human cares about
- How this feature connects to existing functionality]
```

### Optional Fields

```markdown
## Priority
[HIGH | MEDIUM | LOW -- based on human's urgency signals]

## Constraints
[Any constraints the human mentioned:
- "Don't change how X works"
- "It needs to work with the existing Y"
- "Keep it simple for now"]

## Examples
[Concrete examples the human provided:
- "When I say 'mark as done', it should..."
- "The report should look like..."]
```

### Task Format Guidelines

1. **Acceptance criteria must be testable.** "It should work better" is not testable. "Response time under 2 seconds for 100 items" is testable.
2. **Domain context must be accurate.** The Main Agent's domain expertise is its primary contribution here. An incorrect domain model leads to a correct implementation of the wrong thing.
3. **Do not prescribe architecture.** The Main Agent describes WHAT is needed, never HOW to build it. Architecture is the Coding Agent's domain.
4. **Include negative criteria when relevant.** "Must NOT change the existing notification behavior" prevents scope creep.
5. **Quote the human.** When the human's exact words matter (especially for UI text, output format, or naming), include verbatim quotes.

---

## Response Flow

### Standard Flow (Sub-Agent Spawn Pattern)

```
1. Human makes request
2. Main Agent recognizes coding need
3. Main Agent creates structured task
4. Main Agent spawns Coding Agent with task
5. Coding Agent executes development cycle (Stages 2-7)
   5a. [Stage 3] Coding Agent requests domain review of sprint plan
   5b. Main Agent reviews plan for domain correctness
   5c. Coding Agent incorporates feedback
6. Coding Agent delivers results (delivery report file)
7. Main Agent reads delivery report
8. Main Agent verifies domain correctness of the result
9. Main Agent reports to human
```

### Standard Flow (File-Based Pattern)

```
1. Human makes request
2. Main Agent recognizes coding need
3. Main Agent writes tasks/TASK_XXX.md (status: NEW)
3a. Main Agent notifies Coding Agent directly (e.g. /switch dev-agent)
4. Coding Agent picks up task immediately (status: IN_PROGRESS)
5. Coding Agent executes development cycle (Stages 2-7)
   5a. [Stage 3] Coding Agent writes plan review request file
   5b. Main Agent reads request, writes review response file
   5c. Coding Agent reads response, incorporates feedback
6. Coding Agent writes delivery/TASK_XXX_REPORT.md
7. Coding Agent updates task status to DELIVERED
8. Main Agent reads delivery report
9. Main Agent verifies domain correctness
10. Main Agent updates task status to VERIFIED
11. Main Agent reports to human
```

### Error Flow

When the Coding Agent encounters a domain question during implementation:

```
Coding Agent: writes reviews/TASK_XXX_DOMAIN_QUESTION.md
  - The specific question
  - What the Coding Agent has determined so far
  - The options it sees
  - What it needs from the Main Agent to proceed

Main Agent: reads the question, writes response
  - The answer with domain reasoning
  - Any updated acceptance criteria

Coding Agent: reads response, continues implementation
```

### Rejection Flow

The Coding Agent may push back on a task if:
- The task is ambiguous and cannot be started without clarification
- The task conflicts with existing architecture in ways the Main Agent may not realize
- The task scope is too large for a single sprint

In these cases, the Coding Agent writes a response explaining the issue and what it needs. The Main Agent then either clarifies, adjusts the task, or consults the human.

---

## Stage 3 Domain Review Protocol

During Stage 3 (Plan Review), the Coding Agent solicits domain review from the Main Agent. This is the ONLY stage where the Main Agent reviews technical artifacts.

### What the Coding Agent Sends for Review

```markdown
# Plan Review Request: TASK_XXX

## Sprint Plan Summary
[Brief description of what will be built]

## Domain Model Changes
[New entities, modified fields, changed relationships]

## Behavioral Changes
[How the system's behavior will change from the user's perspective]

## Questions for Domain Review
1. [Specific domain question]
2. [Specific domain question]

## Full Sprint Plan
[Link to or inline the complete sprint plan]
```

### What the Main Agent Reviews

The Main Agent evaluates the sprint plan ONLY for domain correctness:

- **Entity model accuracy**: Are the entities and relationships correct for the domain?
- **Business rule compliance**: Does the plan respect all domain constraints?
- **Acceptance criteria alignment**: Will the planned implementation actually satisfy the acceptance criteria?
- **Edge case coverage**: Are domain-specific edge cases addressed?
- **Naming correctness**: Do entity names, field names, and status values match domain terminology?

### What the Main Agent Does NOT Review

- Code architecture decisions
- Technology choices
- Test strategy
- Implementation ordering
- Performance approach
- Module structure

### Review Response Format

```markdown
# Plan Review Response: TASK_XXX

## Domain Correctness: APPROVED | NEEDS_CHANGES

## Findings
### [Finding 1 - severity: CRITICAL | HIGH | MEDIUM | LOW]
[Description of the domain issue]
[What should change]

### [Finding 2]
...

## Answers to Questions
1. [Answer to question 1]
2. [Answer to question 2]

## Additional Domain Context
[Any context the Main Agent realized was missing from the original task]
```

---

## Routing Decision Tree

```
Human request received
  |
  +--> Can the Main Agent handle this with existing capabilities?
  |      |
  |      +--> YES --> Handle directly, no routing needed
  |      |
  |      +--> NO --> Is this a domain/knowledge question (no code needed)?
  |             |
  |             +--> YES --> Answer from domain knowledge
  |             |
  |             +--> NO --> Route to Coding Agent
  |                    |
  |                    +--> Create structured task
  |                    +--> Include all domain context
  |                    +--> Delegate via chosen communication pattern
  |                    +--> Wait for delivery
  |                    +--> Verify and report to human
```

---

## Anti-Patterns

### 1. Vague Delegation

**Wrong**: "The user wants something with tasks, figure it out."

**Right**: Structured task with verbatim human request, gap analysis, testable acceptance criteria, and domain context.

### 2. Architecture Prescription

**Wrong**: "Create a new table called X with fields Y and Z, then write a service that..."

**Right**: "The system needs to track workout exercises with their sets, reps, and weights. Each exercise belongs to a session. Sessions belong to a user." (Describe the domain, not the implementation.)

### 3. Skipping Domain Review

**Wrong**: Coding Agent proceeds directly from sprint plan to implementation without Main Agent review.

**Right**: Every sprint plan goes through Stage 3 domain review. Even if the Main Agent approves with no changes, the review step must happen.

### 4. Main Agent Reviewing Code

**Wrong**: Main Agent reads implementation files and comments on code structure.

**Right**: Main Agent reviews only the delivery report and verifies the feature works from a domain perspective.

### 5. Coding Agent Asking the Human Directly

**Wrong**: Coding Agent surfaces a domain question directly to the human.

**Right**: Coding Agent writes the question to a file/report. Main Agent reads it, consults the human if needed, and relays the answer.

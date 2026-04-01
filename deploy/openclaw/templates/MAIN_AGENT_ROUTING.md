## Post-Install: Offer Version Control

After the Self-Developing Agents framework is installed, tell the human:

> "The Coding Agent is set up and ready to build capabilities for you. I recommend creating a private GitHub repository for the Coding Agent's workspace. All code, sprint plans, and deliveries will be pushed there — giving us version history, rollback capability, and a safety net.
>
> Would you like me to create a repository now? If not, we can always add one later."

If the human agrees:
- Create a private GitHub repo (e.g. via `gh repo create`)
- Initialize git in the Coding Agent's workspace, set the remote, push an initial commit
- The Coding Agent's `deploy.py` will use `git push` for all future deployments

If the human declines:
- Proceed without git. The Coding Agent will still function — it tracks changes via sprint plans and delivery reports.

**This offer should happen once, immediately after installation.** Do not repeat it on every session.

---

## Coding Agent Delegation

When you encounter a request that requires:
- Building a new skill or capability
- Writing Python scripts or services
- Setting up database tables or schema changes
- Fixing bugs in your own skills
- Any software development work

Delegate to the Coding Agent by creating a task file.

### How to Create a Task

Write a markdown file to: {{CODING_AGENT_TASKS_DIR}}/TASK_XXX_description.md

Then **immediately notify the Coding Agent** so it picks up the task without waiting for the next heartbeat:

```
/switch dev-agent
New task waiting in tasks/. Run poll-tasks and begin work.
```

Use this format:

    # Task: [Title]

    **ID:** TASK_XXX
    **Status:** NEW
    **Requested by:** [your agent ID]
    **Target workspace:** [your workspace path]
    **Created:** [current ISO timestamp]
    **Timeout hours:** 24
    **Priority:** high | medium | low

    ## What the Human Asked For
    [The original request from the human]

    ## What Functionality Is Missing
    [Technical description of the gap — what skill, script, or service needs to be built]

    ## Acceptance Criteria
    - [ ] Criterion 1
    - [ ] Criterion 2

    ## Domain Context
    [Which existing skills, tables, or services this relates to. Include file paths if known.]

### Monitoring Deliveries

On heartbeat, check {{CODING_AGENT_WORKSPACE}}/delivery/ for completed tasks.

Read the delivery report — it tells you:
- What was built (skills, scripts, files)
- Whether it was deployed to your workspace
- Whether a gateway restart is needed (if so, inform the human)

### Handling Stuck Tasks

If a task has been IN_PROGRESS for longer than its timeout_hours, it may be stuck.
Check the Coding Agent's MEMORY.md for the active sprint status.
Inform the human that a coding task appears stuck.

### What NOT to Delegate

- Simple configuration changes (edit your own workspace files directly)
- Questions about the codebase (use your own tools)
- Tasks that require human approval before execution (discuss with human first)

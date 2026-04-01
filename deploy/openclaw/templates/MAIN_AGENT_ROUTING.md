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
    **Deploy to:** [your agent ID — the agent that will receive the built skill]
    **Target workspace:** [absolute path to your workspace, e.g. /home/openclaw/.openclaw/workspace-callisto]
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

**Important:** Always fill in `**Deploy to:**` and `**Target workspace:**` with your own agent ID and workspace path. This tells the Coding Agent where to deploy the finished skill.

### Receiving Deploy Notifications — IMMEDIATELY RELAY TO HUMAN

**When you receive any message from the Coding Agent about a completed task, you MUST immediately forward a summary to the human.** Do not wait for the human to ask. The human is expecting results and has no other way to know a task finished.

**WARNING: Do NOT just reply in the inter-session channel.** Replying to the Coding Agent's `sessions_send` message sends your response back to the Coding Agent — the human never sees it. You must use your **message tool** (Telegram, chat, or whatever channel connects you to the human) to relay the notification. The inter-session channel is agent-to-agent only.

When the Coding Agent sends you a message (via `sessions_send`, `/switch`, or direct message) saying a skill has been deployed to your workspace:

1. **Immediately message the human** (via your primary communication channel, e.g. Telegram): "The Coding Agent has delivered a new skill. Let me review and set it up."
2. Read the delivery report from the Coding Agent's `delivery/TASK_XXX_DELIVERY.md`
3. Verify the skill files exist in your `skills/` directory
4. If the report says "gateway restart needed", ask the human for permission, then run `gateway.restart`
5. After restart, confirm the new skill appears in your available skills
6. Present the **Task Completion Summary** to the human:

> **Task Complete: [Title]**
>
> **What was built:** [list from delivery report]
> **Tests:** [X written, Y passing]
> **Review quality:** [sub-agent / single-agent] — [N] review iterations, [N] sub-agents spawned
> **Bugs found & fixed:** [N] critical, [N] high, [N] medium, [N] low
> **Deployed to:** [your workspace] — [skill is now available / gateway restart needed]
> **Limitations:** [any caveats from the report]

All data for this summary comes from the delivery report. Always present it — it gives the human visibility into the development quality, not just the result.

### Monitoring Deliveries (Fallback)

On heartbeat, check {{CODING_AGENT_WORKSPACE}}/delivery/ for completed tasks. This catches any deliveries where the direct notification was missed.

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

---

## Post-Install Self-Check

After installing the Self-Developing Agents framework, verify you have internalized these behaviors. If any are missing from your behavioral rules, add them:

- [ ] **Task delegation**: You know how to create task files in the Coding Agent's `tasks/` directory
- [ ] **Immediate notification**: After dropping a task, you `/switch` to the dev-agent to wake it up
- [ ] **Deploy relay**: When you receive a message from the Coding Agent about a delivery, you **immediately** forward a summary to the human via your primary channel (e.g. Telegram) — do NOT reply in the inter-session channel, that goes back to the Coding Agent, not the human
- [ ] **Gateway restart**: You know to ask the human for permission, then run `gateway.restart`
- [ ] **Delivery monitoring**: On heartbeat, you check the Coding Agent's `delivery/` directory as a fallback
- [ ] **Task Completion Summary**: You present a structured summary (what was built, tests, review quality, bugs found) to the human after every delivery

If any of these rules are not in your loaded workspace files, treat this document as authoritative and follow them.

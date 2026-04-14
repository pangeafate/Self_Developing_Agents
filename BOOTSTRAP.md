# Bootstrap — Day 1 Setup

This is the entry point for any AI agent adopting the Self-Developing Agents Framework. Read this file first, then follow the steps sequentially.

> **Automated alternative:** If you can run Python scripts, Steps 2-5 can be automated:
> ```bash
> python skills/dev-bootstrap/scripts/bootstrap.py --action setup --project-root /path/to/project
> ```
> This creates all directories, copies all files, and runs initial validation. You still need to handle Step 1 (GitHub repo) and Step 6 (readiness report) manually.

---

## Step 0: Capability Detection

Before proceeding, verify you can:

1. **Create files** — write new files to the filesystem
2. **Create directories** — make new folders
3. **Run shell commands** — execute bash/zsh commands
4. **Run Python scripts** — execute `python` or `python3`
5. **Use git** — required for validators. If unavailable, validators run in structural-only mode (skipping ordering/freshness checks)

### If capabilities 1-3 are unavailable (MANUAL_SETUP)

If the **agent** lacks filesystem or shell access, the human must perform physical setup:

(a) Create the workspace directory tree matching the layout described in Step 2 below, including `test/unit/`, `test/integration/`, `test/fixtures/`, `workspace/sprints/`

(b) Copy all `practices/GL-*.md` files from this framework into the workspace

(c) Copy the `validators/` directory into the project root:
   - If Python is available on the machine, run: `python validators/run_all.py --bootstrap --fix`
   - If Python is also unavailable, create the directories listed in (a) manually

(d) Proceed to Step 2 — the agent fills in content only, no file/directory creation needed. The GitHub discussion from Step 1 can be had verbally with the human at any point.

---

## Step 1: Suggest Version Control

Tell the human:

> "I recommend creating a private GitHub repository for this project. All code, workspace files, sprint plans, and documentation will be pushed there. This gives us version history, CI/CD deployment, and a safety net for rollbacks.
>
> If you'd prefer not to set up a repo now, I'll track everything via sprint plan files in the workspace. We can always add a repo later."

If the human creates a repo:
- Initialize it, set the remote, push an initial commit
- All subsequent sprints will push via `git push`

If the human declines:
- Proceed without git. Track all changes via sprint plan files and PROGRESS.md.
- Validators will skip git-dependent checks with advisory messages.

---

## Step 2: Create Project Structure

Create the workspace directory and populate it from the framework's templates:

```
workspace/
├── PROJECT_CONTEXT.md        ← Fill in from human's description of the project
├── ARCHITECTURE.md           ← Initially minimal, grows as the system evolves
├── DATA_SCHEMA.md            ← Empty until first database interaction
├── CODEBASE_STRUCTURE.md     ← Initially minimal, updated as files are created
├── PROJECT_ROADMAP.md        ← Initial roadmap from human's goals
├── PROGRESS.md               ← Empty, ready for Sprint 1
├── FEATURE_LIST.md           ← Populated from human's initial request
├── USER_STORIES.md           ← Derived from initial requirements
├── AGENT_INSTRUCTIONS.md     ← Project-level rules (from templates/AGENT_INSTRUCTIONS.md)
├── AGENT_IDENTITY.md         ← Agent personality and behavioral rules
├── START_UP.md               ← Onboarding guide for new sessions
└── sprints/                  ← Empty directory for sprint plans
```

For each file:
1. Copy the corresponding template from `templates/`
2. Fill in the sections based on what you know from the human's request
3. Leave sections empty (with placeholder text) if you don't have the information yet

**PROJECT_CONTEXT.md** is the most important — fill it in first. Ask the human for clarification if the project's purpose or scope is unclear.

---

## Step 3: Copy Practices

Place the development practice files where the agent can reference them:

```bash
cp practices/GL-*.md workspace/
```

Or create symlinks if the platform supports them. The agent must be able to read these files during every sprint.

---

## Step 4: Set Up Validators

Copy the `validators/` directory into the project root:

```bash
cp -r validators/ ./validators/
```

The validators are Python scripts that enforce the 7-stage development cycle. They should be run before every deploy (manually or via git hooks if configured).

---

## Step 5: Run Initial Validation

```bash
python validators/run_all.py --bootstrap
```

The `--bootstrap` flag runs only `validate_structure.py` and `validate_workspace.py` — the other 5 validators (TDD, RDD, sprint, doc-reality, doc-freshness) are meaningful only after Sprint 1 completes.

Expected output: all checks pass (directory structure exists, no oversized files, no credentials in workspace files).

If checks fail, fix the issues before proceeding.

---

## Step 6: Report Readiness

Tell the human what was set up:

> "Project infrastructure is ready. Here's what I created:
>
> - **Workspace** with project context, architecture, and tracking docs
> - **Development practices** (TDD, RDD, error handling, sprint discipline, etc.)
> - **Validators** that enforce the 7-stage development cycle
> - **Sprint folder** ready for the first sprint plan
>
> I'm ready to start building. Tell me what you need, and I'll begin with Sprint 1."

---

## What Happens Next

When the human gives the first task:

1. The agent recognizes what functionality is needed
2. Creates `workspace/sprints/SP_001_Description.md` with a sprint plan
3. Runs the plan through 2+ review iterations (self-critique)
4. Implements using TDD (test → code → refactor)
5. Runs 2+ post-implementation review iterations
6. Deploys (if CI/CD is configured)
7. Updates all documentation

This cycle repeats for every feature, bug fix, and self-improvement. The validators ensure no stage is skipped.

---

## Brownfield Adoption (Existing Codebase)

If pointing this framework at an existing project with code already written:

1. Run `python validators/run_all.py --bootstrap` to see the gap report
2. Create **Sprint 0: Framework Adoption** — this sprint's goal is to set up workspace files and document the existing codebase
3. Fill in ARCHITECTURE.md, CODEBASE_STRUCTURE.md, and DATA_SCHEMA.md from the existing code
4. For the first few sprints, validators may report many warnings for undocumented modules — treat these as the documentation backlog, not blockers
5. Once the workspace is populated and tests cover critical paths, the full validation suite becomes meaningful

# Context Isolation: The Foundational Quality Principle

## Why This Exists

In our experience across 170+ sprints, we consistently catch significantly more bugs (2-3x in our observation) when critique comes from agents that never saw the original sprint plan. This is not a marginal improvement -- it is the single most impactful quality practice in the entire framework.

The reason is cognitive bias. When you know what you meant to write, you read what you meant instead of what you wrote. This is true for humans and it is equally true for AI agents. An agent that wrote the code, or that read the plan describing what the code should do, will unconsciously fill in gaps, gloss over inconsistencies, and assume correctness where none exists.

Context isolation is the systematic prevention of this bias.

---

## The Five Isolation Rules

### Rule 1: The Coding Agent NEVER Validates Its Own Code

The Coding Agent writes all implementation code (Stage 4). It must NEVER perform quality review on that code. All validation is delegated to context-isolated Helper Agents (Tier 3).

**What this means in practice**:
- After writing code, the Coding Agent does not re-read it to "check for issues"
- The Coding Agent spawns quality agents and gives them the files to review
- The Coding Agent's role after implementation is to orchestrate reviews and consolidate findings -- not to add its own review opinions
- When a quality agent finds an issue, the Coding Agent fixes it. It does not argue with the finding based on its knowledge of what it "meant to do"

**Why**:
The Coding Agent has the strongest bias of any agent in the system. It made every design decision, wrote every line, and understands every tradeoff. This deep context makes it the worst possible reviewer of its own work. It will defend its decisions unconsciously, interpret ambiguous code charitably, and miss exactly the bugs that a fresh pair of eyes would catch.

### Rule 2: Quality Agents NEVER See the Sprint Plan During Stage 5

During Stage 5 (post-implementation review), quality agents -- architect-reviewer, code-reviewer, debugger, security-auditor, performance-reviewer -- must NEVER receive the sprint plan.

**What they receive instead**:
- The actual code files to review
- Existing architecture documentation (not sprint-specific)
- Existing source files that the new code references or modifies
- Test files and test output

**What they do NOT receive**:
- The sprint plan
- The task description from the Main Agent
- The Coding Agent's design rationale
- Comments or notes about "what this is supposed to do"

**The Stage 3 exception**: During Stage 3 (plan review, BEFORE implementation), the architect-reviewer and code-reviewer DO receive the sprint plan. This is correct because in Stage 3, the plan IS the artifact under review. The reviewers are evaluating the plan itself -- checking for architecture risks, verifying that referenced functions exist, and finding implementation issues in the proposed approach. There is no "build intent" bias because nothing has been built yet.

**Why the distinction matters**:
- Stage 3 review: "Is this plan sound?" -- the plan IS the subject
- Stage 5 review: "Is this code correct?" -- the code is the subject, and knowing the plan would bias the review toward confirming plan compliance rather than finding actual bugs

### Rule 3: The Main Agent Reviews Plans but NEVER Reviews Code

The Main Agent participates in Stage 3 (plan review) by evaluating sprint plans for domain correctness. It NEVER participates in Stage 5 (code review).

**What the Main Agent reviews in Stage 3**:
- Are the entities and relationships correct for the domain?
- Do the acceptance criteria match what the human asked for?
- Are business rules respected?
- Is the terminology accurate?

**What the Main Agent never does**:
- Read implementation source files
- Evaluate code architecture or structure
- Comment on test strategy or coverage
- Assess performance characteristics of code

**Why**:
The Main Agent is a domain expert, not an engineering expert. Mixing domain review and code review in a single agent dilutes both. The Main Agent's value is in catching domain errors that engineers miss ("that status transition is wrong because in our domain, X always precedes Y"). Code review is a fundamentally different skill owned by the quality agents.

### Rule 4: Each Review Iteration Starts a Fresh Agent Context

When the Coding Agent runs multiple iterations of gap analysis (part of Stage 5 -- Post-Implementation Review), each iteration uses a freshly spawned agent. The agent from Iteration 1 is never reused for Iteration 2.

**What this means in practice**:
- Iteration 1 spawns a fresh reviewer, reviews, finds issues, reports, terminates
- Coding Agent fixes the issues found in Iteration 1
- Iteration 2 spawns a NEW fresh reviewer with NO knowledge of Iteration 1's findings
- This continues until an iteration finds zero issues

**Why**:
Accumulated context across iterations creates a different form of bias. An agent that found 3 issues in Iteration 1 and sees them fixed in Iteration 2 will unconsciously focus on verifying those 3 fixes rather than searching broadly for new issues. It has "anchored" on the Iteration 1 problem set. A fresh agent in Iteration 2 searches the entire codebase with no anchoring, making it far more likely to find issues in areas Iteration 1 never examined.

### Rule 5: Research Agents May Share Context; Quality Agents Must Not

Helper agents fall into two categories with different isolation requirements:

**Research agents (shared context permitted)**:
- Researcher: searches the codebase, finds relevant files
- Analyzer: traces execution paths, maps dependencies

These agents assist the Coding Agent with information gathering. Their output feeds into the Coding Agent's implementation decisions. Sharing context with them (what is being built, why, relevant files) makes their research more targeted and useful. There is no quality risk because research agents do not evaluate correctness.

**Quality agents (strict isolation required)**:
- Architect-reviewer
- Code-reviewer
- Debugger
- Security-auditor
- Performance-reviewer

These agents evaluate the code's correctness. Any shared context about build intent compromises their objectivity. They must operate with only the code itself and existing (non-sprint-specific) documentation.

---

## What IS Shared vs. What is NEVER Shared

### Shared With Quality Agents (Stage 5)

| Artifact | Rationale |
|----------|-----------|
| Implementation source files | The subject of review |
| Test files and test output | Evidence of correctness (or lack thereof) |
| Existing architecture documentation | Stable reference for architectural evaluation |
| Existing source files modified by the sprint | Context for evaluating changes |
| Domain model documentation (stable, not sprint-specific) | Background knowledge |
| Error logs and stack traces | Debugging evidence |

### NEVER Shared With Quality Agents (Stage 5)

| Artifact | Rationale |
|----------|-----------|
| Sprint plan | Contains build intent -- biases toward confirmation |
| Task description from Main Agent | Contains "what it should do" -- biases toward plan compliance |
| Coding Agent's design notes | Contains rationale -- biases toward defending decisions |
| Previous iteration's review findings | Anchors attention on known issues |
| Commit messages that describe intent | Subtle form of build intent leakage |
| Comments between Coding Agent and Main Agent | Domain review context that biases code review |

### The Intent Leakage Principle

Any information that tells a reviewer "what the code is supposed to do" rather than letting the reviewer determine "what the code actually does" is a form of intent leakage. The entire point of context isolation is to force reviewers to derive the code's behavior from the code itself, then evaluate whether that behavior is correct based on their own analysis.

When intent leaks, reviewers unconsciously shift from "what does this code do?" to "does this code do what it's supposed to?" -- and the latter question systematically misses bugs where the intent itself was flawed.

---

## Anti-Patterns

### Anti-Pattern 1: Single Agent Building + Reviewing

**The pattern**: One agent writes the code and then reviews it, possibly in the same conversation or context.

**Why it fails**: The agent has complete knowledge of its own intent. It will read the code through the lens of what it meant to write, not what it actually wrote. Off-by-one errors, missing edge cases, incorrect field names -- all become invisible because the agent's mental model fills in the gaps.

**The fix**: Separate agents for building and reviewing. The reviewing agent has never seen the building agent's context.

### Anti-Pattern 2: Reviewer Seeing Build Intent

**The pattern**: A separate agent reviews the code, but it receives the sprint plan, task description, or design rationale along with the code.

**Why it fails**: Even with a separate agent, intent knowledge biases the review. The reviewer reads "this function should calculate the weighted average" in the sprint plan, then sees a function that appears to calculate a weighted average, and marks it as correct -- without noticing that the weights are applied in the wrong order or that one weight is hardcoded incorrectly. The intent description satisfied the reviewer's expectation before the code was even fully analyzed.

**The fix**: Quality agents in Stage 5 receive ONLY the code and stable documentation. They must derive the code's purpose from the code itself.

### Anti-Pattern 3: Accumulated Context Across Iterations

**The pattern**: The same reviewer agent runs Iteration 1, finds issues, then runs Iteration 2 on the fixed code.

**Why it fails**: The agent anchors on its Iteration 1 findings. In Iteration 2, it primarily verifies that its previous findings were addressed. It does not search with the same breadth as a fresh agent would. Entire categories of bugs go unexamined because the agent's attention is consumed by confirming fixes.

**The fix**: Each iteration uses a fresh agent with no knowledge of previous iterations.

### Anti-Pattern 4: "Quick Check" Bypass

**The pattern**: The change is "small" or "trivial," so the review stage is skipped. "It's just a one-line fix, no need for review."

**Why it fails**: Small changes in critical code paths cause disproportionate damage. A one-line fix to a financial calculation, a status transition, or an authentication check can introduce catastrophic bugs. The perceived triviality of the change reduces vigilance precisely when correctness matters most.

**The fix**: Every change goes through the full review pipeline. The review may be fast for small changes, but it must happen.

### Anti-Pattern 5: Domain Expert Reviewing Code

**The pattern**: The Main Agent (domain expert) reviews implementation code to "make sure it's right."

**Why it fails**: The Main Agent lacks engineering context. It cannot evaluate code quality, architecture decisions, or implementation correctness. Its review adds false confidence -- "the domain expert approved it" -- without actually verifying technical correctness. Worse, it mixes domain concerns with implementation concerns, making it unclear which type of issue is being evaluated.

**The fix**: The Main Agent reviews sprint plans (Stage 3) for domain correctness. Quality agents review code (Stage 5) for technical correctness. These are separate activities performed by agents with the appropriate expertise.

---

## Why This Works: The Cognitive Bias Argument

Context isolation works because it systematically eliminates three cognitive biases that plague code review:

### 1. Confirmation Bias

When you know what the code should do, you look for evidence that it does that thing. You do not look for evidence that it does something else. A context-isolated reviewer has no expectation to confirm. It must build its understanding from the code, which means it is equally likely to notice correct behavior and incorrect behavior.

### 2. Anchoring Bias

When you have seen previous findings, your attention anchors on those areas. You spend disproportionate time verifying fixes and disproportionately little time searching new areas. A fresh reviewer in each iteration has no anchor. Its attention distributes across the entire codebase based on its own analysis.

### 3. Curse of Knowledge

When you know the design rationale behind a decision, you cannot un-know it. You read the code with the rationale in mind, and ambiguous code reads as clear because you supply the missing context from your knowledge. A context-isolated reviewer encounters ambiguous code as genuinely ambiguous and is far more likely to flag it.

### The Compound Effect

These biases compound. A single agent building and reviewing its own code (combining all three biases) will miss dramatically more bugs than a context-isolated reviewer (eliminating all three). In our experience, this is not a subtle difference -- it manifests as a 2-3x improvement in bug detection rate.

The cost of context isolation is the overhead of spawning and managing separate agents. The benefit is catching bugs before they reach production. Across 170+ sprints, the benefit has consistently and substantially outweighed the cost.

---

## Implementation Checklist

When setting up context isolation in a new project:

- [ ] Coding Agent has a mechanism to spawn helper agents with controlled context
- [ ] Sprint plans are stored in files that are NOT automatically included in Stage 5 review context
- [ ] Quality agent spawn prompts include ONLY: code files, test files, stable documentation
- [ ] Quality agent spawn prompts explicitly exclude: sprint plan, task description, design notes
- [ ] Each gap analysis iteration spawns a fresh agent (no agent reuse across iterations)
- [ ] The Main Agent has a clear boundary: reviews plans in Stage 3, never reads code in Stage 5
- [ ] Research agents are distinguished from quality agents, with appropriate context rules for each
- [ ] The Coding Agent has a mechanism to consolidate quality agent findings without adding its own review opinions

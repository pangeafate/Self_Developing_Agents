#!/usr/bin/env python3
"""Build sub-agent context for a dev-critique review run.

Gathers the role file, selects the correct prompt template, and bundles
source files into a single JSON payload that the orchestrating agent feeds
to a fresh sub-agent context.

Usage:
    python gather-context.py \\
        --role ROLE_NAME \\
        --stage {3,5} \\
        [--files FILE ...] \\
        [--sprint-plan PATH] \\
        [--framework-root PATH]

Output: JSON to stdout.

Exit codes:
    0 — success
    1 — isolation violation (stage 5 + --sprint-plan)
    2 — fatal (role not found, ambiguous role, or invalid --stage)
    3 — configuration error
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STAGES: frozenset[int] = frozenset({3, 5})

# Section headings as they appear in GL-SELF-CRITIQUE.md (without the ``` fences)
_ARCHITECT_HEADING = "Pre-Implementation Review Prompt (for Architect-Reviewer)"
_CODE_REVIEWER_HEADING = "Pre-Implementation Review Prompt (for Code-Reviewer)"
_GAP_ANALYSIS_HEADING = "Post-Implementation Review Prompt (for Gap Analysis Reviewers)"


# ---------------------------------------------------------------------------
# Framework root auto-detection
# ---------------------------------------------------------------------------

def _find_framework_root(start: Path) -> Path | None:
    """Walk up from *start* looking for a directory containing roles/ and practices/."""
    # 1. Environment variable (set by the platform or install.sh at install time)
    env_root = os.environ.get("SDA_FRAMEWORK_ROOT")
    if env_root:
        candidate = Path(env_root).resolve()
        if (candidate / "roles").is_dir() and (candidate / "practices").is_dir():
            return candidate
    # 2. Walk-up heuristic (works during development)
    candidate = start.resolve()
    for _ in range(20):  # bounded walk — stop before hitting filesystem root
        if (candidate / "roles").is_dir() and (candidate / "practices").is_dir():
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    return None


# ---------------------------------------------------------------------------
# Role file lookup
# ---------------------------------------------------------------------------

def _find_role_file(role_name: str, framework_root: Path) -> Path:
    """Glob roles/**/{role_name}.md under framework_root.

    Exits with code 2 if zero or multiple matches are found.
    """
    pattern = f"**/{role_name}.md"
    roles_dir = framework_root / "roles"
    matches = list(roles_dir.glob(pattern))

    if len(matches) == 0:
        print(
            f"ERROR: role '{role_name}' not found under {roles_dir}",
            file=sys.stderr,
        )
        sys.exit(2)

    if len(matches) > 1:
        paths = ", ".join(str(m) for m in sorted(matches))
        print(
            f"ERROR: role '{role_name}' is ambiguous — matched multiple files: {paths}",
            file=sys.stderr,
        )
        sys.exit(2)

    return matches[0]


# ---------------------------------------------------------------------------
# Prompt template extraction
# ---------------------------------------------------------------------------

def _extract_fenced_block(text: str, heading: str) -> str | None:
    """Return the content of the first ```...``` block after *heading*.

    The heading is matched case-insensitively, anywhere in the text.
    Returns None if the heading or a fenced block after it is not found.
    """
    # Find the heading
    pattern = re.compile(re.escape(heading), re.IGNORECASE)
    m = pattern.search(text)
    if m is None:
        return None

    # Search for the opening fence after the heading
    remainder = text[m.end():]
    fence_open = re.search(r"```[^\n]*\n", remainder)
    if fence_open is None:
        return None

    after_open = remainder[fence_open.end():]
    fence_close = after_open.find("```")
    if fence_close == -1:
        return None

    return after_open[:fence_close].strip()


def _load_prompt_templates(framework_root: Path) -> dict[str, str]:
    """Read GL-SELF-CRITIQUE.md and extract the 3 prompt templates.

    Exits with code 3 if the file is missing or a template cannot be parsed.
    """
    gl_path = framework_root / "practices" / "GL-SELF-CRITIQUE.md"
    if not gl_path.exists():
        print(
            f"ERROR: GL-SELF-CRITIQUE.md not found at {gl_path}",
            file=sys.stderr,
        )
        sys.exit(3)

    text = gl_path.read_text(encoding="utf-8")

    templates: dict[str, str] = {}
    for key, heading in [
        ("architect", _ARCHITECT_HEADING),
        ("code-reviewer", _CODE_REVIEWER_HEADING),
        ("gap-analysis", _GAP_ANALYSIS_HEADING),
    ]:
        block = _extract_fenced_block(text, heading)
        if block is None:
            print(
                f"ERROR: could not find prompt template section '{heading}' "
                f"in {gl_path}",
                file=sys.stderr,
            )
            sys.exit(3)
        templates[key] = block

    return templates


def _select_prompt(
    stage: int,
    role: str,
    templates: dict[str, str],
) -> str:
    """Return the correct prompt template for this (stage, role) combination."""
    if stage == 5:
        return templates["gap-analysis"]

    # stage == 3
    if role == "code-reviewer":
        return templates["code-reviewer"]

    # architect-reviewer and any other role → architect prompt
    return templates["architect"]


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build sub-agent review context (JSON output).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--role",
        required=True,
        metavar="ROLE_NAME",
        help="Role file name without .md extension (e.g. architect-reviewer).",
    )
    parser.add_argument(
        "--stage",
        required=True,
        type=int,
        choices=[3, 5],
        metavar="{3,5}",
        help="Pipeline stage: 3=pre-implementation review, 5=gap analysis.",
    )
    parser.add_argument(
        "--files",
        nargs="+",
        metavar="FILE",
        default=[],
        help="Source/test files to include in context_files.",
    )
    parser.add_argument(
        "--sprint-plan",
        metavar="PATH",
        default=None,
        help="Path to the sprint plan document (stage 3 only).",
    )
    parser.add_argument(
        "--framework-root",
        metavar="PATH",
        type=Path,
        default=None,
        help="Override auto-detected framework root directory.",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    args = _parse_args()

    # Validate stage explicitly (argparse choices covers {3,5} but not other ints)
    if args.stage not in VALID_STAGES:
        print(
            f"ERROR: --stage must be 3 or 5, got {args.stage}",
            file=sys.stderr,
        )
        sys.exit(2)

    # Isolation enforcement: stage 5 must never receive the sprint plan
    if args.stage == 5 and args.sprint_plan is not None:
        print(
            "ISOLATION VIOLATION: --sprint-plan must not be passed at stage 5. "
            "Post-implementation reviewers must evaluate code on its own merits, "
            "not against the builder's intent. Remove --sprint-plan and re-run.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Stage 3 without a sprint plan: warn and continue
    if args.stage == 3 and args.sprint_plan is None:
        print(
            "WARNING: --sprint-plan was not provided for stage 3 review. "
            "Pre-implementation reviewers normally need the sprint plan. "
            "Continuing without it.",
            file=sys.stderr,
        )

    # Resolve framework root
    framework_root: Path
    if args.framework_root is not None:
        framework_root = args.framework_root.resolve()
        if not framework_root.is_dir():
            print(
                f"ERROR: --framework-root '{framework_root}' is not a directory.",
                file=sys.stderr,
            )
            sys.exit(3)
    else:
        detected = _find_framework_root(Path(__file__).parent)
        if detected is None:
            print(
                "ERROR: could not auto-detect framework root (no ancestor directory "
                "contains both 'roles/' and 'practices/'). Use --framework-root.",
                file=sys.stderr,
            )
            sys.exit(3)
        framework_root = detected

    # Load role file (exits 2 on not-found or ambiguous)
    role_file = _find_role_file(args.role, framework_root)
    system_prompt = role_file.read_text(encoding="utf-8")

    # Load prompt templates (exits 3 on config error)
    templates = _load_prompt_templates(framework_root)
    review_prompt = _select_prompt(args.stage, args.role, templates)

    # Build context_files list
    context_files: list[dict[str, str]] = []

    # Include --sprint-plan at stage 3
    if args.sprint_plan is not None:
        plan_path = Path(args.sprint_plan)
        if plan_path.is_file():
            context_files.append({
                "path": str(plan_path.resolve()),
                "content": plan_path.read_text(encoding="utf-8"),
            })
        else:
            print(
                f"WARNING: sprint plan not found at '{plan_path}' — skipping.",
                file=sys.stderr,
            )

    # Include --files entries
    for raw_path in args.files:
        file_path = Path(raw_path)
        if file_path.is_file():
            context_files.append({
                "path": str(file_path.resolve()),
                "content": file_path.read_text(encoding="utf-8"),
            })
        else:
            print(
                f"WARNING: file not found '{file_path}' — skipping.",
                file=sys.stderr,
            )

    # Assemble output
    output = {
        "role": args.role,
        "stage": args.stage,
        "system_prompt": system_prompt,
        "review_prompt": review_prompt,
        "context_files": context_files,
        "isolation_verified": True,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

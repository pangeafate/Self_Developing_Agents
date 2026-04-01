#!/usr/bin/env python3
"""create-plan.py — Generate a sprint plan file from the SPRINT_PLAN.md template.

Usage:
    python create-plan.py \\
        --sprint-id SP_042 \\
        --goal "Add user authentication" \\
        --output-dir workspace/sprints/ \\
        [--template path/to/SPRINT_PLAN.md]

Output (JSON to stdout):
    {"sprint_id": "SP_042", "file_path": "...", "created_at": "2026-03-31"}

Exit codes:
    0 — plan created successfully
    2 — fatal error (template not found, I/O failure)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Framework root resolution
# ---------------------------------------------------------------------------

_SCRIPTS_DIR = Path(__file__).parent


def _find_framework_root() -> Path:
    """Locate the SELF_DEVELOPING_AGENTS framework root directory.

    Resolution order:
    1. ``SDA_FRAMEWORK_ROOT`` environment variable (explicit override).
    2. Walk up from this file's directory until a directory containing both
       ``roles/`` and ``practices/`` sub-directories is found.
    3. Fall back to the original 3-parent-walk depth
       (scripts/ -> dev-sprint/ -> skills/ -> SELF_DEVELOPING_AGENTS/).
    """
    # 1. Environment variable override
    env_root = os.environ.get("SDA_FRAMEWORK_ROOT")
    if env_root:
        candidate = Path(env_root).resolve()
        if (candidate / "roles").is_dir() and (candidate / "practices").is_dir():
            return candidate
        # Invalid env var path — fall through to walk-up

    # 2. Walk up looking for the canonical marker directories
    candidate = _SCRIPTS_DIR
    for _ in range(10):  # guard against infinite walk
        candidate = candidate.parent
        if (candidate / "roles").is_dir() and (candidate / "practices").is_dir():
            return candidate

    # 3. Depth-based fallback (original behaviour)
    return _SCRIPTS_DIR.parent.parent.parent


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Convert text to a filename-safe slug.

    Rules:
    - Replace spaces with underscores
    - Strip all characters that are not alphanumeric or underscores
    - Collapse consecutive underscores to one
    - Strip leading/trailing underscores
    """
    slug = text.replace(" ", "_")
    slug = re.sub(r"[^\w]", "", slug)  # keep word chars only (a-z, A-Z, 0-9, _)
    slug = re.sub(r"_+", "_", slug)    # collapse repeated underscores
    return slug.strip("_")


def _render_template(template_text: str, sprint_id: str, goal: str, today: str) -> str:
    """Fill template placeholders with actual values.

    Replacements performed:
    - ``SP_XXX``              → sprint_id  (in the title line)
    - ``[Sprint Name]``       → goal
    - ``[YYYY-MM-DD]``        → today's date
    - ``[DATE]``              → today's date
    """
    text = template_text

    # Replace the title placeholders: "# SP_XXX: [Sprint Name]"
    text = text.replace("SP_XXX", sprint_id)
    text = text.replace("[Sprint Name]", goal)

    # Date placeholders
    text = text.replace("[YYYY-MM-DD]", today)
    text = text.replace("[DATE]", today)

    return text


def create_plan(
    sprint_id: str,
    goal: str,
    output_dir: Path,
    template_path: Path,
) -> Path:
    """Render a sprint plan and write it to disk. Returns the created file path."""
    # Read template
    try:
        template_text = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Cannot read template '{template_path}': {exc}", file=sys.stderr)
        sys.exit(2)

    today = date.today().isoformat()
    rendered = _render_template(template_text, sprint_id, goal, today)

    # Build filename
    slug = _slugify(goal)
    filename = f"{sprint_id}_{slug}.md"

    # Ensure output directory exists
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"ERROR: Cannot create output directory '{output_dir}': {exc}", file=sys.stderr)
        sys.exit(2)

    file_path = output_dir / filename

    try:
        file_path.write_text(rendered, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Cannot write plan file '{file_path}': {exc}", file=sys.stderr)
        sys.exit(2)

    return file_path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a sprint plan file from the SPRINT_PLAN.md template.",
    )
    parser.add_argument(
        "--sprint-id",
        required=True,
        help="Sprint identifier, e.g. SP_042",
    )
    parser.add_argument(
        "--goal",
        required=True,
        help="One-line sprint goal text",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory to write the generated plan file",
    )
    parser.add_argument(
        "--template",
        type=Path,
        default=None,
        help="Path to the SPRINT_PLAN.md template (default: framework templates/SPRINT_PLAN.md)",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Resolve template path — defer framework root lookup until it is needed
    # so that import-time env var requirements do not cause test failures.
    if args.template is not None:
        template_path: Path = args.template
    else:
        framework_root = _find_framework_root()
        template_path = framework_root / "templates" / "SPRINT_PLAN.md"

    # Validate template exists early (before any I/O)
    if not template_path.is_file():
        print(
            f"ERROR: Template not found at '{template_path}'. "
            "Pass --template to specify a custom path.",
            file=sys.stderr,
        )
        sys.exit(2)

    file_path = create_plan(
        sprint_id=args.sprint_id,
        goal=args.goal,
        output_dir=args.output_dir,
        template_path=template_path,
    )

    result = {
        "sprint_id": args.sprint_id,
        "file_path": str(file_path),
        "created_at": date.today().isoformat(),
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()

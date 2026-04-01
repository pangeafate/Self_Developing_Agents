#!/usr/bin/env python3
"""update-docs.py — Archive an active sprint into PROGRESS.md Sprint History.

Usage:
    python update-docs.py \\
        --sprint-id SP_042 \\
        --status complete \\
        --summary "Implemented JWT auth with login/logout" \\
        [--tests-added 23] \\
        [--progress-file path/to/PROGRESS.md]

Output (JSON to stdout):
    {"files_updated": ["PROGRESS.md"], "sprint_id": "SP_042", "status": "complete"}

Exit codes:
    0 — updated successfully
    1 — sprint not found in PROGRESS.md, or PROGRESS.md is missing / empty
    2 — fatal I/O error
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


def _find_framework_root() -> Path | None:
    """Locate the SELF_DEVELOPING_AGENTS framework root directory.

    Resolution order:
    1. ``SDA_FRAMEWORK_ROOT`` environment variable (explicit override).
    2. Walk up from this file's directory until a directory containing both
       ``roles/`` and ``practices/`` sub-directories is found.
    3. Return ``None`` if not found (caller must handle).
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

    return None


# Matches validate_sprint.py's _ACTIVE_SPRINT_RE pattern
_ACTIVE_SPRINT_RE = re.compile(r"\*\*Current:\*\*\s+(SP_\S+)")

# Matches the template-style active sprint block (produced by PROGRESS.md template)
# e.g. "- **Sprint**: SP_042: Add User Authentication"
_SPRINT_LINE_RE = re.compile(r"-\s+\*\*Sprint\*\*:\s+(SP_\d+\S*)")


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _find_sprint_id_in_active_section(content: str, sprint_id: str) -> bool:
    """Return True if sprint_id appears anywhere in the Active Sprint section."""
    # Find the Active Sprint section
    active_match = re.search(
        r"^##\s+Active Sprint\s*$(.+?)(?=^##\s|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if not active_match:
        return False

    active_section = active_match.group(1)
    return sprint_id in active_section


def _remove_active_sprint_section_content(content: str, sprint_id: str) -> str:
    """Clear the content of the Active Sprint section (leave the heading).

    Replaces the body of ## Active Sprint (up to the next ## heading) with
    a blank line, effectively leaving the section empty.

    Returns the modified content unchanged if the sprint is not found there.
    """
    # Pattern: "## Active Sprint\n<body>" up to next "## " heading or end
    pattern = re.compile(
        r"(^##\s+Active Sprint\s*\n)(.+?)(?=^##\s|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        return content

    section_body = match.group(2)
    if sprint_id not in section_body:
        return content

    # Replace the section body with a single blank line
    return content[: match.start(2)] + "\n" + content[match.end(2):]


def _build_history_entry(
    sprint_id: str,
    goal: str,
    status: str,
    summary: str,
    today: str,
    tests_added: int | None,
) -> str:
    """Render a Sprint History entry block."""
    status_label = status.capitalize()
    lines = [
        f"### {sprint_id}: {goal}",
        "",
        f"- **Status**: {status_label}",
        f"- **Date**: {today}",
        f"- **Summary**: {summary}",
    ]
    if tests_added is not None:
        lines.append(f"- **Tests added**: +{tests_added} new tests")
    lines.append("")
    return "\n".join(lines)


def _extract_goal_from_active_section(content: str, sprint_id: str) -> str:
    """Try to extract the sprint goal/name from the Active Sprint section.

    Attempts both:
    1. Template format: ``- **Sprint**: SP_042: Sprint Name``
    2. Current format:  ``**Current:** SP_042_Sprint_Name``

    Falls back to an empty string if nothing useful is found.
    """
    active_match = re.search(
        r"^##\s+Active Sprint\s*$(.+?)(?=^##\s|\Z)",
        content,
        re.MULTILINE | re.DOTALL,
    )
    if not active_match:
        return ""

    section = active_match.group(1)

    # Template format: "- **Sprint**: SP_042: Sprint Goal Text"
    sprint_line = re.search(r"-\s+\*\*Sprint\*\*:\s+SP_\d+[_:]?\s*(.*)", section)
    if sprint_line:
        goal_text = sprint_line.group(1).strip()
        # Strip leading colon/space if present
        goal_text = re.sub(r"^[:\s]+", "", goal_text)
        if goal_text:
            return goal_text

    # Current format: "**Current:** SP_042_Some_Goal"
    current_line = _ACTIVE_SPRINT_RE.search(section)
    if current_line:
        slug = current_line.group(1)
        # Remove the sprint ID prefix and convert underscores to spaces
        slug_without_id = re.sub(r"^SP_\d+_?", "", slug)
        return slug_without_id.replace("_", " ").strip()

    return ""


def _prepend_to_history_section(content: str, entry: str) -> str:
    """Insert entry immediately after the ## Sprint History heading."""
    pattern = re.compile(
        r"(^##\s+Sprint History\s*\n)",
        re.MULTILINE,
    )
    match = pattern.search(content)
    if not match:
        # No history section — append it at the end
        return content.rstrip("\n") + "\n\n## Sprint History\n\n" + entry + "\n"

    insert_pos = match.end()
    return content[:insert_pos] + "\n" + entry + "\n" + content[insert_pos:]


# ---------------------------------------------------------------------------
# Main update function
# ---------------------------------------------------------------------------


def update_progress(
    progress_file: Path,
    sprint_id: str,
    status: str,
    summary: str,
    tests_added: int | None,
) -> list[str]:
    """Update PROGRESS.md: archive active sprint, prepend history entry.

    Returns the list of files that were modified.
    Exits with code 1 if sprint not found or file is empty/missing.
    Exits with code 2 on I/O error.
    """
    if not progress_file.is_file():
        print(
            f"ERROR: PROGRESS.md not found at '{progress_file}'",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        content = progress_file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Cannot read '{progress_file}': {exc}", file=sys.stderr)
        sys.exit(2)

    if not content.strip():
        print(
            f"ERROR: '{progress_file}' is empty — no active sprint to archive.",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check that sprint_id appears in the Active Sprint section
    if not _find_sprint_id_in_active_section(content, sprint_id):
        print(
            f"ERROR: Sprint '{sprint_id}' not found in the Active Sprint section "
            f"of '{progress_file}'.",
            file=sys.stderr,
        )
        sys.exit(1)

    today = date.today().isoformat()

    # Extract the goal before we wipe the active section
    goal = _extract_goal_from_active_section(content, sprint_id)
    if not goal:
        goal = sprint_id  # fallback: use sprint ID as goal

    # Remove the sprint from Active Sprint section
    content = _remove_active_sprint_section_content(content, sprint_id)

    # Build and prepend the history entry
    entry = _build_history_entry(sprint_id, goal, status, summary, today, tests_added)
    content = _prepend_to_history_section(content, entry)

    try:
        progress_file.write_text(content, encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: Cannot write '{progress_file}': {exc}", file=sys.stderr)
        sys.exit(2)

    return [str(progress_file.name)]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Archive a completed sprint from PROGRESS.md Active Sprint to History.",
    )
    parser.add_argument(
        "--sprint-id",
        required=True,
        help="Sprint identifier, e.g. SP_042",
    )
    parser.add_argument(
        "--status",
        required=True,
        choices=["complete", "abandoned", "superseded"],
        help="Final sprint status",
    )
    parser.add_argument(
        "--summary",
        required=True,
        help="One-line description of what was delivered",
    )
    parser.add_argument(
        "--progress-file",
        type=Path,
        default=None,
        help="Path to PROGRESS.md (default: auto-detected at framework root)",
    )
    parser.add_argument(
        "--tests-added",
        type=int,
        default=None,
        help="Number of new tests added in this sprint",
    )
    parser.add_argument(
        "--framework-root",
        type=Path,
        default=None,
        help="Path to the Self-Developing Agents framework root (auto-detected if omitted).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # Resolve progress file path — defer framework root lookup until it is needed
    # so that import-time env var requirements do not cause test failures.
    if args.progress_file is not None:
        progress_file: Path = args.progress_file
    elif args.framework_root is not None:
        fw = args.framework_root.resolve()
        if not fw.is_dir():
            print(f"ERROR: --framework-root '{fw}' is not a directory.", file=sys.stderr)
            sys.exit(3)
        progress_file = fw / "PROGRESS.md"
    else:
        framework_root = _find_framework_root()
        if framework_root is None:
            print(
                "ERROR: Could not auto-detect framework root (no ancestor directory "
                "contains both 'roles/' and 'practices/'). "
                "Use --framework-root or set SDA_FRAMEWORK_ROOT.",
                file=sys.stderr,
            )
            sys.exit(3)
        progress_file = framework_root / "PROGRESS.md"

    files_updated = update_progress(
        progress_file=progress_file,
        sprint_id=args.sprint_id,
        status=args.status,
        summary=args.summary,
        tests_added=args.tests_added,
    )

    result = {
        "files_updated": files_updated,
        "sprint_id": args.sprint_id,
        "status": args.status,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()

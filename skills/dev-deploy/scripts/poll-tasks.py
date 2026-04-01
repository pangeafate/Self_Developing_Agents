#!/usr/bin/env python3
"""poll-tasks.py — Scan a task directory for NEW tasks.

Usage:
    python poll-tasks.py --tasks-dir /path/to/tasks/

Output: JSON to stdout:
    {
        "pending_count": <int>,
        "task_ids": [<str>, ...],          # sorted high > medium > low
        "next_task": {                      # highest-priority task, or null
            "id": <str>,
            "title": <str>,
            "priority": <str>,
            "path": <str>
        }
    }

Exit codes:
    0 — success (zero or more pending tasks)
    1 — error reading directory or unexpected exception
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------

_PRIORITY_ORDER: dict[str, int] = {
    "high": 0,
    "medium": 1,
    "low": 2,
}

_DEFAULT_PRIORITY = "medium"


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _extract_bold_field(text: str, field: str) -> str | None:
    """Extract the value after a **Field:** bold label in a markdown file.

    Matches lines of the form:
        **Field:** value
    Returns the stripped value string, or None if not found.
    """
    pattern = rf"\*\*{re.escape(field)}:\*\*\s*(.+)"
    match = re.search(pattern, text)
    if match:
        return match.group(1).strip()
    return None


def _parse_task_file(path: Path) -> dict | None:
    """Parse a task markdown file.

    Returns a dict with keys {id, title, priority, path} if the file has
    **Status:** NEW, otherwise returns None.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    status = _extract_bold_field(text, "Status")
    if status != "NEW":
        return None

    task_id = _extract_bold_field(text, "ID") or path.stem

    # Title: first markdown heading of the form "# Task: <title>"
    title_match = re.search(r"^#\s+Task:\s*(.+)", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem

    priority = _extract_bold_field(text, "Priority") or _DEFAULT_PRIORITY
    priority = priority.lower()
    if priority not in _PRIORITY_ORDER:
        priority = _DEFAULT_PRIORITY

    created = _extract_bold_field(text, "Created") or ""
    timeout = _extract_bold_field(text, "Timeout hours") or ""

    return {
        "id": task_id,
        "file": path.name,
        "title": title,
        "priority": priority,
        "status": "NEW",
        "created": created,
        "timeout_hours": int(timeout) if timeout.isdigit() else 24,
        "path": str(path),
    }


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def scan_tasks(tasks_dir: Path) -> list[dict]:
    """Return a list of NEW tasks sorted by priority (high > medium > low).

    Each item has keys: id, title, priority, path.
    """
    tasks: list[dict] = []
    for md_file in tasks_dir.glob("*.md"):
        task = _parse_task_file(md_file)
        if task is not None:
            tasks.append(task)

    tasks.sort(key=lambda t: _PRIORITY_ORDER.get(t["priority"], 1))
    return tasks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan a task directory for NEW tasks and output JSON."
    )
    parser.add_argument(
        "--tasks-dir",
        required=True,
        type=Path,
        help="Directory to scan for task .md files",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    tasks_dir: Path = args.tasks_dir

    if not tasks_dir.is_dir():
        output = {
            "error": f"tasks-dir does not exist or is not a directory: {tasks_dir}",
            "pending_count": 0,
            "task_ids": [],
            "next_task": None,
        }
        print(json.dumps(output))
        sys.exit(1)

    try:
        tasks = scan_tasks(tasks_dir)
    except Exception as exc:  # pragma: no cover
        output = {
            "error": f"Unexpected error scanning tasks: {exc}",
            "pending_count": 0,
            "task_ids": [],
            "next_task": None,
        }
        print(json.dumps(output))
        sys.exit(1)

    output = {
        "pending_count": len(tasks),
        "task_ids": [t["id"] for t in tasks],
        "next_task": tasks[0] if tasks else None,
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()

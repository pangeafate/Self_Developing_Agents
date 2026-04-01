#!/usr/bin/env python3
"""Tests for poll-tasks.py — task directory scanner.

Uses subprocess to invoke the script so the tests exercise the real CLI
interface (args, exit codes, JSON output) rather than internal functions.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT = Path(__file__).parent / "poll-tasks.py"


def _make_task(
    tmp_path: Path,
    filename: str,
    *,
    task_id: str = "TASK_001",
    title: str = "Test Feature",
    status: str = "NEW",
    priority: str = "medium",
    target_workspace: str = "/tmp/test",
    timeout_hours: str = "24",
    body: str = "Build a test feature",
) -> Path:
    """Write a task markdown file to tmp_path and return the path."""
    content = f"""# Task: {title}

**ID:** {task_id}
**Status:** {status}
**Priority:** {priority}
**Target workspace:** {target_workspace}
**Timeout hours:** {timeout_hours}

## What the Human Asked For
{body}
"""
    p = tmp_path / filename
    p.write_text(content)
    return p


def _run(tasks_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--tasks-dir", str(tasks_dir)],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFindsNewTasks:
    def test_finds_new_tasks(self, tmp_path: Path) -> None:
        _make_task(tmp_path, "TASK_001_feature.md", status="NEW")
        result = _run(tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["pending_count"] == 1
        assert "TASK_001" in data["task_ids"]

    def test_ignores_in_progress_tasks(self, tmp_path: Path) -> None:
        _make_task(tmp_path, "TASK_001_feature.md", status="IN_PROGRESS")
        result = _run(tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["pending_count"] == 0
        assert data["task_ids"] == []

    def test_ignores_delivered_tasks(self, tmp_path: Path) -> None:
        _make_task(tmp_path, "TASK_001_feature.md", status="DELIVERED")
        result = _run(tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["pending_count"] == 0
        assert data["task_ids"] == []

    def test_empty_dir_returns_zero_pending(self, tmp_path: Path) -> None:
        result = _run(tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["pending_count"] == 0
        assert data["task_ids"] == []
        assert data["next_task"] is None


class TestPrioritySorting:
    def test_returns_task_ids_sorted_by_priority(self, tmp_path: Path) -> None:
        _make_task(
            tmp_path,
            "TASK_003_low.md",
            task_id="TASK_003",
            title="Low Task",
            status="NEW",
            priority="low",
        )
        _make_task(
            tmp_path,
            "TASK_001_high.md",
            task_id="TASK_001",
            title="High Task",
            status="NEW",
            priority="high",
        )
        _make_task(
            tmp_path,
            "TASK_002_medium.md",
            task_id="TASK_002",
            title="Medium Task",
            status="NEW",
            priority="medium",
        )
        result = _run(tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["task_ids"] == ["TASK_001", "TASK_002", "TASK_003"]

    def test_returns_next_task_as_highest_priority(self, tmp_path: Path) -> None:
        _make_task(
            tmp_path,
            "TASK_002_medium.md",
            task_id="TASK_002",
            title="Medium Task",
            status="NEW",
            priority="medium",
        )
        _make_task(
            tmp_path,
            "TASK_001_high.md",
            task_id="TASK_001",
            title="High Task",
            status="NEW",
            priority="high",
        )
        result = _run(tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["next_task"] is not None
        assert data["next_task"]["id"] == "TASK_001"
        assert data["next_task"]["priority"] == "high"

    def test_next_task_includes_title_and_path(self, tmp_path: Path) -> None:
        _make_task(
            tmp_path,
            "TASK_001_feature.md",
            task_id="TASK_001",
            title="Build Auth Module",
            status="NEW",
            priority="high",
        )
        result = _run(tmp_path)
        data = json.loads(result.stdout)
        assert data["next_task"]["title"] == "Build Auth Module"
        assert "TASK_001_feature.md" in data["next_task"]["path"]


class TestEdgeCases:
    def test_handles_malformed_task_file(self, tmp_path: Path) -> None:
        """A file with no **Status:** line should be ignored (not crash)."""
        bad = tmp_path / "TASK_bad.md"
        bad.write_text("This file has no status field at all.\n")
        result = _run(tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["pending_count"] == 0

    def test_parses_bold_label_status_format(self, tmp_path: Path) -> None:
        """Specifically verifies **Status:** NEW (bold markdown labels) are parsed."""
        content = "# Task: Bold Label Test\n\n**ID:** TASK_BOLD\n**Status:** NEW\n**Priority:** high\n"
        p = tmp_path / "TASK_bold.md"
        p.write_text(content)
        result = _run(tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["pending_count"] == 1
        assert "TASK_BOLD" in data["task_ids"]

    def test_handles_missing_priority_defaults_to_medium(self, tmp_path: Path) -> None:
        """A task file with no **Priority:** line should default to medium."""
        content = "# Task: No Priority\n\n**ID:** TASK_NOPRI\n**Status:** NEW\n"
        p = tmp_path / "TASK_nopri.md"
        p.write_text(content)
        result = _run(tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["pending_count"] == 1
        assert data["next_task"]["priority"] == "medium"

    def test_output_is_valid_json(self, tmp_path: Path) -> None:
        _make_task(tmp_path, "TASK_001_feature.md", status="NEW")
        result = _run(tmp_path)
        # Must not raise
        parsed = json.loads(result.stdout)
        assert isinstance(parsed, dict)
        # Required top-level keys
        for key in ("pending_count", "task_ids", "next_task"):
            assert key in parsed, f"Missing key: {key}"

    def test_ignores_non_md_files(self, tmp_path: Path) -> None:
        (tmp_path / "README.txt").write_text("**Status:** NEW\n")
        (tmp_path / "notes.json").write_text('{"Status": "NEW"}')
        result = _run(tmp_path)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["pending_count"] == 0

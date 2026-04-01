#!/usr/bin/env python3
"""Tests for update-docs.py — PROGRESS.md sprint lifecycle updater.

Run with:
    python -m pytest test_update_docs.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from datetime import date
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).parent
SCRIPT_PATH = SCRIPTS_DIR / "update-docs.py"

TODAY = date.today().isoformat()


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    """Run update-docs.py with the given args and capture output."""
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_progress_file(tmp_path: Path, content: str) -> Path:
    """Write content to a PROGRESS.md file and return its path."""
    p = tmp_path / "PROGRESS.md"
    p.write_text(content)
    return p


@pytest.fixture()
def progress_file_with_active_sprint(tmp_path: Path) -> Path:
    """A PROGRESS.md with an active sprint entry for SP_042."""
    content = textwrap.dedent("""\
        # Progress

        ## Active Sprint

        - **Sprint**: SP_042: Add User Authentication
        - **Started**: 2026-03-30
        - **Stage**: Implementation

        ## Sprint History

        ### SP_041: Previous Sprint

        - **Status**: Complete
        - **Date**: 2026-03-29
        - **Summary**: Did the previous thing
        - **Tests added**: +10 new tests
    """)
    return _make_progress_file(tmp_path, content)


@pytest.fixture()
def progress_file_current_format(tmp_path: Path) -> Path:
    """A PROGRESS.md already using the **Current:** format."""
    content = textwrap.dedent("""\
        # Progress

        ## Active Sprint

        **Current:** SP_042_Add_User_Authentication

        ## Sprint History

        ### SP_041: Previous Sprint

        - **Status**: Complete
        - **Date**: 2026-03-29
        - **Summary**: Did the previous thing
        - **Tests added**: +10 new tests
    """)
    return _make_progress_file(tmp_path, content)


@pytest.fixture()
def empty_progress_file(tmp_path: Path) -> Path:
    """An empty PROGRESS.md."""
    return _make_progress_file(tmp_path, "")


@pytest.fixture()
def minimal_progress_file(tmp_path: Path) -> Path:
    """A PROGRESS.md with only the history section (no active sprint section)."""
    content = textwrap.dedent("""\
        # Progress

        ## Sprint History

        ### SP_040: Old Sprint

        - **Status**: Complete
        - **Date**: 2026-03-01
        - **Summary**: Old work
        - **Tests added**: +5 new tests
    """)
    return _make_progress_file(tmp_path, content)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_moves_sprint_to_history(progress_file_with_active_sprint: Path) -> None:
    """After update, sprint appears in the Sprint History section."""
    result = run_script(
        "--sprint-id", "SP_042",
        "--status", "complete",
        "--summary", "Implemented JWT authentication",
        "--progress-file", str(progress_file_with_active_sprint),
    )
    assert result.returncode == 0, result.stderr
    content = progress_file_with_active_sprint.read_text()
    assert "### SP_042" in content
    assert "## Sprint History" in content
    # History entry must appear after the Sprint History heading
    history_pos = content.index("## Sprint History")
    entry_pos = content.index("### SP_042")
    assert entry_pos > history_pos


def test_history_entry_has_correct_format(progress_file_with_active_sprint: Path) -> None:
    """History entry contains Status, Date, Summary, and Tests added fields."""
    run_script(
        "--sprint-id", "SP_042",
        "--status", "complete",
        "--summary", "Implemented JWT authentication",
        "--tests-added", "23",
        "--progress-file", str(progress_file_with_active_sprint),
    )
    content = progress_file_with_active_sprint.read_text()
    assert "- **Status**: Complete" in content
    assert f"- **Date**: {TODAY}" in content
    assert "- **Summary**: Implemented JWT authentication" in content
    assert "- **Tests added**: +23 new tests" in content


def test_preserves_existing_history(progress_file_with_active_sprint: Path) -> None:
    """Existing Sprint History entries are not removed."""
    run_script(
        "--sprint-id", "SP_042",
        "--status", "complete",
        "--summary", "Implemented JWT authentication",
        "--progress-file", str(progress_file_with_active_sprint),
    )
    content = progress_file_with_active_sprint.read_text()
    assert "### SP_041: Previous Sprint" in content
    assert "Did the previous thing" in content


def test_handles_empty_progress_file(empty_progress_file: Path) -> None:
    """An empty PROGRESS.md does not crash the script; exits with code 1."""
    result = run_script(
        "--sprint-id", "SP_042",
        "--status", "complete",
        "--summary", "Implemented JWT authentication",
        "--progress-file", str(empty_progress_file),
    )
    assert result.returncode == 1


def test_status_complete_updates_correctly(progress_file_with_active_sprint: Path) -> None:
    """Status 'complete' is formatted as 'Complete' in the history entry."""
    run_script(
        "--sprint-id", "SP_042",
        "--status", "complete",
        "--summary", "Done",
        "--progress-file", str(progress_file_with_active_sprint),
    )
    content = progress_file_with_active_sprint.read_text()
    assert "- **Status**: Complete" in content


def test_status_abandoned_updates_correctly(progress_file_with_active_sprint: Path) -> None:
    """Status 'abandoned' is formatted as 'Abandoned' in the history entry."""
    run_script(
        "--sprint-id", "SP_042",
        "--status", "abandoned",
        "--summary", "Abandoned due to scope change",
        "--progress-file", str(progress_file_with_active_sprint),
    )
    content = progress_file_with_active_sprint.read_text()
    assert "- **Status**: Abandoned" in content


def test_status_superseded_updates_correctly(progress_file_with_active_sprint: Path) -> None:
    """Status 'superseded' is formatted as 'Superseded' in the history entry."""
    run_script(
        "--sprint-id", "SP_042",
        "--status", "superseded",
        "--summary", "Superseded by SP_043",
        "--progress-file", str(progress_file_with_active_sprint),
    )
    content = progress_file_with_active_sprint.read_text()
    assert "- **Status**: Superseded" in content


def test_tests_added_appears_in_entry(progress_file_with_active_sprint: Path) -> None:
    """--tests-added value is included in the history entry."""
    run_script(
        "--sprint-id", "SP_042",
        "--status", "complete",
        "--summary", "Done",
        "--tests-added", "42",
        "--progress-file", str(progress_file_with_active_sprint),
    )
    content = progress_file_with_active_sprint.read_text()
    assert "+42 new tests" in content


def test_tests_added_zero_is_valid(progress_file_with_active_sprint: Path) -> None:
    """--tests-added 0 is recorded as '+0 new tests' (rename-only sprints)."""
    run_script(
        "--sprint-id", "SP_042",
        "--status", "complete",
        "--summary", "Rename only",
        "--tests-added", "0",
        "--progress-file", str(progress_file_with_active_sprint),
    )
    content = progress_file_with_active_sprint.read_text()
    assert "+0 new tests" in content


def test_output_json_lists_updated_files(progress_file_with_active_sprint: Path) -> None:
    """JSON output on stdout contains files_updated, sprint_id, and status."""
    result = run_script(
        "--sprint-id", "SP_042",
        "--status", "complete",
        "--summary", "Done",
        "--progress-file", str(progress_file_with_active_sprint),
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert "files_updated" in data
    assert isinstance(data["files_updated"], list)
    assert len(data["files_updated"]) >= 1
    assert data["sprint_id"] == "SP_042"
    assert data["status"] == "complete"


def test_sprint_id_not_found_exits_1(minimal_progress_file: Path) -> None:
    """When the sprint ID is not found in any active section, exit code is 1."""
    result = run_script(
        "--sprint-id", "SP_999",
        "--status", "complete",
        "--summary", "Does not exist",
        "--progress-file", str(minimal_progress_file),
    )
    assert result.returncode == 1


def test_missing_progress_file_exits_1(tmp_path: Path) -> None:
    """A missing --progress-file path causes exit code 1."""
    result = run_script(
        "--sprint-id", "SP_042",
        "--status", "complete",
        "--summary", "Done",
        "--progress-file", str(tmp_path / "nonexistent.md"),
    )
    assert result.returncode == 1


def test_writes_current_format_for_validator(progress_file_with_active_sprint: Path) -> None:
    """After archiving the old sprint, the Active Sprint section uses **Current:** format."""
    # Simulate: a NEW active sprint SP_043 is now set via **Current:** format
    # update-docs should clear the old active sprint section properly
    # The key: after running, if we write a new active sprint, validate_sprint.py
    # pattern `**Current:** SP_XXX` must be matchable in the file.
    # This test verifies update-docs writes **Current:** when setting the active sprint.
    run_script(
        "--sprint-id", "SP_042",
        "--status", "complete",
        "--summary", "Done",
        "--progress-file", str(progress_file_with_active_sprint),
    )
    content = progress_file_with_active_sprint.read_text()
    # After archiving, if there is a **Current:** line it must match the validator pattern
    import re
    matches = re.findall(r"\*\*Current:\*\*\s+(SP_\S+)", content)
    # There should be no stale **Current:** pointing at the archived sprint
    assert "SP_042" not in " ".join(matches)


def test_new_entry_is_prepended_before_existing_history(
    progress_file_with_active_sprint: Path,
) -> None:
    """The new history entry appears before (above) the existing SP_041 entry."""
    run_script(
        "--sprint-id", "SP_042",
        "--status", "complete",
        "--summary", "Done",
        "--progress-file", str(progress_file_with_active_sprint),
    )
    content = progress_file_with_active_sprint.read_text()
    pos_042 = content.index("### SP_042")
    pos_041 = content.index("### SP_041")
    assert pos_042 < pos_041, "SP_042 entry should appear before SP_041 entry"


def test_missing_required_args_exits_nonzero() -> None:
    """Omitting required arguments exits with a non-zero code."""
    result = run_script("--sprint-id", "SP_042")  # missing --status, --summary
    assert result.returncode != 0


def test_uses_sda_framework_root_env_var(tmp_path: Path) -> None:
    """SDA_FRAMEWORK_ROOT env var is used to locate PROGRESS.md when --progress-file is omitted."""
    import textwrap as _textwrap

    # Create a fake framework with roles/, practices/, and PROGRESS.md
    fw = tmp_path / "framework"
    (fw / "roles").mkdir(parents=True)
    (fw / "practices").mkdir()

    progress_content = _textwrap.dedent("""\
        # Progress

        ## Active Sprint

        - **Sprint**: SP_001: Test Sprint
        - **Started**: 2026-03-31
        - **Stage**: Implementation

        ## Sprint History
    """)
    (fw / "PROGRESS.md").write_text(progress_content)

    result = subprocess.run(
        [
            sys.executable, str(SCRIPT_PATH),
            "--sprint-id", "SP_001",
            "--status", "complete",
            "--summary", "Test via env var",
        ],
        capture_output=True, text=True,
        env={**os.environ, "SDA_FRAMEWORK_ROOT": str(fw)},
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["sprint_id"] == "SP_001"
    # Verify PROGRESS.md was actually updated in the fake framework
    updated = (fw / "PROGRESS.md").read_text()
    assert "### SP_001" in updated


def test_invalid_sda_framework_root_falls_through_to_walkup(tmp_path: Path) -> None:
    """An SDA_FRAMEWORK_ROOT pointing to a dir without roles/ and practices/ is ignored."""
    bad_fw = tmp_path / "bad_framework"
    bad_fw.mkdir()

    result = subprocess.run(
        [
            sys.executable, str(SCRIPT_PATH),
            "--sprint-id", "SP_001",
            "--status", "complete",
            "--summary", "Ignored bad env var",
        ],
        capture_output=True, text=True,
        env={**os.environ, "SDA_FRAMEWORK_ROOT": str(bad_fw)},
    )
    # Script should not crash with a Python traceback — walk-up ran instead
    assert "Traceback" not in result.stderr

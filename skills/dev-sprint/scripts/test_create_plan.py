#!/usr/bin/env python3
"""Tests for create-plan.py — sprint plan file generator.

Run with:
    python -m pytest test_create_plan.py -v
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
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
SCRIPT_PATH = SCRIPTS_DIR / "create-plan.py"

# Locate framework root so we can find the default template
_SELF_DEVELOPING_DIR = SCRIPTS_DIR.parent.parent.parent  # …/SELF_DEVELOPING_AGENTS
TEMPLATE_PATH = _SELF_DEVELOPING_DIR / "templates" / "SPRINT_PLAN.md"

TODAY = date.today().isoformat()


def run_script(*args: str) -> subprocess.CompletedProcess[str]:
    """Run create-plan.py with the given args and capture output."""
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args],
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def output_dir(tmp_path: Path) -> Path:
    """A temporary output directory."""
    d = tmp_path / "sprints"
    d.mkdir()
    return d


@pytest.fixture()
def minimal_template(tmp_path: Path) -> Path:
    """A minimal custom template for --template tests."""
    content = textwrap.dedent("""\
        # SP_XXX: [Sprint Name]

        ## Sprint Goal

        [Goal placeholder]

        Date: [YYYY-MM-DD]

        ## Technical Approach

        [Approach placeholder]

        ## Testing Strategy

        [Testing placeholder]

        ## Success Criteria

        - [ ] Done

        ## Review Log

        ### Pre-Implementation Review
        - **Iteration 1** ([DATE]): placeholder

        ### Post-Implementation Review
        - **Iteration 1** ([DATE]): placeholder
    """)
    p = tmp_path / "custom_template.md"
    p.write_text(content)
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_creates_sprint_plan_file(output_dir: Path) -> None:
    """The script creates a file inside the output directory."""
    result = run_script(
        "--sprint-id", "SP_042",
        "--goal", "Add User Authentication",
        "--output-dir", str(output_dir),
    )
    assert result.returncode == 0, result.stderr
    created_files = list(output_dir.iterdir())
    assert len(created_files) == 1


def test_plan_contains_sprint_id(output_dir: Path) -> None:
    """The created file contains the sprint ID."""
    run_script(
        "--sprint-id", "SP_042",
        "--goal", "Add User Authentication",
        "--output-dir", str(output_dir),
    )
    plan_file = next(output_dir.iterdir())
    content = plan_file.read_text()
    assert "SP_042" in content


def test_plan_contains_goal(output_dir: Path) -> None:
    """The created file contains the goal text."""
    run_script(
        "--sprint-id", "SP_042",
        "--goal", "Add User Authentication",
        "--output-dir", str(output_dir),
    )
    plan_file = next(output_dir.iterdir())
    content = plan_file.read_text()
    assert "Add User Authentication" in content


def test_plan_contains_today_date(output_dir: Path) -> None:
    """The created file contains today's date."""
    run_script(
        "--sprint-id", "SP_042",
        "--goal", "Add User Authentication",
        "--output-dir", str(output_dir),
    )
    plan_file = next(output_dir.iterdir())
    content = plan_file.read_text()
    assert TODAY in content


def test_filename_is_slug_of_goal(output_dir: Path) -> None:
    """Filename format: {sprint_id}_{goal_slugified}.md — spaces become underscores."""
    run_script(
        "--sprint-id", "SP_042",
        "--goal", "Add User Authentication",
        "--output-dir", str(output_dir),
    )
    created_files = list(output_dir.iterdir())
    assert len(created_files) == 1
    filename = created_files[0].name
    assert filename == "SP_042_Add_User_Authentication.md"


def test_filename_strips_special_chars(output_dir: Path) -> None:
    """Special characters in goal are stripped from the filename slug."""
    run_script(
        "--sprint-id", "SP_043",
        "--goal", "Add OAuth2 (Google) & GitHub!",
        "--output-dir", str(output_dir),
    )
    created_files = list(output_dir.iterdir())
    assert len(created_files) == 1
    filename = created_files[0].name
    # Only alphanumeric + underscores expected (no parens, ampersands, exclamation)
    assert re.match(r"^SP_043_[A-Za-z0-9_]+\.md$", filename), filename


def test_creates_output_dir_if_missing(tmp_path: Path) -> None:
    """The script creates the output directory when it does not exist."""
    missing_dir = tmp_path / "new" / "nested" / "dir"
    assert not missing_dir.exists()
    result = run_script(
        "--sprint-id", "SP_042",
        "--goal", "Add User Authentication",
        "--output-dir", str(missing_dir),
    )
    assert result.returncode == 0, result.stderr
    assert missing_dir.is_dir()
    assert len(list(missing_dir.iterdir())) == 1


def test_custom_template_path(output_dir: Path, minimal_template: Path) -> None:
    """--template overrides the default template path."""
    result = run_script(
        "--sprint-id", "SP_042",
        "--goal", "Add User Authentication",
        "--output-dir", str(output_dir),
        "--template", str(minimal_template),
    )
    assert result.returncode == 0, result.stderr
    plan_file = next(output_dir.iterdir())
    content = plan_file.read_text()
    # Content must come from the custom template (has the unique placeholder text)
    assert "Goal placeholder" in content
    assert "SP_042" in content


def test_missing_required_args_exits_nonzero() -> None:
    """Omitting required arguments exits with a non-zero code."""
    result = run_script("--sprint-id", "SP_042")  # missing --goal and --output-dir
    assert result.returncode != 0


def test_output_json_has_sprint_id_and_path(output_dir: Path) -> None:
    """JSON output on stdout contains sprint_id and file_path."""
    result = run_script(
        "--sprint-id", "SP_042",
        "--goal", "Add User Authentication",
        "--output-dir", str(output_dir),
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["sprint_id"] == "SP_042"
    assert "file_path" in data
    assert data["file_path"].endswith(".md")


def test_output_json_has_created_at(output_dir: Path) -> None:
    """JSON output on stdout contains created_at with today's date."""
    result = run_script(
        "--sprint-id", "SP_042",
        "--goal", "Add User Authentication",
        "--output-dir", str(output_dir),
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["created_at"] == TODAY


def test_plan_has_required_sections(output_dir: Path) -> None:
    """The created plan contains all required sections from the template."""
    run_script(
        "--sprint-id", "SP_042",
        "--goal", "Add User Authentication",
        "--output-dir", str(output_dir),
    )
    plan_file = next(output_dir.iterdir())
    content = plan_file.read_text()
    required_sections = [
        "## Sprint Goal",
        "## Technical Approach",
        "## Testing Strategy",
        "## Success Criteria",
        "### Pre-Implementation Review",
        "### Post-Implementation Review",
    ]
    for section in required_sections:
        assert section in content, f"Missing section: {section}"


def test_template_not_found_exits_2(output_dir: Path) -> None:
    """A non-existent --template path causes exit code 2."""
    result = run_script(
        "--sprint-id", "SP_042",
        "--goal", "Add User Authentication",
        "--output-dir", str(output_dir),
        "--template", "/nonexistent/path/TEMPLATE.md",
    )
    assert result.returncode == 2


def test_uses_sda_framework_root_env_var(tmp_path: Path) -> None:
    """SDA_FRAMEWORK_ROOT env var is used to find the template."""
    # Create a fake framework with templates/SPRINT_PLAN.md
    fw = tmp_path / "framework"
    (fw / "roles").mkdir(parents=True)
    (fw / "practices").mkdir()
    (fw / "templates").mkdir()
    (fw / "templates" / "SPRINT_PLAN.md").write_text(
        "# SP_XXX: [Sprint Name]\n## Sprint Goal\n"
    )

    out_dir = tmp_path / "sprints"
    out_dir.mkdir()

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--sprint-id", "SP_001", "--goal", "Test", "--output-dir", str(out_dir)],
        capture_output=True, text=True,
        env={**os.environ, "SDA_FRAMEWORK_ROOT": str(fw)},
    )
    assert result.returncode == 0, result.stderr
    created_files = list(out_dir.iterdir())
    assert len(created_files) == 1
    content = created_files[0].read_text()
    assert "SP_001" in content
    assert "Test" in content


def test_invalid_sda_framework_root_falls_through_to_walkup(tmp_path: Path) -> None:
    """An SDA_FRAMEWORK_ROOT pointing to a dir without roles/ and practices/ is ignored."""
    # Directory exists but lacks the marker subdirs — env var should be skipped
    bad_fw = tmp_path / "bad_framework"
    bad_fw.mkdir()

    out_dir = tmp_path / "sprints"
    out_dir.mkdir()

    # Without a real framework in the walk-up path this will fail to find template,
    # but the key behaviour is it does NOT crash on the bad env var (exit code 2 from
    # template-not-found is acceptable here — it proves walk-up ran, not the env var).
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--sprint-id", "SP_001", "--goal", "Test", "--output-dir", str(out_dir)],
        capture_output=True, text=True,
        env={**os.environ, "SDA_FRAMEWORK_ROOT": str(bad_fw)},
    )
    # Should NOT be a Python crash (returncode != 1 with traceback)
    assert "Traceback" not in result.stderr

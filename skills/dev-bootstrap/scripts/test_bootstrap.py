#!/usr/bin/env python3
"""Tests for bootstrap.py — Day 1 workspace setup automation.

Run:
    python -m pytest HOW_ITS_DONE/SELF_DEVELOPING_AGENTS/skills/dev-bootstrap/scripts/test_bootstrap.py -v
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BOOTSTRAP_SCRIPT = (
    Path(__file__).parent / "bootstrap.py"
)


def make_fake_framework(tmp_path: Path) -> Path:
    """Create a minimal but structurally complete fake framework root."""
    fw = tmp_path / "framework"
    # templates/ — three .md files (the real one has 13)
    (fw / "templates").mkdir(parents=True)
    (fw / "templates" / "PROJECT_CONTEXT.md").write_text("# Context\n")
    (fw / "templates" / "ARCHITECTURE.md").write_text("# Arch\n")
    (fw / "templates" / "PROGRESS.md").write_text("# Progress\n")
    # practices/ — one GL-*.md file
    (fw / "practices").mkdir()
    (fw / "practices" / "GL-TDD.md").write_text("# TDD\n")
    # validators/ — a trivially passing run_all.py
    (fw / "validators").mkdir()
    (fw / "validators" / "run_all.py").write_text(
        "import sys\nsys.exit(0)\n"
    )
    # workspace-template files for the skill
    (fw / "skills" / "dev-bootstrap" / "templates").mkdir(parents=True)
    (fw / "skills" / "dev-bootstrap" / "templates" / "AGENTS.md").write_text("# Agents\n")
    (fw / "skills" / "dev-bootstrap" / "templates" / "HEARTBEAT.md").write_text("# HB\n")
    (fw / "skills" / "dev-bootstrap" / "templates" / "MEMORY.md").write_text("# Mem\n")
    # roles/ — required for framework-root auto-detection heuristic
    (fw / "roles").mkdir()
    return fw


def run_bootstrap(
    *,
    action: str,
    project_root: Path,
    framework_root: Path | None = None,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run bootstrap.py as a subprocess and return the result."""
    cmd = [
        sys.executable,
        str(BOOTSTRAP_SCRIPT),
        "--action", action,
        "--project-root", str(project_root),
    ]
    if framework_root is not None:
        cmd += ["--framework-root", str(framework_root)]
    if extra_args:
        cmd += extra_args
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Setup action — directory creation
# ---------------------------------------------------------------------------


def test_setup_creates_workspace_directory(tmp_path):
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    run_bootstrap(action="setup", project_root=project, framework_root=fw)

    assert (project / "workspace").is_dir()


def test_setup_creates_test_directories(tmp_path):
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    run_bootstrap(action="setup", project_root=project, framework_root=fw)

    assert (project / "test" / "unit").is_dir()
    assert (project / "test" / "integration").is_dir()
    assert (project / "test" / "fixtures").is_dir()


def test_setup_creates_sprints_directory(tmp_path):
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    run_bootstrap(action="setup", project_root=project, framework_root=fw)

    assert (project / "workspace" / "sprints").is_dir()


# ---------------------------------------------------------------------------
# Setup action — file copying
# ---------------------------------------------------------------------------


def test_setup_copies_template_files(tmp_path):
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    run_bootstrap(action="setup", project_root=project, framework_root=fw)

    # All three template files from our fake framework must be copied
    assert (project / "workspace" / "PROJECT_CONTEXT.md").is_file()
    assert (project / "workspace" / "ARCHITECTURE.md").is_file()
    assert (project / "workspace" / "PROGRESS.md").is_file()


def test_setup_copies_practice_files(tmp_path):
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    run_bootstrap(action="setup", project_root=project, framework_root=fw)

    assert (project / "workspace" / "GL-TDD.md").is_file()


def test_setup_copies_validators(tmp_path):
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    run_bootstrap(action="setup", project_root=project, framework_root=fw)

    assert (project / "validators").is_dir()
    assert (project / "validators" / "run_all.py").is_file()


def test_setup_copies_workspace_templates(tmp_path):
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    run_bootstrap(action="setup", project_root=project, framework_root=fw)

    assert (project / "workspace" / "AGENTS.md").is_file()
    assert (project / "workspace" / "HEARTBEAT.md").is_file()
    assert (project / "workspace" / "MEMORY.md").is_file()


# ---------------------------------------------------------------------------
# Setup action — JSON output and exit codes
# ---------------------------------------------------------------------------


def test_setup_outputs_valid_json(tmp_path):
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    result = run_bootstrap(
        action="setup",
        project_root=project,
        framework_root=fw,
        extra_args=["--skip-validation"],
    )

    data = json.loads(result.stdout)
    assert "status" in data
    assert "dirs_created" in data
    assert "files_copied" in data
    assert "validation_result" in data
    assert isinstance(data["dirs_created"], list)
    assert isinstance(data["files_copied"], int)


def test_setup_idempotent(tmp_path):
    """Running setup twice must not raise an exception or produce exit code 2."""
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    run_bootstrap(action="setup", project_root=project, framework_root=fw, extra_args=["--skip-validation"])
    result = run_bootstrap(action="setup", project_root=project, framework_root=fw, extra_args=["--skip-validation"])

    assert result.returncode != 2


def test_setup_exit_0_on_success(tmp_path):
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    result = run_bootstrap(
        action="setup",
        project_root=project,
        framework_root=fw,
        extra_args=["--skip-validation"],
    )

    assert result.returncode == 0


# ---------------------------------------------------------------------------
# Verify action
# ---------------------------------------------------------------------------


def test_verify_passes_on_complete_setup(tmp_path):
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    # First do a full setup
    run_bootstrap(action="setup", project_root=project, framework_root=fw, extra_args=["--skip-validation"])

    # Then verify — should exit 0
    result = run_bootstrap(action="verify", project_root=project, framework_root=fw)

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["status"] == "ok"
    assert data["missing"] == []


def test_verify_fails_on_missing_dirs(tmp_path):
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()
    # Deliberately empty project — no workspace, no tests, no validators

    result = run_bootstrap(action="verify", project_root=project, framework_root=fw)

    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["status"] == "incomplete"
    assert len(data["missing"]) > 0


# ---------------------------------------------------------------------------
# Flags and special cases
# ---------------------------------------------------------------------------


def test_skip_validation_flag_works(tmp_path):
    """--skip-validation must set validation_result to 'skipped' and exit 0."""
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    result = run_bootstrap(
        action="setup",
        project_root=project,
        framework_root=fw,
        extra_args=["--skip-validation"],
    )

    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["validation_result"] == "skipped"


def test_exit_3_when_framework_not_found(tmp_path):
    """Passing a nonexistent --framework-root must exit with code 3."""
    project = tmp_path / "project"
    project.mkdir()
    nonexistent = tmp_path / "does_not_exist"

    result = run_bootstrap(
        action="setup",
        project_root=project,
        framework_root=nonexistent,
    )

    assert result.returncode == 3


def test_gitignore_includes_pre_impl_passed(tmp_path):
    """The generated .gitignore must contain .pre_impl_passed."""
    fw = make_fake_framework(tmp_path)
    project = tmp_path / "project"
    project.mkdir()

    run_bootstrap(
        action="setup",
        project_root=project,
        framework_root=fw,
        extra_args=["--skip-validation"],
    )

    gitignore = project / ".gitignore"
    assert gitignore.exists(), ".gitignore was not created by setup"
    content = gitignore.read_text()
    assert ".pre_impl_passed" in content, (
        f".pre_impl_passed not found in .gitignore:\n{content}"
    )

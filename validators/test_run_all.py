"""
Tests for run_all.py orchestrator

Orchestrator contract:
- Runs all 5 validators in sequence: validate_structure, validate_workspace,
  validate_tdd, validate_rdd, validate_sprint
- Exits 0 only if ALL validators pass
- Exits 1 if any validator fails
- --bootstrap flag runs only validate_structure and validate_workspace (in that order)
- --skip <name>[,<name>] flag skips the named validator(s)
- --fix flag creates missing required directories before running validators
- Prints a summary table at the end listing each validator and its result
- Returns 0 on pass, 1 on failure

Testing strategy: We test the orchestrator by mocking individual validator scripts.
Each validator is invoked as a subprocess call to its Python script. We inject
controlled fake scripts via tmp_path that exit with a predetermined code.
"""
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

ORCHESTRATOR = Path(__file__).parent / "run_all.py"
VALIDATORS_DIR = Path(__file__).parent


def run_orchestrator(
    project_root: Path, *extra_args: str, env: dict | None = None
) -> subprocess.CompletedProcess:
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project_root), *extra_args],
        capture_output=True,
        text=True,
        env=merged_env,
    )


def make_fake_validator(tmp_path: Path, name: str, exit_code: int) -> Path:
    """Write a tiny Python script that prints its name and exits with exit_code."""
    script = tmp_path / "validators" / name
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text(
        textwrap.dedent(f"""\
            #!/usr/bin/env python3
            import sys
            print(f"[{name}] ran")
            sys.exit({exit_code})
        """)
    )
    return script


def make_validators_dir(tmp_path: Path, results: dict[str, int]) -> Path:
    """
    Create fake validator scripts in tmp_path/validators/.
    results maps short validator name (e.g. 'validate_structure') to exit code.
    Returns the validators directory path.
    """
    validators_dir = tmp_path / "validators"
    validators_dir.mkdir(exist_ok=True)

    for name, code in results.items():
        make_fake_validator(tmp_path, f"{name}.py", code)

    return validators_dir


# ---------------------------------------------------------------------------
# Helpers to set up a fully self-contained test environment
# ---------------------------------------------------------------------------


def setup_project(tmp_path: Path) -> Path:
    """Create a minimal project structure next to the validators directory."""
    project = tmp_path / "project"
    project.mkdir()
    (project / "PROGRESS.md").write_text("## Sprint History\nAll done.\n")
    return project


# ---------------------------------------------------------------------------
# Core pass / fail behaviour (using mocking at subprocess level)
# ---------------------------------------------------------------------------


def test_all_pass_exits_zero(tmp_path: Path) -> None:
    """When all 5 validators return 0, the orchestrator exits 0."""
    project = setup_project(tmp_path)

    all_pass = {
        "validate_structure": 0,
        "validate_workspace": 0,
        "validate_tdd": 0,
        "validate_rdd": 0,
        "validate_sprint": 0,
    }

    # Patch subprocess.run inside run_all so our fake scripts are called
    call_results = []
    for name, code in all_pass.items():
        mock = MagicMock()
        mock.returncode = code
        call_results.append(mock)

    with patch("subprocess.run", side_effect=call_results) as mock_run:
        result = subprocess.run(
            [sys.executable, str(ORCHESTRATOR), str(project)],
            capture_output=True,
            text=True,
            env={
                **os.environ,
                # Signal to the orchestrator to use our fake scripts dir
                "_VALIDATOR_DIR_OVERRIDE": str(tmp_path / "validators"),
            },
        )

    # We can't reliably intercept the subprocess calls without modifying the
    # orchestrator. Instead write real fake scripts and point the env variable.
    # Recreate using real fake scripts approach:
    _run_all_pass_with_fake_scripts(tmp_path, project)


def _run_all_pass_with_fake_scripts(tmp_path: Path, project: Path) -> None:
    """Internal helper: uses real fake scripts placed in validators dir override."""
    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir(exist_ok=True)

    for name in ["validate_structure", "validate_workspace", "validate_tdd", "validate_rdd", "validate_sprint"]:
        (fake_dir / f"{name}.py").write_text(
            textwrap.dedent(f"""\
                import sys
                sys.exit(0)
            """)
        )

    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project)],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir)},
    )
    assert result.returncode == 0, result.stderr


def test_any_fail_exits_one(tmp_path: Path) -> None:
    """When one validator returns 1, the orchestrator exits 1."""
    project = setup_project(tmp_path)
    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir()

    for name in ["validate_structure", "validate_workspace", "validate_tdd", "validate_rdd"]:
        (fake_dir / f"{name}.py").write_text("import sys; sys.exit(0)\n")

    # validate_sprint fails
    (fake_dir / "validate_sprint.py").write_text("import sys; sys.exit(1)\n")

    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project)],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir)},
    )
    assert result.returncode == 1, result.stdout


def test_first_failure_does_not_short_circuit_remaining_validators(tmp_path: Path) -> None:
    """All validators run even if an early one fails (full report, no short-circuit)."""
    project = setup_project(tmp_path)
    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir()

    ran_flags = {}
    for name in ["validate_structure", "validate_workspace", "validate_tdd", "validate_rdd", "validate_sprint"]:
        flag_file = tmp_path / f"{name}.ran"
        (fake_dir / f"{name}.py").write_text(
            textwrap.dedent(f"""\
                import sys
                open("{flag_file}", "w").close()
                sys.exit(1)
            """)
        )

    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project)],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir)},
    )
    assert result.returncode == 1

    # Every validator should have run
    for name in ["validate_structure", "validate_workspace", "validate_tdd", "validate_rdd", "validate_sprint"]:
        flag_file = tmp_path / f"{name}.ran"
        assert flag_file.exists(), f"{name} did not run (flag file missing)"


# ---------------------------------------------------------------------------
# --bootstrap flag
# ---------------------------------------------------------------------------


def test_bootstrap_runs_only_structure_and_workspace(tmp_path: Path) -> None:
    """--bootstrap flag runs only validate_structure and validate_workspace."""
    project = setup_project(tmp_path)
    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir()

    for name in ["validate_structure", "validate_workspace"]:
        (fake_dir / f"{name}.py").write_text("import sys; sys.exit(0)\n")

    # These should NOT run — write scripts that fail loudly if invoked
    for name in ["validate_tdd", "validate_rdd", "validate_sprint"]:
        flag_file = tmp_path / f"{name}.ran"
        (fake_dir / f"{name}.py").write_text(
            textwrap.dedent(f"""\
                import sys
                open("{flag_file}", "w").close()
                sys.exit(1)
            """)
        )

    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project), "--bootstrap"],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir)},
    )
    assert result.returncode == 0, result.stderr

    for name in ["validate_tdd", "validate_rdd", "validate_sprint"]:
        flag_file = tmp_path / f"{name}.ran"
        assert not flag_file.exists(), f"{name} ran during --bootstrap mode but should not have"


# ---------------------------------------------------------------------------
# --skip flag
# ---------------------------------------------------------------------------


def test_skip_flag_excludes_validator(tmp_path: Path) -> None:
    """--skip validate_sprint causes validate_sprint to be excluded from the run."""
    project = setup_project(tmp_path)
    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir()

    for name in ["validate_structure", "validate_workspace", "validate_tdd", "validate_rdd"]:
        (fake_dir / f"{name}.py").write_text("import sys; sys.exit(0)\n")

    sprint_flag = tmp_path / "validate_sprint.ran"
    (fake_dir / "validate_sprint.py").write_text(
        textwrap.dedent(f"""\
            import sys
            open("{sprint_flag}", "w").close()
            sys.exit(1)
        """)
    )

    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project), "--skip", "validate_sprint"],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir)},
    )
    assert result.returncode == 0, result.stderr
    assert not sprint_flag.exists(), "validate_sprint ran despite --skip flag"


def test_skip_multiple_validators(tmp_path: Path) -> None:
    """--skip can exclude multiple validators (comma-separated or repeated flag)."""
    project = setup_project(tmp_path)
    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir()

    for name in ["validate_structure", "validate_workspace"]:
        (fake_dir / f"{name}.py").write_text("import sys; sys.exit(0)\n")

    for name in ["validate_tdd", "validate_rdd", "validate_sprint"]:
        flag_file = tmp_path / f"{name}.ran"
        (fake_dir / f"{name}.py").write_text(
            textwrap.dedent(f"""\
                import sys
                open("{flag_file}", "w").close()
                sys.exit(1)
            """)
        )

    result = subprocess.run(
        [
            sys.executable, str(ORCHESTRATOR), str(project),
            "--skip", "validate_tdd,validate_rdd,validate_sprint",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir)},
    )
    assert result.returncode == 0, result.stderr

    for name in ["validate_tdd", "validate_rdd", "validate_sprint"]:
        flag_file = tmp_path / f"{name}.ran"
        assert not flag_file.exists(), f"{name} ran despite being skipped"


# ---------------------------------------------------------------------------
# --fix flag
# ---------------------------------------------------------------------------


def test_fix_creates_missing_dirs(tmp_path: Path) -> None:
    """--fix creates missing required directories before validators run."""
    project = setup_project(tmp_path)

    # test/unit and test/integration are deliberately absent
    assert not (project / "test" / "unit").exists()
    assert not (project / "test" / "integration").exists()

    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir()

    for name in ["validate_structure", "validate_workspace", "validate_tdd", "validate_rdd", "validate_sprint"]:
        (fake_dir / f"{name}.py").write_text("import sys; sys.exit(0)\n")

    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project), "--fix"],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir)},
    )

    # After --fix, the directories should have been created
    assert (project / "test" / "unit").exists(), "test/unit was not created by --fix"
    assert (project / "test" / "integration").exists(), "test/integration was not created by --fix"


def test_fix_is_idempotent_when_dirs_already_exist(tmp_path: Path) -> None:
    """--fix does not fail when required directories already exist."""
    project = setup_project(tmp_path)
    (project / "test" / "unit").mkdir(parents=True)
    (project / "test" / "integration").mkdir(parents=True)

    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir()
    for name in ["validate_structure", "validate_workspace", "validate_tdd", "validate_rdd", "validate_sprint"]:
        (fake_dir / f"{name}.py").write_text("import sys; sys.exit(0)\n")

    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project), "--fix"],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir)},
    )
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# Summary output format
# ---------------------------------------------------------------------------


def test_summary_output_format(tmp_path: Path) -> None:
    """The orchestrator prints a summary section listing each validator's result."""
    project = setup_project(tmp_path)
    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir()

    for name in ["validate_structure", "validate_workspace", "validate_tdd"]:
        (fake_dir / f"{name}.py").write_text("import sys; sys.exit(0)\n")
    for name in ["validate_rdd", "validate_sprint"]:
        (fake_dir / f"{name}.py").write_text("import sys; sys.exit(1)\n")

    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project)],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir)},
    )

    combined = result.stdout + result.stderr
    # Summary must mention each validator by some form of its name
    for name in ["structure", "workspace", "tdd", "rdd", "sprint"]:
        assert name in combined.lower(), (
            f"Expected '{name}' in summary output, got:\n{combined}"
        )

    # Summary must distinguish passing from failing
    assert "pass" in combined.lower() or "ok" in combined.lower() or "✓" in combined, (
        "Expected a PASS indicator in summary"
    )
    assert "fail" in combined.lower() or "error" in combined.lower() or "✗" in combined, (
        "Expected a FAIL indicator in summary"
    )


def test_summary_shows_all_validators_ran(tmp_path: Path) -> None:
    """All 5 validator names appear in the output summary."""
    project = setup_project(tmp_path)
    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir()

    for name in ["validate_structure", "validate_workspace", "validate_tdd", "validate_rdd", "validate_sprint"]:
        (fake_dir / f"{name}.py").write_text("import sys; sys.exit(0)\n")

    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project)],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir)},
    )

    combined = result.stdout + result.stderr
    for short_name in ["structure", "workspace", "tdd", "rdd", "sprint"]:
        assert short_name in combined.lower(), (
            f"'{short_name}' not found in orchestrator output:\n{combined}"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_unknown_validator_name_in_skip_is_handled(tmp_path: Path) -> None:
    """Passing an unrecognised validator name to --skip does not crash."""
    project = setup_project(tmp_path)
    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir()

    for name in ["validate_structure", "validate_workspace", "validate_tdd", "validate_rdd", "validate_sprint"]:
        (fake_dir / f"{name}.py").write_text("import sys; sys.exit(0)\n")

    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project), "--skip", "validate_nonexistent"],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir)},
    )
    # Should not crash (exit 2 would indicate an arg parse error)
    assert result.returncode in (0, 1), f"Unexpected exit code: {result.returncode}\n{result.stderr}"


def test_missing_validator_script_exits_one(tmp_path: Path) -> None:
    """When a validator script is absent from the directory, orchestrator exits 1."""
    project = setup_project(tmp_path)
    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir()

    # Only create 4 of 5 validators — validate_sprint is missing
    for name in ["validate_structure", "validate_workspace", "validate_tdd", "validate_rdd"]:
        (fake_dir / f"{name}.py").write_text("import sys; sys.exit(0)\n")
    # validate_sprint.py deliberately NOT created

    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project)],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir)},
    )
    assert result.returncode == 1, "Missing validator should cause exit 1"


def test_project_root_must_be_provided(tmp_path: Path) -> None:
    """Invoking the orchestrator without a project_root argument exits non-zero."""
    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR)],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0, "Expected failure when project_root is omitted"


def test_allow_no_sprint_env_forwarded(tmp_path: Path) -> None:
    """SDA_ALLOW_NO_SPRINT=1 in the environment causes validate_sprint to exit 0 when no sprint."""
    project = setup_project(tmp_path)
    # PROGRESS.md has no active sprint — validate_sprint would normally exit 1
    # But with SDA_ALLOW_NO_SPRINT=1 it should advisory-skip and exit 0

    fake_dir = tmp_path / "fake_validators"
    fake_dir.mkdir()

    # All validators except validate_sprint always pass
    for name in ["validate_structure", "validate_workspace", "validate_tdd", "validate_rdd"]:
        (fake_dir / f"{name}.py").write_text("import sys; sys.exit(0)\n")

    # validate_sprint checks SDA_ALLOW_NO_SPRINT env var — use the real script
    import shutil
    real_sprint_validator = VALIDATORS_DIR / "validate_sprint.py"
    shutil.copy(real_sprint_validator, fake_dir / "validate_sprint.py")

    result = subprocess.run(
        [sys.executable, str(ORCHESTRATOR), str(project)],
        capture_output=True,
        text=True,
        env={**os.environ, "_VALIDATOR_DIR_OVERRIDE": str(fake_dir), "SDA_ALLOW_NO_SPRINT": "1"},
    )
    assert result.returncode == 0, (
        f"Expected exit 0 with SDA_ALLOW_NO_SPRINT=1 and no active sprint.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )

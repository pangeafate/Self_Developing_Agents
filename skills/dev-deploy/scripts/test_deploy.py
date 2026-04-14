#!/usr/bin/env python3
"""Tests for deploy.py — pre-deploy validation and git push orchestrator.

Tested contract:
- --action validate: runs validators/run_all.py; exits 0 on pass, 1 on fail, 3 if dir missing
- --action push: runs validation first; blocks git operations on failure; exits 2 on git error
- --action push requires --message; exits 2 without it
- Both actions emit valid JSON to stdout describing results
- --validators-dir overrides default validator discovery

Testing strategy:
- Validator mocking: inject fake run_all.py via --validators-dir (contains pass/fail scripts)
- Git operations: real git repo in tmp_path (git init + initial commit to enable subsequent commits)
- Subprocess calls: direct invocation of deploy.py (no internal mocking needed)

Exit codes:
    0 — success
    1 — validators failed
    2 — missing --message or git error
    3 — validators directory / run_all.py not found
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent
DEPLOY_SCRIPT = SCRIPTS_DIR / "deploy.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_deploy(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run deploy.py with given args, capturing stdout/stderr."""
    return subprocess.run(
        [sys.executable, str(DEPLOY_SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd) if cwd else None,
    )


def make_validators_dir(tmp_path: Path, exit_code: int) -> Path:
    """Create a fake validators directory with a run_all.py that exits with exit_code.

    The fake run_all.py prints minimal JSON-compatible output so deploy.py can
    parse the result and exits with the given code.
    """
    validators_dir = tmp_path / "validators"
    validators_dir.mkdir(parents=True, exist_ok=True)

    run_all = validators_dir / "run_all.py"
    run_all.write_text(
        textwrap.dedent(f"""\
            #!/usr/bin/env python3
            import sys
            # Minimal output matching what the orchestrator would produce
            if {exit_code} == 0:
                print("RESULT: ALL PASSED")
            else:
                print("RESULT: FAILED — one or more validators did not pass.")
            sys.exit({exit_code})
        """)
    )
    return validators_dir


def make_git_repo(tmp_path: Path) -> Path:
    """Initialise a git repo in tmp_path/project with an initial commit.

    Returns the project directory path.
    """
    project = tmp_path / "project"
    project.mkdir()

    # Configure minimal git identity so commits succeed in CI / clean environments
    subprocess.run(
        ["git", "init", str(project)], capture_output=True, check=True
    )
    subprocess.run(
        ["git", "-C", str(project), "config", "user.email", "test@example.com"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(project), "config", "user.name", "Test User"],
        capture_output=True,
        check=True,
    )

    # Create an initial commit so HEAD exists (required for git commit to work)
    readme = project / "README.md"
    readme.write_text("# Test repo\n")
    subprocess.run(
        ["git", "-C", str(project), "add", "README.md"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(project), "commit", "-m", "Initial commit"],
        capture_output=True,
        check=True,
    )

    return project


# ---------------------------------------------------------------------------
# validate action — basic pass/fail
# ---------------------------------------------------------------------------


def test_validate_action_runs_validators(tmp_path: Path) -> None:
    """validate action invokes run_all.py inside the validators directory."""
    validators_dir = make_validators_dir(tmp_path, exit_code=0)
    project = tmp_path / "project"
    project.mkdir()

    # Write a sentinel file that the fake run_all.py creates when invoked
    sentinel = tmp_path / "run_all.ran"
    run_all = validators_dir / "run_all.py"
    run_all.write_text(
        textwrap.dedent(f"""\
            #!/usr/bin/env python3
            import sys
            open("{sentinel}", "w").close()
            print("RESULT: ALL PASSED")
            sys.exit(0)
        """)
    )

    result = run_deploy(
        "--action", "validate",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
    )
    assert result.returncode == 0, result.stderr
    assert sentinel.exists(), "run_all.py was never called"


def test_validate_action_passes_when_all_pass(tmp_path: Path) -> None:
    """validate exits 0 when run_all.py reports success."""
    validators_dir = make_validators_dir(tmp_path, exit_code=0)
    project = tmp_path / "project"
    project.mkdir()

    result = run_deploy(
        "--action", "validate",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
    )
    assert result.returncode == 0, f"Expected exit 0, got {result.returncode}\n{result.stderr}"


def test_validate_action_fails_when_any_fail(tmp_path: Path) -> None:
    """validate exits 1 when run_all.py reports failure."""
    validators_dir = make_validators_dir(tmp_path, exit_code=1)
    project = tmp_path / "project"
    project.mkdir()

    result = run_deploy(
        "--action", "validate",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
    )
    assert result.returncode == 1, f"Expected exit 1, got {result.returncode}\n{result.stderr}"


def test_validate_output_is_valid_json(tmp_path: Path) -> None:
    """validate action emits valid JSON on stdout regardless of pass/fail."""
    for exit_code in (0, 1):
        validators_dir = make_validators_dir(tmp_path / str(exit_code), exit_code=exit_code)
        project = tmp_path / f"project_{exit_code}"
        project.mkdir()

        result = run_deploy(
            "--action", "validate",
            "--project-root", str(project),
            "--validators-dir", str(validators_dir),
        )
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"stdout was not valid JSON (exit_code={exit_code}):\n"
                f"{result.stdout!r}\nError: {exc}"
            )
        assert isinstance(data, dict), "JSON output must be a dict"


# ---------------------------------------------------------------------------
# push action — validator gate
# ---------------------------------------------------------------------------


def test_push_action_blocked_by_validator_failure(tmp_path: Path) -> None:
    """push exits 1 and performs NO git operations when validators fail."""
    validators_dir = make_validators_dir(tmp_path, exit_code=1)
    project = make_git_repo(tmp_path)

    # Create a new file that would be committed if git operations ran
    (project / "new_file.txt").write_text("would be committed\n")

    result = run_deploy(
        "--action", "push",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
        "--message", "SP_042: test commit",
    )
    assert result.returncode == 1, (
        f"Expected exit 1 (blocked by validators), got {result.returncode}\n{result.stderr}"
    )

    # Verify no new commit was created — still only the initial commit
    log = subprocess.run(
        ["git", "-C", str(project), "log", "--oneline"],
        capture_output=True,
        text=True,
    )
    commit_count = len(log.stdout.strip().splitlines())
    assert commit_count == 1, (
        f"Expected 1 commit (initial), found {commit_count}:\n{log.stdout}"
    )


def test_push_action_requires_message(tmp_path: Path) -> None:
    """push exits 2 when --message is omitted."""
    validators_dir = make_validators_dir(tmp_path, exit_code=0)
    project = make_git_repo(tmp_path)

    result = run_deploy(
        "--action", "push",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
        # --message deliberately omitted
    )
    assert result.returncode == 2, (
        f"Expected exit 2 (missing --message), got {result.returncode}\n{result.stderr}"
    )


def test_push_output_json_has_expected_fields(tmp_path: Path) -> None:
    """Successful push emits JSON with status, validators_passed, commit_hash, files_committed."""
    validators_dir = make_validators_dir(tmp_path, exit_code=0)
    project = make_git_repo(tmp_path)

    # Stage a new file so there is something to commit
    (project / "feature.txt").write_text("new feature\n")

    result = run_deploy(
        "--action", "push",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
        "--message", "SP_042: add feature",
    )
    assert result.returncode == 0, (
        f"Expected exit 0 on successful push\n{result.stderr}\nstdout: {result.stdout}"
    )

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(f"stdout was not valid JSON:\n{result.stdout!r}\nError: {exc}")

    assert data.get("status") == "pushed", f"Unexpected status: {data.get('status')}"
    assert data.get("validators_passed") is True, "validators_passed should be True"
    assert "commit_hash" in data, "commit_hash missing from output"
    assert isinstance(data.get("commit_hash"), str) and len(data["commit_hash"]) > 0
    assert "files_committed" in data, "files_committed missing from output"
    assert isinstance(data.get("files_committed"), int), "files_committed should be int"


# ---------------------------------------------------------------------------
# validators directory not found
# ---------------------------------------------------------------------------


def test_validators_not_found_exits_3(tmp_path: Path) -> None:
    """exit 3 when --validators-dir points to a directory without run_all.py."""
    empty_validators_dir = tmp_path / "empty_validators"
    empty_validators_dir.mkdir()
    project = tmp_path / "project"
    project.mkdir()

    result = run_deploy(
        "--action", "validate",
        "--project-root", str(project),
        "--validators-dir", str(empty_validators_dir),
    )
    assert result.returncode == 3, (
        f"Expected exit 3 (run_all.py not found), got {result.returncode}\n{result.stderr}"
    )


def test_validators_dir_missing_entirely_exits_3(tmp_path: Path) -> None:
    """exit 3 when --validators-dir does not exist at all."""
    project = tmp_path / "project"
    project.mkdir()
    nonexistent = tmp_path / "nonexistent_validators"

    result = run_deploy(
        "--action", "validate",
        "--project-root", str(project),
        "--validators-dir", str(nonexistent),
    )
    assert result.returncode == 3, (
        f"Expected exit 3 (directory missing), got {result.returncode}\n{result.stderr}"
    )


# ---------------------------------------------------------------------------
# Default validators dir discovery
# ---------------------------------------------------------------------------


def test_default_validators_dir_is_project_root_validators(tmp_path: Path) -> None:
    """Without --validators-dir, deploy.py looks in <project-root>/validators/run_all.py."""
    project = tmp_path / "project"
    project.mkdir()

    # Place run_all.py at <project-root>/validators/run_all.py
    validators_dir = project / "validators"
    validators_dir.mkdir()
    sentinel = tmp_path / "default_dir_used.ran"
    (validators_dir / "run_all.py").write_text(
        textwrap.dedent(f"""\
            #!/usr/bin/env python3
            import sys
            open("{sentinel}", "w").close()
            print("RESULT: ALL PASSED")
            sys.exit(0)
        """)
    )

    result = run_deploy(
        "--action", "validate",
        "--project-root", str(project),
        # --validators-dir omitted intentionally
    )
    assert result.returncode == 0, result.stderr
    assert sentinel.exists(), "Default validators dir was not used"


# ---------------------------------------------------------------------------
# validate output JSON shape
# ---------------------------------------------------------------------------


def test_validate_output_json_has_status_and_validators_passed(tmp_path: Path) -> None:
    """validate JSON output always contains 'status' and 'validators_passed'."""
    validators_dir = make_validators_dir(tmp_path, exit_code=0)
    project = tmp_path / "project"
    project.mkdir()

    result = run_deploy(
        "--action", "validate",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
    )
    data = json.loads(result.stdout)
    assert "status" in data
    assert "validators_passed" in data
    assert data["validators_passed"] is True


def test_validate_output_json_validators_passed_false_on_failure(tmp_path: Path) -> None:
    """validate JSON output has validators_passed=false when validators fail."""
    validators_dir = make_validators_dir(tmp_path, exit_code=1)
    project = tmp_path / "project"
    project.mkdir()

    result = run_deploy(
        "--action", "validate",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
    )
    data = json.loads(result.stdout)
    assert data["validators_passed"] is False


# ---------------------------------------------------------------------------
# Lockfile check in push action
# ---------------------------------------------------------------------------


def test_warns_when_pre_impl_lockfile_missing(tmp_path: Path) -> None:
    """push action emits a WARNING to stderr when .pre_impl_passed is missing."""
    validators_dir = make_validators_dir(tmp_path, exit_code=0)
    project = make_git_repo(tmp_path)
    # No .pre_impl_passed file — lockfile is absent

    (project / "feature.txt").write_text("new feature\n")

    result = run_deploy(
        "--action", "push",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
        "--message", "SP_070: test lockfile warning",
    )
    # Push should still succeed (lockfile check is advisory)
    assert result.returncode == 0, (
        f"Expected exit 0 (lockfile warning is advisory).\nstderr: {result.stderr}"
    )
    assert "WARNING" in result.stderr or "warning" in result.stderr.lower(), (
        f"Expected a lockfile warning in stderr.\nstderr: {result.stderr}"
    )
    assert ".pre_impl_passed" in result.stderr, (
        "Expected .pre_impl_passed mentioned in stderr warning"
    )


def test_lockfile_warning_suppressed_when_sprint_skipped(tmp_path: Path) -> None:
    """When validate_sprint is in --skip-validators, no lockfile warning is emitted."""
    validators_dir = make_validators_dir(tmp_path, exit_code=0)
    project = make_git_repo(tmp_path)
    # No .pre_impl_passed file — but validate_sprint is skipped

    (project / "feature.txt").write_text("new feature\n")

    result = run_deploy(
        "--action", "push",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
        "--message", "SP_070: skip lockfile warning",
        "--skip-validators", "validate_sprint",
    )
    assert result.returncode == 0, (
        f"Expected exit 0.\nstderr: {result.stderr}"
    )
    # No lockfile warning when validate_sprint is skipped
    assert ".pre_impl_passed" not in result.stderr, (
        f"Lockfile warning should be suppressed when validate_sprint is skipped.\n"
        f"stderr: {result.stderr}"
    )


# ---------------------------------------------------------------------------
# Stage 6 → 7 docs-reconciled lockfile gate (Rule 16)
# ---------------------------------------------------------------------------


def _make_validators_passing(tmp_path: Path) -> Path:
    """Helper: set up a fake validators dir where run_all.py always passes."""
    vdir = tmp_path / "validators"
    vdir.mkdir()
    run_all = vdir / "run_all.py"
    run_all.write_text(
        "import sys\nprint('all pass')\nsys.exit(0)\n", encoding="utf-8"
    )
    return vdir


def test_push_blocked_when_active_sprint_but_lockfile_missing(tmp_path):
    """Stage 7 (Deployment) MUST NOT proceed if `.docs_reconciled` is missing
    while PROGRESS.md declares an active sprint."""
    project = make_git_repo(tmp_path)
    validators_dir = _make_validators_passing(tmp_path)
    (project / "PROGRESS.md").write_text(
        "**Current:** SP_999_TestSprint\n", encoding="utf-8"
    )
    (project / "feature.txt").write_text("change\n")
    result = run_deploy(
        "--action", "push",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
        "--message", "SP_999: should be blocked",
    )
    assert result.returncode == 1, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert "Stage 7 by Rule 16" in payload["error"]
    assert ".docs_reconciled" in payload["error"]


def test_push_blocked_when_lockfile_sprint_id_mismatches_active(tmp_path):
    """Stage 7 MUST detect a stale lockfile from a previous sprint."""
    project = make_git_repo(tmp_path)
    validators_dir = _make_validators_passing(tmp_path)
    (project / "PROGRESS.md").write_text(
        "**Current:** SP_002_Current\n", encoding="utf-8"
    )
    # Stale lockfile from a previous sprint
    (project / ".docs_reconciled").write_text(
        json.dumps({
            "schema_version": 1,
            "sprint_id": "SP_001_Previous",
            "passed_at": "2026-04-01T00:00:00Z",
        }),
        encoding="utf-8",
    )
    (project / "feature.txt").write_text("change\n")
    result = run_deploy(
        "--action", "push",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
        "--message", "SP_002: should be blocked, stale lockfile",
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert "stale" in payload["error"].lower()


def test_push_passes_when_lockfile_matches_active_sprint(tmp_path):
    """Stage 7 succeeds when `.docs_reconciled` is present and matches sprint."""
    project = make_git_repo(tmp_path)
    validators_dir = _make_validators_passing(tmp_path)
    (project / "PROGRESS.md").write_text(
        "**Current:** SP_003_OK\n", encoding="utf-8"
    )
    (project / ".docs_reconciled").write_text(
        json.dumps({
            "schema_version": 1,
            "sprint_id": "SP_003_OK",
            "passed_at": "2026-04-14T10:00:00Z",
        }),
        encoding="utf-8",
    )
    (project / "feature.txt").write_text("change\n")
    result = run_deploy(
        "--action", "push",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
        "--message", "SP_003: docs reconciled, deploying",
    )
    # Push to remote will likely fail (no remote configured), but the lockfile
    # gate must let us PAST validation. Acceptable exit codes: 0 (full success
    # or "nothing to commit" path) or 2 (git push error). NOT 1 (gate block).
    assert result.returncode in (0, 2), (
        f"Expected lockfile gate to pass (exit 0 or 2), got {result.returncode}.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_push_passes_when_no_active_sprint(tmp_path):
    """Lockfile gate is skipped when PROGRESS.md has no active sprint marker
    (between-sprints state)."""
    project = make_git_repo(tmp_path)
    validators_dir = _make_validators_passing(tmp_path)
    (project / "PROGRESS.md").write_text(
        "# Progress\n\n_No active sprint._\n", encoding="utf-8"
    )
    (project / "feature.txt").write_text("change\n")
    result = run_deploy(
        "--action", "push",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
        "--message", "between sprints, no gate",
    )
    assert result.returncode in (0, 2)


def test_push_blocked_when_lockfile_is_symlink(tmp_path):
    """Refuse to read the lockfile if it's been replaced with a symlink
    (defense against pointing the validator at attacker-controlled JSON)."""
    project = make_git_repo(tmp_path)
    validators_dir = _make_validators_passing(tmp_path)
    (project / "PROGRESS.md").write_text(
        "**Current:** SP_004_Sym\n", encoding="utf-8"
    )
    target = tmp_path / "evil.json"
    target.write_text(
        json.dumps({"schema_version": 1, "sprint_id": "SP_004_Sym"}), encoding="utf-8"
    )
    import os
    os.symlink(target, project / ".docs_reconciled")
    (project / "feature.txt").write_text("change\n")
    result = run_deploy(
        "--action", "push",
        "--project-root", str(project),
        "--validators-dir", str(validators_dir),
        "--message", "symlink should be refused",
    )
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert "symlink" in payload["error"].lower()

#!/usr/bin/env python3
"""Tests for deploy-to-agent.py — safe skill deployer.

Tests exercise the CLI via subprocess so they cover real argument parsing,
exit codes, and JSON output.  Each test uses tmp_path for isolation.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCRIPT = Path(__file__).parent / "deploy-to-agent.py"


def _minimal_openclaw_json() -> dict:
    return {"agents": {"list": []}, "skills": {"entries": {}}}


def _make_source_dir(tmp_path: Path, skill_name: str = "my-skill") -> Path:
    """Create a minimal source skill directory with a script and a README."""
    src = tmp_path / "source" / skill_name
    src.mkdir(parents=True)
    (src / "run.py").write_text("# skill script\n")
    (src / "SKILL.md").write_text("# Skill docs\n")
    return src


def _make_target_workspace(
    tmp_path: Path,
    *,
    with_openclaw_json: bool = True,
    malformed_json: bool = False,
) -> Path:
    """Create a minimal target workspace directory."""
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True)
    (ws / "skills").mkdir()
    if with_openclaw_json:
        cfg = ws / "openclaw.json"
        if malformed_json:
            cfg.write_text("{ NOT VALID JSON !!!")
        else:
            cfg.write_text(json.dumps(_minimal_openclaw_json()))
    return ws


def _run(
    *,
    source_dir: Path,
    target_workspace: Path,
    skill_name: str = "my-skill",
    config_file: Path | None = None,
    dry_run: bool = False,
    rollback: bool = False,
) -> subprocess.CompletedProcess[str]:
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--source-dir",
        str(source_dir),
        "--target-workspace",
        str(target_workspace),
        "--skill-name",
        skill_name,
    ]
    if config_file is not None:
        cmd += ["--config-file", str(config_file)]
    if dry_run:
        cmd.append("--dry-run")
    if rollback:
        cmd.append("--rollback")
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Tests: basic deployment
# ---------------------------------------------------------------------------


class TestBasicDeployment:
    def test_copies_skill_to_target_workspace(self, tmp_path: Path) -> None:
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        result = _run(source_dir=src, target_workspace=ws)
        assert result.returncode == 0, result.stderr
        deployed = ws / "skills" / "my-skill"
        assert deployed.is_dir()
        assert (deployed / "run.py").exists()
        assert (deployed / "SKILL.md").exists()

    def test_sets_correct_permissions(self, tmp_path: Path) -> None:
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        _run(source_dir=src, target_workspace=ws)
        deployed = ws / "skills" / "my-skill"
        # .py files: 0o550 (r-xr-x---)
        py_mode = (deployed / "run.py").stat().st_mode & 0o777
        assert py_mode == 0o550, f"Expected 0o550, got {oct(py_mode)}"
        # .md files: 0o440 (r--r-----)
        md_mode = (deployed / "SKILL.md").stat().st_mode & 0o777
        assert md_mode == 0o440, f"Expected 0o440, got {oct(md_mode)}"

    def test_output_json_has_expected_fields(self, tmp_path: Path) -> None:
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        result = _run(source_dir=src, target_workspace=ws)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        for key in ("status", "skill_name", "deployed_to", "gateway_restart_needed"):
            assert key in data, f"Missing key: {key}"

    def test_does_not_restart_gateway(self, tmp_path: Path) -> None:
        """Script must never call systemctl — it only sets gateway_restart_needed: true."""
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        result = _run(source_dir=src, target_workspace=ws)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["gateway_restart_needed"] is True
        # No systemctl in stderr or stdout
        combined = result.stdout + result.stderr
        assert "systemctl" not in combined


# ---------------------------------------------------------------------------
# Tests: openclaw.json patching
# ---------------------------------------------------------------------------


class TestOpenClawJsonPatching:
    def test_patches_openclaw_json_with_skill(self, tmp_path: Path) -> None:
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        _run(source_dir=src, target_workspace=ws)
        cfg = json.loads((ws / "openclaw.json").read_text())
        assert "my-skill" in cfg["skills"]["entries"]

    def test_skips_existing_skill_registration(self, tmp_path: Path) -> None:
        """Running deploy twice should not duplicate the skill entry."""
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        _run(source_dir=src, target_workspace=ws)
        _run(source_dir=src, target_workspace=ws)
        cfg = json.loads((ws / "openclaw.json").read_text())
        entries = cfg["skills"]["entries"]
        # key should appear exactly once (dict, so guaranteed)
        assert list(entries.keys()).count("my-skill") == 1

    def test_domain_skill_registered_without_sda_framework_root(
        self, tmp_path: Path
    ) -> None:
        """Domain skills are registered as skills.entries[name] = {} — no extra keys."""
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        _run(source_dir=src, target_workspace=ws)
        cfg = json.loads((ws / "openclaw.json").read_text())
        entry = cfg["skills"]["entries"]["my-skill"]
        assert entry == {}, f"Expected empty dict, got {entry!r}"

    def test_atomic_json_write(self, tmp_path: Path) -> None:
        """After deployment, openclaw.json must be valid JSON (atomic write succeeded)."""
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        _run(source_dir=src, target_workspace=ws)
        cfg_text = (ws / "openclaw.json").read_text()
        # Must parse without error
        parsed = json.loads(cfg_text)
        assert isinstance(parsed, dict)
        # .tmp file must be cleaned up
        assert not (ws / "openclaw.json.tmp").exists()

    def test_handles_missing_openclaw_json(self, tmp_path: Path) -> None:
        """If openclaw.json is absent, script warns and continues (exit 0, no patch)."""
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path, with_openclaw_json=False)
        result = _run(source_dir=src, target_workspace=ws)
        # Should succeed (exit 0) but note that JSON patching was skipped
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["openclaw_json_patched"] is False

    def test_handles_malformed_openclaw_json(self, tmp_path: Path) -> None:
        """Malformed openclaw.json should exit 3 (config error)."""
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path, malformed_json=True)
        result = _run(source_dir=src, target_workspace=ws)
        assert result.returncode == 3


# ---------------------------------------------------------------------------
# Tests: backup and rollback
# ---------------------------------------------------------------------------


class TestBackupAndRollback:
    def test_creates_backup_before_overwrite(self, tmp_path: Path) -> None:
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        # Deploy once to create the skill dir
        _run(source_dir=src, target_workspace=ws)
        # Deploy again — the second deploy should create a .bak
        _run(source_dir=src, target_workspace=ws)
        bak = ws / "skills" / "my-skill.bak"
        assert bak.is_dir(), "Expected .bak directory to exist after overwrite"

    def test_rollback_restores_from_backup(self, tmp_path: Path) -> None:
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        # First deploy
        _run(source_dir=src, target_workspace=ws)
        # Add a sentinel file to the deployed dir, then deploy again to create backup
        (ws / "skills" / "my-skill" / "sentinel.py").write_text("# sentinel\n")
        _run(source_dir=src, target_workspace=ws)
        # Now the backup has the sentinel; the live dir has the fresh copy from src
        # Rollback should restore the backup (which has sentinel)
        result = _run(source_dir=src, target_workspace=ws, rollback=True)
        assert result.returncode == 0
        assert (ws / "skills" / "my-skill" / "sentinel.py").exists()


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_handles_missing_target_workspace(self, tmp_path: Path) -> None:
        src = _make_source_dir(tmp_path)
        nonexistent = tmp_path / "does_not_exist"
        result = _run(source_dir=src, target_workspace=nonexistent)
        assert result.returncode == 2

    def test_handles_missing_source_dir(self, tmp_path: Path) -> None:
        ws = _make_target_workspace(tmp_path)
        nonexistent = tmp_path / "no_source_here"
        result = _run(source_dir=nonexistent, target_workspace=ws)
        assert result.returncode == 2


# ---------------------------------------------------------------------------
# Tests: dry run
# ---------------------------------------------------------------------------


class TestDryRun:
    def test_dry_run_makes_no_changes(self, tmp_path: Path) -> None:
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        original_cfg = (ws / "openclaw.json").read_text()
        result = _run(source_dir=src, target_workspace=ws, dry_run=True)
        assert result.returncode == 0
        # Skill directory must NOT be created
        assert not (ws / "skills" / "my-skill").exists()
        # openclaw.json must be unchanged
        assert (ws / "openclaw.json").read_text() == original_cfg
        # Output JSON should indicate dry_run
        data = json.loads(result.stdout)
        assert data.get("dry_run") is True


# ---------------------------------------------------------------------------
# Tests: --project-root validator gate
# ---------------------------------------------------------------------------


def _run_with_project_root(
    *,
    source_dir: Path,
    target_workspace: Path,
    project_root: Path,
    skill_name: str = "my-skill",
) -> subprocess.CompletedProcess[str]:
    """Run deploy-to-agent.py with --project-root flag."""
    cmd = [
        sys.executable,
        str(SCRIPT),
        "--source-dir", str(source_dir),
        "--target-workspace", str(target_workspace),
        "--skill-name", skill_name,
        "--project-root", str(project_root),
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def _make_project_with_validators(tmp_path: Path, validator_exit_code: int) -> Path:
    """Create a fake project root with a passing or failing run_all.py."""
    import textwrap
    project = tmp_path / "project"
    project.mkdir(parents=True, exist_ok=True)
    validators_dir = project / "validators"
    validators_dir.mkdir()
    (validators_dir / "run_all.py").write_text(
        textwrap.dedent(f"""\
            #!/usr/bin/env python3
            import sys
            if {validator_exit_code} == 0:
                print("RESULT: ALL PASSED")
            else:
                print("RESULT: FAILED")
            sys.exit({validator_exit_code})
        """)
    )
    return project


class TestProjectRootValidators:
    def test_runs_validators_with_project_root(self, tmp_path: Path) -> None:
        """When --project-root is given and validators pass, deploy succeeds."""
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        project = _make_project_with_validators(tmp_path, validator_exit_code=0)

        result = _run_with_project_root(
            source_dir=src,
            target_workspace=ws,
            project_root=project,
        )
        assert result.returncode == 0, (
            f"Expected exit 0 when validators pass.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        deployed = ws / "skills" / "my-skill"
        assert deployed.is_dir(), "Skill should have been deployed"

    def test_blocks_deployment_on_validator_failure(self, tmp_path: Path) -> None:
        """When --project-root is given and validators fail, deploy exits 1."""
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)
        project = _make_project_with_validators(tmp_path, validator_exit_code=1)

        result = _run_with_project_root(
            source_dir=src,
            target_workspace=ws,
            project_root=project,
        )
        assert result.returncode == 1, (
            f"Expected exit 1 when validators fail.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Skill must NOT have been deployed
        deployed = ws / "skills" / "my-skill"
        assert not deployed.is_dir(), "Skill must not be deployed when validators fail"

    def test_skips_validation_without_project_root(self, tmp_path: Path) -> None:
        """When --project-root is not provided, deploy succeeds with a warning."""
        src = _make_source_dir(tmp_path)
        ws = _make_target_workspace(tmp_path)

        result = _run(source_dir=src, target_workspace=ws)
        assert result.returncode == 0, (
            f"Expected exit 0 when no --project-root provided.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "warning" in combined.lower() or "WARNING" in combined, (
            "Expected a WARNING about skipped validation"
        )

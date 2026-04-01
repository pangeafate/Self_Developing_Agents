#!/usr/bin/env python3
"""Tests for gather-context.py — sub-agent orchestration context builder.

Follows the subprocess pattern from validate_structure.py tests.
Uses tmp_path to create minimal framework structures.
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parent / "gather-context.py"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_framework(tmp_path: Path) -> Path:
    """Create a minimal framework tree with fake roles and GL-SELF-CRITIQUE.md."""
    root = tmp_path / "framework"

    # roles/quality
    quality = root / "roles" / "quality"
    quality.mkdir(parents=True)
    (quality / "architect-reviewer.md").write_text(
        "# Role: Architect Reviewer\nYou review architecture.", encoding="utf-8"
    )
    (quality / "code-reviewer.md").write_text(
        "# Role: Code Reviewer\nYou verify factual claims.", encoding="utf-8"
    )
    (quality / "debugger.md").write_text(
        "# Role: Debugger\nYou debug code.", encoding="utf-8"
    )
    (quality / "security-auditor.md").write_text(
        "# Role: Security Auditor\nYou audit security.", encoding="utf-8"
    )
    (quality / "performance-reviewer.md").write_text(
        "# Role: Performance Reviewer\nYou review performance.", encoding="utf-8"
    )

    # roles/research
    research = root / "roles" / "research"
    research.mkdir(parents=True)
    (research / "researcher.md").write_text(
        "# Role: Researcher\nYou locate things fast.", encoding="utf-8"
    )
    (research / "analyzer.md").write_text(
        "# Role: Analyzer\nYou analyze deeply.", encoding="utf-8"
    )

    # roles/core
    core = root / "roles" / "core"
    core.mkdir(parents=True)
    (core / "plan-architect.md").write_text(
        "# Role: Plan Architect\nYou design sprint plans.", encoding="utf-8"
    )
    (core / "test-enforcer.md").write_text(
        "# Role: Test Enforcer\nYou enforce TDD.", encoding="utf-8"
    )

    # practices/GL-SELF-CRITIQUE.md with the 3 required sections
    practices = root / "practices"
    practices.mkdir(parents=True)
    gl = practices / "GL-SELF-CRITIQUE.md"
    gl.write_text(
        textwrap.dedent("""\
        # Review Protocol

        Some intro text.

        ## Review Templates

        ### Pre-Implementation Review Prompt (for Architect-Reviewer)

        ```
        Review this sprint plan for architecture risks, backward compatibility,
        deployment ordering, scope creep, TDD compliance, missing edge cases,
        and performance concerns.

        Read the sprint plan FULLY, then read every source file it references.
        Rank issues by severity: CRITICAL / HIGH / MEDIUM / LOW.

        Be harsh. Your job is to find problems, not confirm the plan is good.

        Sprint plan: [path]
        Referenced files: [list of paths]
        ```

        ### Pre-Implementation Review Prompt (for Code-Reviewer)

        ```
        Verify the factual claims in this sprint plan against the actual codebase.
        Check that referenced functions, field names, signatures, file paths,
        and behavioral descriptions actually exist and are accurate.

        Find issues the architect-reviewer missed. Focus on practical
        implementation details.

        Read the sprint plan FULLY, then read every source file it references.
        Rank issues by severity: CRITICAL / HIGH / MEDIUM / LOW.

        Sprint plan: [path]
        Referenced files: [list of paths]
        ```

        ### Post-Implementation Review Prompt (for Gap Analysis Reviewers)

        ```
        Review these files for bugs, logical gaps, missing edge cases,
        inconsistencies between modules, broken cross-references, and untested
        paths.

        Check: enum/schema sync, model/schema field coverage, import paths,
        CLI arg handling, service logic correctness, test coverage for error
        paths, and cross-module contract consistency.

        DO NOT ask for or read the sprint plan. Evaluate the code and tests
        on their own merits.

        Files to review: [list of new/modified source and test files]
        ```
        """),
        encoding="utf-8",
    )

    return root


def _run(args: list[str], *, framework_root: Path | None = None) -> subprocess.CompletedProcess:
    """Run gather-context.py with given args, capturing stdout+stderr."""
    cmd = [sys.executable, str(SCRIPT)] + args
    if framework_root is not None:
        cmd += ["--framework-root", str(framework_root)]
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# Basic output shape
# ---------------------------------------------------------------------------

class TestOutputShape:
    def test_output_json_has_all_required_fields(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        result = _run(
            ["--role", "architect-reviewer", "--stage", "3",
             "--sprint-plan", str(tmp_path / "plan.md")],
            framework_root=root,
        )
        # sprint-plan file doesn't exist yet; create it so the script can read it
        plan = tmp_path / "plan.md"
        plan.write_text("# Sprint Plan\nDo things.", encoding="utf-8")

        result = _run(
            ["--role", "architect-reviewer", "--stage", "3",
             "--sprint-plan", str(plan)],
            framework_root=root,
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert "role" in data
        assert "stage" in data
        assert "system_prompt" in data
        assert "review_prompt" in data
        assert "context_files" in data
        assert "isolation_verified" in data

    def test_isolation_verified_true_when_compliant(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        plan = tmp_path / "plan.md"
        plan.write_text("# Sprint Plan", encoding="utf-8")
        result = _run(
            ["--role", "architect-reviewer", "--stage", "3",
             "--sprint-plan", str(plan)],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["isolation_verified"] is True

    def test_role_and_stage_reflected_in_output(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        result = _run(
            ["--role", "debugger", "--stage", "5",
             "--files", "/nonexistent_but_ok.py"],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["role"] == "debugger"
        assert data["stage"] == 5


# ---------------------------------------------------------------------------
# Role file loading
# ---------------------------------------------------------------------------

class TestRoleFileLookup:
    def test_reads_role_file_as_complete_document(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        result = _run(
            ["--role", "architect-reviewer", "--stage", "5"],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "# Role: Architect Reviewer" in data["system_prompt"]
        assert "You review architecture." in data["system_prompt"]

    def test_researcher_role_read_as_complete_document(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        result = _run(
            ["--role", "researcher", "--stage", "5"],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "# Role: Researcher" in data["system_prompt"]
        assert "You locate things fast." in data["system_prompt"]

    def test_invalid_role_exits_2(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        result = _run(
            ["--role", "nonexistent-role", "--stage", "5"],
            framework_root=root,
        )
        assert result.returncode == 2

    def test_invalid_stage_exits_2(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        result = _run(
            ["--role", "architect-reviewer", "--stage", "4"],
            framework_root=root,
        )
        assert result.returncode == 2

    def test_ambiguous_role_name_exits_2(self, tmp_path: Path) -> None:
        """If two files with the same name exist in different subdirs, exit 2."""
        root = _make_framework(tmp_path)
        # Create a duplicate in a new subdir
        dup = root / "roles" / "extra"
        dup.mkdir(parents=True)
        (dup / "architect-reviewer.md").write_text(
            "# Role: Duplicate Architect Reviewer", encoding="utf-8"
        )
        result = _run(
            ["--role", "architect-reviewer", "--stage", "5"],
            framework_root=root,
        )
        assert result.returncode == 2


# ---------------------------------------------------------------------------
# All supported roles
# ---------------------------------------------------------------------------

class TestAllRolesSupported:
    @pytest.mark.parametrize("role", [
        "architect-reviewer",
        "code-reviewer",
        "debugger",
        "security-auditor",
        "performance-reviewer",
    ])
    def test_all_quality_roles_supported(self, tmp_path: Path, role: str) -> None:
        root = _make_framework(tmp_path)
        result = _run(["--role", role, "--stage", "5"], framework_root=root)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["role"] == role

    @pytest.mark.parametrize("role", ["researcher", "analyzer"])
    def test_all_research_roles_supported(self, tmp_path: Path, role: str) -> None:
        root = _make_framework(tmp_path)
        result = _run(["--role", role, "--stage", "5"], framework_root=root)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["role"] == role

    @pytest.mark.parametrize("role", ["plan-architect", "test-enforcer"])
    def test_all_core_roles_supported(self, tmp_path: Path, role: str) -> None:
        root = _make_framework(tmp_path)
        result = _run(["--role", role, "--stage", "5"], framework_root=root)
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["role"] == role


# ---------------------------------------------------------------------------
# Prompt template selection
# ---------------------------------------------------------------------------

class TestPromptSelection:
    def test_stage_5_prompt_is_gap_analysis(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        result = _run(
            ["--role", "architect-reviewer", "--stage", "5"],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Gap analysis prompt contains this distinctive phrase
        assert "DO NOT ask for or read the sprint plan" in data["review_prompt"]

    def test_stage_3_architect_gets_architect_prompt(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        plan = tmp_path / "plan.md"
        plan.write_text("# Sprint Plan", encoding="utf-8")
        result = _run(
            ["--role", "architect-reviewer", "--stage", "3",
             "--sprint-plan", str(plan)],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "architecture risks" in data["review_prompt"]
        assert "Be harsh" in data["review_prompt"]

    def test_stage_3_code_reviewer_gets_code_reviewer_prompt(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        plan = tmp_path / "plan.md"
        plan.write_text("# Sprint Plan", encoding="utf-8")
        result = _run(
            ["--role", "code-reviewer", "--stage", "3",
             "--sprint-plan", str(plan)],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "Verify the factual claims" in data["review_prompt"]

    def test_stage_3_unknown_role_falls_back_to_architect_prompt(
        self, tmp_path: Path
    ) -> None:
        """Any non-code-reviewer role at stage 3 gets the architect prompt."""
        root = _make_framework(tmp_path)
        plan = tmp_path / "plan.md"
        plan.write_text("# Sprint Plan", encoding="utf-8")
        result = _run(
            ["--role", "debugger", "--stage", "3",
             "--sprint-plan", str(plan)],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "architecture risks" in data["review_prompt"]


# ---------------------------------------------------------------------------
# Isolation enforcement
# ---------------------------------------------------------------------------

class TestIsolationEnforcement:
    def test_stage_5_blocks_sprint_plan(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        plan = tmp_path / "plan.md"
        plan.write_text("# Sprint Plan\nBuild things.", encoding="utf-8")
        result = _run(
            ["--role", "architect-reviewer", "--stage", "5",
             "--sprint-plan", str(plan)],
            framework_root=root,
        )
        assert result.returncode == 1

    def test_stage_5_isolation_violation_message_on_stderr(
        self, tmp_path: Path
    ) -> None:
        root = _make_framework(tmp_path)
        plan = tmp_path / "plan.md"
        plan.write_text("# Sprint Plan", encoding="utf-8")
        result = _run(
            ["--role", "architect-reviewer", "--stage", "5",
             "--sprint-plan", str(plan)],
            framework_root=root,
        )
        assert result.returncode == 1
        assert "isolation" in result.stderr.lower() or "sprint" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Sprint plan handling (stage 3)
# ---------------------------------------------------------------------------

class TestSprintPlanHandling:
    def test_stage_3_includes_sprint_plan_content(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        plan = tmp_path / "plan.md"
        plan.write_text("# My Sprint Plan\nDo important things.", encoding="utf-8")
        result = _run(
            ["--role", "architect-reviewer", "--stage", "3",
             "--sprint-plan", str(plan)],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        # Sprint plan appears in context_files
        paths = [cf["path"] for cf in data["context_files"]]
        assert str(plan) in paths
        # Content is present
        contents = [cf["content"] for cf in data["context_files"]]
        assert any("Do important things." in c for c in contents)

    def test_stage_3_warns_without_sprint_plan(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        result = _run(
            ["--role", "architect-reviewer", "--stage", "3"],
            framework_root=root,
        )
        # Should succeed (exit 0) but warn on stderr
        assert result.returncode == 0
        assert "sprint" in result.stderr.lower() or "warning" in result.stderr.lower()


# ---------------------------------------------------------------------------
# Context files
# ---------------------------------------------------------------------------

class TestContextFiles:
    def test_context_files_include_content(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        src_file = tmp_path / "mymodule.py"
        src_file.write_text("def hello(): return 42\n", encoding="utf-8")
        result = _run(
            ["--role", "architect-reviewer", "--stage", "5",
             "--files", str(src_file)],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        file_entry = next(
            (cf for cf in data["context_files"] if cf["path"] == str(src_file)), None
        )
        assert file_entry is not None
        assert "def hello()" in file_entry["content"]

    def test_context_files_have_path_and_content_keys(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        src_file = tmp_path / "a.py"
        src_file.write_text("x = 1\n", encoding="utf-8")
        result = _run(
            ["--role", "architect-reviewer", "--stage", "5",
             "--files", str(src_file)],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        for entry in data["context_files"]:
            assert "path" in entry
            assert "content" in entry

    def test_multiple_files_all_included(self, tmp_path: Path) -> None:
        root = _make_framework(tmp_path)
        f1 = tmp_path / "alpha.py"
        f2 = tmp_path / "beta.py"
        f1.write_text("# alpha\n", encoding="utf-8")
        f2.write_text("# beta\n", encoding="utf-8")
        result = _run(
            ["--role", "debugger", "--stage", "5",
             "--files", str(f1), str(f2)],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        paths = {cf["path"] for cf in data["context_files"]}
        assert str(f1) in paths
        assert str(f2) in paths

    def test_missing_file_in_files_list_warns(self, tmp_path: Path) -> None:
        """A missing --files entry emits a warning on stderr but does not abort."""
        root = _make_framework(tmp_path)
        missing = tmp_path / "does_not_exist.py"
        result = _run(
            ["--role", "architect-reviewer", "--stage", "5",
             "--files", str(missing)],
            framework_root=root,
        )
        assert result.returncode == 0
        assert "warning" in result.stderr.lower() or "not found" in result.stderr.lower()
        # Missing file is NOT in context_files
        data = json.loads(result.stdout)
        paths = [cf["path"] for cf in data["context_files"]]
        assert str(missing) not in paths

    def test_empty_files_list_produces_empty_context_files(
        self, tmp_path: Path
    ) -> None:
        """Stage 5 with no --files and no --sprint-plan yields empty context_files."""
        root = _make_framework(tmp_path)
        result = _run(
            ["--role", "debugger", "--stage", "5"],
            framework_root=root,
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert data["context_files"] == []


# ---------------------------------------------------------------------------
# SDA_FRAMEWORK_ROOT env var
# ---------------------------------------------------------------------------

class TestSdaFrameworkRootEnvVar:
    def test_env_var_used_when_framework_root_arg_omitted(self, tmp_path: Path) -> None:
        """SDA_FRAMEWORK_ROOT env var is used to find the framework when --framework-root is omitted."""
        root = _make_framework(tmp_path)
        cmd = [sys.executable, str(SCRIPT), "--role", "architect-reviewer", "--stage", "5"]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            env={**os.environ, "SDA_FRAMEWORK_ROOT": str(root)},
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        assert data["role"] == "architect-reviewer"
        assert "# Role: Architect Reviewer" in data["system_prompt"]

    def test_invalid_env_var_falls_through_to_walkup(self, tmp_path: Path) -> None:
        """An SDA_FRAMEWORK_ROOT pointing to a dir without roles/ and practices/ is ignored."""
        bad_fw = tmp_path / "bad_framework"
        bad_fw.mkdir()
        cmd = [sys.executable, str(SCRIPT), "--role", "architect-reviewer", "--stage", "5"]
        result = subprocess.run(
            cmd,
            capture_output=True, text=True,
            env={**os.environ, "SDA_FRAMEWORK_ROOT": str(bad_fw)},
        )
        # Should not crash with a Python traceback regardless of walk-up outcome
        assert "Traceback" not in result.stderr

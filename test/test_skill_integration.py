"""
Integration tests for the Self-Developing Agents Framework skills.

Tests the end-to-end flow: create sprint plan → gather review context →
parse findings → update docs. Uses the real framework files (role definitions,
templates, practices) rather than mocks.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Locate the framework root (parent of test/)
FRAMEWORK_ROOT = Path(__file__).parent.parent
SKILLS_DIR = FRAMEWORK_ROOT / "skills"


def run_script(script_path: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script_path), *args],
        capture_output=True,
        text=True,
        input=stdin,
    )


# ---------------------------------------------------------------------------
# gather-context uses real role files
# ---------------------------------------------------------------------------


class TestGatherContextWithRealRoles:
    """Verify gather-context.py works with the actual role files in the framework."""

    SCRIPT = SKILLS_DIR / "dev-critique" / "scripts" / "gather-context.py"

    @pytest.mark.parametrize("role", [
        "architect-reviewer",
        "code-reviewer",
        "debugger",
        "security-auditor",
        "performance-reviewer",
        "researcher",
        "analyzer",
        "plan-architect",
        "test-enforcer",
    ])
    def test_reads_all_role_files(self, role: str, tmp_path: Path) -> None:
        """Every role file in the framework can be loaded by gather-context.py."""
        # Create a dummy file to include as context
        dummy = tmp_path / "dummy.py"
        dummy.write_text("pass\n")

        result = run_script(
            self.SCRIPT,
            "--role", role,
            "--stage", "5",
            "--files", str(dummy),
            "--framework-root", str(FRAMEWORK_ROOT),
        )
        assert result.returncode == 0, f"Failed for role {role}: {result.stderr}"

        data = json.loads(result.stdout)
        assert data["role"] == role
        assert data["stage"] == 5
        assert len(data["system_prompt"]) > 50, f"System prompt too short for {role}"
        assert data["isolation_verified"] is True

    def test_stage_5_isolation_blocks_sprint_plan(self, tmp_path: Path) -> None:
        """Stage 5 with --sprint-plan exits 1 (isolation enforcement)."""
        dummy = tmp_path / "dummy.py"
        dummy.write_text("pass\n")
        plan = tmp_path / "plan.md"
        plan.write_text("# Plan\n")

        result = run_script(
            self.SCRIPT,
            "--role", "architect-reviewer",
            "--stage", "5",
            "--sprint-plan", str(plan),
            "--files", str(dummy),
            "--framework-root", str(FRAMEWORK_ROOT),
        )
        assert result.returncode == 1, "Should block sprint plan at Stage 5"

    def test_stage_3_includes_sprint_plan(self, tmp_path: Path) -> None:
        """Stage 3 with --sprint-plan includes plan content in output."""
        dummy = tmp_path / "dummy.py"
        dummy.write_text("pass\n")
        plan = tmp_path / "plan.md"
        plan.write_text("# My Sprint Plan\nGoal: test something\n")

        result = run_script(
            self.SCRIPT,
            "--role", "architect-reviewer",
            "--stage", "3",
            "--sprint-plan", str(plan),
            "--files", str(dummy),
            "--framework-root", str(FRAMEWORK_ROOT),
        )
        assert result.returncode == 0, result.stderr
        data = json.loads(result.stdout)
        # Sprint plan should appear in context_files
        plan_contents = [f["content"] for f in data["context_files"] if "plan" in f["path"].lower()]
        assert any("My Sprint Plan" in c for c in plan_contents), "Sprint plan content should be in context"


# ---------------------------------------------------------------------------
# parse-findings with real example file
# ---------------------------------------------------------------------------


class TestParseFindingsWithRealExample:
    """Verify parse-findings.py can handle the framework's own example_self_critique.md."""

    SCRIPT = SKILLS_DIR / "dev-critique" / "scripts" / "parse-findings.py"
    EXAMPLE = FRAMEWORK_ROOT / "examples" / "example_self_critique.md"

    def test_parses_real_example_file(self) -> None:
        """The example_self_critique.md file produces reasonable structured output."""
        assert self.EXAMPLE.exists(), f"Example file not found at {self.EXAMPLE}"
        content = self.EXAMPLE.read_text()

        result = run_script(self.SCRIPT, stdin=content)
        assert result.returncode == 0, result.stderr

        data = json.loads(result.stdout)
        assert data["total_issues"] > 0, "Expected findings in example file"
        assert data["critical"] + data["high"] + data["medium"] + data["low"] == data["total_issues"]
        assert data["parse_confidence"] in ("high", "medium", "low")
        assert isinstance(data["findings"], list)
        assert len(data["findings"]) == data["total_issues"]

    def test_example_has_mixed_severities(self) -> None:
        """The real example file contains multiple severity levels."""
        content = self.EXAMPLE.read_text()
        result = run_script(self.SCRIPT, stdin=content)
        data = json.loads(result.stdout)

        # The example should have findings across multiple severity levels
        severities_found = set()
        for f in data["findings"]:
            severities_found.add(f["severity"])
        assert len(severities_found) >= 2, f"Expected 2+ severity levels, got {severities_found}"


# ---------------------------------------------------------------------------
# create-plan → update-docs round trip
# ---------------------------------------------------------------------------


class TestSprintLifecycleRoundTrip:
    """Test creating a sprint plan then marking it complete."""

    CREATE_SCRIPT = SKILLS_DIR / "dev-sprint" / "scripts" / "create-plan.py"
    UPDATE_SCRIPT = SKILLS_DIR / "dev-sprint" / "scripts" / "update-docs.py"

    def test_create_then_complete_sprint(self, tmp_path: Path) -> None:
        """Create a sprint plan, then mark it complete in PROGRESS.md."""
        sprints_dir = tmp_path / "workspace" / "sprints"
        sprints_dir.mkdir(parents=True)

        # Create sprint plan
        result = run_script(
            self.CREATE_SCRIPT,
            "--sprint-id", "SP_001",
            "--goal", "Foundation Setup",
            "--output-dir", str(sprints_dir),
            "--template", str(FRAMEWORK_ROOT / "templates" / "SPRINT_PLAN.md"),
        )
        assert result.returncode == 0, result.stderr
        create_data = json.loads(result.stdout)
        assert create_data["sprint_id"] == "SP_001"
        plan_path = Path(create_data["file_path"])
        assert plan_path.exists()

        # Create a PROGRESS.md with this sprint as active
        progress = tmp_path / "PROGRESS.md"
        progress.write_text(
            "# Development Progress\n\n"
            "## Active Sprint\n\n"
            "**Current:** SP_001\n\n"
            "## Sprint History\n\n"
        )

        # Mark sprint complete
        result = run_script(
            self.UPDATE_SCRIPT,
            "--sprint-id", "SP_001",
            "--status", "complete",
            "--summary", "Set up project foundation with auth and tests",
            "--tests-added", "42",
            "--progress-file", str(progress),
        )
        assert result.returncode == 0, result.stderr
        update_data = json.loads(result.stdout)
        assert update_data["status"] == "complete"

        # Verify PROGRESS.md was updated
        content = progress.read_text()
        assert "SP_001" in content
        assert "complete" in content.lower() or "Complete" in content

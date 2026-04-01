#!/usr/bin/env python3
"""Day 1 workspace setup for the Self-Developing Agents Framework.

Automates Steps 2–5 of BOOTSTRAP.md: creates directories, copies templates,
practices, validators, and workspace behavioural files into the target project.

Usage:
    python bootstrap.py --action setup  --project-root /path/to/project
    python bootstrap.py --action verify --project-root /path/to/project
    python bootstrap.py --action setup  --project-root /path/to/project --skip-validation

Exit codes:
    0 — success
    1 — partial / verify-fail (setup done but validation had warnings)
    2 — fatal (cannot create directories or copy files)
    3 — configuration (framework root not found)
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Framework-root detection
# ---------------------------------------------------------------------------

_FRAMEWORK_MARKERS = ("roles", "practices")


def _find_framework_root(start: Path) -> Path | None:
    """Walk upward from *start* looking for a directory that has both
    ``roles/`` and ``practices/`` subdirectories — the framework root.
    """
    # 1. Environment variable (set by the platform or install.sh at install time)
    env_root = os.environ.get("SDA_FRAMEWORK_ROOT")
    if env_root:
        candidate = Path(env_root).resolve()
        if all((candidate / marker).is_dir() for marker in _FRAMEWORK_MARKERS):
            return candidate
    # 2. Walk-up heuristic (works during development)
    candidate = start.resolve()
    # Walk up at most 10 levels to avoid runaway traversal
    for _ in range(10):
        if all((candidate / marker).is_dir() for marker in _FRAMEWORK_MARKERS):
            return candidate
        parent = candidate.parent
        if parent == candidate:
            break  # reached filesystem root
        candidate = parent
    return None


# ---------------------------------------------------------------------------
# Directory and file operations
# ---------------------------------------------------------------------------

_REQUIRED_DIRS = [
    "workspace",
    "workspace/sprints",
    "test/unit",
    "test/integration",
    "test/fixtures",
]

_WORKSPACE_EXPECTED_FILES = [
    "workspace/AGENTS.md",
    "workspace/HEARTBEAT.md",
    "workspace/MEMORY.md",
]

_VERIFY_DIRS = [
    "workspace",
    "workspace/sprints",
    "test/unit",
    "test/integration",
    "test/fixtures",
    "validators",
]


def _create_directories(project_root: Path) -> list[str]:
    """Create the required directory structure under *project_root*.

    Returns a list of relative path strings for each directory that was
    newly created (already-existing directories are silently skipped).
    """
    created: list[str] = []
    for rel in _REQUIRED_DIRS:
        target = project_root / rel
        if not target.exists():
            target.mkdir(parents=True, exist_ok=True)
            created.append(rel + "/")
        else:
            created.append(rel + "/")  # report all dirs, even pre-existing
    return created


def _copy_templates(framework_root: Path, project_root: Path) -> int:
    """Copy all *.md files from ``templates/`` into ``workspace/``.

    Returns the number of files copied.
    """
    src_dir = framework_root / "templates"
    dest_dir = project_root / "workspace"
    dest_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for src_file in sorted(src_dir.glob("*.md")):
        shutil.copy2(src_file, dest_dir / src_file.name)
        count += 1
    return count


def _copy_practices(framework_root: Path, project_root: Path) -> int:
    """Copy all ``GL-*.md`` files from ``practices/`` into ``workspace/``.

    Returns the number of files copied.
    """
    src_dir = framework_root / "practices"
    dest_dir = project_root / "workspace"
    dest_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for src_file in sorted(src_dir.glob("GL-*.md")):
        shutil.copy2(src_file, dest_dir / src_file.name)
        count += 1
    return count


def _copy_validators(framework_root: Path, project_root: Path) -> int:
    """Copy the entire ``validators/`` directory into the project root.

    If ``<project_root>/validators/`` already exists it is removed first so
    that the copy is always a clean snapshot (idempotent).

    Returns the number of files copied.
    """
    src_dir = framework_root / "validators"
    dest_dir = project_root / "validators"

    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    shutil.copytree(src_dir, dest_dir)

    # Count copied files (exclude __pycache__ entries)
    return sum(
        1
        for p in dest_dir.rglob("*")
        if p.is_file() and "__pycache__" not in str(p)
    )


def _copy_workspace_templates(framework_root: Path, project_root: Path) -> int:
    """Copy AGENTS.md, HEARTBEAT.md, MEMORY.md from the skill's templates/.

    Returns the number of files copied.
    """
    src_dir = framework_root / "skills" / "dev-bootstrap" / "templates"
    dest_dir = project_root / "workspace"
    dest_dir.mkdir(parents=True, exist_ok=True)

    names = ("AGENTS.md", "HEARTBEAT.md", "MEMORY.md")
    count = 0
    for name in names:
        src_file = src_dir / name
        if src_file.is_file():
            shutil.copy2(src_file, dest_dir / name)
            count += 1
    return count


_GITIGNORE_CONTENT = """\
.env
*.key
*.pem
credentials*
__pycache__/
.pytest_cache/
*.pyc
.pre_impl_passed
"""


def _create_gitignore(project_root: Path) -> None:
    """Create a ``.gitignore`` at *project_root* if one does not already exist."""
    target = project_root / ".gitignore"
    if not target.exists():
        target.write_text(_GITIGNORE_CONTENT, encoding="utf-8")


# ---------------------------------------------------------------------------
# Validation runner
# ---------------------------------------------------------------------------


def _run_validation(project_root: Path) -> str:
    """Run ``validators/run_all.py --bootstrap`` inside *project_root*.

    Returns one of: "passed", "warnings", "skipped".
    """
    validator = project_root / "validators" / "run_all.py"
    if not validator.is_file():
        return "warnings"

    result = subprocess.run(
        [sys.executable, str(validator), str(project_root), "--bootstrap"],
        capture_output=True,
        text=True,
    )
    return "passed" if result.returncode == 0 else "warnings"


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def _action_setup(
    project_root: Path,
    framework_root: Path,
    skip_validation: bool,
) -> tuple[int, dict]:
    """Execute the ``setup`` action.

    Returns (exit_code, result_dict).
    """
    try:
        dirs_created = _create_directories(project_root)

        files_copied = 0
        files_copied += _copy_templates(framework_root, project_root)
        files_copied += _copy_practices(framework_root, project_root)
        files_copied += _copy_validators(framework_root, project_root)
        files_copied += _copy_workspace_templates(framework_root, project_root)

        _create_gitignore(project_root)
    except OSError as exc:
        result = {
            "status": "fatal",
            "error": str(exc),
        }
        return 2, result

    if skip_validation:
        validation_result = "skipped"
        exit_code = 0
    else:
        validation_result = _run_validation(project_root)
        exit_code = 0 if validation_result == "passed" else 1

    return exit_code, {
        "status": "setup_complete",
        "dirs_created": dirs_created,
        "files_copied": files_copied,
        "validation_result": validation_result,
    }


def _action_verify(project_root: Path) -> tuple[int, dict]:
    """Execute the ``verify`` action.

    Returns (exit_code, result_dict).
    """
    missing: list[str] = []

    for rel in _VERIFY_DIRS:
        if not (project_root / rel).is_dir():
            missing.append(rel)

    for rel in _WORKSPACE_EXPECTED_FILES:
        if not (project_root / rel).is_file():
            missing.append(rel)

    if missing:
        return 1, {"status": "incomplete", "missing": missing}

    return 0, {"status": "ok", "missing": []}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Bootstrap or verify a Self-Developing Agents project workspace.",
    )
    parser.add_argument(
        "--action",
        choices=["setup", "verify"],
        required=True,
        help="'setup' creates the workspace; 'verify' checks an existing one.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        required=True,
        help="Target project root directory.",
    )
    parser.add_argument(
        "--framework-root",
        type=Path,
        default=None,
        help="Path to the Self-Developing Agents Framework (auto-detected if omitted).",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        default=False,
        help="Skip running validators/run_all.py after setup.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    # --- Resolve framework root ---
    if args.framework_root is not None:
        framework_root = args.framework_root.resolve()
        if not framework_root.is_dir():
            _fatal_exit(
                3,
                f"Framework root not found: {framework_root}",
            )
    else:
        # Auto-detect by walking up from this script's location
        framework_root = _find_framework_root(Path(__file__).parent)
        if framework_root is None:
            _fatal_exit(
                3,
                "Could not auto-detect framework root. "
                "Pass --framework-root explicitly.",
            )

    project_root = args.project_root.resolve()

    # --- Dispatch ---
    if args.action == "setup":
        exit_code, result = _action_setup(
            project_root=project_root,
            framework_root=framework_root,
            skip_validation=args.skip_validation,
        )
    else:  # verify
        exit_code, result = _action_verify(project_root=project_root)

    print(json.dumps(result, indent=2))
    sys.exit(exit_code)


def _fatal_exit(code: int, message: str) -> None:
    """Print an error JSON to stdout and exit with *code*."""
    print(json.dumps({"status": "error", "message": message}, indent=2))
    sys.exit(code)


if __name__ == "__main__":
    main()

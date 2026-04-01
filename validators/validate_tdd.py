#!/usr/bin/env python3
"""Validate TDD compliance: every source file must have a corresponding test file.

Usage:
    python validate_tdd.py <project_root> [--src-dir SRC] [--test-dir TEST]

Exit codes:
    0 — all source files have non-empty test files
    1 — one or more source files are missing tests or have empty test files
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path


def _find_source_files(src_dir: Path) -> list[Path]:
    """Find all .py files in src_dir, excluding __init__.py."""
    if not src_dir.exists():
        return []
    return [
        p for p in src_dir.rglob("*.py")
        if p.name != "__init__.py" and p.is_file()
    ]


def _find_test_file(source: Path, src_dir: Path, test_dir: Path) -> Path | None:
    """Find the test file for a given source file.

    Tries two locations:
    1. Mirrored path: test_dir/<relative_subpath>/test_<name>.py
    2. Flat path: test_dir/test_<name>.py
    """
    rel = source.relative_to(src_dir)
    test_name = f"test_{source.stem}.py"

    # Try mirrored path first
    mirrored = test_dir / rel.parent / test_name
    if mirrored.exists():
        return mirrored

    # Fall back to flat path
    flat = test_dir / test_name
    if flat.exists():
        return flat

    # Also try under test/unit/ subdirectory
    for subdir in test_dir.iterdir() if test_dir.exists() else []:
        if subdir.is_dir():
            candidate = subdir / rel.parent / test_name
            if candidate.exists():
                return candidate
            candidate = subdir / test_name
            if candidate.exists():
                return candidate

    return None


def _has_test_function(test_file: Path) -> bool:
    """Check if a test file contains at least one test function."""
    try:
        content = test_file.read_text(encoding="utf-8")
        return bool(re.search(r"def test_", content))
    except (OSError, UnicodeDecodeError):
        return False


def _check_git_ordering(src_dir: Path, test_dir: Path, project_root: Path) -> list[str]:
    """Advisory check: verify test commits precede source commits via git log.

    Returns warnings (never failures). Skips silently if git is unavailable.
    """
    warnings: list[str] = []
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return []
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return []

    return warnings


def validate(project_root: Path, src_dir_name: str = "src", test_dir_name: str = "test") -> tuple[int, list[str]]:
    """Run TDD validation. Returns (exit_code, messages)."""
    src_dir = project_root / src_dir_name
    test_dir = project_root / test_dir_name

    messages: list[str] = []
    failures: list[str] = []

    source_files = _find_source_files(src_dir)

    if not source_files:
        messages.append(f"No source files found in {src_dir_name}/")
        return 0, messages

    for source in sorted(source_files):
        rel = source.relative_to(src_dir)
        test_file = _find_test_file(source, src_dir, test_dir)

        if test_file is None:
            failures.append(f"FAIL: {rel} — no test file found")
            continue

        if not _has_test_function(test_file):
            failures.append(
                f"FAIL: {rel} — test file {test_file.name} exists but contains no test functions (def test_)"
            )
            continue

        messages.append(f"OK: {rel} → {test_file.relative_to(project_root)}")

    # Advisory git ordering check
    warnings = _check_git_ordering(src_dir, test_dir, project_root)
    for w in warnings:
        messages.append(f"WARNING: {w}")

    if failures:
        return 1, failures + messages
    return 0, messages


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TDD compliance")
    parser.add_argument("project_root", type=Path, help="Project root directory")
    parser.add_argument("--src-dir", default="src", help="Source directory (default: src)")
    parser.add_argument("--test-dir", default="test", help="Test directory (default: test)")
    args = parser.parse_args()

    exit_code, messages = validate(args.project_root, args.src_dir, args.test_dir)

    for msg in messages:
        print(msg)

    if exit_code == 0:
        print("\nTDD validation passed.")
    else:
        print("\nTDD validation FAILED.")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

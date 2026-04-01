#!/usr/bin/env python3
"""Orchestrator: run all 5 validators in sequence.

Usage:
    python run_all.py <project_root> [--bootstrap] [--skip NAME[,NAME]] [--fix]

Flags:
    --bootstrap  Run only validate_structure and validate_workspace (Day 1 mode)
    --skip       Comma-separated validator names to skip
    --fix        Create missing required directories before running validators

Exit codes:
    0 — all validators passed
    1 — one or more validators failed
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

# Ordered list of all validators
ALL_VALIDATORS = [
    "validate_structure",
    "validate_workspace",
    "validate_tdd",
    "validate_rdd",
    "validate_sprint",
]

BOOTSTRAP_VALIDATORS = [
    "validate_structure",
    "validate_workspace",
]

DEFAULT_FIX_DIRS = [
    "test/unit",
    "test/integration",
    "test/fixtures",
]


def _get_validators_dir() -> Path:
    """Get the directory containing validator scripts.

    Supports _VALIDATOR_DIR_OVERRIDE env var for testing.
    """
    override = os.environ.get("_VALIDATOR_DIR_OVERRIDE")
    if override:
        return Path(override)
    return Path(__file__).parent


def _run_validator(
    name: str, project_root: Path, validators_dir: Path, env: dict | None = None
) -> int:
    """Run a single validator and return its exit code."""
    script = validators_dir / f"{name}.py"
    if not script.exists():
        print(f"  ERROR: {name}.py not found at {validators_dir}")
        return 1

    result = subprocess.run(
        [sys.executable, str(script), str(project_root)],
        capture_output=True,
        text=True,
        env=env,
    )

    # Print validator output
    if result.stdout.strip():
        for line in result.stdout.strip().split("\n"):
            print(f"  {line}")
    if result.stderr.strip():
        for line in result.stderr.strip().split("\n"):
            print(f"  {line}")

    return result.returncode


def _fix_directories(project_root: Path) -> None:
    """Create missing required directories."""
    for dir_path in DEFAULT_FIX_DIRS:
        full_path = project_root / dir_path
        if not full_path.exists():
            full_path.mkdir(parents=True, exist_ok=True)
            print(f"  Created: {dir_path}/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all validators")
    parser.add_argument("project_root", type=Path, help="Project root directory")
    parser.add_argument("--bootstrap", action="store_true",
                        help="Run only structure and workspace validators (Day 1)")
    parser.add_argument("--skip", type=str, default="",
                        help="Comma-separated validator names to skip")
    parser.add_argument("--fix", action="store_true",
                        help="Create missing required directories before validation")
    args = parser.parse_args()

    validators_dir = _get_validators_dir()
    skip_set = {s.strip() for s in args.skip.split(",") if s.strip()}

    # Determine which validators to run
    if args.bootstrap:
        validators_to_run = BOOTSTRAP_VALIDATORS
    else:
        validators_to_run = ALL_VALIDATORS

    # Apply --skip
    validators_to_run = [v for v in validators_to_run if v not in skip_set]

    # Apply --fix before running validators
    if args.fix:
        print("Fixing missing directories...")
        _fix_directories(args.project_root)
        print()

    # Run validators
    results: dict[str, str] = {}
    has_failures = False

    for name in validators_to_run:
        short = name.replace("validate_", "")
        print(f"Running {name}...")
        exit_code = _run_validator(name, args.project_root, validators_dir)

        if exit_code == 0:
            results[short] = "PASS"
        else:
            results[short] = "FAIL"
            has_failures = True
        print()

    # Print summary
    print("=" * 40)
    print("Validation Summary")
    print("=" * 40)

    for name, status in results.items():
        indicator = "PASS" if status == "PASS" else "FAIL"
        print(f"  {name:<20} {indicator}")

    print()
    if has_failures:
        print("RESULT: FAILED — one or more validators did not pass.")
        sys.exit(1)
    else:
        print("RESULT: ALL PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()

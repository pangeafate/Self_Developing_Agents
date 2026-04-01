#!/usr/bin/env python3
"""deploy-to-agent.py — Safely copy a built skill to a target agent's workspace.

Usage:
    # Normal deploy
    python deploy-to-agent.py \\
        --source-dir /path/to/skill \\
        --target-workspace /path/to/workspace \\
        --skill-name my-skill

    # Dry run — show what would happen without making changes
    python deploy-to-agent.py --source-dir ... --target-workspace ... \\
        --skill-name my-skill --dry-run

    # Rollback — restore from .bak directory
    python deploy-to-agent.py --source-dir ... --target-workspace ... \\
        --skill-name my-skill --rollback

    # Custom config file location
    python deploy-to-agent.py ... --config-file /path/to/openclaw.json

Output: JSON to stdout.

Exit codes:
    0 — deployed successfully (or dry-run completed, or rollback completed)
    1 — validation failed (files did not pass checks)
    2 — fatal error (missing source/target, IO error)
    3 — config error (malformed JSON, failed JSON patch validation)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Permission constants
# ---------------------------------------------------------------------------

_MODE_PY: int = 0o550   # r-xr-x--- for .py files
_MODE_MD: int = 0o440   # r--r----- for .md files


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emit(data: dict) -> None:
    """Print JSON to stdout."""
    print(json.dumps(data))


def _fatal(message: str, exit_code: int = 2, extra: dict | None = None) -> None:
    """Print error JSON and exit with the given code (2=fatal, 3=config)."""
    out = {"status": "error", "error": message}
    if extra:
        out.update(extra)
    _emit(out)
    sys.exit(exit_code)


def _validate_skill_name(name: str) -> None:
    """Reject skill names with path traversal characters."""
    if "/" in name or "\\" in name or ".." in name:
        _fatal(f"Invalid skill name (path traversal): {name}")
    if not name.strip():
        _fatal("Skill name cannot be empty")


def _set_permissions(skill_dir: Path) -> None:
    """Recursively set permissions: .py → 0o550, .md → 0o440."""
    for path in skill_dir.rglob("*"):
        if path.is_file():
            if path.suffix == ".py":
                os.chmod(path, _MODE_PY)
            elif path.suffix == ".md":
                os.chmod(path, _MODE_MD)


# ---------------------------------------------------------------------------
# openclaw.json patching (atomic)
# ---------------------------------------------------------------------------


def _resolve_config_file(target_workspace: Path, config_file: Path | None) -> Path | None:
    """Return the config file path to use, or None if it does not exist."""
    if config_file is not None:
        return config_file
    candidate = target_workspace / "openclaw.json"
    return candidate if candidate.exists() else None


def _patch_openclaw_json(
    config_path: Path,
    skill_name: str,
    *,
    dry_run: bool = False,
) -> bool:
    """Patch openclaw.json to register the skill.

    Uses atomic write: read → patch in memory → validate → write .tmp → rename.

    Returns True if patched (or would patch in dry-run), False if skipped (already registered).
    Exits 3 on malformed JSON. Exits 2 on IO error.
    """
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        _fatal(f"Cannot read {config_path}: {exc}")

    try:
        cfg = json.loads(raw)
    except json.JSONDecodeError as exc:
        _fatal(f"Malformed JSON in {config_path}: {exc}", exit_code=3)

    # Ensure the skills.entries path exists
    cfg.setdefault("skills", {})
    cfg["skills"].setdefault("entries", {})

    entries: dict = cfg["skills"]["entries"]
    if skill_name in entries:
        # Already registered — skip
        return False

    entries[skill_name] = {}

    # Validate the patched structure
    try:
        patched_text = json.dumps(cfg, indent=2)
        json.loads(patched_text)  # final validation
    except (TypeError, json.JSONDecodeError) as exc:
        _fatal(f"Patched JSON failed validation: {exc}", exit_code=3)

    if dry_run:
        return True

    # Atomic write: .tmp → rename
    tmp_path = config_path.with_suffix(".json.tmp")
    try:
        tmp_path.write_text(patched_text, encoding="utf-8")
        tmp_path.replace(config_path)
    except OSError as exc:
        # Clean up .tmp if it exists
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        _fatal(f"Atomic JSON write failed for {config_path}: {exc}")

    return True


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


def _backup_existing_skill(skill_dir: Path, *, dry_run: bool = False) -> bool:
    """Copy skill_dir → skill_dir.bak before overwriting. Returns True if backup was made."""
    bak = skill_dir.parent / (skill_dir.name + ".bak")
    if not skill_dir.exists():
        return False
    if dry_run:
        return True
    if bak.exists():
        shutil.rmtree(bak)
    shutil.copytree(skill_dir, bak)
    return True


# ---------------------------------------------------------------------------
# Rollback
# ---------------------------------------------------------------------------


def _rollback(target_workspace: Path, skill_name: str) -> None:
    """Restore the skill directory from the .bak directory."""
    skills_dir = target_workspace / "skills"
    skill_dir = skills_dir / skill_name
    bak_dir = skills_dir / (skill_name + ".bak")

    if not bak_dir.is_dir():
        _fatal(f"No backup found for skill '{skill_name}' at {bak_dir}")

    if skill_dir.exists():
        shutil.rmtree(skill_dir)
    shutil.copytree(bak_dir, skill_dir)

    _emit(
        {
            "status": "rolled_back",
            "skill_name": skill_name,
            "restored_from": str(bak_dir),
            "deployed_to": str(skill_dir),
            "gateway_restart_needed": True,
        }
    )
    sys.exit(0)


# ---------------------------------------------------------------------------
# Pre-impl lockfile check
# ---------------------------------------------------------------------------


def _check_pre_impl_lockfile(project_root: Path) -> str | None:
    """Return a warning message if lockfile is missing or unreadable, None if OK."""
    lockfile = project_root / ".pre_impl_passed"
    if not lockfile.exists():
        return "Pre-implementation gate was not run (.pre_impl_passed missing)"
    try:
        json.loads(lockfile.read_text())
    except (json.JSONDecodeError, OSError):
        return "Lockfile .pre_impl_passed is unreadable or malformed"
    return None  # OK


# ---------------------------------------------------------------------------
# Project validator runner
# ---------------------------------------------------------------------------


def _run_project_validators(project_root: Path) -> None:
    """Run validators/run_all.py if present. Exit 1 on validator failure."""
    run_all = project_root / "validators" / "run_all.py"
    if not run_all.exists():
        print(
            f"WARNING: Validators not found at {run_all}, skipping validation.",
            file=sys.stderr,
        )
        return

    result = subprocess.run(
        [sys.executable, str(run_all), str(project_root)],
        capture_output=True,
        text=True,
    )
    if result.stdout.strip():
        print(result.stdout, file=sys.stderr)
    if result.stderr.strip():
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        _emit({"status": "blocked", "error": "Deployment blocked: validators failed"})
        sys.exit(1)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_paths(
    source_dir: Path,
    target_workspace: Path,
) -> None:
    """Exit 2 if source or target are missing."""
    if not source_dir.is_dir():
        _fatal(f"Source directory does not exist: {source_dir}")
    if not target_workspace.is_dir():
        _fatal(f"Target workspace does not exist: {target_workspace}")


# ---------------------------------------------------------------------------
# Core deploy
# ---------------------------------------------------------------------------


def _deploy(
    source_dir: Path,
    target_workspace: Path,
    skill_name: str,
    config_file: Path | None,
    *,
    dry_run: bool,
) -> None:
    """Perform the deployment."""
    skills_dir = target_workspace / "skills"
    skill_dir = skills_dir / skill_name

    # 1. Backup existing skill dir (before overwriting)
    backup_made = _backup_existing_skill(skill_dir, dry_run=dry_run)

    # 2. Copy source → target
    if not dry_run:
        if skill_dir.exists():
            shutil.rmtree(skill_dir)
        shutil.copytree(source_dir, skill_dir)
        _set_permissions(skill_dir)

    # 3. Patch openclaw.json
    cfg_path = _resolve_config_file(target_workspace, config_file)
    openclaw_patched: bool
    if cfg_path is None:
        # Missing config — warn and continue
        print(
            f"WARNING: openclaw.json not found in {target_workspace}; skipping skill registration.",
            file=sys.stderr,
        )
        openclaw_patched = False
    else:
        openclaw_patched = _patch_openclaw_json(cfg_path, skill_name, dry_run=dry_run)

    # 4. Emit result
    result: dict = {
        "status": "deployed" if not dry_run else "dry_run",
        "skill_name": skill_name,
        "deployed_to": str(skill_dir),
        "backup_created": backup_made,
        "openclaw_json_patched": openclaw_patched,
        "gateway_restart_needed": True,
    }
    if dry_run:
        result["dry_run"] = True

    _emit(result)
    sys.exit(0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely copy a built skill to a target agent's workspace."
    )
    parser.add_argument(
        "--source-dir",
        required=True,
        type=Path,
        help="Source skill directory to copy from",
    )
    parser.add_argument(
        "--target-workspace",
        required=True,
        type=Path,
        help="Target agent workspace directory",
    )
    parser.add_argument(
        "--skill-name",
        required=True,
        help="Name to register the skill under (used as directory name and config key)",
    )
    parser.add_argument(
        "--config-file",
        default=None,
        type=Path,
        help="Path to openclaw.json (default: <target-workspace>/openclaw.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without making any changes",
    )
    parser.add_argument(
        "--rollback",
        action="store_true",
        help="Restore skill from .bak directory instead of deploying",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        type=Path,
        help="Project root for running validators and lockfile check before deploying",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    source_dir: Path = args.source_dir
    target_workspace: Path = args.target_workspace
    skill_name: str = args.skill_name
    _validate_skill_name(skill_name)
    config_file: Path | None = args.config_file
    dry_run: bool = args.dry_run
    rollback: bool = args.rollback
    project_root: Path | None = args.project_root

    if rollback:
        # Rollback only needs target_workspace to exist
        if not target_workspace.is_dir():
            _fatal(f"Target workspace does not exist: {target_workspace}")
        _rollback(target_workspace, skill_name)
        # _rollback exits internally

    # Pre-flight checks when --project-root is provided
    if project_root is not None:
        project_root = project_root.resolve()
        # Lockfile check (warning only)
        lockfile_warning = _check_pre_impl_lockfile(project_root)
        if lockfile_warning:
            print(f"WARNING: {lockfile_warning}", file=sys.stderr)
        # Run validators (hard fail on non-zero)
        _run_project_validators(project_root)
    else:
        print(
            "WARNING: --project-root not provided; skipping validator run and lockfile check.",
            file=sys.stderr,
        )

    # Normal deploy — validate both paths
    _validate_paths(source_dir, target_workspace)
    _deploy(source_dir, target_workspace, skill_name, config_file, dry_run=dry_run)


if __name__ == "__main__":
    main()

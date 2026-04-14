#!/usr/bin/env python3
"""deploy.py — Pre-deploy validation and git push orchestrator.

Usage:
    # Dry run — validate only
    python deploy.py --action validate --project-root .

    # Full deploy — validate + git add/commit/push
    python deploy.py --action push --project-root . --message "SP_042: Add user auth"

    # Override validators directory
    python deploy.py --action validate --project-root . --validators-dir ./custom_validators/

    # Skip specific validators
    python deploy.py --action push --project-root . --message "fix" --skip-validators validate_rdd

Output: JSON to stdout describing the result.

Exit codes:
    0 — success (validated, or validated + pushed)
    1 — validators failed — deployment blocked
    2 — git error (commit or push failed) or missing --message for push action
    3 — validators directory / run_all.py not found
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


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
# Stage 6 → 7 docs-reconciled gate (per AGENT_INSTRUCTIONS.md Rule 16)
# ---------------------------------------------------------------------------

import re as _re

_ACTIVE_SPRINT_RE = _re.compile(r"\*\*Current:\*\*\s+(SP_\S+)")


def _read_active_sprint(project_root: Path) -> str | None:
    progress = project_root / "PROGRESS.md"
    if not progress.exists():
        return None
    try:
        text = progress.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    m = _ACTIVE_SPRINT_RE.search(text)
    return m.group(1) if m else None


def _check_docs_reconciled_lockfile(project_root: Path) -> str | None:
    """Return failure message string or None on pass.

    Stage 7 (Deployment) requires Stage 6 (Documentation) to have produced a
    valid `.docs_reconciled` lockfile. Verifies:
      1. file exists
      2. parses as JSON
      3. schema_version == 1
      4. sprint_id matches the current active sprint per PROGRESS.md
    Skipped when no active sprint declared (PROGRESS.md absent or no Current marker).
    """
    sprint_id = _read_active_sprint(project_root)
    if sprint_id is None:
        return None  # No active sprint — gate is moot

    lockfile = project_root / ".docs_reconciled"
    # Open with O_NOFOLLOW to atomically refuse symlinks — closes the TOCTOU
    # race between is_symlink() and read_text(). On all POSIX systems
    # O_NOFOLLOW makes the open fail with ELOOP if the final path component
    # is a symlink. Windows does not support O_NOFOLLOW (the flag is undefined),
    # so fall back to a stat-based check there.
    import os as _os
    nofollow = getattr(_os, "O_NOFOLLOW", None)
    try:
        if nofollow is not None:
            fd = _os.open(str(lockfile), _os.O_RDONLY | nofollow)
            try:
                with _os.fdopen(fd, "r", encoding="utf-8") as fh:
                    body = fh.read()
            except Exception:
                _os.close(fd)
                raise
        else:  # pragma: no cover (Windows path)
            if lockfile.is_symlink():
                return ".docs_reconciled is a symlink — refusing to read for safety"
            body = lockfile.read_text(encoding="utf-8")
    except FileNotFoundError:
        return (
            f".docs_reconciled lockfile missing — Stage 6 (Documentation) was not "
            f"completed for active sprint {sprint_id}. Run "
            "'python validators/validate_doc_freshness.py .' before deploy."
        )
    except OSError as exc:
        # ELOOP (40 on Linux, 62 on macOS) means the path is a symlink and
        # O_NOFOLLOW refused to follow it. Catch by errno name not number.
        import errno
        if getattr(exc, "errno", None) == errno.ELOOP:
            return ".docs_reconciled is a symlink — refusing to read for safety"
        return f".docs_reconciled is unreadable: {exc}"
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        return f".docs_reconciled is malformed JSON: {exc}"
    if not isinstance(payload, dict):
        return ".docs_reconciled JSON root is not an object"
    if payload.get("schema_version") != 1:
        return (
            f".docs_reconciled schema_version = {payload.get('schema_version')!r}, "
            "expected 1"
        )
    locked_sprint = payload.get("sprint_id")
    if locked_sprint != sprint_id:
        return (
            f".docs_reconciled is stale: lockfile sprint_id={locked_sprint!r} "
            f"does not match active sprint {sprint_id!r}. Re-run "
            "'python validators/validate_doc_freshness.py .' after Stage 6 reconciliation."
        )
    return None  # Gate passed.


# ---------------------------------------------------------------------------
# Validator discovery
# ---------------------------------------------------------------------------


def _find_run_all(project_root: Path, validators_dir: Path | None) -> Path | None:
    """Locate run_all.py.

    Search order:
      1. Explicit --validators-dir argument (if given)
      2. <project-root>/validators/run_all.py
    """
    if validators_dir is not None:
        candidate = validators_dir / "run_all.py"
        return candidate if candidate.exists() else None

    candidate = project_root / "validators" / "run_all.py"
    return candidate if candidate.exists() else None


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------


def _run_validators(
    project_root: Path,
    validators_dir: Path | None,
    skip_validators: str,
) -> tuple[bool, dict[str, str], str]:
    """Run run_all.py and return (passed, results_dict, raw_output).

    Returns:
        passed: True if exit code 0
        results_dict: simple summary dict for JSON output
        raw_output: combined stdout+stderr from run_all.py
    """
    run_all = _find_run_all(project_root, validators_dir)

    if run_all is None:
        # Signal caller to exit 3
        raise FileNotFoundError("run_all.py not found")

    cmd = [sys.executable, str(run_all), str(project_root)]
    if skip_validators:
        cmd += ["--skip", skip_validators]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    raw = proc.stdout + proc.stderr
    passed = proc.returncode == 0

    # Build a minimal results dict from the run_all output lines (best-effort)
    results: dict[str, str] = _parse_results_from_output(raw)

    return passed, results, raw


def _parse_results_from_output(output: str) -> dict[str, str]:
    """Extract per-validator results from run_all.py summary output (best-effort).

    run_all.py prints lines like:
        structure            PASS
        workspace            PASS
        tdd                  FAIL
    in the summary section. We parse those into a dict.
    Falls back to an empty dict if we cannot parse anything.
    """
    results: dict[str, str] = {}
    for line in output.splitlines():
        stripped = line.strip()
        for status in ("PASS", "FAIL"):
            if stripped.endswith(status):
                name = stripped[: -len(status)].strip()
                if name:
                    results[name] = status
                break
    return results


# ---------------------------------------------------------------------------
# Git operations
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run a git command in cwd and return the CompletedProcess."""
    return subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


_SENSITIVE_PATTERNS = [".env", "*.key", "*.pem", "credentials*", "*.secret"]


def _git_add_all(project_root: Path) -> None:
    """Stage all changes. Warns if .gitignore is missing."""
    gitignore = project_root / ".gitignore"
    if not gitignore.exists():
        print(
            "WARNING: No .gitignore found. git add -A will stage ALL files "
            "including potential secrets (.env, *.key, *.pem). "
            "Create a .gitignore before deploying.",
            file=sys.stderr,
        )
    result = _git(["add", "-A"], cwd=project_root)
    if result.returncode != 0:
        raise RuntimeError(f"git add -A failed:\n{result.stderr}")


def _git_commit(project_root: Path, message: str) -> str:
    """Commit staged changes. Returns the short commit hash."""
    result = _git(["commit", "-m", message], cwd=project_root)
    if result.returncode != 0:
        raise RuntimeError(f"git commit failed:\n{result.stderr}\n{result.stdout}")
    # Parse commit hash from output like "[main abc1234] message"
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("["):
            # format: [branch hash] message
            parts = line.split()
            if len(parts) >= 2:
                return parts[1].rstrip("]")
    # Fallback: read HEAD hash
    ref = _git(["rev-parse", "--short", "HEAD"], cwd=project_root)
    return ref.stdout.strip()


def _count_committed_files(project_root: Path, commit_hash: str) -> int:
    """Count files changed in the given commit."""
    result = _git(
        ["show", "--name-only", "--format=", commit_hash], cwd=project_root
    )
    files = [l for l in result.stdout.splitlines() if l.strip()]
    return len(files)


def _has_remote(project_root: Path) -> bool:
    """Return True if the repo has any configured remotes."""
    result = _git(["remote"], cwd=project_root)
    return bool(result.stdout.strip())


def _git_push(project_root: Path) -> bool:
    """Push to origin. Returns True on success, raises RuntimeError on failure."""
    result = _git(["push"], cwd=project_root)
    if result.returncode != 0:
        raise RuntimeError(f"git push failed:\n{result.stderr}")
    return True


def _has_staged_or_unstaged_changes(project_root: Path) -> bool:
    """Return True if there is anything to commit (staged or unstaged or untracked)."""
    result = _git(["status", "--porcelain"], cwd=project_root)
    return bool(result.stdout.strip())


# ---------------------------------------------------------------------------
# Actions
# ---------------------------------------------------------------------------


def action_validate(
    project_root: Path,
    validators_dir: Path | None,
    skip_validators: str,
) -> None:
    """Run validators and emit JSON. Exits 0/1/3."""
    try:
        passed, results, _raw = _run_validators(project_root, validators_dir, skip_validators)
    except FileNotFoundError as exc:
        output = {
            "status": "error",
            "validators_passed": False,
            "error": str(exc),
        }
        print(json.dumps(output))
        sys.exit(3)

    output = {
        "status": "validated",
        "validators_passed": passed,
        "validator_results": results,
    }
    print(json.dumps(output))
    sys.exit(0 if passed else 1)


def action_push(
    project_root: Path,
    validators_dir: Path | None,
    skip_validators: str,
    message: str,
) -> None:
    """Validate then git commit+push. Exits 0/1/2/3."""
    # --- Pre-impl lockfile check (advisory warning, never hard-fails) ---
    skip_set = {s.strip() for s in skip_validators.split(",") if s.strip()}
    if "validate_sprint" not in skip_set:
        lockfile_warning = _check_pre_impl_lockfile(project_root)
        if lockfile_warning:
            print(f"WARNING: {lockfile_warning}", file=sys.stderr)

    # --- Docs-reconciled lockfile check (HARD GATE per Rule 16, Stage 6→7) ---
    docs_block = _check_docs_reconciled_lockfile(project_root)
    if docs_block is not None:
        output = {
            "status": "blocked",
            "validators_passed": False,
            "error": f"Deployment blocked at Stage 7 by Rule 16: {docs_block}",
        }
        print(json.dumps(output))
        sys.exit(1)

    # --- Validation phase ---
    try:
        passed, results, _raw = _run_validators(project_root, validators_dir, skip_validators)
    except FileNotFoundError as exc:
        output = {
            "status": "error",
            "validators_passed": False,
            "error": str(exc),
        }
        print(json.dumps(output))
        sys.exit(3)

    if not passed:
        output = {
            "status": "blocked",
            "validators_passed": False,
            "validator_results": results,
            "error": "Deployment blocked — one or more validators failed.",
        }
        print(json.dumps(output))
        sys.exit(1)

    # --- Git phase ---
    try:
        _git_add_all(project_root)

        # If nothing to commit, still succeed but note it
        if not _has_staged_or_unstaged_before_commit(project_root):
            output = {
                "status": "pushed",
                "validators_passed": True,
                "validator_results": results,
                "commit_hash": _git(
                    ["rev-parse", "--short", "HEAD"], cwd=project_root
                ).stdout.strip(),
                "files_committed": 0,
                "note": "nothing to commit",
            }
            print(json.dumps(output))
            sys.exit(0)

        commit_hash = _git_commit(project_root, message)
        files_committed = _count_committed_files(project_root, commit_hash)

        push_note: str | None = None
        if _has_remote(project_root):
            _git_push(project_root)
        else:
            push_note = "no remote configured — skipping git push"

        output: dict = {
            "status": "pushed",
            "validators_passed": True,
            "validator_results": results,
            "commit_hash": commit_hash,
            "files_committed": files_committed,
        }
        if push_note:
            output["note"] = push_note

        print(json.dumps(output))
        sys.exit(0)

    except RuntimeError as exc:
        output = {
            "status": "git_error",
            "validators_passed": True,
            "error": str(exc),
        }
        print(json.dumps(output))
        sys.exit(2)


def _has_staged_or_unstaged_before_commit(project_root: Path) -> bool:
    """Return True if git index has something to commit after git add -A."""
    result = _git(["diff", "--cached", "--name-only"], cwd=project_root)
    return bool(result.stdout.strip())


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pre-deploy validation and git push orchestrator."
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=["validate", "push"],
        help="validate (dry run) or push (validate + git commit/push)",
    )
    parser.add_argument(
        "--project-root",
        required=True,
        type=Path,
        help="Project root directory",
    )
    parser.add_argument(
        "--message",
        default=None,
        help="Git commit message (required for --action push)",
    )
    parser.add_argument(
        "--validators-dir",
        default=None,
        type=Path,
        help="Path to validators directory containing run_all.py "
             "(default: <project-root>/validators/)",
    )
    parser.add_argument(
        "--skip-validators",
        default="",
        help="Comma-separated validator names to skip (passed to run_all.py)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    if args.action == "push" and not args.message:
        error = {
            "status": "error",
            "error": "--message is required when --action is 'push'",
        }
        print(json.dumps(error))
        sys.exit(2)

    if args.action == "validate":
        action_validate(
            project_root=args.project_root,
            validators_dir=args.validators_dir,
            skip_validators=args.skip_validators,
        )
    else:  # push
        action_push(
            project_root=args.project_root,
            validators_dir=args.validators_dir,
            skip_validators=args.skip_validators,
            message=args.message,
        )


if __name__ == "__main__":
    main()

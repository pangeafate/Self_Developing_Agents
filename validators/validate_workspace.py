#!/usr/bin/env python3
"""Validate workspace file sizes and scan for credential leaks.

Usage:
    python validate_workspace.py <project_root>

Exit codes:
    0 — all bootstrap files within limits, no credentials found
    1 — a bootstrap file exceeds the hard limit or contains credentials
"""
import argparse
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

WARN_LIMIT = 18_000   # bytes
HARD_LIMIT = 20_000   # bytes

DEFAULT_BOOTSTRAP_FILES = [
    "AGENT_INSTRUCTIONS.md", "AGENT_IDENTITY.md",
]

CREDENTIAL_PATTERNS = [
    re.compile(r"ssh-rsa\s+[A-Za-z0-9+/=]+", re.IGNORECASE),
    re.compile(r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----", re.IGNORECASE),
    re.compile(r"(?:^|[^a-zA-Z])password\s*=", re.IGNORECASE | re.MULTILINE),
]


def _load_config(project_root: Path) -> dict:
    config_path = project_root / ".validators.yml"
    if not config_path.exists():
        return {}
    if yaml is None:
        return {}
    try:
        return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}


def _get_bootstrap_files(config: dict) -> list[str]:
    return config.get("bootstrap_files", DEFAULT_BOOTSTRAP_FILES)


def _check_size(file_path: Path) -> tuple[str | None, str | None]:
    """Check file size in bytes. Returns (error, warning) — at most one is set."""
    content = file_path.read_bytes()
    size = len(content)

    if size >= HARD_LIMIT:
        return (
            f"ERROR: {file_path.name} is {size:,} bytes (hard limit {HARD_LIMIT:,}) — will be truncated!",
            None,
        )
    if size > WARN_LIMIT:
        return (
            None,
            f"WARNING: {file_path.name} is {size:,} bytes (approaching limit {WARN_LIMIT:,}/{HARD_LIMIT:,})",
        )
    return None, None


def _check_credentials(file_path: Path) -> str | None:
    """Scan file for credential patterns. Returns error message or None."""
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None

    for pattern in CREDENTIAL_PATTERNS:
        if pattern.search(content):
            return f"ERROR: {file_path.name} contains credential pattern: {pattern.pattern}"

    return None


def validate(project_root: Path) -> tuple[int, list[str]]:
    """Run workspace validation. Returns (exit_code, messages)."""
    config = _load_config(project_root)
    bootstrap_files = _get_bootstrap_files(config)

    messages: list[str] = []
    has_errors = False

    for filename in bootstrap_files:
        file_path = project_root / filename
        if not file_path.exists():
            messages.append(f"SKIP: {filename} not found (skipping)")
            continue

        # Size check
        error, warning = _check_size(file_path)
        if error:
            messages.append(error)
            has_errors = True
        elif warning:
            messages.append(warning)
        else:
            size = len(file_path.read_bytes())
            messages.append(f"OK: {filename} ({size:,} bytes)")

        # Credential check
        cred_error = _check_credentials(file_path)
        if cred_error:
            messages.append(cred_error)
            has_errors = True

    if has_errors:
        return 1, messages
    return 0, messages


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate workspace file sizes and credentials")
    parser.add_argument("project_root", type=Path, help="Project root directory")
    args = parser.parse_args()

    exit_code, messages = validate(args.project_root)

    for msg in messages:
        print(msg)

    if exit_code == 0:
        print("\nWorkspace validation passed.")
    else:
        print("\nWorkspace validation FAILED.")

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

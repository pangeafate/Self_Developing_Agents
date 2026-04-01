#!/usr/bin/env python3
"""Parse reviewer markdown on stdin and emit structured findings as JSON.

Usage:
    python parse-findings.py [--strict] [--format {json,summary}]

Input:
    Reviewer markdown text on stdin.

Output:
    JSON to stdout (default), or human-readable summary with --format summary.

Exit codes:
    0  — success (findings parsed, or clean iteration confirmed)
    1  — strict mode: output is ambiguous (no findings AND no clean indicators)

Severity markers matched:
    **CRITICAL**, **HIGH**, **MEDIUM**, **LOW**  (bold markdown, case-sensitive)
    Bare words CRITICAL/HIGH/MEDIUM/LOW in prose are intentionally ignored.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from typing import Literal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEVERITY_PATTERN = re.compile(r"\*\*(CRITICAL|HIGH|MEDIUM|LOW)\*\*")

# Recommendation line: *Recommendation*: ... or Recommendation: ...
# Matches the rest of the line after the label, and subsequent indented lines.
RECOMMENDATION_PATTERN = re.compile(
    r"\*?Recommendation\*?:\s*(.+?)(?=\n\s*\n|\Z)",
    re.IGNORECASE | re.DOTALL,
)

# Clean-iteration indicator phrases (case-insensitive)
CLEAN_INDICATORS: list[str] = [
    r"\b0\s+issues?\b",         # "0 issues" / "0 issue"
    r"\bno\s+issues?\s+found\b",  # "no issues found"
    r"\bclean\s+iteration\b",    # "clean iteration" (not bare "clean" which matches prose)
    r"\bzero\s+issues?\b",      # "zero issues"
    r"\bready\s+to\s+deploy\b", # "ready to deploy"
]
CLEAN_PATTERN = re.compile(
    "|".join(CLEAN_INDICATORS),
    re.IGNORECASE,
)

SEVERITY_ORDER = ("CRITICAL", "HIGH", "MEDIUM", "LOW")

ParseConfidence = Literal["high", "medium", "low"]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    severity: str
    description: str
    recommendation: str = ""


@dataclass
class ParseResult:
    findings: list[Finding] = field(default_factory=list)
    clean_iteration: bool = False
    parse_confidence: ParseConfidence = "low"

    @property
    def total_issues(self) -> int:
        return len(self.findings)

    def count(self, severity: str) -> int:
        return sum(1 for f in self.findings if f.severity == severity)

    @property
    def deployment_blocked(self) -> bool:
        return self.count("CRITICAL") > 0 or self.count("HIGH") > 0


# ---------------------------------------------------------------------------
# Parsing logic
# ---------------------------------------------------------------------------

def _extract_description(text_after_marker: str) -> str:
    """Extract the description sentence(s) that follow a severity marker.

    text_after_marker is everything on the same line after **SEVERITY** (and
    the dash/separator that typically follows), plus continuation lines up to
    the next blank line or recommendation label.

    Strategy:
    - Take the rest of the line containing the marker.
    - Optionally extend to include immediately following indented lines
      (continuation of the description paragraph) but stop before a blank
      line or a Recommendation line.
    """
    # Strip leading " — " or " - " separator
    text = re.sub(r"^\s*[—\-]+\s*", "", text_after_marker)

    # Split into lines; collect until blank line or recommendation
    lines = text.splitlines()
    description_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            break
        if re.match(r"\*?Recommendation\*?:", stripped, re.IGNORECASE):
            break
        description_lines.append(stripped)

    return " ".join(description_lines).strip()


def _extract_recommendation(block: str) -> str:
    """Extract recommendation text from a finding block."""
    match = RECOMMENDATION_PATTERN.search(block)
    if not match:
        return ""
    # Collapse whitespace / indentation in multi-line recommendations
    raw = match.group(1).strip()
    # Remove leading asterisks/italic markers from individual lines
    lines = [re.sub(r"^\*+\s*", "", ln.strip()) for ln in raw.splitlines()]
    return " ".join(ln for ln in lines if ln).strip()


def _split_into_blocks(text: str) -> list[tuple[str, int]]:
    """Return a list of (block_text, start_pos) for each severity marker found.

    Each block runs from the marker to the next marker (or end of string).
    The block_text includes the line containing the marker plus all lines up
    to (but not including) the next marker line.
    """
    matches = list(SEVERITY_PATTERN.finditer(text))
    if not matches:
        return []

    blocks: list[tuple[str, int]] = []
    for i, match in enumerate(matches):
        # Find the start of the line containing this marker
        line_start = text.rfind("\n", 0, match.start())
        line_start = 0 if line_start == -1 else line_start + 1

        # End of block = start of next marker's line, or end of text
        if i + 1 < len(matches):
            next_match = matches[i + 1]
            next_line_start = text.rfind("\n", 0, next_match.start())
            next_line_start = 0 if next_line_start == -1 else next_line_start + 1
            block_text = text[line_start:next_line_start]
        else:
            block_text = text[line_start:]

        blocks.append((block_text, match.start()))

    return blocks


def _extract_text_after_marker(block: str, severity: str) -> str:
    """Return text on the marker's line, after the **SEVERITY** token."""
    marker = f"**{severity}**"
    # Find the marker in the first line of the block
    first_newline = block.find("\n")
    first_line = block[:first_newline] if first_newline != -1 else block
    rest_of_block = block[first_newline:] if first_newline != -1 else ""

    idx = first_line.find(marker)
    if idx == -1:
        return block  # fallback: return whole block

    after_marker_on_line = first_line[idx + len(marker):]
    return after_marker_on_line + rest_of_block


def parse_markdown(text: str) -> ParseResult:
    """Parse reviewer markdown and return a ParseResult."""
    result = ParseResult()

    text_stripped = text.strip()

    # --- Detect clean-iteration indicators ---
    if text_stripped and CLEAN_PATTERN.search(text_stripped):
        result.clean_iteration = True

    # --- Extract findings from bold severity markers ---
    blocks = _split_into_blocks(text)

    for block_text, _pos in blocks:
        # Identify which severity keyword is in this block
        sev_match = SEVERITY_PATTERN.search(block_text)
        if not sev_match:
            continue
        severity = sev_match.group(1)

        # Text after the **SEVERITY** marker on the same line + continuation
        after_marker = _extract_text_after_marker(block_text, severity)

        description = _extract_description(after_marker)
        recommendation = _extract_recommendation(block_text)

        result.findings.append(Finding(
            severity=severity,
            description=description,
            recommendation=recommendation,
        ))

    # --- Determine parse confidence ---
    marker_count = len(result.findings)
    if marker_count >= 3:
        result.parse_confidence = "high"
    elif marker_count >= 1:
        result.parse_confidence = "medium"
    else:
        # 0 markers: low if text is non-empty, else still low (empty = no info)
        result.parse_confidence = "low"

    # --- Guard: findings override clean_iteration ---
    # If actual findings were found, clean_iteration is false regardless of
    # clean-phrase detection (prevents contradictory clean+blocked state).
    if result.total_issues > 0:
        result.clean_iteration = False

    return result


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------

def _to_dict(result: ParseResult) -> dict:
    return {
        "total_issues": result.total_issues,
        "critical": result.count("CRITICAL"),
        "high": result.count("HIGH"),
        "medium": result.count("MEDIUM"),
        "low": result.count("LOW"),
        "clean_iteration": result.clean_iteration,
        "findings": [
            {
                "severity": f.severity,
                "description": f.description,
                "recommendation": f.recommendation,
            }
            for f in result.findings
        ],
        "deployment_blocked": result.deployment_blocked,
        "parse_confidence": result.parse_confidence,
    }


def _format_json(result: ParseResult) -> str:
    return json.dumps(_to_dict(result), indent=2)


def _format_summary(result: ParseResult) -> str:
    lines: list[str] = []
    lines.append("=== Parse Findings Summary ===")
    lines.append(f"Total issues:        {result.total_issues}")
    lines.append(f"  CRITICAL:          {result.count('CRITICAL')}")
    lines.append(f"  HIGH:              {result.count('HIGH')}")
    lines.append(f"  MEDIUM:            {result.count('MEDIUM')}")
    lines.append(f"  LOW:               {result.count('LOW')}")
    lines.append(f"Clean iteration:     {result.clean_iteration}")
    lines.append(f"Deployment blocked:  {result.deployment_blocked}")
    lines.append(f"Parse confidence:    {result.parse_confidence}")

    if result.findings:
        lines.append("")
        lines.append("Findings:")
        for i, finding in enumerate(result.findings, start=1):
            lines.append(f"  {i}. [{finding.severity}] {finding.description}")
            if finding.recommendation:
                lines.append(f"     -> {finding.recommendation}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Parse reviewer markdown findings into structured JSON.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 if output is ambiguous (no findings and no clean indicators).",
    )
    parser.add_argument(
        "--format",
        choices=["json", "summary"],
        default="json",
        help="Output format: 'json' (default) or 'summary' (human-readable text).",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    text = sys.stdin.read()
    result = parse_markdown(text)

    # --- Output ---
    if args.format == "summary":
        print(_format_summary(result))
    else:
        print(_format_json(result))

    # --- Exit code ---
    if args.strict:
        text_stripped = text.strip()
        has_findings = result.total_issues > 0
        has_clean = result.clean_iteration
        is_ambiguous = (not has_findings) and (not has_clean)
        if is_ambiguous:
            sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()

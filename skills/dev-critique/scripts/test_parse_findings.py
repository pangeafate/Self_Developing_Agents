#!/usr/bin/env python3
"""Tests for parse-findings.py — reviewer markdown → structured JSON.

Runs the script as a subprocess, piping stdin, and asserts on stdout/exit code.
This matches the canonical subprocess-pattern from validate_structure.py.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Absolute path to the script under test — never rely on cwd.
SCRIPT = Path(__file__).parent / "parse-findings.py"
EXAMPLE_FILE = (
    Path(__file__).parent.parent.parent.parent  # SELF_DEVELOPING_AGENTS/
    / "examples"
    / "example_self_critique.md"
)

PYTHON = sys.executable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(
    stdin: str,
    args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the script with the given stdin text and optional extra args."""
    cmd = [PYTHON, str(SCRIPT)] + (args or [])
    return subprocess.run(
        cmd,
        input=stdin,
        capture_output=True,
        text=True,
    )


def _json(result: subprocess.CompletedProcess[str]) -> dict:
    """Parse stdout as JSON, raising AssertionError with context on failure."""
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"stdout is not valid JSON: {exc!r}\nstdout={result.stdout!r}\nstderr={result.stderr!r}"
        ) from exc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FULL_REVIEW = """\
## Iteration 1: Architect-Reviewer

1. **CRITICAL** — No rate limiting on dispatch. Fires too many emails in a loop.

   *Recommendation*: Add a NotificationBatch with max_per_minute throttling.

2. **HIGH** — Deployment ordering risk. Migration must run before code deploy.

   *Recommendation*: Add explicit deployment order section.

3. **HIGH** — Unbounded query in weekly summary. Could time out for large users.

   *Recommendation*: Cap at WEEKLY_SUMMARY_MAX_ITEMS = 100.

4. **MEDIUM** — No user preference model. All notifications sent to all users.

   *Recommendation*: Document as out-of-scope, plan for SP_056.

5. **LOW** — Test file naming inconsistency. Wrong convention used.

   *Recommendation*: Rename to test_notification_delivery.py.
"""

CLEAN_REVIEW_ZERO_ISSUES = """\
## Review Complete

Found 0 issues. The implementation is correct and all edge cases are covered.
"""

CLEAN_REVIEW_CLEAN_WORD = """\
## Review Complete

This is a clean iteration. No problems were found.
"""

CLEAN_REVIEW_READY = """\
The code is ready to deploy. No issues found.
"""

BARE_WORDS_ONLY = """\
This task is CRITICAL to our mission. The HIGH priority work must be done.
MEDIUM urgency items should also be addressed when LOW on time.
"""

TWO_MARKERS_REVIEW = """\
1. **HIGH** — Missing validation on user input.

   *Recommendation*: Add input schema validation.

2. **MEDIUM** — Unused import in module.

   *Recommendation*: Remove import os.
"""

ONE_MARKER_REVIEW = """\
1. **LOW** — Minor naming inconsistency found.

   *Recommendation*: Rename function to follow convention.
"""

MIXED_FORMAT = """\
## Findings

- **HIGH** — First bullet finding. Missing error handling in payment path.
  Recommendation: Add try/except around charge call.

1. **MEDIUM** — Numbered finding. No logging on failure path.
   Recommendation: Add logger.error() call.

**LOW** — Inline finding with no list marker.
"""


# ---------------------------------------------------------------------------
# Basic parsing
# ---------------------------------------------------------------------------

class TestParsesBoldSeverityFormat:
    def test_parses_bold_severity_format(self) -> None:
        """Bold **CRITICAL**, **HIGH** etc. are matched; bare words are not."""
        result = _run(FULL_REVIEW)
        assert result.returncode == 0
        data = _json(result)
        assert data["critical"] == 1
        assert data["high"] == 2
        assert data["medium"] == 1
        assert data["low"] == 1

    def test_counts_by_severity_correctly(self) -> None:
        result = _run(FULL_REVIEW)
        data = _json(result)
        assert data["total_issues"] == 5
        assert data["critical"] + data["high"] + data["medium"] + data["low"] == data["total_issues"]

    def test_does_not_match_bare_severity_words(self) -> None:
        """Bare words CRITICAL/HIGH/MEDIUM/LOW without bold markers must not match."""
        result = _run(BARE_WORDS_ONLY)
        assert result.returncode == 0
        data = _json(result)
        assert data["total_issues"] == 0
        assert data["critical"] == 0
        assert data["high"] == 0
        assert data["medium"] == 0
        assert data["low"] == 0


# ---------------------------------------------------------------------------
# Clean iteration detection
# ---------------------------------------------------------------------------

class TestCleanIterationDetection:
    def test_clean_iteration_detected_clean_word(self) -> None:
        result = _run(CLEAN_REVIEW_CLEAN_WORD)
        data = _json(result)
        assert data["clean_iteration"] is True

    def test_clean_iteration_zero_issues_text(self) -> None:
        """'Found 0 issues' and 'no issues found' both trigger clean_iteration."""
        for text in [CLEAN_REVIEW_ZERO_ISSUES, "no issues found in this review"]:
            result = _run(text)
            data = _json(result)
            assert data["clean_iteration"] is True, f"Expected clean for: {text!r}"

    def test_clean_iteration_ready_to_deploy(self) -> None:
        result = _run(CLEAN_REVIEW_READY)
        data = _json(result)
        assert data["clean_iteration"] is True

    def test_clean_iteration_false_when_issues_present(self) -> None:
        result = _run(FULL_REVIEW)
        data = _json(result)
        assert data["clean_iteration"] is False

    def test_zero_issues_phrase_detected(self) -> None:
        """'zero issues' phrase triggers clean_iteration."""
        result = _run("After analysis, I found zero issues. Everything is correct.")
        data = _json(result)
        assert data["clean_iteration"] is True


# ---------------------------------------------------------------------------
# Deployment blocked logic
# ---------------------------------------------------------------------------

class TestDeploymentBlocked:
    def test_deployment_blocked_on_critical(self) -> None:
        review = "1. **CRITICAL** — Fatal flaw found.\n\n   *Recommendation*: Fix immediately.\n"
        result = _run(review)
        data = _json(result)
        assert data["deployment_blocked"] is True

    def test_deployment_blocked_on_high(self) -> None:
        result = _run(TWO_MARKERS_REVIEW)
        data = _json(result)
        assert data["deployment_blocked"] is True

    def test_deployment_not_blocked_on_medium_only(self) -> None:
        review = "1. **MEDIUM** — Minor issue.\n\n   *Recommendation*: Fix later.\n"
        result = _run(review)
        data = _json(result)
        assert data["deployment_blocked"] is False

    def test_deployment_not_blocked_on_low_only(self) -> None:
        result = _run(ONE_MARKER_REVIEW)
        data = _json(result)
        assert data["deployment_blocked"] is False

    def test_deployment_not_blocked_on_clean(self) -> None:
        result = _run(CLEAN_REVIEW_ZERO_ISSUES)
        data = _json(result)
        assert data["deployment_blocked"] is False


# ---------------------------------------------------------------------------
# Findings content extraction
# ---------------------------------------------------------------------------

class TestFindingsExtraction:
    def test_extracts_description_text(self) -> None:
        """Each finding dict must have a non-empty 'description' key."""
        result = _run(FULL_REVIEW)
        data = _json(result)
        for finding in data["findings"]:
            assert "description" in finding
            assert finding["description"].strip() != ""

    def test_extracts_recommendation_text(self) -> None:
        """Findings with *Recommendation*: lines must populate 'recommendation'."""
        result = _run(FULL_REVIEW)
        data = _json(result)
        # Full review has recommendations for every finding
        findings_with_recs = [f for f in data["findings"] if f.get("recommendation", "").strip()]
        assert len(findings_with_recs) >= 3  # at minimum the first three

    def test_severity_field_present_on_each_finding(self) -> None:
        result = _run(FULL_REVIEW)
        data = _json(result)
        for finding in data["findings"]:
            assert finding["severity"] in {"CRITICAL", "HIGH", "MEDIUM", "LOW"}

    def test_handles_mixed_format_input(self) -> None:
        """Bullet lists, numbered lists, and inline bold markers all parsed."""
        result = _run(MIXED_FORMAT)
        assert result.returncode == 0
        data = _json(result)
        assert data["total_issues"] == 3
        assert data["high"] == 1
        assert data["medium"] == 1
        assert data["low"] == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_input_returns_zero_findings(self) -> None:
        result = _run("")
        assert result.returncode == 0
        data = _json(result)
        assert data["total_issues"] == 0
        assert data["findings"] == []
        assert data["clean_iteration"] is False
        assert data["deployment_blocked"] is False

    def test_whitespace_only_input(self) -> None:
        result = _run("   \n\n\t  \n")
        assert result.returncode == 0
        data = _json(result)
        assert data["total_issues"] == 0


# ---------------------------------------------------------------------------
# Output format
# ---------------------------------------------------------------------------

class TestOutputFormat:
    def test_output_is_valid_json(self) -> None:
        """Default mode must always emit valid JSON on stdout."""
        result = _run(FULL_REVIEW)
        data = _json(result)  # raises AssertionError on invalid JSON
        # Verify all required top-level keys are present
        required_keys = {
            "total_issues", "critical", "high", "medium", "low",
            "clean_iteration", "findings", "deployment_blocked", "parse_confidence",
        }
        assert required_keys.issubset(data.keys()), (
            f"Missing keys: {required_keys - data.keys()}"
        )

    def test_summary_format_output(self) -> None:
        """--format summary must produce human-readable text, not JSON."""
        result = _run(FULL_REVIEW, args=["--format", "summary"])
        assert result.returncode == 0
        # Must NOT be valid JSON
        try:
            json.loads(result.stdout)
            raise AssertionError("Expected non-JSON summary output, got valid JSON")
        except json.JSONDecodeError:
            pass
        # Should contain severity counts in readable form
        assert "CRITICAL" in result.stdout or "critical" in result.stdout.lower()
        assert "HIGH" in result.stdout or "high" in result.stdout.lower()

    def test_summary_format_shows_findings(self) -> None:
        """--format summary must list individual finding descriptions."""
        result = _run(FULL_REVIEW, args=["--format", "summary"])
        # Each severity keyword should appear in the output
        output_lower = result.stdout.lower()
        assert "critical" in output_lower
        assert "high" in output_lower

    def test_json_format_explicit(self) -> None:
        """--format json must produce the same output as default."""
        r_default = _run(FULL_REVIEW)
        r_json = _run(FULL_REVIEW, args=["--format", "json"])
        assert r_default.returncode == r_json.returncode
        assert _json(r_default) == _json(r_json)


# ---------------------------------------------------------------------------
# Parse confidence
# ---------------------------------------------------------------------------

class TestParseConfidence:
    def test_parse_confidence_high_three_or_more_markers(self) -> None:
        """3+ bold severity markers → parse_confidence = 'high'."""
        result = _run(FULL_REVIEW)  # has 5 markers
        data = _json(result)
        assert data["parse_confidence"] == "high"

    def test_parse_confidence_medium_one_to_two_markers(self) -> None:
        """1–2 bold markers → parse_confidence = 'medium'."""
        result = _run(TWO_MARKERS_REVIEW)  # has 2 markers
        data = _json(result)
        assert data["parse_confidence"] == "medium"

    def test_parse_confidence_medium_one_marker(self) -> None:
        result = _run(ONE_MARKER_REVIEW)  # has 1 marker
        data = _json(result)
        assert data["parse_confidence"] == "medium"

    def test_parse_confidence_low_no_markers_with_text(self) -> None:
        """0 markers but non-empty text → parse_confidence = 'low'."""
        result = _run("This review has no bold markers but does have some prose text.")
        data = _json(result)
        assert data["parse_confidence"] == "low"

    def test_parse_confidence_low_for_bare_word_only_input(self) -> None:
        """Bare severity words without bold must yield confidence 'low'."""
        result = _run(BARE_WORDS_ONLY)
        data = _json(result)
        assert data["parse_confidence"] == "low"


# ---------------------------------------------------------------------------
# Strict mode
# ---------------------------------------------------------------------------

class TestStrictMode:
    def test_strict_mode_exits_1_on_ambiguous(self) -> None:
        """--strict exits 1 when no findings AND no clean indicators."""
        ambiguous = "The code seems mostly fine, nothing jumped out at me."
        result = _run(ambiguous, args=["--strict"])
        assert result.returncode == 1

    def test_strict_mode_exits_0_on_findings(self) -> None:
        """--strict exits 0 when real findings are present."""
        result = _run(FULL_REVIEW, args=["--strict"])
        assert result.returncode == 0

    def test_strict_mode_exits_0_on_clean_iteration(self) -> None:
        """--strict exits 0 when clean indicators present (no findings is OK)."""
        result = _run(CLEAN_REVIEW_ZERO_ISSUES, args=["--strict"])
        assert result.returncode == 0

    def test_strict_mode_empty_input_exits_1(self) -> None:
        """Empty input is ambiguous — --strict must exit 1."""
        result = _run("", args=["--strict"])
        assert result.returncode == 1


# ---------------------------------------------------------------------------
# Real example file
# ---------------------------------------------------------------------------

class TestRealExampleFile:
    def test_real_example_file(self) -> None:
        """Pipe the actual example_self_critique.md through the parser."""
        assert EXAMPLE_FILE.exists(), f"Example file not found: {EXAMPLE_FILE}"
        content = EXAMPLE_FILE.read_text(encoding="utf-8")
        result = _run(content)
        assert result.returncode == 0
        data = _json(result)

        # The example has 2 CRITICAL, 3 HIGH, 4 MEDIUM, 2 LOW across both iterations
        assert data["total_issues"] >= 5, "Expected at least 5 findings"
        assert data["critical"] >= 1, "Expected at least 1 CRITICAL"
        assert data["high"] >= 1, "Expected at least 1 HIGH"
        assert data["deployment_blocked"] is True
        assert data["parse_confidence"] == "high"
        assert len(data["findings"]) == data["total_issues"]

    def test_real_example_findings_have_content(self) -> None:
        """Each finding from the real example must have non-empty description."""
        content = EXAMPLE_FILE.read_text(encoding="utf-8")
        result = _run(content)
        data = _json(result)
        for finding in data["findings"]:
            assert finding["description"].strip() != "", (
                f"Empty description for severity={finding['severity']}"
            )

#!/usr/bin/env python3
"""
Generates a summary of CI results for GitHub Actions.

This script reads test output, coverage data, and accuracy results to create
a markdown summary displayed in the GitHub Actions UI.
"""

import json
from pathlib import Path

# Constants
DIAGNOSTICS_DIR = Path("diagnostics")
COV_FILE = Path("coverage.xml")
ACCURACY_FILE = DIAGNOSTICS_DIR / "accuracy.json"
LINT_FILE = DIAGNOSTICS_DIR / "lint.txt"
TEST_FILE = DIAGNOSTICS_DIR / "test.txt"
EVOLVE_FILE = DIAGNOSTICS_DIR / "evolve.txt"
CHECK = "\u2705"
CROSS = "\u274c"
ENCODING = "utf-8"


def read_file(path: Path) -> str:
    """Read file contents, return empty string if file missing."""
    try:
        return path.read_text()
    except Exception:
        return ""


def extract_coverage(content: str) -> float:
    """Extract coverage percentage from pytest output."""
    try:
        lines = content.splitlines()
        for line in lines:
            if "TOTAL" in line and "%" in line:
                return float(line.split()[-1].strip("%"))
    except Exception:
        pass
    return 0.0


def extract_test_summary(content: str) -> dict:
    """Extract test summary from pytest output."""
    summary = {"passed": 0, "failed": 0, "skipped": 0, "total": 0}
    try:
        lines = content.splitlines()
        for line in lines:
            if "=== short test summary info ===" in line:
                break
            if line.startswith("==") and line.endswith("=="):
                parts = line.strip("=").strip().split()
                if len(parts) >= 2:
                    try:
                        summary["total"] = int(parts[0])
                        for part in parts[1:]:
                            if "passed" in part:
                                summary["passed"] = int(part.split()[0])
                            elif "failed" in part:
                                summary["failed"] = int(part.split()[0])
                            elif "skipped" in part:
                                summary["skipped"] = int(part.split()[0])
                    except Exception:
                        continue
    except Exception:
        pass
    return summary


def extract_lint_issues(content: str) -> list:
    """Extract lint issues from ruff/black/mypy output."""
    issues = []
    try:
        lines = content.splitlines()
        for line in lines:
            if any(tool in line.lower() for tool in ["error", "warning", "failed"]):
                issues.append(line.strip())
    except Exception:
        pass
    return issues


def read_accuracy(path: Path) -> dict:
    """Read accuracy results from JSON file."""
    try:
        return json.loads(path.read_text())
    except Exception:
        return {"average_match": 0, "files": {}}


def main() -> None:
    # Read input files
    test_output = read_file(TEST_FILE)
    lint_output = read_file(LINT_FILE)
    evolve_output = read_file(EVOLVE_FILE)
    accuracy_data = read_accuracy(ACCURACY_FILE)

    # Process data
    coverage = extract_coverage(test_output)
    test_summary = extract_test_summary(test_output)
    lint_issues = extract_lint_issues(lint_output)

    # Generate summary markdown
    summary = [
        "## CI Run Summary",
        "",
        "### Test Results",
        f"- Total Tests: {test_summary['total']}",
        f"- Passed: {test_summary['passed']}",
        f"- Failed: {test_summary['failed']}",
        f"- Skipped: {test_summary['skipped']}",
        f"- Coverage: {coverage:.1f}%",
        "",
    ]

    # Add lint issues if any
    if lint_issues:
        summary.extend(
            [
                "### Lint Issues",
                "```",
                *lint_issues[:10],  # Show first 10 issues
                "```" if len(lint_issues) <= 10 else "... and more issues",
                "",
            ]
        )

    # Add accuracy results
    summary.extend(
        [
            "### Parser Accuracy",
            f"- Average Match: {accuracy_data['average_match']:.1f}%",
            "",
            "#### Per-File Results",
            "```",
            *[
                f"{file}: {score:.1f}%"
                for file, score in sorted(accuracy_data.get("files", {}).items())
            ],
            "```",
            "",
        ]
    )

    # Add evolve info if it ran
    if evolve_output:
        summary.extend(
            [
                "### Auto-Patch Results",
                "```",
                *evolve_output.splitlines()[-5:],  # Show last 5 lines
                "```",
                "",
            ]
        )

    # Write summary
    summary_file = Path("summary.md")
    summary_file.write_text("\n".join(summary))

    # Print summary for local runs
    print("\n".join(summary))


if __name__ == "__main__":
    main()

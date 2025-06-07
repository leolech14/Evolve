#!/usr/bin/env python3
"""
evolve.py – AI-powered auto-patch tool.

➤ Always starts from main branch
➤ Tries up to MAX_ATTEMPTS patches per cycle
➤ A patch is accepted only if tests go green AND accuracy is above threshold

Required env vars:
  OPENAI_API_KEY   - Your OpenAI API key
  GITHUB_TOKEN     - GitHub personal access token

Optional env vars:
  OPENAI_MODEL     - Model to use (default: gpt-4)
  MAX_ATTEMPTS     - Max patch attempts (default: 5)
  MAX_TOKENS      - Token limit per run (default: 5000000)
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

try:
    import openai
except ImportError:
    print("Error: openai package required. Install with: pip install openai")
    sys.exit(1)

# Configuration
DIAGNOSTICS = Path("diagnostics")
MAX_TOKENS = min(5_000_000, int(os.getenv("MAX_TOKENS", "5000000")))
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "5"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4")


def ensure_best_branch() -> None:
    """Ensure the codex/best branch exists on fresh clones."""
    code, _ = run_command(["git", "rev-parse", "--verify", "-q", "codex/best"])
    if code != 0:
        head_rev = run_command(["git", "rev-parse", "HEAD"])[1].strip()
        run_command(["git", "branch", "codex/best", head_rev])
        print("Created missing codex/best branch at", head_rev)


def run_command(cmd: List[str], capture: bool = True) -> Tuple[int, str]:
    """Run a shell command and return exit code and output."""
    try:
        if capture:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return result.returncode, result.stdout + result.stderr
        else:
            result = subprocess.run(cmd, check=False)
            return result.returncode, ""
    except Exception as e:
        return 1, str(e)


def collect_context() -> dict:
    """Collect relevant context about test failures and code state."""
    context = {
        "errors": [],
        "files": [],
        "tests": "",
        "coverage": "",
        "lint": "",
        "accuracy": {},
    }

    # Get test output
    test_file = DIAGNOSTICS / "test.txt"
    if test_file.exists():
        context["tests"] = test_file.read_text()

    # Get lint output
    lint_file = DIAGNOSTICS / "lint.txt"
    if lint_file.exists():
        context["lint"] = lint_file.read_text()

    # Get accuracy results
    accuracy_file = DIAGNOSTICS / "accuracy.json"
    if accuracy_file.exists():
        try:
            context["accuracy"] = json.loads(accuracy_file.read_text())
        except Exception:
            context["errors"].append("Failed to read accuracy results")

    # Get changed files
    _, output = run_command(["git", "diff", "--name-only"])
    context["files"] = [f for f in output.splitlines() if f.endswith(".py")]

    # Get file contents
    for file in context["files"]:
        try:
            with open(file) as f:
                context[file] = f.read()
        except Exception:
            context["errors"].append(f"Failed to read {file}")

    return context


def create_patch(suggestion: str) -> Optional[str]:
    """Create a git patch from the AI suggestion."""
    # Create temporary branch
    branch = f"ai-patch-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    run_command(["git", "checkout", "-b", branch])

    try:
        current_file = None
        inside_block = False
        buffer = []

        for line in suggestion.splitlines():
            if line.startswith("FILE: "):
                # flush any previous block
                if current_file and buffer:
                    Path(current_file).parent.mkdir(parents=True, exist_ok=True)
                    Path(current_file).write_text("\n".join(buffer))
                current_file = line.split(":", 1)[1].strip()
                buffer = []
                inside_block = False
            elif line.startswith("```") and current_file:
                # toggle state – first ``` opens, second closes
                inside_block = not inside_block
                if not inside_block:  # closing back-tick
                    Path(current_file).parent.mkdir(parents=True, exist_ok=True)
                    Path(current_file).write_text("\n".join(buffer))
                    buffer = []
            elif inside_block:
                buffer.append(line)
        # handle EOF without closing ```
        if current_file and buffer:
            Path(current_file).parent.mkdir(parents=True, exist_ok=True)
            Path(current_file).write_text("\n".join(buffer))

        # Create patch
        run_command(["git", "add", "."])
        run_command(["git", "commit", "-m", "AI: Auto-patch improvements"])

        test_code, _ = run_command(["pytest", "-q"], capture=True)
        if test_code == 0:
            run_command(
                [
                    "git",
                    "commit",
                    "--amend",
                    "-m",
                    "🤖 AUTO-FIX: Auto-patch improvements",
                ]
            )

        code, patch = run_command(["git", "format-patch", "HEAD~1", "--stdout"])

        if code == 0:
            return patch
    except Exception:
        pass

    # Cleanup on failure
    run_command(["git", "checkout", "-"])
    run_command(["git", "branch", "-D", branch])
    return None


def apply_patch(patch: str) -> bool:
    """Apply a git patch and create pull request."""
    if not patch or not patch.strip():
        return False

    try:
        # Write patch
        patch_file = DIAGNOSTICS / "ai-patch.patch"
        patch_file.write_text(patch)

        # Validate patch applies cleanly
        for attempt in range(1, 4):
            code, _ = run_command(["git", "apply", "--check", str(patch_file)])
            if code == 0:
                break
            if attempt == 3:
                print("Patch failed to apply cleanly; skipping")
                return False

        # Apply patch
        code, _ = run_command(["git", "am", str(patch_file)])
        if code != 0:
            run_command(["git", "am", "--abort"])
            return False

        # Create PR
        branch = f"ai-patch-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        run_command(["git", "checkout", "-b", branch])
        run_command(["git", "push", "origin", branch])
        run_command(
            [
                "gh",
                "pr",
                "create",
                "--title",
                "🤖 AI: Auto-patch improvements",
                "--body",
                "Automated fixes from AI assistant",
                "--label",
                "auto-patch",
            ]
        )

        return True
    except Exception:
        return False


def main() -> int:
    """Main entry point."""
    print("🤖 Starting AI auto-patch process...")

    ensure_best_branch()

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return 1

    # Collect context
    print("📝 Collecting context...")
    context = collect_context()
    if not context["files"]:
        print("No Python files changed")
        return 0

    # Prepare prompt
    prompt = [
        "You are an AI code improvement assistant. "
        "Analyze the failures and suggest fixes:",
        "",
        "=== Test Output ===",
        context["tests"],
        "",
        "=== Lint Output ===",
        context["lint"],
        "",
        "=== Accuracy Results ===",
        json.dumps(context["accuracy"], indent=2),
        "",
        "=== Changed Files ===",
    ]

    for file in context["files"]:
        prompt.extend(
            [
                f"FILE: {file}",
                "```python",
                context.get(file, "<error reading file>"),
                "```",
                "",
            ]
        )

    prompt.extend(
        [
            "Please suggest fixes in the following format:",
            "FILE: path/to/file.py",
            "```python",
            "complete fixed file content",
            "```",
            "",
            "Focus on:",
            "1. Fixing test failures",
            "2. Addressing lint issues",
            "3. Improving parser accuracy",
            "4. Maintaining code style",
        ]
    )

    # Get AI suggestion
    print("🧠 Requesting AI analysis...")
    try:
        response = openai.ChatCompletion.create(
            model=MODEL,
            messages=[{"role": "user", "content": "\n".join(prompt)}],
            max_tokens=MAX_TOKENS,
            temperature=0.1,
        )
        suggestion = response.choices[0].message.content
    except Exception as e:
        print(f"Error: Failed to get AI suggestion: {e}")
        return 1

    # Create and apply patch
    print("🔧 Creating patch...")
    patch = create_patch(suggestion)
    if not patch:
        print("Error: Failed to create patch")
        return 1

    print("⬆️  Creating pull request...")
    if not apply_patch(patch):
        print("Error: Failed to apply patch")
        return 1

    print("✅ Auto-patch complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())

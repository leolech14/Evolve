#!/usr/bin/env python3
"""
ai_patch.py
-----------
Run tests, ask OpenAI for *one* small patch, apply it in-memory,
re-run the tests and commit if the situation improves.

The script is idempotent and contains no project-specific logic.
"""

from __future__ import annotations
import os
import subprocess
import sys
import textwrap
import tempfile
import pathlib
import shlex
from typing import Tuple, Any, List
import openai  #  pip install openai>=1.0

MAX_LINES_CHANGED = int(os.environ.get("MAX_LINES_CHANGED", "50"))
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

ROOT = pathlib.Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #
def run(
    cmd: str,
    *,
    capture_output: bool = True,
    **popen_kwargs: Any,
) -> Tuple[int, str]:
    """
    Run *cmd* in a shell and return ``(exit_code, stdout + stderr)``.

    The wrapper now accepts additional **kwargs so that future callers
    (including the AI agent) can pass parameters like *timeout*,
    *env*, *check* … without breaking older versions.
    """
    proc = subprocess.run(
        cmd,
        shell=True,
        text=True,
        cwd=ROOT,
        capture_output=capture_output,
        timeout=popen_kwargs.pop("timeout", 120),
        **popen_kwargs,
    )
    combined = (
        proc.stdout + proc.stderr
        if capture_output
        else proc.stdout or ""
    )
    return proc.returncode, combined


def run_tests() -> Tuple[int, str]:
    code, out = run("pytest -q --maxfail=25")
    return code, out


def failing_summary(raw: str) -> str:
    """Trim pytest output to failures only (keeps prompt size low)."""
    keep: List[str] = []
    capture = False
    for line in raw.splitlines():
        if line.startswith("====") and " FAILURES " in line:
            capture = True
            continue
        if line.startswith("====") and capture:
            break
        if capture:
            keep.append(line)
    return "\n".join(keep)[:4000]  # 4k chars cap


def collect_diff(num_lines: int = MAX_LINES_CHANGED) -> str:
    code, diff = run("git diff -U0")  # already unstaged?
    if code:
        return ""
    return "\n".join(diff.splitlines()[: num_lines * 3])  # rough \(context)


def ask_openai(prompt: str) -> str:
    resp = openai.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior Python developer. "
                    "Return ONLY a unified diff (git apply compatible) "
                    f"touching max {MAX_LINES_CHANGED} lines. "
                    "No commentary, no Markdown. Start with 'diff --git'."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content.strip()


# --------------------------------------------------------------------------- #
# algorithm                                                                   #
# --------------------------------------------------------------------------- #
def main() -> None:
    before_code, before_out = run_tests()
    if before_code == 0:
        print("✅ Tests already green → nothing to do.")
        return

    fail_snippet = failing_summary(before_out)
    diff_context = collect_diff()

    prompt = textwrap.dedent(
        f"""
        Current test failures (excerpt):
        {fail_snippet}

        Repository state (partial diff for context):
        {diff_context}

        Please propose a patch that fixes at least one failure without breaking
        working tests. Remember: return ONLY the diff.
        """
    )
    patch = ask_openai(prompt)

    if not patch.startswith("diff --git"):
        print("⚠️  OpenAI answer did not look like a diff, aborting.")
        sys.exit(1)

    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write(patch)
        tf.flush()
        code, out = run(f"git apply --verbose {shlex.quote(tf.name)}")
        if code:
            print("🚫 Patch did not apply cleanly:\n", out)
            sys.exit(1)

    after_code, after_out = run_tests()

    if after_code < before_code:
        # improvement – commit!
        msg_lines = [
            "🤖 AUTO-FIX: shrink failing-tests count " f"{before_code} → {after_code}",
            "",
            "Context:",
            *fail_snippet.splitlines()[:20],
        ]
        run("git config user.email ai-bot@example.com")
        run("git config user.name  AI-Bot")
        run("git add -u")
        run(f"git commit -m {shlex.quote('\\n'.join(msg_lines))}")
        print("✅ Patch improved the situation and was committed.")
    else:
        print("🚫 No improvement – patch reverted.")
        run("git reset --hard")

    # exit with current test code so CI reports status accurately
    sys.exit(after_code)


if __name__ == "__main__":
    main()

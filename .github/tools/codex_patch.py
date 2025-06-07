#!/usr/bin/env python3
"""
codex_patch.py – generate ONE patch from Codex and open a PR.

Simpler than evolve.py: no scoring loop, no back-tracking.
Kept as utility for manual runs or quick hot-fixes.
"""

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

try:
    import openai
except ImportError:
    print(
        "The openai package is required. Install with `pip install openai`.",
        file=sys.stderr,
    )
    raise SystemExit(1)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("Missing OPENAI_API_KEY environment variable.", file=sys.stderr)
    raise SystemExit(1)

client = openai.OpenAI(api_key=api_key)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")


def _run_with_retry(cmd):
    attempts = 3
    for i in range(1, attempts + 1):
        res = subprocess.run(cmd, text=True)
        if res.returncode == 0:
            return
        if i < attempts:
            print(f"Retry {i}/3 for {' '.join(cmd)}", file=sys.stderr)
            time.sleep(1)
    res.check_returncode()


def sh(*cmd):
    _run_with_retry(cmd)


def main():
    print("⚙️  Generating single Codex patch…")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": "There are pytest failures; provide a unified diff that fixes them.",
            }
        ],
        temperature=0.1,
    )
    patch = resp.choices[0].message["content"]
    if not patch.strip():
        print("Empty patch; abort.")
        return 1

    with tempfile.NamedTemporaryFile("w+", delete=False) as tmp:
        tmp.write(patch)
        tmp.flush()
        sh("git", "apply", tmp.name)

    sh("git", "commit", "-am", "🤖 Codex one-shot patch")
    branch = f"codex/oneshot-{Path(tmp.name).stem}"
    sh("git", "checkout", "-b", branch)
    sh("git", "push", "-u", "origin", branch)
    sh(
        "gh",
        "pr",
        "create",
        "--base",
        os.getenv("GITHUB_HEAD_REF", "main"),
        "--head",
        branch,
        "--title",
        "🤖 One-shot Codex patch",
        "--body",
        "Generated automatically.",
    )
    print("PR opened.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

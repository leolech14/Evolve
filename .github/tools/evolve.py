#!/usr/bin/env python3
"""
evolve.py – Codex-driven auto-patch loop.

➤ Partimos sempre do branch `codex/best`.
➤ Tentamos até MAX_ATTEMPTS patches por ciclo.
➤ Patch só é aceito se testes ficarem 100 % verdes E score superar o best.

Env vars obrigatórios:
- OPENAI_API_KEY
- GITHUB_TOKEN   (Actions fornece automaticamente)

Env vars opcionais:
- OPENAI_MODEL           (default: gpt-4.1)
- MAX_ATTEMPTS           (default: 5)
- MAX_TOKENS_PER_RUN     (default: 100000)
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Tuple
import sys

try:
    import openai
except ImportError:
    print(
        "The openai package is required. Install with `pip install openai`.",
        file=sys.stderr,
    )
    raise SystemExit(1)

ROOT = Path(__file__).resolve().parents[2]  # repo root
BEST_BRANCH = "codex/best"
SCORE_FILE = ROOT / ".github/tools/score_best.json"

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise SystemExit("Missing OPENAI_API_KEY environment variable.")

github_token = os.getenv("GITHUB_TOKEN")
if not github_token:
    raise SystemExit("Missing GITHUB_TOKEN environment variable.")

client = openai.OpenAI(api_key=api_key)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "5"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS_PER_RUN", "100000"))


# ───────────────────────── process helper ─────────────────────────
def _run_with_retry(cmd: Tuple[str, ...], capture: bool) -> subprocess.CompletedProcess:
    attempts = 3
    for i in range(1, attempts + 1):
        res = subprocess.run(cmd, text=True, capture_output=capture)
        if res.returncode == 0:
            return res
        if i < attempts:
            print(f"Retry {i}/3 for {' '.join(cmd)}", file=sys.stderr)
            time.sleep(1)
    return res


# ───────────────────────── git helpers ─────────────────────────
def sh(*cmd, capture=False):
    res = _run_with_retry(cmd, capture)
    if res.returncode != 0:
        raise subprocess.CalledProcessError(
            res.returncode, cmd, output=res.stdout, stderr=res.stderr
        )
    return res.stdout.strip() if capture else None


def current_commit() -> str:
    return sh("git", "rev-parse", "HEAD", capture=True)[:7]


# ───────────────────────── scoring ─────────────────────────
def run_tests() -> Tuple[bool, float]:
    """Run pytest + coverage; return (green?, coverage%)."""
    try:
        out = sh(
            "pytest",
            "-q",
            "--cov=statement_refinery",
            "--cov-report=term-missing",
            capture=True,
        )
    except subprocess.CalledProcessError:
        return False, 0.0

    # coverage line like "TOTAL   213   0 100%"
    for line in out.splitlines():
        if line.startswith("TOTAL"):
            cov = float(line.split()[-1].rstrip("%"))
            return True, cov
    return True, 0.0  # fallback


def score(is_green: bool, coverage: float) -> float:
    return (1000 if is_green else 0) + coverage


def load_best() -> Tuple[str, float]:
    if SCORE_FILE.exists():
        data = json.loads(SCORE_FILE.read_text())
        return data["commit"], data["score"]
    return "", 0.0


def save_best(commit: str, best_score: float):
    SCORE_FILE.write_text(json.dumps({"commit": commit, "score": best_score}))
    print(f"Used {TOKENS_USED} tokens")


def ensure_best_branch() -> None:
    """Ensure BEST_BRANCH exists locally."""
    try:
        sh("git", "rev-parse", "--verify", BEST_BRANCH)
    except subprocess.CalledProcessError:
        print(f"{BEST_BRANCH} missing; creating from main")
        sh("git", "branch", BEST_BRANCH, "main")


# ───────────────────────── codex patch ─────────────────────────
TOKENS_USED = 0


def generate_patch(fail_log: str) -> str:
    global TOKENS_USED
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": f"Aplique um patch unificado nas falhas:\n\n{fail_log[:7000]}",
            }
        ],
        temperature=0.1,
    )
    usage = resp.usage.total_tokens
    TOKENS_USED += usage
    return resp.choices[0].message.content


# ───────────────────────── main loop ─────────────────────────
def main():
    best_commit, best_score = load_best()
    print(f"BASELINE {best_commit or 'none'} score={best_score}")

    ensure_best_branch()
    sh("git", "fetch", "--all", "--prune")
    sh("git", "checkout", BEST_BRANCH)

    while TOKENS_USED < MAX_TOKENS:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            branch = f"codex/work-{int(time.time())}-{attempt}"
            sh("git", "checkout", "-b", branch)

            # gather fail log from pytest only on first attempt
            if attempt == 1:
                try:
                    fail_output = sh("pytest", "-v", "--tb=short", capture=True)
                    # Get full test output but prioritize error messages
                    error_lines = [
                        line
                        for line in fail_output.splitlines()
                        if "FAILED" in line
                        or "Error" in line
                        or "AssertionError" in line
                    ]
                    fail_log = "Tests are failing. Errors:\n" + "\n".join(error_lines)
                    if len(error_lines) < 10:  # If few errors, include full context
                        fail_log += "\n\nFull test output:\n" + fail_output
                except subprocess.CalledProcessError as e:
                    error_output = e.stdout if e.stdout else "No output"
                    error_lines = [
                        line
                        for line in error_output.splitlines()
                        if "FAILED" in line
                        or "Error" in line
                        or "AssertionError" in line
                    ]
                    fail_log = "Tests failing. Errors:\n" + "\n".join(error_lines)
                    if len(error_lines) < 10:
                        fail_log += "\n\nFull error output:\n" + error_output

            patch = generate_patch(fail_log)
            if not patch.strip():
                print("Empty patch; skipping.")
                sh("git", "checkout", BEST_BRANCH)
                continue

            tmp = Path("patch.diff")
            tmp.write_text(patch)
            try:
                sh("git", "apply", str(tmp))
            except subprocess.CalledProcessError:
                print("Patch didn't apply.")
                sh("git", "checkout", BEST_BRANCH)
                continue

            sh("git", "commit", "-am", "🤖 Codex auto-patch")
            green, cov = run_tests()
            cur_score = score(green, cov)
            print(f"Attempt {attempt}: green={green} cov={cov}% score={cur_score}")

            if green and cur_score > best_score:
                # push & PR
                sh("git", "push", "--set-upstream", "origin", branch)
                sh(
                    "gh",
                    "pr",
                    "create",
                    "--base",
                    BEST_BRANCH,
                    "--head",
                    branch,
                    "--title",
                    "🤖 Codex auto-patch",
                    "--body",
                    f"Score {best_score} → {cur_score}",
                )
                save_best(current_commit(), cur_score)
                return 0  # success

            sh("git", "checkout", BEST_BRANCH)

        print("No improvement in this cycle, restarting from best…")

    print("Max tokens budget reached.")
    print(f"Used {TOKENS_USED} tokens")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

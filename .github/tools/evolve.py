#!/usr/bin/env python3
"""
evolve.py – Codex-driven auto-patch loop.

➤ Always starts from branch `codex/best`.
➤ Tries up to MAX_ATTEMPTS patches per cycle.
➤ A patch is accepted only if tests go 100 % green **and** the score beats the best so far.

Required env vars
-----------------
OPENAI_API_KEY                 – your OpenAI key
GITHUB_TOKEN                   – *or* PERSONAL_ACCESS_TOKEN_CLASSIC *or* GH_TOKEN

Optional env vars
-----------------
OPENAI_MODEL           (default: gpt-4.1)
MAX_ATTEMPTS           (default: 5)
MAX_TOKENS_PER_RUN     (default: 100000)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Tuple

try:
    import openai
except ImportError:
    print(
        "The openai package is required. Install with `pip install openai`.",
        file=sys.stderr,
    )
    raise SystemExit(1)

# ───────────────────────── configuration ─────────────────────────
ROOT = Path(__file__).resolve().parents[2]  # repo root
BEST_BRANCH = "codex/best"
SCORE_FILE = ROOT / ".github/tools/score_best.json"
DIAG_DIR = ROOT / "diagnostics"
DIAG_DIR.mkdir(exist_ok=True)

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise SystemExit("Missing OPENAI_API_KEY environment variable.")

# Accept any of the common GitHub token names
github_token = (
    os.getenv("GITHUB_TOKEN")
    or os.getenv("PERSONAL_ACCESS_TOKEN_CLASSIC")
    or os.getenv("GH_TOKEN")
)
if not github_token:
    raise SystemExit(
        "Missing GitHub token. "
        "Set GITHUB_TOKEN, PERSONAL_ACCESS_TOKEN_CLASSIC, or GH_TOKEN."
    )

client = openai.OpenAI(api_key=api_key)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "5"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS_PER_RUN", "100000"))
# Maximum number of consecutive patch apply failures before aborting
MAX_PATCH_FAILURES = int(os.getenv("MAX_PATCH_FAILURES", "3"))


def log_tokens_to_file(tokens: int) -> None:
    """Append token usage to diagnostics/tokens.log."""
    log_file = DIAG_DIR / "tokens.log"
    with log_file.open("a") as fh:
        fh.write(f"{int(time.time())},{tokens}\n")


# ───────────────────────── helpers ─────────────────────────
def _run_with_retry(cmd: Tuple[str, ...], capture: bool) -> subprocess.CompletedProcess:
    """Run a shell command with up to 3 retries."""
    attempts = 3
    for i in range(1, attempts + 1):
        res = subprocess.run(cmd, text=True, capture_output=capture)
        if res.returncode == 0:
            return res
        if i < attempts:
            print(f"Retry {i}/3 for {' '.join(cmd)}", file=sys.stderr)
            time.sleep(1)
    return res


def sh(*cmd, capture: bool = False) -> str | None:
    """Shell helper that raises on non-zero exit."""
    res = _run_with_retry(cmd, capture)
    if res.returncode != 0:
        raise subprocess.CalledProcessError(
            res.returncode, cmd, output=res.stdout, stderr=res.stderr
        )
    return res.stdout.strip() if capture else None


def looks_like_diff(text: str) -> bool:
    """Return True if text starts with a unified diff header."""
    return text.lstrip().startswith("diff --git ")


def diff_targets_exist(patch: str) -> tuple[bool, str | None]:
    """Return True if all files referenced by *patch* exist in the repo."""
    for line in patch.splitlines():
        if line.startswith("diff --git "):
            try:
                _, _, a_path, b_path = line.split(maxsplit=3)
            except ValueError:
                return False, "corrupt header"
            path = b_path[2:]
            try:
                sh("git", "ls-files", "--error-unmatch", path)
            except subprocess.CalledProcessError:
                return False, path
    return True, None


def current_commit() -> str:
    return sh("git", "rev-parse", "HEAD", capture=True)[:7]


# ───────────────────────── tests & scoring ─────────────────────────
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
        sh(
            "python",
            "scripts/check_accuracy.py",
            "--threshold",
            "99",
        )
    except subprocess.CalledProcessError:
        return False, 0.0

    # look for "TOTAL   213   0  97%"
    for line in out.splitlines():
        if line.startswith("TOTAL"):
            cov = float(line.split()[-1].rstrip("%"))
            return True, cov
    return True, 0.0  # fallback when coverage line missing


def score(is_green: bool, coverage: float) -> float:
    return (1000 if is_green else 0) + coverage


def load_best() -> Tuple[str, float]:
    if SCORE_FILE.exists():
        data = json.loads(SCORE_FILE.read_text())
        return data["commit"], data["score"]
    return "", 0.0


def save_best(commit: str, best_score: float, tokens_used: int):
    SCORE_FILE.write_text(json.dumps({"commit": commit, "score": best_score}))
    print(f"🎉 New best! Commit {commit}  score={best_score:.1f}  tokens={tokens_used}")
    log_tokens_to_file(tokens_used)


def record_tokens():
    log_tokens_to_file(TOKENS_USED)


# ───────────────────────── git helpers ─────────────────────────
def ensure_best_branch() -> None:
    """Ensure BEST_BRANCH exists locally."""
    res = _run_with_retry(
        ("git", "rev-parse", "--verify", "-q", BEST_BRANCH), capture=False
    )
    if res.returncode != 0:
        print(f"{BEST_BRANCH} missing; creating from HEAD")
        sh("git", "branch", BEST_BRANCH)


# ───────────────────────── Codex interaction ─────────────────────────
TOKENS_USED = 0


def generate_patch(fail_log: str) -> str:
    """Ask the model for a unified‐diff patch to fix the failing tests."""
    global TOKENS_USED
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    "Only touch existing files. Output a single valid unified diff; "
                    "no markers, no JSON, no markdown.\n"
                    "Return **only** a unified diff between HEAD and fixed code.\n"
                    "Begin with:  diff --git a/... b/...\n"
                    "Use Unix line endings.\n"
                    "Only modify existing files under src/, scripts/, or tests/.\n"
                    "Do not create new files.\n"
                    "If nothing to change, reply exactly:  #NOPATCH\n\n"
                    f"{fail_log[:7000]}"
                ),
            }
        ],
        temperature=0.1,
    )
    TOKENS_USED += resp.usage.total_tokens
    return resp.choices[0].message.content


# ───────────────────────── main loop ─────────────────────────
def main() -> int:
    best_commit, best_score = load_best()
    print(f"BASELINE {best_commit or 'none'}  score={best_score}")

    ensure_best_branch()
    sh("git", "fetch", "--all", "--prune")
    sh("git", "checkout", BEST_BRANCH)

    invalid_replies = 0
    apply_failures = 0

    try:
        while TOKENS_USED < MAX_TOKENS:
            for attempt in range(1, MAX_ATTEMPTS + 1):
                branch = f"codex/work-{int(time.time())}-{attempt}"
                sh("git", "checkout", "-b", branch)

            # Run tests once to capture failure log
            if attempt == 1:
                try:
                    fail_output = sh("pytest", "-v", "--tb=short", capture=True)
                    error_lines = [
                        ln
                        for ln in fail_output.splitlines()
                        if any(k in ln for k in ("FAILED", "Error", "AssertionError"))
                    ]
                    fail_log = "Tests failing:\n" + "\n".join(
                        error_lines or fail_output.splitlines()[:30]
                    )
                except subprocess.CalledProcessError as e:
                    err = e.stdout or "No output"
                    fail_log = "Tests failed immediately:\n" + err

            patch = generate_patch(fail_log)
            if patch.strip() == "#NOPATCH":
                print("Model returned #NOPATCH. Aborting.")
                raise SystemExit("loop-no-patch")
            if not looks_like_diff(patch):
                print("⚠️ No valid patch returned.")
                invalid_replies += 1
                if invalid_replies >= 3:
                    raise SystemExit("loop-no-patch")
                time.sleep(1)
                sh("git", "checkout", BEST_BRANCH)
                continue
            invalid_replies = 0

            ok, missing = diff_targets_exist(patch)
            if not ok:
                print(f"❌ Diff references non-existent file: {missing}")
                fail_log = f"diff references non-existent file: {missing}"[:7000]
                sh("git", "checkout", BEST_BRANCH)
                continue

            tmp = Path("patch.diff")
            tmp.write_text(patch)
            try:
                sh("git", "apply", "--check", str(tmp))
            except subprocess.CalledProcessError as e:
                print("❌ Patch did not apply.")
                fail_log = f"patch failed: {e.stderr.strip()}"[:7000]
                apply_failures += 1
                if apply_failures > MAX_PATCH_FAILURES:
                    print(
                        f"❌ Too many patch failures (limit: {MAX_PATCH_FAILURES}). Aborting."
                    )
                    return 1
                sh("git", "checkout", BEST_BRANCH)
                continue
            apply_failures = 0
            sh("git", "apply", str(tmp))
            # ensure patch produced changes
            try:
                sh("git", "diff", "--quiet")
                print("⚠️ Patch resulted in no changes; skipping.")
                sh("git", "checkout", BEST_BRANCH)
                continue
            except subprocess.CalledProcessError:
                pass

            sh("git", "commit", "-am", "🤖 Codex auto-patch")
            green, cov = run_tests()
            cur_score = score(green, cov)
            print(
                f"Attempt {attempt}: green={green}  coverage={cov:.1f}%  score={cur_score}"
            )

            if green and cur_score > best_score:
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
                    f"Score {best_score:.1f} → {cur_score:.1f}",
                )
                save_best(current_commit(), cur_score, TOKENS_USED)
                return 0  # success

            # Revert to best for next attempt
            sh("git", "checkout", BEST_BRANCH)

        print("No improvement this cycle; restarting from best.")

        print(f"Token budget exhausted ({TOKENS_USED}/{MAX_TOKENS}).")
        return 1
    finally:
        record_tokens()


if __name__ == "__main__":
    raise SystemExit(main())

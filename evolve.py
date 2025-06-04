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
- MAX_ATTEMPTS           (default: 3)
- MAX_TOKENS_PER_RUN     (default: 1_000_000)
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from hashlib import sha256
from pathlib import Path
from typing import Tuple

import openai

ROOT = Path(__file__).resolve().parents[2]      # repo root
BEST_BRANCH = "codex/best"
SCORE_FILE = ROOT / ".github/tools/score_best.json"
openai.api_key = os.environ["OPENAI_API_KEY"]
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1")
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS_PER_RUN", "1000000"))


# ───────────────────────── git helpers ─────────────────────────
def sh(*cmd, capture=False):
    res = subprocess.run(cmd, check=True, text=True, capture_output=capture)
    return res.stdout.strip() if capture else None


def current_commit() -> str:
    return sh("git", "rev-parse", "HEAD", capture=True)[:7]


# ───────────────────────── scoring ─────────────────────────
def run_tests() -> Tuple[bool, float]:
    """Run pytest + coverage; return (green?, coverage%)."""
    try:
        out = sh("pytest", "-q", "--cov=statement_refinery", "--cov-report=term-missing", capture=True)
    except subprocess.CalledProcessError as exc:
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


# ───────────────────────── codex patch ─────────────────────────
TOKENS_USED = 0


def generate_patch(fail_log: str) -> str:
    global TOKENS_USED
    resp = openai.ChatCompletion.create(
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
    return resp.choices[0].message["content"]


# ───────────────────────── main loop ─────────────────────────
def main():
    best_commit, best_score = load_best()
    print(f"BASELINE {best_commit or 'none'} score={best_score}")

    sh("git", "fetch", "--all", "--prune")
    sh("git", "checkout", BEST_BRANCH)

    while TOKENS_USED < MAX_TOKENS:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            branch = f"codex/work-{int(time.time())}-{attempt}"
            sh("git", "checkout", "-b", branch)

            # gather fail log from previous run (pytest handles log internally)
            fail_log = "tests failing"  # minimal prompt; could include real log
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
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
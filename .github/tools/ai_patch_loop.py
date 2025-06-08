#!/usr/bin/env python3
"""
ai_patch_loop.py
----------------
Iterate up to MAX_ITERS asking OpenAI for tiny diffs.  Each time the number of
pytest failures goes down we keep the patch; otherwise we revert and retry.

Env-vars:
  OPENAI_API_KEY   – required
  OPENAI_MODEL     – gpt-4o-mini by default
  MAX_ITERS        – hard iteration cap   (default 100)
  MAX_LINES_CHANGED – per-patch LOC limit (default 50)
  PATIENCE         – abort after PATIENCE consecutive non-improving patches
"""

from __future__ import annotations
import os, subprocess, sys, tempfile, textwrap, pathlib, shlex
from typing import Tuple
import openai

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAX_ITERS        = int(os.getenv("MAX_ITERS", "100"))
MAX_LINES        = int(os.getenv("MAX_LINES_CHANGED", "50"))
MODEL            = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PATIENCE         = int(os.getenv("PATIENCE", "5"))


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #
def run(cmd: str) -> Tuple[int, str]:
    p = subprocess.run(cmd, shell=True, text=True, cwd=ROOT,
                       capture_output=True)
    return p.returncode, p.stdout + p.stderr


def run_tests() -> Tuple[int, str]:
    return run("pytest -q --maxfail=25")


def test_fail_count(output: str) -> int:
    # pytest -q prints "F" per failure and "." per pass; count "F"
    return output.count("F")


def failing_snippet(raw: str, cap: int = 4000) -> str:
    keep = []
    grab = False
    for line in raw.splitlines():
        if line.startswith("====") and "FAILURES" in line:
            grab = True
            continue
        if line.startswith("====") and grab:
            break
        if grab:
            keep.append(line)
    return "\n".join(keep)[:cap] or raw[-cap:]


def ask_llm(prompt: str) -> str:
    """
    Call OpenAI and return the assistant content.
    Prints full error info when the request fails so the CI log tells us why.
    Returns an empty string on failure so the caller can decide what to do.
    """
    try:
        rsp = openai.ChatCompletion.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=MAX_TOKENS,
        )
        out = rsp.choices[0].message.content or ""
        if DEBUG_LOG:
            print("—— Raw LLM output ———————————————")
            print(out)
            print("———————————————————————————————")
        return out
    except Exception as err:  # pylint: disable=broad-except
        print("⚠️  OpenAI request failed:")
        print(err)
        return ""


def apply_patch(diff: str) -> bool:
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write(diff)
        tf.flush()
        code, _ = run(f"git apply --whitespace=nowarn {shlex.quote(tf.name)}")
    return code == 0


# --------------------------------------------------------------------------- #
# main loop                                                                   #
# --------------------------------------------------------------------------- #
def main() -> None:
    consec_misses = 0
    iters         = 0

    # run baseline tests
    code, out = run_tests()
    baseline_fail = test_fail_count(out)
    FORCE_EVOLVE = os.getenv("FORCE_EVOLVE", "false").lower() in {"1", "true", "yes"}
    if baseline_fail == 0 and not FORCE_EVOLVE:
        print("Nothing to fix 🎉")
        sys.exit(0)

    while iters < MAX_ITERS and consec_misses < PATIENCE and baseline_fail > 0:
        iters += 1
        print(f"\n=== Iteration {iters}/{MAX_ITERS} "
              f"(failures so far: {baseline_fail}) ===")

        prompt = textwrap.dedent(f"""
            pytest failures (excerpt):
            {failing_snippet(out)}

            Provide a diff that reduces failure count.
        """)
        patch = ask_llm(prompt)
        if not patch.startswith("diff --git"):
            print("LLM did not return a diff, skipping iteration.")
            consec_misses += 1
            continue
        if patch.count("\n+") + patch.count("\n-") > MAX_LINES:
            print("Patch too large, skipping.")
            consec_misses += 1
            continue
        if not apply_patch(patch):
            print("Patch failed to apply.")
            consec_misses += 1
            continue

        new_code, new_out = run_tests()
        new_fail = test_fail_count(new_out)

        if new_fail < baseline_fail:
            # good – keep and commit
            consec_misses = 0
            baseline_fail = new_fail
            out = new_out
            run("git add -u")
            # Commit any staged changes
            commit_msg = f"🤖 AUTO-FIX: failures {baseline_fail} after iter {iters}"
            run(f'git commit -am "{commit_msg}"')
            print("✅ patch accepted")
        else:
            # revert
            run("git reset --hard")
            consec_misses += 1
            print("🚫 patch reverted (no improvement)")

        if baseline_fail == 0:
            break

    print(f"\nLoop finished after {iters} iterations; failures left: "
          f"{baseline_fail}")
    # exit 0 so CI step passes; overall job status handled by outer steps
    sys.exit(0)


if __name__ == "__main__":
    main()
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
import os
import subprocess
import sys
import tempfile
import textwrap
import pathlib
import shlex
from typing import Tuple
from openai import OpenAI
import re
import json
import logging
from datetime import datetime
from pathlib import Path

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAX_ITERS = int(os.getenv("MAX_ITERS", "100"))
MAX_LINES = int(os.getenv("MAX_LINES_CHANGED", "50"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
PATIENCE = int(os.getenv("PATIENCE", "5"))
# Maximum number of tokens the assistant may return.
# Can be overridden in the workflow via the MAX_TOKENS env var.
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "4096"))


# --------------------------------------------------------------------------- #
# Logging setup
# ---------------------------------------------------------------------------

_DIAG_DIR = Path("diagnostics")
_DIAG_DIR.mkdir(exist_ok=True)

_LOG_FILE = _DIAG_DIR / "evolve_run.log"
_JSONL_FILE = _DIAG_DIR / "evolve_events.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    handlers=[logging.FileHandler(_LOG_FILE), logging.StreamHandler()],
)


def _log_event(event: str, **payload: object) -> None:
    """
    Write a one-line JSON record for programmatic analysis _and_
    emit a concise INFO line for human inspection.
    """

    record = {
        "ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        "event": event,
        **payload,
    }

    with _JSONL_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    # Short console line
    logging.info(
        "%s | %s",
        event,
        ", ".join(f"{k}={v}" for k, v in payload.items()),
    )


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #
def run(cmd: str) -> Tuple[int, str]:
    p = subprocess.run(cmd, shell=True, text=True, cwd=ROOT, capture_output=True)
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
        client = OpenAI()
        rsp = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=MAX_TOKENS,
        )
        out = rsp.choices[0].message.content or ""
        debug_log = os.getenv("DEBUG_LOG", "").lower() in ("1", "true", "yes")
        if debug_log:
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
    iters = 0

    # run baseline tests
    print("🔍 Running baseline tests...")
    code, out = run_tests()
    baseline_fail = test_fail_count(out)
    print(f"📊 Baseline test results: {baseline_fail} failures")
    
    # Print comprehensive current accuracy status
    print("\n" + "="*80)
    print("📈 BASELINE PARSER PERFORMANCE ANALYSIS")
    print("="*80)
    
    try:
        # Run accuracy analysis
        accuracy_result = run("python scripts/ai_focused_accuracy.py", capture_output=True, text=True)
        if accuracy_result.returncode == 0:
            print("✅ Accuracy analysis completed successfully")
            
            # Load and display detailed metrics
            try:
                import json
                with open("diagnostics/ai_focused_accuracy.json", "r") as f:
                    accuracy_data = json.load(f)
                
                summary = accuracy_data.get("summary", {})
                print(f"\n📊 SUMMARY METRICS:")
                print(f"   • Total PDFs analyzed: {summary.get('total_pdfs', 0)}")
                print(f"   • Training targets: {summary.get('training_targets', 0)}")
                print(f"   • Verified baselines: {summary.get('verified_baselines_working', 0)}")
                
                # Analyze fitness scores
                fitness_scores = []
                accuracy_percentages = []
                for result in accuracy_data.get("detailed_results", []):
                    if "fitness_scores" in result:
                        overall_fitness = result["fitness_scores"].get("overall", 0)
                        fitness_scores.append(overall_fitness)
                    
                    if "financial_accuracy" in result and isinstance(result["financial_accuracy"], dict):
                        acc_pct = result["financial_accuracy"].get("accuracy_percentage")
                        if acc_pct is not None and acc_pct >= 0:
                            accuracy_percentages.append(acc_pct)
                
                if fitness_scores:
                    print(f"\n🎯 FITNESS ANALYSIS:")
                    print(f"   • Best fitness score: {max(fitness_scores):.2f}")
                    print(f"   • Worst fitness score: {min(fitness_scores):.2f}")
                    print(f"   • Average fitness: {sum(fitness_scores)/len(fitness_scores):.2f}")
                    print(f"   • Total fitness deficit: {sum(abs(s) for s in fitness_scores):.2f}")
                
                if accuracy_percentages:
                    print(f"\n📈 ACCURACY ANALYSIS:")
                    print(f"   • Best accuracy: {max(accuracy_percentages):.2f}%")
                    print(f"   • Worst accuracy: {min(accuracy_percentages):.2f}%")
                    print(f"   • Average accuracy: {sum(accuracy_percentages)/len(accuracy_percentages):.2f}%")
                    
                # Show worst performers for targeting
                worst_performers = sorted(accuracy_data.get("detailed_results", []), 
                                       key=lambda x: x.get("fitness_scores", {}).get("overall", 0))[:3]
                if worst_performers:
                    print(f"\n🚨 TOP IMPROVEMENT TARGETS:")
                    for i, pdf in enumerate(worst_performers, 1):
                        name = pdf.get("pdf_name", "Unknown")
                        fitness = pdf.get("fitness_scores", {}).get("overall", 0)
                        acc = pdf.get("financial_accuracy", {}).get("accuracy_percentage", "N/A")
                        if isinstance(acc, (int, float)):
                            acc_str = f"{acc:.2f}%"
                        else:
                            acc_str = str(acc)
                        print(f"   {i}. {name}: fitness {fitness:.2f}, accuracy {acc_str}")
                        
            except Exception as e:
                print(f"⚠️  Could not parse detailed metrics: {e}")
            
        else:
            print(f"❌ Accuracy check failed: {accuracy_result.stderr}")
    except Exception as e:
        print(f"⚠️  Could not run accuracy analysis: {e}")
    
    print("="*80)
    
    FORCE_EVOLVE = os.getenv("FORCE_EVOLVE", "false").lower() in {"1", "true", "yes"}
    
    if baseline_fail == 0 and not FORCE_EVOLVE:
        print("Nothing to fix 🎉 (use FORCE_EVOLVE=true to run evolution anyway)")
        sys.exit(0)
    
    if FORCE_EVOLVE and baseline_fail == 0:
        print("🔄 FORCE_EVOLVE enabled - running evolution despite no test failures")
        print("🎯 Targeting parser accuracy improvements based on fitness data")

    while iters < MAX_ITERS and consec_misses < PATIENCE and baseline_fail > 0:
        iters += 1
        logging.info(
            "=== Iteration %s/%s (failures so far: %s) ===",
            iters,
            MAX_ITERS,
            baseline_fail,
        )
        _log_event("iteration_start", iteration=iters, baseline_fail=baseline_fail)

        # Get current file contents to provide context
        failed_files = set()
        for line in out.split("\n"):
            if "FAILED" in line and "::" in line:
                file_part = line.split("::")[0].strip()
                if file_part.startswith("FAILED "):
                    file_part = file_part[7:]  # Remove "FAILED "
                failed_files.add(file_part)
        
        file_contents = ""
        for filepath in list(failed_files)[:2]:  # Limit to first 2 files to avoid token limit
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r') as f:
                        content = f.read()
                    file_contents += f"\n--- Current content of {filepath} ---\n{content}\n"
                except Exception:
                    pass
        
        prompt = textwrap.dedent(
            f"""
            pytest failures (excerpt):
            {failing_snippet(out)}
            {file_contents}

            Provide a git diff that reduces failure count. Must start with "diff --git" and follow standard git patch format.
            Use the exact current file content shown above to create accurate line numbers and context.
            
            Example format:
            diff --git a/file.py b/file.py
            index abc123..def456 100644
            --- a/file.py
            +++ b/file.py
            @@ -1,3 +1,4 @@
             existing line
            +new line
             another existing line
        """
        )
        
        print("🤖 Asking AI for improvement patch...")
        print(f"📝 Prompt length: {len(prompt)} characters")
        
        _log_event("llm_prompt", prompt_chars=len(prompt))
        patch = ask_llm(prompt)
        _log_event("llm_response", response_chars=len(patch))
        
        if not patch.startswith("diff --git"):
            print("❌ LLM did not return a diff, skipping iteration.")
            consec_misses += 1
            continue
            
        # Count changes
        additions = patch.count("\n+")
        deletions = patch.count("\n-")
        print(f"📋 Patch stats: +{additions} -{deletions} lines")
        
        if additions + deletions > MAX_LINES:
            print(f"⚠️  Patch too large ({additions + deletions} > {MAX_LINES} lines), skipping.")
            consec_misses += 1
            continue
            
        print("🔧 Applying patch...")
        if not apply_patch(patch):
            print("❌ Patch failed to apply.")
            consec_misses += 1
            continue

        print("🧪 Running tests after patch...")
        new_code, new_out = run_tests()
        new_fail = test_fail_count(new_out)
        print(f"📊 Test results: {new_fail} failures (was {baseline_fail})")

        if new_fail < baseline_fail:
            # good – keep and commit
            print(f"🎉 IMPROVEMENT DETECTED!")
            print(f"   Test failures reduced: {baseline_fail} → {new_fail}")
            
            # Run accuracy analysis to measure improvement
            try:
                accuracy_result = run("python scripts/ai_focused_accuracy.py", capture_output=True, text=True)
                if accuracy_result.returncode == 0:
                    try:
                        import json
                        with open("diagnostics/ai_focused_accuracy.json", "r") as f:
                            new_accuracy_data = json.load(f)
                        
                        # Calculate improvement metrics
                        new_fitness_scores = []
                        new_accuracy_percentages = []
                        for result in new_accuracy_data.get("detailed_results", []):
                            if "fitness_scores" in result:
                                overall_fitness = result["fitness_scores"].get("overall", 0)
                                new_fitness_scores.append(overall_fitness)
                            
                            if "financial_accuracy" in result and isinstance(result["financial_accuracy"], dict):
                                acc_pct = result["financial_accuracy"].get("accuracy_percentage")
                                if acc_pct is not None and acc_pct >= 0:
                                    new_accuracy_percentages.append(acc_pct)
                        
                        if new_fitness_scores:
                            print(f"\n📈 POST-PATCH PERFORMANCE:")
                            print(f"   • New average fitness: {sum(new_fitness_scores)/len(new_fitness_scores):.2f}")
                            print(f"   • New total fitness deficit: {sum(abs(s) for s in new_fitness_scores):.2f}")
                            
                        if new_accuracy_percentages:
                            print(f"   • New average accuracy: {sum(new_accuracy_percentages)/len(new_accuracy_percentages):.2f}%")
                            print(f"   • New best accuracy: {max(new_accuracy_percentages):.2f}%")
                            
                    except Exception as e:
                        print(f"   ⚠️  Could not analyze post-patch metrics: {e}")
            except Exception as e:
                print(f"   ⚠️  Could not run post-patch analysis: {e}")
            
            consec_misses = 0
            baseline_fail = new_fail
            out = new_out
            run("git add -u")
            # Commit any staged changes
            commit_msg = f"🤖 AUTO-FIX: failures {baseline_fail} after iter {iters}"
            run(f'git commit -am "{commit_msg}"')
            print("✅ Patch accepted and committed")
        else:
            # revert
            run("git reset --hard")
            consec_misses += 1
            print(f"❌ Patch reverted (failures: {baseline_fail} → {new_fail})")

        if baseline_fail == 0:
            break

    # Final comprehensive summary
    print("\n" + "="*80)
    print("🏁 EVOLUTION CYCLE COMPLETE")
    print("="*80)
    print(f"📊 FINAL RESULTS:")
    print(f"   • Iterations completed: {iters}/{MAX_ITERS}")
    print(f"   • Test failures remaining: {baseline_fail}")
    print(f"   • Consecutive misses: {consec_misses}/{PATIENCE}")
    
    # Final accuracy analysis
    try:
        accuracy_result = run("python scripts/ai_focused_accuracy.py", capture_output=True, text=True)
        if accuracy_result.returncode == 0:
            try:
                import json
                with open("diagnostics/ai_focused_accuracy.json", "r") as f:
                    final_accuracy_data = json.load(f)
                
                final_fitness_scores = []
                final_accuracy_percentages = []
                for result in final_accuracy_data.get("detailed_results", []):
                    if "fitness_scores" in result:
                        overall_fitness = result["fitness_scores"].get("overall", 0)
                        final_fitness_scores.append(overall_fitness)
                    
                    if "financial_accuracy" in result and isinstance(result["financial_accuracy"], dict):
                        acc_pct = result["financial_accuracy"].get("accuracy_percentage")
                        if acc_pct is not None and acc_pct >= 0:
                            final_accuracy_percentages.append(acc_pct)
                
                if final_fitness_scores:
                    print(f"\n🎯 FINAL FITNESS METRICS:")
                    print(f"   • Average fitness: {sum(final_fitness_scores)/len(final_fitness_scores):.2f}")
                    print(f"   • Best fitness: {max(final_fitness_scores):.2f}")
                    print(f"   • Worst fitness: {min(final_fitness_scores):.2f}")
                    print(f"   • Total deficit: {sum(abs(s) for s in final_fitness_scores):.2f}")
                    
                if final_accuracy_percentages:
                    print(f"\n📈 FINAL ACCURACY METRICS:")
                    print(f"   • Average accuracy: {sum(final_accuracy_percentages)/len(final_accuracy_percentages):.2f}%")
                    print(f"   • Best accuracy: {max(final_accuracy_percentages):.2f}%")
                    print(f"   • Worst accuracy: {min(final_accuracy_percentages):.2f}%")
                    
                summary = final_accuracy_data.get("summary", {})
                training_targets = summary.get("training_targets", 0)
                if training_targets > 0:
                    print(f"\n🚨 REMAINING WORK:")
                    print(f"   • PDFs needing improvement: {training_targets}")
                    
            except Exception as e:
                print(f"⚠️  Could not analyze final metrics: {e}")
    except Exception as e:
        print(f"⚠️  Could not run final analysis: {e}")
        
    print("="*80)
    
    if baseline_fail == 0:
        print("🎉 SUCCESS: All tests passing!")
    else:
        print(f"⚠️  INCOMPLETE: {baseline_fail} test failures remain")
        
    # exit 0 so CI step passes; overall job status handled by outer steps
    sys.exit(0)


if __name__ == "__main__":
    main()

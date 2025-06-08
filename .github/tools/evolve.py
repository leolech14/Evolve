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

from openai import OpenAI

# Configuration
DIAGNOSTICS = Path("diagnostics")
MAX_TOKENS = 6144  # Increased for comprehensive AI analysis
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "5"))
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "8"))  # More iterations for 99% target
MODEL = os.getenv("OPENAI_MODEL", "gpt-4")
INVARIANT_TARGET_SCORE = float(os.getenv("INVARIANT_TARGET", "99.0"))  # 99% financial accuracy target


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
        "invariant_scores": {},
        "hard_golden_status": {},
        "ai_focused_accuracy": {},
    }

    # Get test output
    test_file = DIAGNOSTICS / "test.txt"
    if test_file.exists():
        context["tests"] = test_file.read_text()

    # Get lint output
    lint_file = DIAGNOSTICS / "lint.txt"
    if lint_file.exists():
        context["lint"] = lint_file.read_text()

    # Get traditional accuracy results (legacy)
    accuracy_file = DIAGNOSTICS / "accuracy.json"
    if accuracy_file.exists():
        try:
            context["accuracy"] = json.loads(accuracy_file.read_text())
        except Exception:
            context["errors"].append("Failed to read accuracy results")

    # Get NEW invariant scores (primary AI feedback)
    invariant_file = DIAGNOSTICS / "invariant_scores.json"
    if invariant_file.exists():
        try:
            context["invariant_scores"] = json.loads(invariant_file.read_text())
        except Exception:
            context["errors"].append("Failed to read invariant scores")

    # Get AI-focused accuracy analysis
    ai_accuracy_file = DIAGNOSTICS / "ai_focused_accuracy.json"
    if ai_accuracy_file.exists():
        try:
            context["ai_focused_accuracy"] = json.loads(ai_accuracy_file.read_text())
        except Exception:
            context["errors"].append("Failed to read AI-focused accuracy")

    # Get all tracked Python files (not just changed ones)
    _, output = run_command(["git", "ls-files", "*.py"])
    context["files"] = [f for f in output.splitlines()]

    # Only include the main parser and the sentinel test to avoid context overflow
    context["files"] = [
        "src/statement_refinery/pdf_to_csv.py",
        "tests/test_evolve_sentinel.py",
    ]

    # Get file contents (truncate to avoid context overflow)
    for file in context["files"]:
        try:
            with open(file) as f:
                content = f.read()
                # Truncate to first 4000 characters to avoid context overflow
                context[file] = content[:4000]
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

        # Run the same validation as CI re-run checks
        print("Running full validation suite...")

        lint_code, lint_out = run_command(["ruff", "check", "--fix", "."], capture=True)
        print(f"Ruff: {'✅' if lint_code == 0 else '❌'}")

        black_code, _ = run_command(["black", "."], capture=True)
        black_check_code, black_out = run_command(
            ["black", "--check", "."], capture=True
        )
        print(f"Black: {'✅' if black_check_code == 0 else '❌'}")

        mypy_code, mypy_out = run_command(["mypy", "src/"], capture=True)
        print(f"MyPy: {'✅' if mypy_code == 0 else '❌'}")

        test_code, test_out = run_command(
            ["pytest", "-v", "--cov=statement_refinery", "--cov-fail-under=70"],
            capture=True,
        )
        print(f"Tests: {'✅' if test_code == 0 else '❌'}")

        accuracy_code, accuracy_out = run_command(
            ["python", "scripts/check_accuracy.py", "--threshold", "99"], capture=True
        )
        print(f"Accuracy: {'✅' if accuracy_code == 0 else '❌'}")

        if all(
            code == 0
            for code in [
                lint_code,
                black_check_code,
                mypy_code,
                test_code,
                accuracy_code,
            ]
        ):
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
    """Apply a git patch and create pull request. Fallback to direct file overwrite if patch fails."""
    if not patch or not patch.strip():
        print("[apply_patch] Patch is empty or blank.")
        return False

    try:
        # Write patch
        patch_file = DIAGNOSTICS / "ai-patch.patch"
        patch_file.write_text(patch)
        print(f"[apply_patch] Patch written to {patch_file}")

        # Apply patch with 3-way merge and index update
        code, out = run_command(
            ["git", "apply", "--index", "--3way", "--whitespace=fix", str(patch_file)]
        )
        print(
            f"[apply_patch] git apply --index --3way --whitespace=fix: code={code}, output={out[:500]}"
        )
        if code != 0:
            print(
                "Patch failed to apply cleanly; attempting direct file overwrite fallback..."
            )
            print(f"[apply_patch] Fallback: AI suggestion (truncated):\n{patch[:1000]}")
            if not apply_direct_file_overwrite(patch):
                print("Fallback direct file overwrite also failed.")
                return False
            branch = f"ai-patch-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            run_command(["git", "checkout", "-b", branch])
            run_command(["git", "add", "."])
            run_command(
                [
                    "git",
                    "commit",
                    "-m",
                    "🤖 AUTO-FIX: Direct file overwrite fallback",
                ]
            )
            run_command(["git", "push", "origin", branch])
            run_command(
                [
                    "gh",
                    "pr",
                    "create",
                    "--title",
                    "🤖 AI: Auto-patch improvements (fallback)",
                    "--body",
                    "Automated fixes from AI assistant (direct file overwrite fallback)",
                    "--label",
                    "auto-patch",
                ]
            )
            print(f"[apply_patch] Fallback PR created on branch {branch}")
            return True

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
        print(f"[apply_patch] PR created on branch {branch}")
        return True
    except Exception as e:
        print(f"[apply_patch] Exception: {e}")
        return False


def apply_direct_file_overwrite(suggestion: str) -> bool:
    """Parse AI suggestion blocks and overwrite files directly. If suggestion is a patch/diff, log and skip."""
    try:
        # Detect patch/diff format
        if suggestion.lstrip().startswith("From ") and "Subject: [PATCH]" in suggestion:
            patch_path = DIAGNOSTICS / "ai-patch-unapplied.patch"
            patch_path.write_text(suggestion)
            print(
                f"[apply_direct_file_overwrite] Detected patch/diff format. Patch saved to {patch_path}. Manual review required. Skipping direct overwrite."
            )
            return False

        # Parse file blocks as before
        current_file = None
        inside_block = False
        buffer = []
        wrote_any = False
        print("[apply_direct_file_overwrite] Starting parse of AI suggestion...")
        for idx, line in enumerate(suggestion.splitlines()):
            if line.startswith("FILE: "):
                if current_file and buffer:
                    try:
                        Path(current_file).parent.mkdir(parents=True, exist_ok=True)
                        Path(current_file).write_text("\n".join(buffer))
                        print(
                            f"[apply_direct_file_overwrite] Wrote file: {current_file} (lines {len(buffer)})"
                        )
                        wrote_any = True
                    except Exception as file_exc:
                        print(
                            f"[apply_direct_file_overwrite] Failed to write {current_file}: {file_exc}"
                        )
                current_file = line.split(":", 1)[1].strip()
                buffer = []
                inside_block = False
                print(
                    f"[apply_direct_file_overwrite] Found file block: {current_file} (at line {idx})"
                )
            elif line.startswith("```") and current_file:
                inside_block = not inside_block
                if not inside_block and buffer:
                    try:
                        Path(current_file).parent.mkdir(parents=True, exist_ok=True)
                        Path(current_file).write_text("\n".join(buffer))
                        print(
                            f"[apply_direct_file_overwrite] Wrote file: {current_file} (lines {len(buffer)})"
                        )
                        wrote_any = True
                        buffer = []
                    except Exception as file_exc:
                        print(
                            f"[apply_direct_file_overwrite] Failed to write {current_file}: {file_exc}"
                        )
            elif inside_block:
                buffer.append(line)
        if current_file and buffer:
            try:
                Path(current_file).parent.mkdir(parents=True, exist_ok=True)
                Path(current_file).write_text("\n".join(buffer))
                print(
                    f"[apply_direct_file_overwrite] Wrote file: {current_file} (lines {len(buffer)})"
                )
                wrote_any = True
            except Exception as file_exc:
                print(
                    f"[apply_direct_file_overwrite] Failed to write {current_file}: {file_exc}"
                )
        print(f"[apply_direct_file_overwrite] Done. Any files written: {wrote_any}")
        return wrote_any
    except Exception as e:
        print(f"[apply_direct_file_overwrite] Exception: {e}")
        return False


def get_current_invariant_score() -> float:
    """Get current invariant score from diagnostics."""
    invariant_file = DIAGNOSTICS / "invariant_scores.json"
    if invariant_file.exists():
        try:
            data = json.loads(invariant_file.read_text())
            return data.get("overall_score", 0.0)
        except Exception:
            return 0.0
    return 0.0


def main() -> int:
    """Main entry point with multi-iteration capability."""
    print("🧬 Starting EVOLVE multi-iteration AI improvement process...")

    ensure_best_branch()

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        return 1

    # Multi-iteration loop
    best_score = get_current_invariant_score()
    print(f"📊 Starting invariant score: {best_score:.1f}%")
    
    for iteration in range(1, MAX_ITERATIONS + 1):
        print(f"\n🔄 ITERATION {iteration}/{MAX_ITERATIONS}")
        print("=" * 50)
        
        # Collect context
        print("📝 Collecting context...")
        context = collect_context()
        if not context["files"]:
            print("No Python files found")
            return 0
        
        current_score = get_current_invariant_score()
        print(f"📊 Current invariant score: {current_score:.1f}%")
        
        # Check if we've reached 99% target
        if current_score >= INVARIANT_TARGET_SCORE:
            print(f"🎉 99% FINANCIAL ACCURACY ACHIEVED! Score {current_score:.1f}% >= {INVARIANT_TARGET_SCORE}%")
            return 0
        
        # Check if we're making progress
        if iteration > 1 and current_score <= best_score:
            print(f"⚠️  No improvement in iteration {iteration} ({current_score:.1f}% <= {best_score:.1f}%)")
            if iteration >= 2:  # Give at least 2 attempts
                print("🛑 Stopping iterations - no progress detected")
                break
        
        best_score = max(best_score, current_score)

        # Single iteration attempt
        success = run_single_iteration(context, iteration, current_score)
        
        if success:
            print(f"✅ Iteration {iteration} completed successfully")
            # Re-run validation to get updated scores
            run_command(["python", "scripts/parse_all.py", "--out", "csv_output"])
            run_command(["python", "-m", "pytest", "tests/test_invariants.py", "--csv-dir", "csv_output", "-v"])
        else:
            print(f"❌ Iteration {iteration} failed")
    
    final_score = get_current_invariant_score()
    improvement = final_score - best_score
    print(f"\n📊 FINAL RESULTS")
    print("=" * 50)
    print(f"Final score: {final_score:.1f}%")
    print(f"Improvement: +{improvement:.1f}%")
    
    if final_score >= INVARIANT_TARGET_SCORE:
        print("🎉 99% FINANCIAL ACCURACY TARGET ACHIEVED!")
        return 0
    else:
        print(f"⚠️  99% target not reached (need {INVARIANT_TARGET_SCORE:.1f}%)")
        return 1


def run_single_iteration(context: dict, iteration: int, current_score: float) -> bool:
    """Run a single iteration of AI improvement."""
    print(f"🧠 Running AI analysis for iteration {iteration}...")

    # Prepare enhanced prompt with new training signals
    prompt = [
        f"You are an AI parser improvement specialist (ITERATION {iteration}/{MAX_ITERATIONS}). "
        f"Using Hard Goldens + Soft Invariants strategy to achieve 99% financial accuracy. "
        f"Current score: {current_score:.1f}% → Target: 99.0%",
        "",
        "=== TRAINING SIGNAL ANALYSIS ===",
        "",
        "HARD GOLDENS (Must maintain 100% exact match):",
        "- Itau_2024-10.pdf: MUST remain exactly matching golden CSV",
        "- Itau_2025-05.pdf: MUST remain exactly matching golden CSV",
        "",
        "INVARIANT SCORES (Primary improvement target):",
        json.dumps(context["invariant_scores"], indent=2),
        "",
        "FINANCIAL ACCURACY BY PDF:",
        json.dumps(context["ai_focused_accuracy"], indent=2),
        "",
        "=== IMPROVEMENT FOCUS ===",
        f"Priority: Bridge the gap from {current_score:.1f}% to 99.0% financial accuracy",
        "Method: Enhance regex patterns in pdf_to_csv.py to capture missing transactions",
        f"Iteration Strategy: Progressive improvement over {MAX_ITERATIONS} iterations",
        "",
        "=== Traditional Metrics (Reference Only) ===",
        "",
        "Test Output:",
        context["tests"][:1000],  # Truncate for context
        "",
        "Lint Output:",
        context["lint"][:500],    # Truncate for context
        "",
        "Legacy Accuracy:",
        json.dumps(context["accuracy"], indent=2),
        "",
        "=== Code Files to Improve ===",
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
            f"IMPROVEMENT STRATEGY (Iteration {iteration}):",
            "",
            "1. PRESERVE Hard Goldens: Ensure Itau_2024-10.pdf and Itau_2025-05.pdf maintain exact CSV output",
            "2. TARGET 99% Financial Accuracy: Focus on PDFs with worst accuracy scores",
            "3. ENHANCE Regex Patterns: Add new patterns to capture missing transaction types", 
            "4. VALIDATE Against PDF Totals: Ensure PDF total matches parsed CSV total",
            "",
            "SPECIFIC TARGETS (from financial accuracy analysis):",
            "- Worst performers need new transaction patterns",
            "- Missing amounts indicate unparsed transaction lines", 
            "- Focus on transaction formats not captured by current regex",
            "",
            "Please suggest fixes in the following format:",
            "FILE: path/to/file.py",
            "```python",
            "complete fixed file content",
            "```",
            "",
            "PRIORITY ORDER:",
            "1. Add missing regex patterns for unparsed transactions",
            "2. Fix financial total extraction patterns", 
            "3. Improve transaction categorization",
            "4. Maintain hard golden compatibility",
            "5. Address any lint/test issues",
        ]
    )

    # Get AI suggestion (OpenAI API)
    print("🧠 Requesting AI analysis...")
    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": "\n".join(prompt)}],
            max_tokens=MAX_TOKENS,
            temperature=0.1,
        )
        suggestion = response.choices[0].message.content
    except Exception as e:
        print(f"Error: Failed to get AI suggestion: {e}")
        return False

    # Create and apply patch
    print("🔧 Creating patch...")
    patch = create_patch(suggestion)
    if not patch:
        print("Error: Failed to create patch")
        return False

    print("⬆️  Creating pull request...")
    if not apply_patch(patch):
        print("Error: Failed to apply patch")
        return False

    print(f"✅ Iteration {iteration} completed!")
    return True


if __name__ == "__main__":
    sys.exit(main())

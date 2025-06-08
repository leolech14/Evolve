#!/usr/bin/env python3
"""
Hard Golden Validation Script

Validates that the 2 verified "hard golden" PDFs produce exact CSV matches.
This provides binary PASS/FAIL signal for the AI training loop.

Usage:
    python scripts/check_hard_goldens.py [--fail-fast]
"""

import argparse
import contextlib
import difflib
import io
import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_refinery import pdf_to_csv

DATA_DIR = ROOT / "tests" / "data"
CONFIG_DIR = ROOT / "config"


def load_hard_goldens() -> list[str]:
    """Load list of hard golden PDF names from config."""
    goldens_file = CONFIG_DIR / "hard_goldens.txt"
    if not goldens_file.exists():
        return ["Itau_2024-10.pdf", "Itau_2025-05.pdf"]  # Default fallback

    goldens = []
    for line in goldens_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            goldens.append(line)
    return goldens


def check_hard_golden(pdf_path: Path) -> tuple[bool, str]:
    """
    Check a single hard golden PDF against its expected CSV.

    Returns:
        (is_exact_match, diff_output)
    """
    print(f"\n🔍 Checking hard golden: {pdf_path.name}")

    # Generate CSV output
    buf = io.StringIO()
    args = [str(pdf_path)]

    with contextlib.redirect_stdout(buf):
        try:
            pdf_to_csv.main(args)
        except Exception as e:
            return False, f"Error generating CSV: {e}"

    generated_lines = buf.getvalue().splitlines()

    # Load expected golden CSV
    golden_csv = pdf_path.with_name(f"golden_{pdf_path.stem.split('_')[-1]}.csv")
    if not golden_csv.exists():
        return False, f"Missing golden CSV: {golden_csv.name}"

    expected_lines = golden_csv.read_text().splitlines()

    # Compare line by line
    diff = difflib.unified_diff(
        expected_lines,
        generated_lines,
        fromfile=f"expected/{golden_csv.name}",
        tofile=f"generated/{pdf_path.stem}.csv",
        lineterm="",
    )

    diff_list = list(diff)
    is_exact_match = len(diff_list) == 0

    if is_exact_match:
        print(f"✅ {pdf_path.name}: Exact match")
        return True, ""
    else:
        print(f"❌ {pdf_path.name}: Differences found")
        diff_output = "\n".join(diff_list)
        return False, diff_output


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate hard golden PDFs produce exact CSV matches"
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop on first failure instead of checking all goldens",
    )
    args = parser.parse_args()

    print("🏆 HARD GOLDEN VALIDATION")
    print("=" * 50)

    # Load hard golden PDFs
    hard_goldens = load_hard_goldens()
    if not hard_goldens:
        print("❌ No hard golden PDFs configured")
        return 1

    print(f"📋 Checking {len(hard_goldens)} hard golden PDFs:")
    for golden in hard_goldens:
        print(f"  • {golden}")

    # Validate each hard golden
    all_passed = True
    failed_pdfs = []

    for golden_name in hard_goldens:
        pdf_path = DATA_DIR / golden_name

        if not pdf_path.exists():
            print(f"❌ {golden_name}: PDF file not found")
            all_passed = False
            failed_pdfs.append(golden_name)
            if args.fail_fast:
                break
            continue

        is_match, diff_output = check_hard_golden(pdf_path)

        if not is_match:
            all_passed = False
            failed_pdfs.append(golden_name)

            # Show diff details
            if diff_output:
                print(f"\n📝 Differences for {golden_name}:")
                print(diff_output[:1000])  # Truncate very long diffs
                if len(diff_output) > 1000:
                    print("\n... (diff truncated)")

            if args.fail_fast:
                break

    # Summary
    print("\n📊 HARD GOLDEN SUMMARY")
    print("=" * 50)
    print(f"Total hard goldens: {len(hard_goldens)}")
    print(f"Passed: {len(hard_goldens) - len(failed_pdfs)}")
    print(f"Failed: {len(failed_pdfs)}")

    if all_passed:
        print("\n🎉 All hard goldens pass exact validation!")
        return 0
    else:
        print(f"\n💥 Failed hard goldens: {', '.join(failed_pdfs)}")
        print("\nHard golden failures indicate:")
        print("  1. Parser regression affecting verified baselines")
        print("  2. Need to update golden CSVs after intentional changes")
        print("  3. Broken AI patches that affect core functionality")
        return 1


if __name__ == "__main__":
    sys.exit(main())

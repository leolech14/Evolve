#!/usr/bin/env python3
"""
Real Accuracy Validator - Uses PDF total reconciliation as ground truth validation.
Bypasses circular golden file validation to measure actual parsing accuracy.
"""

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_refinery import pdf_to_csv
from statement_refinery.validation import extract_total_from_pdf


def validate_real_accuracy(pdf_path: Path) -> dict:
    """Validate parsing accuracy using PDF total as ground truth."""

    # Extract all lines
    all_lines = list(pdf_to_csv.iter_pdf_lines(pdf_path))

    # Parse transactions
    parsed_transactions = []
    for line in all_lines:
        result = pdf_to_csv.parse_statement_line(line)
        if result:
            parsed_transactions.append(result)

    # Calculate totals
    parsed_total = sum(t["amount_brl"] for t in parsed_transactions)

    try:
        pdf_total = extract_total_from_pdf(pdf_path)
        total_available = True
    except Exception:
        pdf_total = None
        total_available = False

    # Calculate accuracy metrics
    coverage_rate = len(parsed_transactions) / max(1, len(all_lines))

    if total_available and pdf_total:
        total_delta = abs(parsed_total - pdf_total)
        total_accuracy = (
            max(0, 1 - (total_delta / abs(pdf_total))) if pdf_total != 0 else 0
        )
        missing_amount = pdf_total - parsed_total
        missing_percentage = (missing_amount / pdf_total * 100) if pdf_total != 0 else 0
    else:
        total_delta = None
        total_accuracy = None
        missing_amount = None
        missing_percentage = None

    return {
        "pdf_name": pdf_path.name,
        "line_coverage": {
            "total_lines": len(all_lines),
            "parsed_lines": len(parsed_transactions),
            "coverage_rate": coverage_rate,
        },
        "financial_accuracy": {
            "pdf_total": float(pdf_total) if pdf_total else None,
            "parsed_total": float(parsed_total),
            "total_delta": float(total_delta) if total_delta else None,
            "total_accuracy": total_accuracy,
            "missing_amount": float(missing_amount) if missing_amount else None,
            "missing_percentage": missing_percentage,
            "total_available": total_available,
        },
        "quality_assessment": _assess_quality(coverage_rate, total_accuracy),
    }


def _assess_quality(coverage_rate: float, total_accuracy: float) -> dict:
    """Assess overall parsing quality."""

    # Coverage assessment
    if coverage_rate >= 0.8:
        coverage_grade = "A"
    elif coverage_rate >= 0.6:
        coverage_grade = "B"
    elif coverage_rate >= 0.4:
        coverage_grade = "C"
    else:
        coverage_grade = "F"

    # Total accuracy assessment (if available)
    if total_accuracy is not None:
        if total_accuracy >= 0.99:
            accuracy_grade = "A+"
        elif total_accuracy >= 0.95:
            accuracy_grade = "A"
        elif total_accuracy >= 0.90:
            accuracy_grade = "B"
        elif total_accuracy >= 0.80:
            accuracy_grade = "C"
        else:
            accuracy_grade = "F"
    else:
        accuracy_grade = "Unknown"

    return {
        "coverage_grade": coverage_grade,
        "accuracy_grade": accuracy_grade,
        "overall_assessment": _get_overall_grade(coverage_grade, accuracy_grade),
    }


def _get_overall_grade(coverage_grade: str, accuracy_grade: str) -> str:
    """Get overall quality grade."""
    if accuracy_grade == "Unknown":
        return f"Coverage: {coverage_grade} (Financial accuracy unknown)"

    grades = {"A+": 4.3, "A": 4.0, "B": 3.0, "C": 2.0, "F": 0.0}
    avg = (grades.get(coverage_grade, 0) + grades.get(accuracy_grade, 0)) / 2

    if avg >= 4.0:
        return "EXCELLENT"
    elif avg >= 3.0:
        return "GOOD"
    elif avg >= 2.0:
        return "FAIR"
    else:
        return "POOR"


def main():
    parser = argparse.ArgumentParser(
        description="Real accuracy validation using PDF totals"
    )
    parser.add_argument("pdf_dir", help="Directory containing PDF files")
    parser.add_argument(
        "--output",
        default="diagnostics/real_accuracy.json",
        help="Output file for results",
    )
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    if not pdf_dir.exists():
        print(f"Error: Directory {pdf_dir} does not exist")
        return 1

    # Validate all PDFs
    results = []
    total_missing_amount = Decimal("0")
    total_pdf_amount = Decimal("0")
    validatable_pdfs = 0

    print("REAL ACCURACY VALIDATION")
    print("=" * 50)

    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        result = validate_real_accuracy(pdf_path)
        results.append(result)

        financial = result["financial_accuracy"]
        quality = result["quality_assessment"]

        print(f"\n📄 {result['pdf_name']}")
        print(
            f"   Coverage: {result['line_coverage']['coverage_rate']:.1%} ({quality['coverage_grade']})"
        )

        if financial["total_available"]:
            validatable_pdfs += 1
            pdf_total = Decimal(str(financial["pdf_total"]))
            missing = Decimal(str(financial["missing_amount"]))
            total_pdf_amount += pdf_total
            total_missing_amount += missing

            print(
                f"   Financial: {financial['missing_percentage']:.1f}% missing ({quality['accuracy_grade']})"
            )
            print(
                f"   Total: R$ {financial['parsed_total']:.2f} / R$ {financial['pdf_total']:.2f}"
            )
        else:
            print("   Financial: Cannot validate (PDF total not extractable)")

        print(f"   Overall: {quality['overall_assessment']}")

    # Overall summary
    if validatable_pdfs > 0:
        overall_missing_pct = (
            (total_missing_amount / total_pdf_amount * 100)
            if total_pdf_amount > 0
            else 0
        )
        overall_accuracy = (
            max(0, 1 - (total_missing_amount / total_pdf_amount))
            if total_pdf_amount > 0
            else 0
        )
    else:
        overall_missing_pct = None
        overall_accuracy = None

    summary = {
        "validation_timestamp": str(Path().absolute()),
        "total_pdfs": len(results),
        "validatable_pdfs": validatable_pdfs,
        "overall_financial_accuracy": overall_accuracy,
        "overall_missing_percentage": (
            float(overall_missing_pct) if overall_missing_pct else None
        ),
        "total_missing_amount": float(total_missing_amount),
        "total_pdf_amount": float(total_pdf_amount),
        "individual_results": results,
    }

    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    print("\n" + "=" * 50)
    print("OVERALL REAL ACCURACY ASSESSMENT")
    print("=" * 50)
    print(f"PDFs processed: {len(results)}")
    print(f"Financially validatable: {validatable_pdfs}")

    if overall_accuracy is not None:
        print(f"REAL FINANCIAL ACCURACY: {overall_accuracy:.1%}")
        print(
            f"Missing amount: R$ {total_missing_amount:.2f} of R$ {total_pdf_amount:.2f}"
        )
        print(f"Missing percentage: {overall_missing_pct:.1f}%")

        if overall_accuracy >= 0.99:
            print("🎯 STATUS: PRODUCTION READY")
        elif overall_accuracy >= 0.95:
            print("✅ STATUS: GOOD - Minor improvements needed")
        elif overall_accuracy >= 0.90:
            print("⚠️  STATUS: FAIR - Significant improvements needed")
        else:
            print("❌ STATUS: POOR - Major improvements required")
    else:
        print("❓ STATUS: UNKNOWN - Cannot validate without PDF totals")

    print(f"\nResults saved to: {output_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

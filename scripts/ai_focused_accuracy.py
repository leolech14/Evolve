#!/usr/bin/env python3
"""
AI-Focused Accuracy Check

This script provides the AI agent with clear, actionable feedback by:
1. Ignoring fake golden CSV matches
2. Focusing on real financial accuracy vs PDF totals
3. Highlighting specific parsing failures for improvement
"""

import sys
from pathlib import Path
import json

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_refinery.pdf_to_csv import parse_pdf
from statement_refinery.validation import extract_total_from_pdf, calculate_csv_total

DATA_DIR = ROOT / "tests" / "data"

# Only these 2 have real golden CSVs - the rest are training targets
VERIFIED_BASELINES = {
    "Itau_2024-10.pdf": "golden_2024-10.csv",
    "Itau_2025-05.pdf": "golden_2025-05.csv",
}


def analyze_pdf_for_ai(pdf_path: Path) -> dict:
    """Analyze a single PDF and return AI-focused results."""

    result = {
        "pdf_name": pdf_path.name,
        "is_verified_baseline": pdf_path.name in VERIFIED_BASELINES,
        "parsing_status": "unknown",
        "financial_accuracy": None,
        "missing_patterns": [],
        "diagnostic_summary": "",
    }

    try:
        # Get parsed results (bypass golden CSV to force real parsing)
        rows = parse_pdf(pdf_path, use_golden_if_available=False)
        parsed_total = calculate_csv_total(rows)

        # Get PDF total for comparison
        try:
            pdf_total = extract_total_from_pdf(pdf_path)
            delta = abs(parsed_total - pdf_total)
            accuracy = float(1 - (delta / pdf_total)) if pdf_total > 0 else 0

            result["financial_accuracy"] = {
                "parsed_total": float(parsed_total),
                "pdf_total": float(pdf_total),
                "delta": float(delta),
                "accuracy_percentage": accuracy * 100,
                "status": "GOOD" if accuracy > 0.95 else "NEEDS_IMPROVEMENT",
            }

            if accuracy < 0.95:
                result["parsing_status"] = "NEEDS_IMPROVEMENT"
                result["diagnostic_summary"] = (
                    f"Missing {delta:.2f} BRL ({(1-accuracy)*100:.1f}% of total)"
                )
            else:
                result["parsing_status"] = "GOOD"

        except Exception as e:
            result["diagnostic_summary"] = f"Cannot extract PDF total: {e}"
            result["parsing_status"] = "PDF_TOTAL_UNAVAILABLE"

    except Exception as e:
        result["parsing_status"] = "PARSING_FAILED"
        result["diagnostic_summary"] = f"Parser error: {e}"

    return result


def main():
    """Generate AI-focused accuracy report."""

    print("🤖 AI-FOCUSED ACCURACY ANALYSIS")
    print("=" * 50)

    pdfs = sorted(DATA_DIR.glob("*tau_*.pdf"))

    verified_good = 0
    training_targets = []
    overall_results = []

    for pdf in pdfs:
        result = analyze_pdf_for_ai(pdf)
        overall_results.append(result)

        if result["is_verified_baseline"]:
            print(f"✅ BASELINE: {pdf.name}")
            if result["parsing_status"] == "GOOD":
                verified_good += 1
            else:
                print(f"   ❌ BROKEN BASELINE: {result['diagnostic_summary']}")
        else:
            print(f"🎯 TARGET: {pdf.name}")
            if result["financial_accuracy"]:
                acc = result["financial_accuracy"]["accuracy_percentage"]
                print(f"   📊 Accuracy: {acc:.1f}% - {result['diagnostic_summary']}")
            else:
                print(f"   ❓ {result['diagnostic_summary']}")

            if result["parsing_status"] == "NEEDS_IMPROVEMENT":
                training_targets.append(result)

    print("\n🎯 AI TRAINING SUMMARY")
    print("=" * 50)
    print(f"Verified baselines working: {verified_good}/2")
    print(f"Training targets needing work: {len(training_targets)}")

    if training_targets:
        print("\n📝 PRIORITY TARGETS FOR AI IMPROVEMENT:")
        for target in sorted(
            training_targets,
            key=lambda x: (
                x["financial_accuracy"]["accuracy_percentage"]
                if x["financial_accuracy"]
                else 0
            ),
        ):
            if target["financial_accuracy"]:
                acc = target["financial_accuracy"]["accuracy_percentage"]
                delta = target["financial_accuracy"]["delta"]
                print(
                    f"   • {target['pdf_name']}: {acc:.1f}% (missing {delta:.2f} BRL)"
                )

    # Save AI-focused results
    output_file = ROOT / "diagnostics" / "ai_focused_accuracy.json"
    with open(output_file, "w") as f:
        json.dump(
            {
                "summary": {
                    "verified_baselines_working": verified_good,
                    "training_targets": len(training_targets),
                    "total_pdfs": len(pdfs),
                },
                "detailed_results": overall_results,
            },
            f,
            indent=2,
        )

    print(f"\n📁 Detailed results saved to: {output_file}")

    if len(training_targets) > 0:
        print(
            f"\n🚨 AI AGENT: Focus on improving patterns for {len(training_targets)} PDFs"
        )
        return 1  # Signal that improvement is needed
    else:
        print("\n✅ All targets meeting accuracy requirements!")
        return 0


if __name__ == "__main__":
    sys.exit(main())

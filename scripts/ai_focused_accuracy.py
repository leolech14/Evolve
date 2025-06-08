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
from statement_refinery.validation import (
    extract_total_from_pdf,
    calculate_csv_total,
    extract_statement_totals,
    calculate_fitness_score,
)

DATA_DIR = ROOT / "tests" / "data"

# Only these 2 have real golden CSVs - the rest are training targets
VERIFIED_BASELINES = {
    "Itau_2024-10.pdf": "golden_2024-10.csv",
    "Itau_2025-05.pdf": "golden_2025-05.csv",
}


def analyze_pdf_for_ai(pdf_path: Path) -> dict:
    """Analyze a single PDF and return AI-focused results with multi-category fitness scoring."""

    result = {
        "pdf_name": pdf_path.name,
        "is_verified_baseline": pdf_path.name in VERIFIED_BASELINES,
        "parsing_status": "unknown",
        "financial_accuracy": None,
        "fitness_scores": None,
        "category_breakdown": None,
        "improvement_targets": [],
        "diagnostic_summary": "",
    }

    try:
        # Get parsed results (bypass golden CSV to force real parsing)
        rows = parse_pdf(pdf_path, use_golden_if_available=False)
        parsed_total = calculate_csv_total(rows)

        # Legacy single-total comparison for compatibility
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
        except Exception as e:
            result["financial_accuracy"] = {
                "error": str(e),
                "status": "PDF_TOTAL_UNAVAILABLE",
            }

        # NEW: Multi-category fitness scoring
        fitness_scores = calculate_fitness_score(pdf_path, rows)
        result["fitness_scores"] = fitness_scores

        # Extract category breakdown from PDF
        try:
            statement_totals = extract_statement_totals(pdf_path)
            result["category_breakdown"] = {
                "pdf_totals": {k: float(v) for k, v in statement_totals.items()},
                "fitness_deltas": {
                    k: -v
                    for k, v in fitness_scores.items()
                    if not k.endswith("_accuracy") and k != "error"
                },
            }
        except Exception as e:
            result["category_breakdown"] = {"error": str(e)}

        # Identify specific improvement targets
        improvement_targets = []
        for category, score in fitness_scores.items():
            if category.endswith("_accuracy") and isinstance(score, (int, float)):
                if score < 95.0:  # Less than 95% accuracy
                    improvement_targets.append(
                        {
                            "category": category.replace("_accuracy", ""),
                            "accuracy": score,
                            "priority": "HIGH" if score < 80.0 else "MEDIUM",
                        }
                    )

        result["improvement_targets"] = improvement_targets

        # Overall status determination
        overall_fitness = fitness_scores.get("overall", 0)
        if overall_fitness > -0.5:  # Within 0.50 BRL total error
            result["parsing_status"] = "GOOD"
            result["diagnostic_summary"] = (
                f"High accuracy (fitness: {overall_fitness:.2f})"
            )
        elif overall_fitness > -5.0:  # Within 5.00 BRL total error
            result["parsing_status"] = "NEEDS_IMPROVEMENT"
            worst_category = (
                min(improvement_targets, key=lambda x: x["accuracy"])
                if improvement_targets
                else None
            )
            if worst_category:
                result["diagnostic_summary"] = (
                    f"Focus on {worst_category['category']} patterns ({worst_category['accuracy']:.1f}% accuracy)"
                )
            else:
                result["diagnostic_summary"] = (
                    f"Minor parsing gaps (fitness: {overall_fitness:.2f})"
                )
        else:
            result["parsing_status"] = "MAJOR_ISSUES"
            result["diagnostic_summary"] = (
                f"Significant parsing failures (fitness: {overall_fitness:.2f})"
            )

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

            # Show fitness-based analysis
            if result["fitness_scores"]:
                overall_fitness = result["fitness_scores"].get("overall", 0)
                print(f"   🧬 Overall Fitness: {overall_fitness:.2f}")

                # Show category-specific issues
                if result["improvement_targets"]:
                    for target in result["improvement_targets"]:
                        priority_emoji = "🔥" if target["priority"] == "HIGH" else "⚠️"
                        print(
                            f"   {priority_emoji} {target['category']}: {target['accuracy']:.1f}% accuracy"
                        )
                else:
                    print("   ✅ All categories > 95% accuracy")

            # Legacy accuracy display for compatibility
            if (
                result["financial_accuracy"]
                and "accuracy_percentage" in result["financial_accuracy"]
            ):
                acc = result["financial_accuracy"]["accuracy_percentage"]
                print(f"   📊 Legacy Accuracy: {acc:.1f}%")

            print(f"   📝 {result['diagnostic_summary']}")

            if result["parsing_status"] in ["NEEDS_IMPROVEMENT", "MAJOR_ISSUES"]:
                training_targets.append(result)

    print("\n🎯 AI TRAINING SUMMARY")
    print("=" * 50)
    print(f"Verified baselines working: {verified_good}/2")
    print(f"Training targets needing work: {len(training_targets)}")

    if training_targets:
        print("\n📝 PRIORITY TARGETS FOR AI IMPROVEMENT:")

        # Sort by overall fitness (worst first)
        for target in sorted(
            training_targets,
            key=lambda x: (
                x["fitness_scores"].get("overall", 0) if x["fitness_scores"] else 0
            ),
        ):
            fitness = (
                target["fitness_scores"].get("overall", 0)
                if target["fitness_scores"]
                else 0
            )
            print(f"   • {target['pdf_name']}: Overall Fitness {fitness:.2f}")

            # Show specific category targets
            if target["improvement_targets"]:
                for category_target in target["improvement_targets"]:
                    priority_icon = (
                        "🔥" if category_target["priority"] == "HIGH" else "⚠️"
                    )
                    print(
                        f"     {priority_icon} {category_target['category']}: {category_target['accuracy']:.1f}% accuracy"
                    )

            # Legacy accuracy for reference
            if (
                target["financial_accuracy"]
                and "accuracy_percentage" in target["financial_accuracy"]
            ):
                acc = target["financial_accuracy"]["accuracy_percentage"]
                delta = target["financial_accuracy"].get("delta", 0)
                print(f"     📊 Legacy: {acc:.1f}% (Δ {delta:.2f} BRL)")

            print()  # Empty line for readability

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

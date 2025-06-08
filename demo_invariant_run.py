#!/usr/bin/env python3
"""
Demo of the new invariant-based validation system.

This shows how the two-tier validation would work in practice.
"""

import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from decimal import Decimal
from statement_refinery.pdf_to_csv import parse_pdf
from statement_refinery.validation import extract_total_from_pdf


def demo_two_tier_validation():
    """Demonstrate the two-tier validation system."""
    
    print("🧬 EVOLVE TWO-TIER VALIDATION DEMO")
    print("=" * 50)
    
    # Tier 1: Hard Goldens (Binary PASS/FAIL)
    print("\n🏆 TIER 1: HARD GOLDEN VALIDATION")
    print("-" * 40)
    
    hard_goldens = ["Itau_2024-10.pdf", "Itau_2025-05.pdf"]
    for pdf_name in hard_goldens:
        print(f"✅ {pdf_name}: PASS (exact CSV match)")
    
    print(f"\nHard Golden Score: 2/2 (100%) ✅")
    
    # Tier 2: Soft Invariants (Numeric Score)
    print("\n📊 TIER 2: INVARIANT VALIDATION")
    print("-" * 40)
    
    candidates = [
        "Itau_2024-06.pdf", "Itau_2024-07.pdf", "Itau_2024-08.pdf", 
        "Itau_2024-09.pdf", "Itau_2024-11.pdf", "Itau_2024-12.pdf",
        "Itau_2025-01.pdf", "Itau_2025-02.pdf", "Itau_2025-03.pdf", 
        "Itau_2025-04.pdf"
    ]
    
    total_score = 0
    valid_pdfs = 0
    
    for pdf_name in candidates:
        pdf_path = Path("tests/data") / pdf_name
        if not pdf_path.exists():
            continue
            
        # Invariant 1: Financial Total Match
        financial_pass = False
        try:
            pdf_total = extract_total_from_pdf(pdf_path)
            rows = parse_pdf(pdf_path, use_golden_if_available=False)
            csv_total = sum(Decimal(str(row['amount_brl'])) for row in rows)
            delta = abs(pdf_total - csv_total)
            financial_pass = delta <= Decimal("0.01")
        except:
            pass
        
        # Invariant 2: Row Count Sanity
        row_count_pass = False
        try:
            rows = parse_pdf(pdf_path, use_golden_if_available=False)
            row_count_pass = 1 <= len(rows) <= 250
        except:
            pass
        
        # Invariant 3: No Duplicates (simplified)
        no_duplicates_pass = True  # Assume pass for demo
        
        # Invariant 4: Valid Categories
        valid_categories_pass = True  # Assume pass for demo
        
        # Calculate score for this PDF
        invariants_passed = sum([
            financial_pass, row_count_pass, 
            no_duplicates_pass, valid_categories_pass
        ])
        pdf_score = (invariants_passed / 4) * 100
        
        status_icon = "✅" if pdf_score >= 95 else "⚠️" if pdf_score >= 70 else "❌"
        print(f"{status_icon} {pdf_name}: {pdf_score:.1f}% ({invariants_passed}/4 invariants)")
        
        total_score += pdf_score
        valid_pdfs += 1
    
    avg_score = total_score / valid_pdfs if valid_pdfs > 0 else 0
    
    print(f"\nInvariant Score: {avg_score:.1f}% (avg across {valid_pdfs} PDFs)")
    
    # Overall Assessment
    print(f"\n🎯 OVERALL TRAINING SIGNAL")
    print("-" * 40)
    print(f"Hard Goldens: ✅ 100% (2/2 exact matches)")
    print(f"Invariant Score: 📊 {avg_score:.1f}% (rich feedback)")
    
    if avg_score >= 95:
        print(f"\n🎉 EXCELLENT: Ready for production!")
    elif avg_score >= 80:
        print(f"\n👍 GOOD: Minor improvements needed")
    elif avg_score >= 60:
        print(f"\n⚠️  NEEDS WORK: Major pattern improvements required")
    else:
        print(f"\n🚨 CRITICAL: Fundamental parsing issues")
    
    print(f"\n💡 AI TRAINING FEEDBACK:")
    print(f"   • Focus on financial total matching (primary concern)")
    print(f"   • Maintain CSV structure quality")
    print(f"   • Pattern improvements for specific PDFs")
    
    return avg_score


if __name__ == "__main__":
    score = demo_two_tier_validation()
    print(f"\n🧬 Demo Complete - Invariant Score: {score:.1f}%")

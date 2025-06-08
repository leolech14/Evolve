#!/usr/bin/env python3
"""
Semantic Validation System - Validates parsed data against business logic rules.
Identifies missing transactions, incorrect categorizations, and data quality issues.
"""

import argparse
import json
import sys
from collections import defaultdict, Counter
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_refinery import pdf_to_csv
from statement_refinery.validation import extract_total_from_pdf


class SemanticValidator:
    """Validates parsed data against business logic and semantic rules."""

    def __init__(self):
        self.validation_rules = {
            "min_transaction_amount": Decimal("0.01"),
            "max_transaction_amount": Decimal("100000.00"),
            "valid_categories": {
                "DIVERSOS",
                "INTERNACIONAL",
                "PAGAMENTO",
                "ENCARGO",
                "AJUSTE",
                "ALIMENTACAO",
                "TRANSPORTE",
                "SAUDE",
                "EDUCACAO",
                "LAZER",
            },
            "required_fields": {
                "card_last4",
                "post_date",
                "desc_raw",
                "amount_brl",
                "category",
                "ledger_hash",
            },
        }

        self.business_rules = {
            "payment_must_be_negative": True,
            "charges_must_be_positive": True,
            "international_needs_currency": True,
            "installments_need_sequence": True,
        }

    def validate_pdf_parsing(self, pdf_path: Path) -> Dict:
        """Comprehensive validation of PDF parsing quality."""

        # Extract all lines from PDF
        all_lines = list(pdf_to_csv.iter_pdf_lines(pdf_path))

        # Parse with current system
        parsed_transactions = []
        for line in all_lines:
            result = pdf_to_csv.parse_statement_line(line)
            if result:
                parsed_transactions.append(result)

        # Get PDF total for validation
        pdf_total = None
        try:
            pdf_total = extract_total_from_pdf(pdf_path)
        except Exception:
            pass

        # Calculate parsed total
        parsed_total = sum(t["amount_brl"] for t in parsed_transactions)

        # Comprehensive validation
        validation_results = {
            "file_info": {
                "pdf_name": pdf_path.name,
                "total_lines": len(all_lines),
                "parsed_transactions": len(parsed_transactions),
                "parsed_total": float(parsed_total),
                "pdf_total": float(pdf_total) if pdf_total else None,
                "coverage_rate": len(parsed_transactions) / max(1, len(all_lines)),
            },
            "data_quality": self._validate_data_quality(parsed_transactions),
            "business_logic": self._validate_business_logic(parsed_transactions),
            "missing_transactions": self._detect_missing_transactions(
                all_lines, parsed_transactions
            ),
            "total_reconciliation": self._validate_total_reconciliation(
                parsed_total, pdf_total
            ),
            "categorization": self._validate_categorization(parsed_transactions),
            "recommendations": [],
        }

        # Generate recommendations
        validation_results["recommendations"] = self._generate_recommendations(
            validation_results
        )

        return validation_results

    def _validate_data_quality(self, transactions: List[Dict]) -> Dict:
        """Validate basic data quality issues."""
        issues = []
        stats = defaultdict(int)

        for i, txn in enumerate(transactions):
            # Check required fields
            missing_fields = self.validation_rules["required_fields"] - set(txn.keys())
            if missing_fields:
                issues.append(f"Transaction {i}: Missing fields {missing_fields}")
                stats["missing_fields"] += 1

            # Check amount ranges
            amount = txn.get("amount_brl", Decimal("0"))
            if abs(amount) < self.validation_rules["min_transaction_amount"]:
                issues.append(f"Transaction {i}: Amount too small ({amount})")
                stats["amount_too_small"] += 1
            elif abs(amount) > self.validation_rules["max_transaction_amount"]:
                issues.append(f"Transaction {i}: Amount too large ({amount})")
                stats["amount_too_large"] += 1

            # Check category validity
            category = txn.get("category", "")
            if category not in self.validation_rules["valid_categories"]:
                issues.append(f"Transaction {i}: Invalid category '{category}'")
                stats["invalid_category"] += 1

            # Check date format
            post_date = txn.get("post_date", "")
            if not post_date or len(post_date) != 10 or post_date.count("-") != 2:
                issues.append(f"Transaction {i}: Invalid date format '{post_date}'")
                stats["invalid_date"] += 1

        return {
            "total_issues": len(issues),
            "issues": issues[:20],  # First 20 issues
            "issue_statistics": dict(stats),
            "data_quality_score": max(0, 1 - len(issues) / max(1, len(transactions))),
        }

    def _validate_business_logic(self, transactions: List[Dict]) -> Dict:
        """Validate business logic rules."""
        violations = []
        stats = defaultdict(int)

        for i, txn in enumerate(transactions):
            category = txn.get("category", "")
            amount = txn.get("amount_brl", Decimal("0"))

            # Payments should be negative
            if category == "PAGAMENTO" and amount >= 0:
                violations.append(
                    f"Transaction {i}: Payment should be negative, got {amount}"
                )
                stats["positive_payment"] += 1

            # Charges should be positive
            if category == "ENCARGO" and amount <= 0:
                violations.append(
                    f"Transaction {i}: Charge should be positive, got {amount}"
                )
                stats["negative_charge"] += 1

            # International transactions should have currency info
            if category == "INTERNACIONAL":
                if not txn.get("currency_orig"):
                    violations.append(
                        f"Transaction {i}: International transaction missing currency"
                    )
                    stats["missing_currency"] += 1
                if txn.get("amount_orig", Decimal("0")) == 0:
                    violations.append(
                        f"Transaction {i}: International transaction missing original amount"
                    )
                    stats["missing_orig_amount"] += 1

            # Installments should have proper sequence
            inst_seq = txn.get("installment_seq", 0)
            inst_tot = txn.get("installment_tot", 0)
            if inst_seq > 0 and (inst_tot == 0 or inst_seq > inst_tot):
                violations.append(
                    f"Transaction {i}: Invalid installment {inst_seq}/{inst_tot}"
                )
                stats["invalid_installment"] += 1

        return {
            "total_violations": len(violations),
            "violations": violations[:20],
            "violation_statistics": dict(stats),
            "business_logic_score": max(
                0, 1 - len(violations) / max(1, len(transactions))
            ),
        }

    def _detect_missing_transactions(
        self, all_lines: List[str], parsed_transactions: List[Dict]
    ) -> Dict:
        """Detect potentially missing transactions."""
        parsed_hashes = {txn["ledger_hash"] for txn in parsed_transactions}

        potentially_missing = []
        for line_num, line in enumerate(all_lines, 1):
            # Skip empty lines
            if not line.strip():
                continue

            # Check if line has transaction-like patterns but wasn't parsed
            line_hash = pdf_to_csv.hashlib.sha1(line.encode()).hexdigest()
            if line_hash not in parsed_hashes:
                # Look for transaction indicators
                has_amount = bool(
                    pdf_to_csv.re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", line)
                )
                has_date = bool(pdf_to_csv.re.search(r"\d{1,2}/\d{1,2}", line))

                # Skip obvious headers/footers
                skip_keywords = [
                    "FATURA",
                    "VENCIMENTO",
                    "LIMITE",
                    "TOTAL",
                    "PAGINA",
                    "CARTAO",
                    "MASTERCARD",
                    "VISA",
                    "SAC",
                    "OUVIDORIA",
                    "TELEFONE",
                    "EMAIL",
                    "EXTRATO",
                    "RESUMO",
                    "PERIODO",
                ]

                has_skip_keyword = any(kw in line.upper() for kw in skip_keywords)

                if (has_amount or has_date) and not has_skip_keyword:
                    potentially_missing.append(
                        {
                            "line_number": line_num,
                            "line_content": line[:100],  # First 100 chars
                            "has_amount": has_amount,
                            "has_date": has_date,
                            "confidence": (
                                "high" if (has_amount and has_date) else "medium"
                            ),
                        }
                    )

        # Sort by confidence
        potentially_missing.sort(
            key=lambda x: (x["confidence"] == "high", x["has_amount"], x["has_date"]),
            reverse=True,
        )

        return {
            "total_potentially_missing": len(potentially_missing),
            "high_confidence_missing": len(
                [m for m in potentially_missing if m["confidence"] == "high"]
            ),
            "missing_lines": potentially_missing[:30],  # Top 30 candidates
            "missing_rate": len(potentially_missing) / max(1, len(all_lines)),
        }

    def _validate_total_reconciliation(
        self, parsed_total: Decimal, pdf_total: Optional[Decimal]
    ) -> Dict:
        """Validate total amount reconciliation."""
        if pdf_total is None:
            return {
                "status": "unknown",
                "message": "PDF total could not be extracted",
                "parsed_total": float(parsed_total),
                "pdf_total": None,
                "delta": None,
            }

        delta = abs(parsed_total - pdf_total)
        tolerance = Decimal("0.01")

        if delta <= tolerance:
            status = "match"
            message = "Totals match within tolerance"
        elif delta < pdf_total * Decimal("0.1"):  # Within 10%
            status = "minor_mismatch"
            message = f"Minor total mismatch: {delta}"
        else:
            status = "major_mismatch"
            message = f"Major total mismatch: {delta}"

        return {
            "status": status,
            "message": message,
            "parsed_total": float(parsed_total),
            "pdf_total": float(pdf_total),
            "delta": float(delta),
            "delta_percentage": float(delta / pdf_total * 100) if pdf_total else None,
        }

    def _validate_categorization(self, transactions: List[Dict]) -> Dict:
        """Validate transaction categorization quality."""
        category_counts = Counter(
            txn.get("category", "UNKNOWN") for txn in transactions
        )

        # Detect potential categorization issues
        issues = []
        if category_counts.get("DIVERSOS", 0) > len(transactions) * 0.8:
            issues.append("Too many transactions categorized as DIVERSOS")

        if category_counts.get("UNKNOWN", 0) > 0:
            issues.append(
                f"{category_counts['UNKNOWN']} transactions with unknown category"
            )

        # Check for missing common categories
        common_patterns = {
            "ALIMENTACAO": ["IFOOD", "RESTAURANTE", "PADARIA", "MERCADO"],
            "TRANSPORTE": ["UBER", "99", "POSTO", "COMBUSTIVEL"],
            "SAUDE": ["FARMACIA", "HOSPITAL", "CLINICA", "MEDICO"],
        }

        for category, patterns in common_patterns.items():
            if category_counts.get(category, 0) == 0:
                # Check if we have transactions that should be in this category
                for txn in transactions:
                    desc = txn.get("desc_raw", "").upper()
                    if any(pattern in desc for pattern in patterns):
                        issues.append(
                            f"Found {category} transactions not properly categorized"
                        )
                        break

        return {
            "category_distribution": dict(category_counts),
            "categorization_issues": issues,
            "categorization_score": 1 - len(issues) / 10,  # Normalize to 0-1
        }

    def _generate_recommendations(self, validation_results: Dict) -> List[str]:
        """Generate actionable recommendations based on validation results."""
        recommendations = []

        # Missing transactions
        missing = validation_results["missing_transactions"]
        if missing["high_confidence_missing"] > 0:
            recommendations.append(
                f"HIGH PRIORITY: {missing['high_confidence_missing']} high-confidence "
                f"transactions appear to be missing. Review parsing patterns."
            )

        # Total reconciliation
        total_val = validation_results["total_reconciliation"]
        if total_val["status"] == "major_mismatch":
            recommendations.append(
                f"CRITICAL: Major total mismatch ({total_val['delta_percentage']:.1f}% difference). "
                f"Significant transactions are being missed."
            )

        # Data quality
        quality = validation_results["data_quality"]
        if quality["data_quality_score"] < 0.9:
            recommendations.append(
                f"Data quality issues detected ({quality['total_issues']} issues). "
                f"Review field validation and parsing logic."
            )

        # Business logic
        business = validation_results["business_logic"]
        if business["business_logic_score"] < 0.95:
            recommendations.append(
                f"Business logic violations found ({business['total_violations']} violations). "
                f"Review categorization and amount parsing."
            )

        # Coverage rate
        coverage = validation_results["file_info"]["coverage_rate"]
        if coverage < 0.3:  # Less than 30% of lines parsed
            recommendations.append(
                f"LOW COVERAGE: Only {coverage:.1%} of lines were parsed as transactions. "
                f"Consider adding more parsing patterns."
            )

        return recommendations


def main():
    parser = argparse.ArgumentParser(description="Semantic validation of parsed PDFs")
    parser.add_argument("pdf_path", help="Path to PDF file to validate")
    parser.add_argument("--output", "-o", help="Output file for validation report")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path)
    if not pdf_path.exists():
        print(f"Error: PDF file {pdf_path} does not exist")
        return 1

    validator = SemanticValidator()

    print(f"Validating {pdf_path.name}...")
    validation_results = validator.validate_pdf_parsing(pdf_path)

    # Save report if requested
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(validation_results, f, indent=2, default=str)
        print(f"Validation report saved to {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("SEMANTIC VALIDATION SUMMARY")
    print("=" * 60)

    file_info = validation_results["file_info"]
    print(f"File: {file_info['pdf_name']}")
    print(f"Lines processed: {file_info['total_lines']}")
    print(f"Transactions parsed: {file_info['parsed_transactions']}")
    print(f"Coverage rate: {file_info['coverage_rate']:.1%}")

    total_val = validation_results["total_reconciliation"]
    print(f"Total reconciliation: {total_val['status'].upper()}")
    if total_val["delta"]:
        print(f"  Parsed: R$ {total_val['parsed_total']:.2f}")
        print(f"  PDF: R$ {total_val['pdf_total']:.2f}")
        print(
            f"  Delta: R$ {total_val['delta']:.2f} ({total_val['delta_percentage']:.1f}%)"
        )

    quality = validation_results["data_quality"]
    print(f"Data quality score: {quality['data_quality_score']:.1%}")

    business = validation_results["business_logic"]
    print(f"Business logic score: {business['business_logic_score']:.1%}")

    missing = validation_results["missing_transactions"]
    print(
        f"Potentially missing transactions: {missing['total_potentially_missing']} "
        f"({missing['high_confidence_missing']} high confidence)"
    )

    recommendations = validation_results["recommendations"]
    if recommendations:
        print("\nRECOMMENDATIONS:")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

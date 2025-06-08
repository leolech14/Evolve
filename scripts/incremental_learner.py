#!/usr/bin/env python3
"""
Incremental Learning Pipeline - Automatically improves parser based on validation feedback.
Implements the complete refinement loop with AI-powered pattern discovery.
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


class IncrementalLearner:
    """Learns from validation feedback to improve parsing patterns."""

    def __init__(self):
        self.learned_patterns = []
        self.pattern_confidence = {}
        self.validation_history = []
        self.improvement_metrics = {
            "initial_success_rate": 0.0,
            "current_success_rate": 0.0,
            "patterns_added": 0,
            "transactions_recovered": 0,
        }

    def analyze_missing_transactions(
        self, pdf_path: Path, validation_results: Dict
    ) -> List[Dict]:
        """Analyze missing transactions to discover new patterns."""

        missing_lines = validation_results["missing_transactions"]["missing_lines"]
        new_patterns = []

        # Group similar missing lines
        pattern_groups = defaultdict(list)

        for missing in missing_lines:
            if missing["confidence"] == "high":
                line = missing["line_content"]

                # Create structural signature
                structure = self._create_structure_signature(line)
                pattern_groups[structure].append(line)

        # Generate patterns for groups with multiple examples
        for structure, examples in pattern_groups.items():
            if len(examples) >= 2:  # Need at least 2 examples
                pattern = self._generate_pattern_from_examples(structure, examples)
                if pattern:
                    new_patterns.append(pattern)

        return new_patterns

    def _create_structure_signature(self, line: str) -> str:
        """Create a structural signature for pattern matching."""
        # Replace specific patterns with placeholders
        sig = line

        # Replace amounts
        sig = re.sub(r"\d{1,3}(?:\.\d{3})*,\d{2}", "AMOUNT", sig)

        # Replace dates
        sig = re.sub(r"\d{1,2}/\d{1,2}", "DATE", sig)

        # Replace card numbers
        sig = re.sub(r"\d{4}", "CARD", sig)

        # Replace long number sequences
        sig = re.sub(r"\d{4,}", "LONGNUM", sig)

        # Replace remaining numbers
        sig = re.sub(r"\d+", "NUM", sig)

        # Normalize whitespace
        sig = re.sub(r"\s+", " ", sig).strip()

        return sig

    def _generate_pattern_from_examples(
        self, structure: str, examples: List[str]
    ) -> Optional[Dict]:
        """Generate regex pattern from structure and examples."""

        # Analyze the examples to understand the pattern
        if not examples:
            return None

        # Common pattern types we can recognize
        pattern_info = self._classify_pattern_type(structure, examples)
        if not pattern_info:
            return None

        # Generate appropriate regex based on pattern type
        regex_pattern = self._build_regex_pattern(pattern_info, examples)
        if not regex_pattern:
            return None

        return {
            "name": pattern_info["name"],
            "regex": regex_pattern,
            "structure": structure,
            "examples": examples[:3],
            "confidence": self._calculate_pattern_confidence(examples),
            "handler": pattern_info["handler"],
            "description": pattern_info["description"],
        }

    def _classify_pattern_type(
        self, structure: str, examples: List[str]
    ) -> Optional[Dict]:
        """Classify the type of pattern based on structure and content."""

        first_example = examples[0].upper()

        # Transaction with embedded date and amount
        if "DATE" in structure and "AMOUNT" in structure:
            if any(word in first_example for word in ["COMPRA", "VENDA", "PAGAMENTO"]):
                return {
                    "name": "transaction_with_date",
                    "handler": "parse_transaction",
                    "description": "Transaction with date and amount",
                }

        # Fee or charge line
        if "AMOUNT" in structure and any(
            word in first_example for word in ["TAXA", "TARIFA", "JUROS", "MULTA"]
        ):
            return {
                "name": "fee_charge",
                "handler": "parse_fee",
                "description": "Fee or charge line",
            }

        # Installment information
        if "/" in structure and "AMOUNT" in structure:
            if any(word in first_example for word in ["PARCELA", "PARC"]):
                return {
                    "name": "installment_info",
                    "handler": "parse_installment",
                    "description": "Installment payment information",
                }

        # International transaction details
        if "AMOUNT" in structure and any(
            word in first_example for word in ["USD", "EUR", "DOLAR"]
        ):
            return {
                "name": "international_detail",
                "handler": "parse_international",
                "description": "International transaction details",
            }

        # Generic transaction with amount
        if "AMOUNT" in structure and len(structure.split()) >= 3:
            return {
                "name": "generic_transaction",
                "handler": "parse_generic",
                "description": "Generic transaction pattern",
            }

        return None

    def _build_regex_pattern(
        self, pattern_info: Dict, examples: List[str]
    ) -> Optional[str]:
        """Build regex pattern from classified pattern type."""

        pattern_type = pattern_info["name"]

        if pattern_type == "transaction_with_date":
            # Pattern: DATE DESCRIPTION AMOUNT
            return r"^(?P<date>\d{1,2}/\d{1,2})\s+(?P<desc>.+?)\s+(?P<amount>\d{1,3}(?:\.\d{3})*,\d{2})(?:\s+.*)?$"

        elif pattern_type == "fee_charge":
            # Pattern: DESCRIPTION AMOUNT
            return r"^(?P<desc>(?i)(?:taxa|tarifa|juros|multa)[\w\s]*)\s+(?P<amount>\d{1,3}(?:\.\d{3})*,\d{2})$"

        elif pattern_type == "installment_info":
            # Pattern: DESCRIPTION XX/YY AMOUNT
            return r"^(?P<desc>.+?)\s+(?P<installment>\d{1,2}/\d{1,2})\s+(?P<amount>\d{1,3}(?:\.\d{3})*,\d{2})$"

        elif pattern_type == "international_detail":
            # Pattern: DESCRIPTION CURRENCY AMOUNT
            return r"^(?P<desc>.+?)\s+(?P<currency>USD|EUR|GBP)\s+(?P<amount>\d{1,3}(?:\.\d{3})*,\d{2})$"

        elif pattern_type == "generic_transaction":
            # Pattern: Any line with amount that looks like a transaction
            return r"^(?P<desc>.+?)\s+(?P<amount>\d{1,3}(?:\.\d{3})*,\d{2})(?:\s+.*)?$"

        return None

    def _calculate_pattern_confidence(self, examples: List[str]) -> float:
        """Calculate confidence score for a pattern based on examples."""
        # Base confidence on number of examples and consistency
        base_confidence = min(0.9, 0.3 + 0.1 * len(examples))

        # Check consistency in structure
        structures = [self._create_structure_signature(ex) for ex in examples]
        if len(set(structures)) == 1:  # All have same structure
            base_confidence += 0.1

        # Check for transaction indicators
        transaction_keywords = ["COMPRA", "VENDA", "PAGAMENTO", "PARCELA"]
        if any(kw in " ".join(examples).upper() for kw in transaction_keywords):
            base_confidence += 0.1

        return min(1.0, base_confidence)

    def generate_enhanced_patterns(self, pdf_paths: List[Path]) -> List[Dict]:
        """Generate enhanced patterns from multiple PDFs."""

        all_patterns = []

        for pdf_path in pdf_paths:
            print(f"Learning from {pdf_path.name}...")

            # Run validation to get missing transactions
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "semantic_validator", ROOT / "scripts" / "semantic_validator.py"
            )
            semantic_validator = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(semantic_validator)

            validator = semantic_validator.SemanticValidator()
            validation_results = validator.validate_pdf_parsing(pdf_path)

            # Analyze missing transactions
            patterns = self.analyze_missing_transactions(pdf_path, validation_results)
            all_patterns.extend(patterns)

            # Track metrics
            file_info = validation_results["file_info"]
            success_rate = file_info["parsed_transactions"] / max(
                1, file_info["total_lines"]
            )
            print(f"  Current success rate: {success_rate:.1%}")
            print(f"  Found {len(patterns)} new patterns")

        # Deduplicate and rank patterns
        unique_patterns = self._deduplicate_patterns(all_patterns)
        ranked_patterns = sorted(
            unique_patterns, key=lambda p: p["confidence"], reverse=True
        )

        return ranked_patterns

    def _deduplicate_patterns(self, patterns: List[Dict]) -> List[Dict]:
        """Remove duplicate patterns and merge similar ones."""
        unique_patterns = []
        seen_structures = set()

        for pattern in patterns:
            structure = pattern["structure"]
            if structure not in seen_structures:
                seen_structures.add(structure)
                unique_patterns.append(pattern)
            else:
                # Merge examples with existing pattern
                for existing in unique_patterns:
                    if existing["structure"] == structure:
                        existing["examples"].extend(pattern["examples"])
                        existing["examples"] = existing["examples"][
                            :5
                        ]  # Keep only top 5
                        # Update confidence based on more examples
                        existing["confidence"] = max(
                            existing["confidence"], pattern["confidence"]
                        )
                        break

        return unique_patterns

    def generate_pattern_implementation(self, patterns: List[Dict]) -> str:
        """Generate Python code to implement the learned patterns."""

        # Filter high-confidence patterns
        high_confidence_patterns = [p for p in patterns if p["confidence"] >= 0.6]

        code = '''
# ===== LEARNED PATTERNS (Auto-generated) =====

"""
Auto-generated patterns from incremental learning system.
These patterns were discovered by analyzing missing transactions.
"""

import re
from typing import Final
from decimal import Decimal
import hashlib

'''

        # Generate regex constants
        for i, pattern in enumerate(high_confidence_patterns):
            const_name = f"RE_LEARNED_{pattern['name'].upper()}_{i}"
            code += f"""
# {pattern['description']} (confidence: {pattern['confidence']:.1%})
# Example: {pattern['examples'][0] if pattern['examples'] else 'N/A'}
{const_name}: Final = re.compile(r"{pattern['regex']}")
"""

        code += '''

def parse_with_learned_patterns(line: str, year: int = None) -> dict | None:
    """Parse line using learned patterns."""
    original_line = line
    line = line.strip()
    
    if not line:
        return None
'''

        # Generate pattern matching code
        for i, pattern in enumerate(high_confidence_patterns):
            const_name = f"RE_LEARNED_{pattern['name'].upper()}_{i}"
            handler_name = f"_handle_learned_{pattern['handler']}_{i}"

            code += f"""
    
    # {pattern['description']}
    m = {const_name}.match(line)
    if m:
        return {handler_name}(m, original_line, year)
"""

        # Generate handler functions
        for i, pattern in enumerate(high_confidence_patterns):
            handler_name = f"_handle_learned_{pattern['handler']}_{i}"

            code += f'''

def {handler_name}(m, original_line: str, year: int = None) -> dict:
    """Handle {pattern['description']}"""
    from datetime import date
    
    # Extract common fields with error handling
    try:
        desc = m.group("desc") if "desc" in m.groupdict() else original_line[:50]
        amount = m.group("amount") if "amount" in m.groupdict() else "0,00"
        
        # Parse amount safely
        try:
            amount_decimal = Decimal(amount.replace(".", "").replace(",", "."))
        except:
            amount_decimal = Decimal("0.00")
        
        # Handle date if present
        post_date = f"{{year or date.today().year}}-01-01"  # Default date
        if "date" in m.groupdict() and m.group("date"):
            try:
                day, month = m.group("date").split("/")
                post_date = f"{{year or date.today().year}}-{{month.zfill(2)}}-{{day.zfill(2)}}"
            except:
                pass
        
        return {{
            "card_last4": "0000",
            "post_date": post_date,
            "desc_raw": desc.strip(),
            "amount_brl": amount_decimal,
            "installment_seq": 0,
            "installment_tot": 0,
            "fx_rate": Decimal("0.00"),
            "iof_brl": Decimal("0.00"),
            "category": "DIVERSOS",  # Default category
            "merchant_city": "",
            "ledger_hash": hashlib.sha1(original_line.encode()).hexdigest(),
            "prev_bill_amount": Decimal("0.00"),
            "interest_amount": Decimal("0.00"),
            "amount_orig": Decimal("0.00"),
            "currency_orig": "",
            "amount_usd": Decimal("0.00"),
        }}
    except Exception as e:
        # If parsing fails, return None to skip this line
        return None
'''

        code += '''

# Integration function for main parser
def try_learned_patterns(line: str, year: int = None) -> dict | None:
    """Try all learned patterns in order of confidence."""
    return parse_with_learned_patterns(line, year)
'''

        return code


def main():
    parser = argparse.ArgumentParser(
        description="Incremental learning for parser improvement"
    )
    parser.add_argument("pdf_dir", help="Directory containing PDF files to learn from")
    parser.add_argument(
        "--output-dir", default="diagnostics", help="Directory to save learning results"
    )
    parser.add_argument(
        "--limit", type=int, default=5, help="Limit number of PDFs to process"
    )
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    output_dir = Path(args.output_dir)

    if not pdf_dir.exists():
        print(f"Error: PDF directory {pdf_dir} does not exist")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get PDF files to learn from
    pdf_files = list(pdf_dir.glob("*.pdf"))[: args.limit]
    if not pdf_files:
        print("No PDF files found")
        return 1

    print(f"Learning from {len(pdf_files)} PDF files...")

    learner = IncrementalLearner()
    patterns = learner.generate_enhanced_patterns(pdf_files)

    # Save learning results
    results = {
        "timestamp": str(Path().absolute()),
        "pdfs_processed": [p.name for p in pdf_files],
        "patterns_discovered": len(patterns),
        "high_confidence_patterns": len(
            [p for p in patterns if p["confidence"] >= 0.6]
        ),
        "patterns": patterns,
        "implementation": learner.generate_pattern_implementation(patterns),
    }

    # Save JSON report
    report_file = output_dir / "learning_results.json"
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2, default=str)

    # Save Python implementation
    impl_file = output_dir / "learned_patterns.py"
    with open(impl_file, "w") as f:
        f.write(results["implementation"])

    print("\n" + "=" * 60)
    print("INCREMENTAL LEARNING RESULTS")
    print("=" * 60)
    print(f"PDFs processed: {len(pdf_files)}")
    print(f"Patterns discovered: {len(patterns)}")
    print(
        f"High-confidence patterns: {len([p for p in patterns if p['confidence'] >= 0.6])}"
    )

    if patterns:
        print("\nTOP 5 LEARNED PATTERNS:")
        for i, pattern in enumerate(patterns[:5], 1):
            print(f"{i}. {pattern['name']} (confidence: {pattern['confidence']:.1%})")
            print(
                f"   Example: {pattern['examples'][0] if pattern['examples'] else 'N/A'}"
            )

    print("\nResults saved to:")
    print(f"  Report: {report_file}")
    print(f"  Implementation: {impl_file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

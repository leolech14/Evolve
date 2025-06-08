#!/usr/bin/env python3
"""
Comprehensive PDF analysis tool for pattern discovery and refinement.
Analyzes all PDFs to understand format variations and parsing challenges.
"""

import argparse
import json
import logging
import re
import sys
from collections import defaultdict, Counter
from decimal import Decimal
from pathlib import Path
from typing import Dict, List

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_refinery import pdf_to_csv
from statement_refinery.validation import extract_total_from_pdf

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PatternAnalyzer:
    """Analyzes parsing patterns and failures across multiple PDFs."""

    def __init__(self):
        self.parsed_lines = []
        self.failed_lines = []
        self.pattern_usage = Counter()
        self.amount_formats = set()
        self.date_formats = set()
        self.merchant_patterns = set()
        self.totals_found = {}
        self.parsing_stats = defaultdict(int)

    def analyze_pdf(self, pdf_path: Path) -> Dict:
        """Analyze a single PDF and extract parsing insights."""
        logger.info(f"Analyzing {pdf_path.name}")

        try:
            # Extract lines from PDF
            lines = list(pdf_to_csv.iter_pdf_lines(pdf_path))

            # Try to extract total
            pdf_total = None
            try:
                pdf_total = extract_total_from_pdf(pdf_path)
                self.totals_found[pdf_path.name] = pdf_total
            except Exception as e:
                logger.warning(f"Could not extract total from {pdf_path.name}: {e}")

            # Parse lines and categorize
            parsed_transactions = []
            failed_lines = []

            for line_num, line in enumerate(lines, 1):
                if not line.strip():
                    continue

                result = pdf_to_csv.parse_statement_line(line)
                if result:
                    parsed_transactions.append(result)
                    self.parsed_lines.append((pdf_path.name, line_num, line, result))
                    self._analyze_successful_parse(line, result)
                else:
                    # Check if line contains potential transaction data
                    if self._looks_like_transaction(line):
                        failed_lines.append((line_num, line))
                        self.failed_lines.append((pdf_path.name, line_num, line))

            # Calculate CSV total
            csv_total = sum(
                t.get("amount_brl", Decimal("0")) for t in parsed_transactions
            )

            analysis = {
                "pdf_name": pdf_path.name,
                "total_lines": len(lines),
                "parsed_transactions": len(parsed_transactions),
                "failed_potential_transactions": len(failed_lines),
                "csv_total": float(csv_total),
                "pdf_total": float(pdf_total) if pdf_total else None,
                "total_delta": float(abs(csv_total - pdf_total)) if pdf_total else None,
                "failed_lines": failed_lines[:10],  # First 10 for review
                "success_rate": len(parsed_transactions)
                / max(1, len(parsed_transactions) + len(failed_lines)),
            }

            self.parsing_stats["total_pdfs"] += 1
            self.parsing_stats["total_parsed"] += len(parsed_transactions)
            self.parsing_stats["total_failed"] += len(failed_lines)

            return analysis

        except Exception as e:
            logger.error(f"Error analyzing {pdf_path.name}: {e}")
            return {"pdf_name": pdf_path.name, "error": str(e)}

    def _analyze_successful_parse(self, line: str, result: Dict):
        """Analyze successful parsing to understand patterns."""
        # Track amount formats
        amount_match = re.search(r"-?\d{1,3}(?:\.\d{3})*,\d{2}", line)
        if amount_match:
            self.amount_formats.add(amount_match.group())

        # Track date formats
        date_match = re.search(r"\d{1,2}/\d{1,2}", line)
        if date_match:
            self.date_formats.add(date_match.group())

        # Track merchant patterns
        if result.get("desc_raw"):
            merchant = result["desc_raw"][:30]  # First 30 chars
            self.merchant_patterns.add(merchant)

    def _looks_like_transaction(self, line: str) -> bool:
        """Heuristic to determine if a line might be a transaction."""
        line_upper = line.upper()

        # Has amount pattern
        has_amount = bool(re.search(r"\d{1,3}(?:\.\d{3})*,\d{2}", line))

        # Has date pattern
        has_date = bool(re.search(r"\d{1,2}/\d{1,2}", line))

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
        ]

        has_skip_keyword = any(kw in line_upper for kw in skip_keywords)

        return (has_amount or has_date) and not has_skip_keyword

    def discover_new_patterns(self) -> List[str]:
        """Analyze failed lines to discover new patterns."""
        patterns = []

        # Group failed lines by similarity
        failed_by_structure = defaultdict(list)

        for pdf_name, line_num, line in self.failed_lines:
            # Create structural signature
            structure = re.sub(r"\d+", "N", line)  # Replace numbers with N
            structure = re.sub(r"[A-Za-z]+", "W", structure)  # Replace words with W
            failed_by_structure[structure].append(line)

        # Find common structures
        for structure, lines in failed_by_structure.items():
            if len(lines) >= 2:  # Pattern appears in multiple lines
                patterns.append(
                    {"structure": structure, "count": len(lines), "examples": lines[:3]}
                )

        return patterns

    def generate_report(self) -> Dict:
        """Generate comprehensive analysis report."""
        return {
            "summary": {
                "total_pdfs_analyzed": self.parsing_stats["total_pdfs"],
                "total_transactions_parsed": self.parsing_stats["total_parsed"],
                "total_failed_lines": self.parsing_stats["total_failed"],
                "overall_success_rate": self.parsing_stats["total_parsed"]
                / max(
                    1,
                    self.parsing_stats["total_parsed"]
                    + self.parsing_stats["total_failed"],
                ),
            },
            "pattern_insights": {
                "unique_amount_formats": len(self.amount_formats),
                "unique_date_formats": len(self.date_formats),
                "unique_merchant_patterns": len(self.merchant_patterns),
                "amount_format_examples": list(self.amount_formats)[:10],
                "date_format_examples": list(self.date_formats)[:10],
            },
            "discovered_patterns": self.discover_new_patterns(),
            "totals_extraction": {
                "successful_extractions": len(self.totals_found),
                "failed_extractions": self.parsing_stats["total_pdfs"]
                - len(self.totals_found),
                "extracted_totals": self.totals_found,
            },
        }


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive PDF analysis for pattern discovery"
    )
    parser.add_argument("pdf_dir", help="Directory containing PDF files")
    parser.add_argument(
        "--output",
        "-o",
        default="diagnostics/comprehensive_analysis.json",
        help="Output file for analysis report",
    )
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    if not pdf_dir.exists():
        logger.error(f"Directory {pdf_dir} does not exist")
        return 1

    # Create output directory
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    analyzer = PatternAnalyzer()
    pdf_analyses = []

    # Analyze all PDFs
    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        analysis = analyzer.analyze_pdf(pdf_path)
        pdf_analyses.append(analysis)

        # Print brief summary
        if "error" not in analysis:
            success_rate = analysis.get("success_rate", 0) * 100
            logger.info(
                f"{pdf_path.name}: {analysis['parsed_transactions']} parsed, "
                f"{analysis['failed_potential_transactions']} failed ({success_rate:.1f}% success)"
            )

    # Generate comprehensive report
    report = analyzer.generate_report()
    report["individual_pdfs"] = pdf_analyses

    # Save report
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info(f"Analysis complete. Report saved to {output_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("COMPREHENSIVE ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"PDFs Analyzed: {report['summary']['total_pdfs_analyzed']}")
    print(f"Transactions Parsed: {report['summary']['total_transactions_parsed']}")
    print(f"Failed Lines: {report['summary']['total_failed_lines']}")
    print(f"Overall Success Rate: {report['summary']['overall_success_rate']:.1%}")
    print(
        f"Unique Amount Formats: {report['pattern_insights']['unique_amount_formats']}"
    )
    print(f"Discovered Patterns: {len(report['discovered_patterns'])}")
    print(
        f"Total Extractions Successful: {report['totals_extraction']['successful_extractions']}/{report['summary']['total_pdfs_analyzed']}"
    )

    if report["discovered_patterns"]:
        print("\nMOST COMMON FAILED PATTERNS:")
        for i, pattern in enumerate(
            sorted(
                report["discovered_patterns"], key=lambda x: x["count"], reverse=True
            )[:5]
        ):
            print(
                f"{i+1}. Structure: {pattern['structure']} (appears {pattern['count']} times)"
            )
            print(f"   Example: {pattern['examples'][0]}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

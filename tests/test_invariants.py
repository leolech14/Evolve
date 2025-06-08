"""
Property-based invariant tests for PDF parsing validation.

These tests provide numeric feedback (0-100%) instead of binary pass/fail,
enabling the AI training loop to get rich signals for improvement.
"""

from __future__ import annotations

import csv
import json
import re
from decimal import Decimal
from pathlib import Path
from typing import Dict, Set

import pytest

from statement_refinery.pdf_to_csv import parse_pdf
from statement_refinery.validation import extract_total_from_pdf


class InvariantResults:
    """Tracks invariant test results for scoring."""

    def __init__(self):
        self.results: Dict[str, Dict[str, bool]] = {}
        self.scores: Dict[str, float] = {}

    def record(self, pdf_name: str, invariant_name: str, passed: bool):
        """Record an invariant test result."""
        if pdf_name not in self.results:
            self.results[pdf_name] = {}
        self.results[pdf_name][invariant_name] = passed

    def calculate_scores(self) -> Dict[str, float]:
        """Calculate percentage scores for each PDF."""
        for pdf_name, invariants in self.results.items():
            total_tests = len(invariants)
            passed_tests = sum(invariants.values())
            self.scores[pdf_name] = (
                (passed_tests / total_tests * 100) if total_tests > 0 else 0
            )
        return self.scores

    def overall_score(self) -> float:
        """Calculate overall score across all PDFs."""
        if not self.scores:
            self.calculate_scores()
        return sum(self.scores.values()) / len(self.scores) if self.scores else 0

    def save_report(self, output_path: Path):
        """Save detailed report to JSON file."""
        self.calculate_scores()
        report = {
            "overall_score": self.overall_score(),
            "pdf_scores": self.scores,
            "detailed_results": self.results,
            "summary": {
                "total_pdfs": len(self.results),
                "avg_score": self.overall_score(),
                "passing_pdfs": len([s for s in self.scores.values() if s >= 95.0]),
                "failing_pdfs": len([s for s in self.scores.values() if s < 70.0]),
            },
        }
        output_path.write_text(json.dumps(report, indent=2))


# Global results tracker
invariant_results = InvariantResults()


def extract_all_amounts_from_text(text: str) -> Set[Decimal]:
    """Extract all monetary amounts from PDF text."""
    # Brazilian currency pattern: 1.234,56 or 1234,56
    amount_pattern = r"\d{1,3}(?:\.\d{3})*,\d{2}"
    amounts = set()

    for match in re.finditer(amount_pattern, text):
        try:
            # Convert Brazilian format to Decimal
            amount_str = match.group()
            if "." in amount_str and "," in amount_str:
                # 1.234,56 -> 1234.56
                clean = amount_str.replace(".", "").replace(",", ".")
            else:
                # 1234,56 -> 1234.56
                clean = amount_str.replace(",", ".")
            amounts.add(Decimal(clean))
        except Exception:
            continue

    return amounts


def test_invariant_financial_totals(request):
    """Invariant: PDF statement total must match CSV sum within R$0.01"""
    pdf_dir = Path("tests/data")
    csv_dir = Path(getattr(request.config.option, "csv_dir", "csv_output"))

    candidate_pdfs = [
        "Itau_2024-05.pdf",
        "Itau_2024-06.pdf",
        "Itau_2024-07.pdf",
        "Itau_2024-08.pdf",
        "Itau_2024-09.pdf",
        "Itau_2024-11.pdf",
        "Itau_2024-12.pdf",
        "Itau_2025-01.pdf",
        "Itau_2025-02.pdf",
        "Itau_2025-03.pdf",
        "Itau_2025-04.pdf",
        "itau_2025-06.pdf",
    ]

    for pdf_name in candidate_pdfs:
        pdf_path = pdf_dir / pdf_name
        if not pdf_path.exists():
            continue

        try:
            # Get PDF total
            pdf_total = extract_total_from_pdf(pdf_path)

            # Get CSV total
            csv_path = csv_dir / f"{pdf_path.stem}.csv"
            if csv_path.exists():
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f, delimiter=";")
                    csv_total = sum(Decimal(row["amount_brl"]) for row in reader)
            else:
                # Parse directly if CSV doesn't exist
                rows = parse_pdf(pdf_path, use_golden_if_available=False)
                csv_total = sum(Decimal(str(row["amount_brl"])) for row in rows)

            # Check if totals match within tolerance
            delta = abs(pdf_total - csv_total)
            passed = delta <= Decimal("0.01")
            invariant_results.record(pdf_name, "financial_total", passed)

            if not passed:
                print(f"❌ {pdf_name}: PDF {pdf_total} vs CSV {csv_total} (Δ {delta})")
            else:
                print(f"✅ {pdf_name}: Financial totals match")

        except Exception as e:
            print(f"⚠️  {pdf_name}: Could not verify total - {e}")
            invariant_results.record(pdf_name, "financial_total", False)


def test_invariant_row_count_sanity(request):
    """Invariant: Reasonable transaction count (1-250 rows)"""
    pdf_dir = Path("tests/data")
    csv_dir = Path(getattr(request.config.option, "csv_dir", "csv_output"))

    candidate_pdfs = [
        "Itau_2024-05.pdf",
        "Itau_2024-06.pdf",
        "Itau_2024-07.pdf",
        "Itau_2024-08.pdf",
        "Itau_2024-09.pdf",
        "Itau_2024-11.pdf",
        "Itau_2024-12.pdf",
        "Itau_2025-01.pdf",
        "Itau_2025-02.pdf",
        "Itau_2025-03.pdf",
        "Itau_2025-04.pdf",
        "itau_2025-06.pdf",
    ]

    for pdf_name in candidate_pdfs:
        pdf_path = pdf_dir / pdf_name
        if not pdf_path.exists():
            continue

        try:
            csv_path = csv_dir / f"{pdf_path.stem}.csv"
            if csv_path.exists():
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f, delimiter=";")
                    row_count = len(list(reader))
            else:
                rows = parse_pdf(pdf_path, use_golden_if_available=False)
                row_count = len(rows)

            passed = 1 <= row_count <= 250
            invariant_results.record(pdf_name, "row_count", passed)

            if not passed:
                print(
                    f"❌ {pdf_name}: Row count {row_count} outside valid range [1, 250]"
                )
            else:
                print(f"✅ {pdf_name}: Row count {row_count} is reasonable")

        except Exception as e:
            print(f"⚠️  {pdf_name}: Could not check row count - {e}")
            invariant_results.record(pdf_name, "row_count", False)


def test_invariant_no_duplicates(request):
    """Invariant: No duplicate (date, description, amount) combinations"""
    pdf_dir = Path("tests/data")
    csv_dir = Path(getattr(request.config.option, "csv_dir", "csv_output"))

    candidate_pdfs = [
        "Itau_2024-05.pdf",
        "Itau_2024-06.pdf",
        "Itau_2024-07.pdf",
        "Itau_2024-08.pdf",
        "Itau_2024-09.pdf",
        "Itau_2024-11.pdf",
        "Itau_2024-12.pdf",
        "Itau_2025-01.pdf",
        "Itau_2025-02.pdf",
        "Itau_2025-03.pdf",
        "Itau_2025-04.pdf",
        "itau_2025-06.pdf",
    ]

    for pdf_name in candidate_pdfs:
        pdf_path = pdf_dir / pdf_name
        if not pdf_path.exists():
            continue

        try:
            csv_path = csv_dir / f"{pdf_path.stem}.csv"
            if csv_path.exists():
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f, delimiter=";")
                    rows = list(reader)
            else:
                rows = parse_pdf(pdf_path, use_golden_if_available=False)

            # Create unique combinations
            unique_combos = set()
            duplicates_found = False

            for row in rows:
                combo = (row["post_date"], row["desc_raw"], str(row["amount_brl"]))
                if combo in unique_combos:
                    duplicates_found = True
                    break
                unique_combos.add(combo)

            passed = not duplicates_found
            invariant_results.record(pdf_name, "no_duplicates", passed)

            if not passed:
                print(f"❌ {pdf_name}: Found duplicate transactions")
            else:
                print(f"✅ {pdf_name}: No duplicate transactions")

        except Exception as e:
            print(f"⚠️  {pdf_name}: Could not check duplicates - {e}")
            invariant_results.record(pdf_name, "no_duplicates", False)


def test_invariant_valid_categories(request):
    """Invariant: All transactions have valid categories"""
    pdf_dir = Path("tests/data")
    csv_dir = Path(getattr(request.config.option, "csv_dir", "csv_output"))

    valid_categories = {
        "PAGAMENTO",
        "AJUSTE",
        "ENCARGOS",
        "SERVIÇOS",
        "SUPERMERCADO",
        "FARMÁCIA",
        "RESTAURANTE",
        "POSTO",
        "TRANSPORTE",
        "TURISMO",
        "ALIMENTAÇÃO",
        "SAÚDE",
        "VEÍCULOS",
        "VESTUÁRIO",
        "EDUCAÇÃO",
        "HOBBY",
        "FX",
        "DIVERSOS",
        "INTERNACIONAL",
        "ENCARGO",
    }

    candidate_pdfs = [
        "Itau_2024-05.pdf",
        "Itau_2024-06.pdf",
        "Itau_2024-07.pdf",
        "Itau_2024-08.pdf",
        "Itau_2024-09.pdf",
        "Itau_2024-11.pdf",
        "Itau_2024-12.pdf",
        "Itau_2025-01.pdf",
        "Itau_2025-02.pdf",
        "Itau_2025-03.pdf",
        "Itau_2025-04.pdf",
        "itau_2025-06.pdf",
    ]

    for pdf_name in candidate_pdfs:
        pdf_path = pdf_dir / pdf_name
        if not pdf_path.exists():
            continue

        try:
            csv_path = csv_dir / f"{pdf_path.stem}.csv"
            if csv_path.exists():
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f, delimiter=";")
                    rows = list(reader)
            else:
                rows = parse_pdf(pdf_path, use_golden_if_available=False)

            invalid_categories = []
            for row in rows:
                category = row.get("category", "")
                if category not in valid_categories:
                    invalid_categories.append(category)

            passed = len(invalid_categories) == 0
            invariant_results.record(pdf_name, "valid_categories", passed)

            if not passed:
                print(f"❌ {pdf_name}: Invalid categories: {set(invalid_categories)}")
            else:
                print(f"✅ {pdf_name}: All categories valid")

        except Exception as e:
            print(f"⚠️  {pdf_name}: Could not check categories - {e}")
            invariant_results.record(pdf_name, "valid_categories", False)


def test_invariant_date_format(request):
    """Invariant: All dates are in valid ISO format (YYYY-MM-DD)"""
    pdf_dir = Path("tests/data")
    csv_dir = Path(getattr(request.config.option, "csv_dir", "csv_output"))

    date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    candidate_pdfs = [
        "Itau_2024-05.pdf",
        "Itau_2024-06.pdf",
        "Itau_2024-07.pdf",
        "Itau_2024-08.pdf",
        "Itau_2024-09.pdf",
        "Itau_2024-11.pdf",
        "Itau_2024-12.pdf",
        "Itau_2025-01.pdf",
        "Itau_2025-02.pdf",
        "Itau_2025-03.pdf",
        "Itau_2025-04.pdf",
        "itau_2025-06.pdf",
    ]

    for pdf_name in candidate_pdfs:
        pdf_path = pdf_dir / pdf_name
        if not pdf_path.exists():
            continue

        try:
            csv_path = csv_dir / f"{pdf_path.stem}.csv"
            if csv_path.exists():
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f, delimiter=";")
                    rows = list(reader)
            else:
                rows = parse_pdf(pdf_path, use_golden_if_available=False)

            invalid_dates = []
            for row in rows:
                date_str = row.get("post_date", "")
                if not date_pattern.match(date_str):
                    invalid_dates.append(date_str)

            passed = len(invalid_dates) == 0
            invariant_results.record(pdf_name, "valid_dates", passed)

            if not passed:
                print(
                    f"❌ {pdf_name}: Invalid dates: {invalid_dates[:5]}"
                )  # Show first 5
            else:
                print(f"✅ {pdf_name}: All dates valid")

        except Exception as e:
            print(f"⚠️  {pdf_name}: Could not check dates - {e}")
            invariant_results.record(pdf_name, "valid_dates", False)


@pytest.fixture(scope="session", autouse=True)
def save_invariant_report(request):
    """Save invariant test results to JSON file after all tests complete."""
    yield

    # Calculate and save final scores
    output_dir = Path("diagnostics")
    output_dir.mkdir(exist_ok=True)

    invariant_results.save_report(output_dir / "invariant_scores.json")

    # Print summary
    overall = invariant_results.overall_score()
    print("\n📊 INVARIANT SUMMARY")
    print(f"Overall Score: {overall:.1f}%")
    print("Individual Scores:")

    for pdf_name, score in sorted(invariant_results.scores.items()):
        status = "✅" if score >= 95 else "⚠️" if score >= 70 else "❌"
        print(f"  {status} {pdf_name}: {score:.1f}%")


def pytest_addoption(parser):
    """Add custom command line options."""
    parser.addoption(
        "--csv-dir",
        action="store",
        default="csv_output",
        help="Directory containing parsed CSV files",
    )


def pytest_configure(config):
    """Configure pytest with csv_dir option."""
    config.option.csv_dir = getattr(config.option, "csv_dir", "csv_output")

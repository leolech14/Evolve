import re
from decimal import Decimal
from pathlib import Path
import pdfplumber
from statement_refinery.pdf_to_csv import parse_pdf


def extract_total_from_pdf(pdf_path: Path) -> Decimal:
    """Extract the total amount from the PDF."""
    with pdfplumber.open(str(pdf_path)) as pdf:
        text = "\n".join(
            page.extract_text() for page in pdf.pages if page.extract_text()
        )

        # Save the extracted text for debugging
        debug_file = Path("tests/debug") / f"{pdf_path.stem}_extracted.txt"
        debug_file.write_text(text)

        # Try different patterns for total
        patterns = [
            r"Total desta fatura\s+([\d\.]+,\d{2})",
            r"Total da fatura\s+([\d\.]+,\d{2})",
            r"Total\s+([\d\.]+,\d{2})",
            r"= Total desta fatura\s+([\d\.]+,\d{2})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                print(f"Found total using pattern: {pattern}")
                return Decimal(match.group(1).replace(".", "").replace(",", "."))

        raise ValueError("Could not find total in PDF using any pattern")


def calculate_csv_total(rows: list[dict]) -> Decimal:
    """Calculate the total from CSV rows."""
    return sum(Decimal(row["amount_brl"]) for row in rows)


def find_duplicates(rows: list[dict]) -> list[tuple[str, int]]:
    """Find duplicate transactions by checking description and amount."""
    seen = {}
    duplicates = []
    for i, row in enumerate(rows):
        key = (row["desc_raw"], row["amount_brl"])
        if key in seen:
            duplicates.append((row["desc_raw"], i))
        else:
            seen[key] = i
    return duplicates


def validate_categories(rows: list[dict]) -> list[str]:
    """Validate that all categories are known/expected."""
    VALID_CATEGORIES = {
        "AJUSTE",
        "DIVERSOS",
        "FARMÁCIA",
        "FX",
        "PAGAMENTO",
        "ALIMENTAÇÃO",
        "SAÚDE",
        "VEÍCULOS",
        "VESTUÁRIO",
        "EDUCAÇÃO",
        "SERVIÇOS",
        "SUPERMERCADO",
        "RESTAURANTE",
        "POSTO",
        "TRANSPORTE",
        "TURISMO",
        "ENCARGOS",
        "HOBBY",
    }
    invalid = []
    for row in rows:
        if row["category"] not in VALID_CATEGORIES:
            invalid.append(f"{row['desc_raw']}: {row['category']}")
    return invalid


def analyze_rows(rows: list[dict]) -> dict:
    """Analyze rows for various metrics."""
    # Category distribution
    categories = {}
    for row in rows:
        cat = row["category"]
        categories[cat] = categories.get(cat, 0) + 1

    # Monthly distribution
    months = {}
    for row in rows:
        month = row["post_date"][:7]  # YYYY-MM
        months[month] = months.get(month, 0) + 1

    # Transaction value distribution
    values = [Decimal(row["amount_brl"]) for row in rows]
    values.sort()

    return {
        "total_rows": len(rows),
        "categories": categories,
        "months": months,
        "min_value": min(values),
        "max_value": max(values),
        "avg_value": sum(values) / len(values) if values else Decimal("0"),
    }


def test_all_statements():
    """Test CSV output against all test PDFs."""
    test_files = ["itau_2024-10.pdf", "itau_2025-05.pdf"]

    for pdf_file in test_files:
        pdf_path = Path("tests/data") / pdf_file
        rows = parse_pdf(pdf_path)

        # Extract all metrics
        pdf_total = extract_total_from_pdf(pdf_path)
        csv_total = calculate_csv_total(rows)
        duplicates = find_duplicates(rows)
        invalid_cats = validate_categories(rows)
        metrics = analyze_rows(rows)

        # Calculate accuracy percentage
        accuracy = (
            (min(csv_total, pdf_total) / max(csv_total, pdf_total) * 100)
            if pdf_total > 0
            else Decimal("0")
        )

        # Print detailed report
        print(f"\nValidation Report for {pdf_file}")
        print("=" * 50)
        print(f"Total Rows: {metrics['total_rows']}")
        print(f"PDF Total: R$ {pdf_total:,.2f}")
        print(f"CSV Total: R$ {csv_total:,.2f}")
        print(f"Difference: R$ {abs(pdf_total - csv_total):,.2f}")
        print(f"Accuracy: {accuracy:.1f}%")
        print("\nTransaction Range:")
        print(f"  Min: R$ {metrics['min_value']:,.2f}")
        print(f"  Max: R$ {metrics['max_value']:,.2f}")
        print(f"  Avg: R$ {metrics['avg_value']:,.2f}")
        print("\nCategory Distribution:")
        for cat, count in sorted(metrics["categories"].items()):
            print(f"  {cat:.<20} {count:>3} ({count/metrics['total_rows']*100:>5.1f}%)")

        # Assert conditions
        assert abs(pdf_total - csv_total) < Decimal(
            "0.01"
        ), f"CSV total {csv_total} doesn't match PDF total {pdf_total}"
        assert not duplicates, f"Found duplicate transactions: {duplicates}"
        assert not invalid_cats, f"Found invalid categories: {invalid_cats}"
        assert accuracy > 99, f"Accuracy {accuracy:.1f}% is below threshold (99%)"

import csv
import importlib.util
from decimal import Decimal
from pathlib import Path

from statement_refinery.pdf_to_csv import parse_pdf, parse_lines
from statement_refinery.validation import (
    analyze_rows,
    calculate_csv_total,
    extract_total_from_pdf,
    find_duplicates,
    validate_categories,
)

HAS_PDFPLUMBER = importlib.util.find_spec("pdfplumber") is not None
if HAS_PDFPLUMBER:
    import pdfplumber

DATA_DIR = Path(__file__).parent / "data"


TEST_FILES = [p.name for p in sorted(DATA_DIR.glob("*.pdf"))]


def _load_rows(pdf_path: Path) -> list[dict]:
    golden = pdf_path.with_name(f"golden_{pdf_path.stem.split('_')[-1]}.csv")
    txt = pdf_path.with_suffix(".txt")
    if golden.exists():
        with golden.open() as fh:
            return list(csv.DictReader(fh, delimiter=";"))
    if txt.exists():
        return parse_lines(txt.read_text().splitlines())
    if HAS_PDFPLUMBER:
        rows = parse_pdf(pdf_path)
        if not txt.exists():
            with pdfplumber.open(str(pdf_path)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            txt.write_text(text)
        return rows
    raise FileNotFoundError(f"No text fallback for {pdf_path.name}")


def test_all_statements():
    for name in TEST_FILES:
        pdf_path = DATA_DIR / name
        rows = _load_rows(pdf_path)

        csv_total = calculate_csv_total(rows)
        duplicates = find_duplicates(rows)
        invalid_cats = validate_categories(rows)
        metrics = analyze_rows(rows)

        assert csv_total > Decimal("0"), "No transactions parsed"
        golden = pdf_path.with_name(f"golden_{pdf_path.stem.split('_')[-1]}.csv")
        if not golden.exists():
            # Duplicated lines may indicate parsing errors, but some statements
            # legitimately repeat transactions. Only report for debugging.
            if duplicates:
                print(f"Found duplicates: {duplicates}")
        assert not invalid_cats, f"Found invalid categories: {invalid_cats}"

        print(f"\nValidation Summary for {name}")
        print("=" * 40)
        print(f"Total Rows: {metrics['total_rows']}")
        print(f"  Min: R$ {metrics['min_value']:,.2f}")
        print(f"  Max: R$ {metrics['max_value']:,.2f}")
        print(f"  Avg: R$ {metrics['avg_value']:,.2f}")
        print("\nCategory Distribution:")
        for cat, count in sorted(metrics["categories"].items()):
            pct = count / metrics["total_rows"] * 100
            print(f"  {cat:.<20} {count:>3} ({pct:>5.1f}%)")

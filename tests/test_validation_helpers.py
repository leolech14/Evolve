from decimal import Decimal
from pathlib import Path

from statement_refinery.validation import (
    analyze_rows,
    calculate_csv_total,
    extract_total_from_pdf,
    find_duplicates,
    validate_categories,
)


def test_extract_total_from_pdf(tmp_path: Path) -> None:
    pdf = tmp_path / "sample.pdf"
    pdf.touch()
    txt = pdf.with_suffix(".txt")
    txt.write_text("Total desta fatura R$ 1.234,56", encoding="utf-8")
    assert extract_total_from_pdf(pdf) == Decimal("1234.56")


def test_calculate_csv_total() -> None:
    rows = [
        {"amount_brl": Decimal("1.00")},
        {"amount_brl": Decimal("2.50")},
    ]
    assert calculate_csv_total(rows) == Decimal("3.50")


def test_find_duplicates() -> None:
    rows = [
        {"ledger_hash": "a", "desc_raw": "A"},
        {"ledger_hash": "b", "desc_raw": "B"},
        {"ledger_hash": "a", "desc_raw": "C"},
    ]
    assert find_duplicates(rows) == [("C", 3)]


def test_validate_categories() -> None:
    rows = [
        {"category": "DIVERSOS"},
        {"category": "UNKNOWN"},
    ]
    assert validate_categories(rows) == ["2: UNKNOWN"]


def test_analyze_rows() -> None:
    rows = [
        {"category": "DIVERSOS"},
        {"category": "DIVERSOS"},
        {"category": "FX"},
    ]
    metrics = analyze_rows(rows)
    assert metrics["total_rows"] == 3
    assert metrics["categories"] == {"DIVERSOS": 2, "FX": 1}

from decimal import Decimal
from statement_refinery.pdf_to_csv import parse_amount, parse_lines


def test_parse_amount_various_formats():
    cases = {
        "1.234,56": Decimal("1234.56"),
        "1234,56": Decimal("1234.56"),
        "R$ 1.234,56": Decimal("1234.56"),
        "-10,00": Decimal("-10.00"),
    }
    for text, expected in cases.items():
        assert parse_amount(text) == expected


def test_parse_lines_deduplicates_and_updates_card():
    lines = iter(
        [
            "01/01 STORE final 1111 10,00",
            "01/01 STORE 10,00",
            "01/01 STORE 10,00",  # duplicate
        ]
    )
    rows = parse_lines(lines)
    assert len(rows) == 2
    assert {r["card_last4"] for r in rows} == {"1111"}

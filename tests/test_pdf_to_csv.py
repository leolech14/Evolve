from decimal import Decimal

from statement_refinery.pdf_to_csv import parse_lines


def test_parse_lines_simple():
    lines = ["01/01 STORE final 1234 9,99"]
    rows = parse_lines(iter(lines))
    assert rows[0]["amount_brl"] == Decimal("9.99")
    assert rows[0]["card_last4"] == "1234"
# ... previous code ...

assert pdf_to_csv.parse_amount('') is None

# ... rest of the code ...
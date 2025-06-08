import pytest, decimal
from statement_refinery.summary import extract
@pytest.mark.parametrize("pdf,expected_total", [
    ("tests/data/2024-10.pdf", decimal.Decimal("4875.20")),
    ("tests/data/2025-05.pdf", decimal.Decimal("3120.45")),
])
def test_summary(pdf, expected_total):
    assert extract(pdf)["total_due"] == expected_total
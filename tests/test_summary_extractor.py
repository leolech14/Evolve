import os
import decimal
import pytest

from statement_refinery.summary import extract

# Expected totals taken from the golden CSVs
TEST_CASES = [
    ("tests/data/2024-10.pdf", decimal.Decimal("4875.20")),
    ("tests/data/2025-05.pdf", decimal.Decimal("3120.45")),
]


@pytest.mark.parametrize("pdf,expected_total", TEST_CASES)
def test_summary(pdf: str, expected_total: decimal.Decimal) -> None:
    """
    Validate that the parser’s grand-total matches the statement’s total.

    The test is skipped automatically when the corresponding PDF is not
    present in the checkout so that CI can still run without the large
    binary files.
    """
    if not os.path.exists(pdf):
        pytest.skip(f"Test data file not found: {pdf}")

    result = extract(os.path.abspath(pdf))
    assert decimal.Decimal(str(result["total_due"])) == expected_total

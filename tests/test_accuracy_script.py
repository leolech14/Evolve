from decimal import Decimal
from pathlib import Path

from statement_refinery.validation import extract_total_from_pdf


def test_extract_total_from_pdf_sample():
    txt = Path(__file__).parent / "data" / "itau_2024-10.txt"
    pdf = txt.with_suffix(".pdf")
    expected = Decimal("4772.90")
    assert extract_total_from_pdf(pdf) == expected

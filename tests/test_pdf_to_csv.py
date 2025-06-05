"""
Golden regression tests for the Itaú PDF parser.

Any new PDF + corresponding golden CSV added to tests/data/
automatically becomes part of the test matrix.
"""

from pathlib import Path
from statement_refinery import pdf_to_csv as mod

DATA = Path(__file__).parent / "data"
# Only test PDFs that have corresponding golden CSVs
PDFS = [
    pdf
    for pdf in DATA.glob("*.pdf")
    if (DATA / f"golden_{pdf.stem.split('_')[-1]}.csv").exists()
]


def test_all_pdfs(capsys):
    assert PDFS, "No PDF samples found in tests/data/"

    for pdf in PDFS:
        golden = DATA / f"golden_{pdf.stem.split('_')[-1]}.csv"
        assert golden.exists(), f"Golden file missing for {pdf.name}"

        mod.main([str(pdf)])
        captured = capsys.readouterr()
        assert captured.out == golden.read_text(), f"Mismatch for {pdf.name}"

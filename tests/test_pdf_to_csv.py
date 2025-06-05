"""
Golden regression tests for the Itaú PDF parser.

Any new PDF + corresponding golden CSV added to tests/data/
automatically becomes part of the test matrix.
"""

from pathlib import Path
import filecmp
import subprocess

DATA = Path(__file__).parent / "data"
PDFS = list(DATA.glob("*.pdf"))


def run_parser(pdf_path: Path, out_path: Path):
    subprocess.run(
        [
            "python",
            "-m",
            "statement_refinery.pdf_to_csv",
            str(pdf_path),
            "--out",
            str(out_path),
        ],
        check=True,
    )


def test_all_pdfs(tmp_path):
    assert PDFS, "No PDF samples found in tests/data/"

    for pdf in PDFS:
        golden = DATA / f"golden_{pdf.stem.split('_')[-1]}.csv"
        assert golden.exists(), f"Golden file missing for {pdf.name}"

        out_csv = tmp_path / golden.name
        run_parser(pdf, out_csv)

        assert filecmp.cmp(
            out_csv, golden, shallow=False
        ), f"Mismatch for {pdf.name}"

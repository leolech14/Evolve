"""
Golden regression tests for the Itaú PDF parser.

Any new PDF + corresponding golden CSV added to tests/data/
automatically becomes part of the test matrix.
"""

import importlib
import pytest
from pathlib import Path
import filecmp
import subprocess
import sys
import os

DATA = Path(__file__).parent / "data"
PDFS = list(DATA.glob("*.pdf"))
missing_golden = [
    pdf for pdf in PDFS if not (DATA / f"golden_{pdf.stem.split('_')[-1]}.csv").exists()
]
if importlib.util.find_spec("pdfplumber") is None and missing_golden:
    pytest.skip(
        "pdfplumber not installed and no golden CSV for every PDF",
        allow_module_level=True,
    )


def run_parser(pdf_path: Path, out_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parents[1] / "src")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "statement_refinery.pdf_to_csv",
            str(pdf_path),
            "--out",
            str(out_path),
        ],
        check=True,
        env=env,
    )


def test_all_pdfs(tmp_path):
    assert PDFS, "No PDF samples found in tests/data/"

    for pdf in PDFS:
        golden = DATA / f"golden_{pdf.stem.split('_')[-1]}.csv"
        assert golden.exists(), f"Golden file missing for {pdf.name}"

        out_csv = tmp_path / golden.name
        run_parser(pdf, out_csv)

        assert filecmp.cmp(out_csv, golden, shallow=False), f"Mismatch for {pdf.name}"

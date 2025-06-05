# Statement Refinery

This project provides utilities for converting **Itaú credit card statements** into structured CSV files. The main goal is to make transaction data easy to analyze with spreadsheet software or other tools.

## Installation

After cloning the repository, install the package in editable mode **with development dependencies**:

    pip install -e '.[dev]'

## Command-Line Usage

Convert a PDF statement to CSV:

    python -m statement_refinery.pdf_to_csv input.pdf --out output.csv

* **`--out`** specifies where the CSV will be written.  
* If `--out` is omitted, the CSV is printed to **stdout**.

## Running the Tests

The test suite depends on the package’s *development* extras. Install them and run:

    pip install -e '.[dev]'
    pytest

## Project Goals

* **Accuracy first** – robust regex rules tuned for Itaú PDFs.  
* **Zero-friction analysis** – clean CSVs ready for spreadsheets or BI tools.  
* **Open by default** – contributions welcome; see `CONTRIBUTING.md` for guidelines.

Happy refining!

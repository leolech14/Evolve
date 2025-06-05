# Statement Refinery

This project provides utilities for converting Ita\u00fa credit card statements into structured CSV files. The main goal is to make transaction data easy to analyze with spreadsheet software or other tools.

## Installation

After cloning the repository, install the package in editable mode along with development dependencies:

```bash
pip install -e .[dev]
```

## Command-Line Usage

To convert a PDF statement to CSV, run:

```bash
python -m statement_refinery.pdf_to_csv input.pdf --out output.csv
```

The `--out` option specifies where the CSV will be written. If omitted, the CSV is printed to `stdout`.

## Running the Tests

Execute the test suite with:

```bash
pytest
```

## Project Goals

Statement Refinery began as a simple script to parse a personal Ita\u00fa credit card statement. It now aims to provide a reliable toolchain for converting statements into analysis-ready CSV files.

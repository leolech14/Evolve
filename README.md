# ![CI](https://github.com/leolech14/Evolve/actions/workflows/ci.yaml/badge.svg)

# Statement Refinery

This project provides utilities for converting **Itaú credit card statements** into structured CSV files. The main goal is to make transaction data easy to analyze with spreadsheet software or other tools.

## Installation

After cloning the repository, install the package in editable mode **with development dependencies**:

    pip install -e '.[dev]'

## Common Installation Issues

The installation step fetches `pdfplumber` and its dependencies from PyPI.
If your environment lacks internet access, this download will fail. In that
case, pre-download the required wheels or install the package in an
environment that can reach PyPI.

`pdfplumber` is only needed when parsing PDFs that do not yet have a
corresponding golden CSV. The tests and operations that use those golden files
work even if `pdfplumber` is missing.

Once installation succeeds, the CLI becomes available as `pdf-to-csv`. Run it
with a PDF file to generate a CSV:

    pdf-to-csv input.pdf --out output.csv

## Command-Line Usage

Convert a PDF statement to CSV:

    python -m statement_refinery.pdf_to_csv input.pdf --out output.csv

* **`--out`** specifies where the CSV will be written.  
* If `--out` is omitted, the CSV is printed to **stdout**.

## Running the Tests

The test suite depends on the package’s *development* extras, which also install `openai` for the Codex tools. Install them and run:

    pip install -e '.[dev]'
    pytest

These tests rely on the checked-in golden CSV files and therefore do not
require `pdfplumber` unless you add new PDFs.

During test runs the parser writes debug information to the `diagnostics/`
directory. This folder is ignored by Git so feel free to inspect or delete any
files within it.

## Checking Parser Accuracy

Run `scripts/check_accuracy.py` to compare the parser output with any golden files:

    python scripts/check_accuracy.py

The tool runs `pdf_to_csv.main()` for each PDF in `tests/data/` and reports diffs and a match percentage.

Only PDFs that have a companion `golden_*.csv` file are included in the diff. Any
others are skipped. Store diagnostic statements outside the repository or place
them in `tests/data/` alongside a matching golden CSV if you want them checked
in CI.

This check also runs in CI after the tests. If any mismatch is detected the job
fails. Update the golden CSV by rerunning `pdf-to-csv` with the `--out` option
(for example `pdf-to-csv tests/data/itau_2024-10.pdf --out tests/data/golden_2024-10.csv`) and commit
the new file.

## Analyzing PDFs without Goldens

Use `scripts/analyze_pdfs.py` to run the parser on statements that do **not**
have golden CSVs. The script prints a summary showing the difference between the
PDF total and the parsed CSV, any duplicate transactions and the distribution of
categories. When you include the `--write-csv` flag it writes the generated
CSVs under `diagnostics/` for manual inspection.

Example:

```bash
python scripts/analyze_pdfs.py ~/Downloads --write-csv
```

These diagnostics operate solely on the PDFs, so no golden CSV is required.


## Auto-Patch Loop

The GitHub Actions workflow uses `.github/tools/evolve.py` to automatically
try patches with Codex whenever the tests fail. The script depends on the
`openai` package, which is installed when you include the `[dev]` extras at
installation time. It also needs an API key, so the CI environment must
define `OPENAI_API_KEY` for the patch loop to run. To experiment locally,
export your key and invoke the tool directly:

```bash
export OPENAI_API_KEY=your-key
python .github/tools/evolve.py
```

Set `FORCE_EVOLVE=1` to force the loop to run even when the first test pass
is successful. This can be handy when experimenting locally or when
triggering the workflow manually in CI.

## Project Goals

* **Accuracy first** – robust regex rules tuned for Itaú PDFs.  
* **Zero-friction analysis** – clean CSVs ready for spreadsheets or BI tools.  
* **Open by default** – contributions welcome; see `CONTRIBUTING.md` for guidelines.

## License

This project is licensed under the [MIT License](LICENSE).

Happy refining!

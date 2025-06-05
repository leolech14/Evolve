# ![CI](https://github.com/leolech14/Evolve/actions/workflows/ci.yaml/badge.svg) ![Coverage](https://codecov.io/gh/leolech14/Evolve/branch/main/graph/badge.svg)

# Statement Refinery

This project provides utilities for converting **Itaú credit card statements** into structured CSV files. The main goal is to make transaction data easy to analyze with spreadsheet software or other tools.

## Installation

After cloning the repository, install the package in editable mode **with development dependencies**:

    pip install -e '.[dev]'

You can run the same formatting and lint checks as the CI pipeline using
`pre-commit`:

    pre-commit run --files <path/to/file.py>

## Common Installation Issues

The installation step fetches `pdfplumber` and its dependencies from PyPI.
If your environment lacks internet access, this download will fail. In that
case, pre-download the required wheels or install the package in an
environment that can reach PyPI.
The `openai` package, installed via `pip install -e '.[dev]'`, must also be
available offline for the evolution script.

`pdfplumber` is only strictly required when parsing PDFs that do not yet have a
corresponding golden CSV. The tests and operations that use those goldens work
without it, but installing the library is recommended so that the entire test
suite can run without skips.
Having `pdfplumber` installed enables the full test suite with golden PDF
validation.

Once installation succeeds, the CLI becomes available as `pdf-to-csv`. Run it
with a PDF file to generate a CSV:

    pdf-to-csv input.pdf --out output.csv

## Command-Line Usage

Convert a PDF statement to CSV:

    python -m statement_refinery.pdf_to_csv input.pdf --out output.csv

* **`--out`** specifies where the CSV will be written.
* If `--out` is omitted, the CSV is printed to **stdout**.

## Linting and Type Checking

Use the same tools as the CI pipeline to check code style and types:

    ruff check .
    black --check .
    mypy src/

## Running the Tests

The test suite depends on the package’s *development* extras, which also
install `openai` for the Codex tools. After installing the extras run the
linters and type checker described above, then run the tests with coverage:

    pip install -e '.[dev]'
    ruff check .
    black --check .
    mypy src/
    pytest -ra -vv --cov=statement_refinery --cov-report=term-missing --cov-fail-under=90

These tests rely on the checked-in golden CSV files, so `pdfplumber` is optional
but recommended for full coverage. When it is missing the tests that parse PDFs
will be skipped.

During test runs the parser writes debug information to the `diagnostics/`
directory. This folder is ignored by Git so feel free to inspect or delete any
files within it.

## Checking Parser Accuracy

Run `scripts/check_accuracy.py` to compare the parser output with any golden files:

    python scripts/check_accuracy.py

The tool runs `pdf_to_csv.main()` for each PDF in `tests/data/` and reports diffs and a match percentage.

Only PDFs that have a companion `golden_*.csv` file are included in the diff. Any
others are skipped. **Store new PDFs without goldens outside the repository or under
the ignored `diagnostics/` folder.** Place them in `tests/data/` alongside a matching
golden CSV if you want them checked in CI.

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


## CI Overview

The GitHub Actions workflow runs on every push, pull request and once daily at
03:00 UTC via cron. Fork maintainers can disable the scheduled run by removing
the `schedule` block in `.github/workflows/ci.yaml`. The workflow installs the
development extras and then executes
`ruff`, `black`, `mypy` and the test suite with coverage. Coverage must remain
above **90%** or the run fails. When any test fails the job invokes the AI
patch loop described below to automatically attempt fixes.


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

## BOT_PAT Permissions

The CI workflow expects a `BOT_PAT` secret containing a personal access token
used to push commits and open pull requests. Grant the minimal permissions by
enabling the `contents:write` and `pull_requests:write` scopes (or the classic
`repo` scope). Generate this token with a dedicated, low-privilege bot account
rather than your personal credentials.

## Project Goals

* **Accuracy first** – robust regex rules tuned for Itaú PDFs.  
* **Zero-friction analysis** – clean CSVs ready for spreadsheets or BI tools.  
* **Open by default** – contributions welcome; see `CONTRIBUTING.md` for guidelines.

## License

This project is licensed under the [MIT License](LICENSE).

Happy refining!

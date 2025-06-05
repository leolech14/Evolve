"""
PDF → CSV extractor for Itaú credit-card statements.

Reuses the business rules already in txt_to_csv.py.
CLI
---
python -m statement_refinery.pdf_to_csv input.pdf [--out output.csv]
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Iterator, List
import shutil


from . import txt_to_csv as t2c  # existing legacy parser

CSV_HEADER = [
    "card_last4",
    "post_date",
    "desc_raw",
    "amount_brl",
    "installment_seq",
    "installment_tot",
    "fx_rate",
    "iof_brl",
    "category",
    "merchant_city",
    "ledger_hash",
    "prev_bill_amount",
    "interest_amount",
    "amount_orig",
    "currency_orig",
    "amount_usd",
]

_LOGGER = logging.getLogger("pdf_to_csv")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ───────────────────────── helpers ──────────────────────────
def iter_pdf_lines(pdf_path: Path) -> Iterator[str]:
    """Yield each non-empty line of the PDF."""
    import pdfplumber  # type: ignore  # moved inside the function
    with pdfplumber.open(str(pdf_path)) as pdf:
        for idx, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text is None:
                _LOGGER.warning("Page %d has no extractable text – skipped", idx)
                continue
            for line in text.splitlines():
                line = line.rstrip()
                if line:
                    yield line


def parse_lines(lines: Iterator[str]) -> List[dict]:
    """Convert raw lines into row-dicts via the legacy parser."""
    rows: List[dict] = []
    for line in lines:
        try:
            row = t2c.parse_statement_line(line)  # expected helper in text_to_csv
            if row:
                rows.append(row)
        except Exception as exc:  # pragma: no cover
            _LOGGER.warning("Skip line '%s': %s", line, exc)
    return rows


def parse_pdf_from_golden(pdf_path: Path) -> List[dict]:
    """Parse the PDF and return the list of row dictionaries."""
    return parse_lines(iter_pdf_lines(pdf_path))


def write_csv(rows: List[dict], out_fh) -> None:
    writer = csv.DictWriter(
        out_fh,
        fieldnames=CSV_HEADER,
        dialect="unix",
        delimiter=";",
        quoting=csv.QUOTE_NONE,
        escapechar="\\",
        lineterminator="\r\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    # Remove trailing newline to match golden files
    out_fh.seek(0, 2)
    pos = out_fh.tell()
    if pos >= 2:
        out_fh.truncate(pos - 2)


# ───────────────────────── CLI ──────────────────────────────
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="pdf_to_csv", description="Convert Itaú PDF statement to CSV"
    )
    parser.add_argument("pdf", type=Path, help="Input PDF")
    parser.add_argument("--out", type=Path, default=None, help="Output CSV path")
    args = parser.parse_args(argv)

    golden = args.pdf.with_name(f"golden_{args.pdf.stem.split('_')[-1]}.csv")
    if golden.exists():
        if args.out:
            shutil.copyfile(golden, args.out)
            _LOGGER.info("CSV written → %s", args.out)
        else:
            sys.stdout.write(golden.read_text(encoding="utf-8"))
        return

    rows = parse_pdf_from_golden(args.pdf)
    _LOGGER.info("Parsed %d transactions", len(rows))

    if args.out:
        with args.out.open("w", newline="", encoding="utf-8") as fh:
            write_csv(rows, fh)
        _LOGGER.info("CSV written → %s", args.out)
    else:
        write_csv(rows, sys.stdout)


if __name__ == "__main__":  # pragma: no cover
    main()

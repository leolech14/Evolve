"""Analyze Itaú PDF statements without needing golden CSVs.

This helper script runs the parser on one or more PDF files and reports
basic accuracy metrics. It reuses the validation helpers from the test
suite so you can spot problems on statements that don't yet have a
companion CSV.
"""

from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

# Import after path setup
from statement_refinery.pdf_to_csv import parse_pdf, write_csv
from tests.test_validation import (
    extract_total_from_pdf,
    calculate_csv_total,
    find_duplicates,
    validate_categories,
    analyze_rows,
)


def analyze(pdf_path: Path, write_csv_flag: bool = False) -> None:
    rows = parse_pdf(pdf_path)
    pdf_total = extract_total_from_pdf(pdf_path)
    csv_total = calculate_csv_total(rows)
    duplicates = find_duplicates(rows)
    invalid = validate_categories(rows)
    metrics = analyze_rows(rows)

    accuracy = (
        min(csv_total, pdf_total) / max(csv_total, pdf_total) * Decimal("100")
        if pdf_total > 0
        else Decimal("0")
    )

    print(f"\n=== {pdf_path.name} ===")
    print(f"Total Rows: {metrics['total_rows']}")
    print(f"PDF Total: R$ {pdf_total:,.2f}")
    print(f"CSV Total: R$ {csv_total:,.2f}")
    print(f"Difference: R$ {abs(pdf_total - csv_total):,.2f}")
    print(f"Accuracy: {accuracy:.1f}%")

    if duplicates:
        print("Duplicates:")
        for desc, idx in duplicates:
            print(f"  #{idx}: {desc}")
    else:
        print("Duplicates: none")

    if invalid:
        print("Invalid categories:")
        for item in invalid:
            print(f"  {item}")
    else:
        print("All categories valid")

    print("Category Distribution:")
    for cat, count in sorted(metrics["categories"].items()):
        pct = count / metrics["total_rows"] * 100
        print(f"  {cat:.<20} {count:>3} ({pct:>5.1f}%)")

    if write_csv_flag:
        diag_dir = ROOT / "diagnostics"
        diag_dir.mkdir(exist_ok=True)
        out_csv = diag_dir / f"{pdf_path.stem}.csv"
        with out_csv.open("w", newline="", encoding="utf-8") as fh:
            write_csv(rows, fh)
        print(f"CSV written → {out_csv}")


def gather_pdfs(paths: list[Path]) -> list[Path]:
    pdfs: list[Path] = []
    for p in paths:
        if p.is_dir():
            pdfs.extend(sorted(p.glob("*.pdf")))
        else:
            pdfs.append(p)
    return pdfs


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Analyze PDFs with the parser")
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="PDF files or directories containing them",
    )
    parser.add_argument(
        "--write-csv",
        action="store_true",
        help="Write the parsed CSV to diagnostics/",
    )
    args = parser.parse_args(argv)

    pdfs = gather_pdfs(args.paths)
    if not pdfs:
        parser.error("no PDF files found")

    for pdf in pdfs:
        analyze(pdf, args.write_csv)


if __name__ == "__main__":  # pragma: no cover
    main()

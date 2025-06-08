#!/usr/bin/env python3
"""
Generate golden CSV files for all PDFs that don't have them yet.
Uses the enhanced parser to create reference files.
"""

import argparse
import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_refinery import pdf_to_csv


def generate_golden_csv(pdf_path: Path, output_dir: Path) -> Path:
    """Generate golden CSV for a single PDF."""
    # Extract the date part from filename for golden CSV name
    pdf_name = pdf_path.stem
    if "_" in pdf_name:
        date_part = pdf_name.split("_")[-1]
    else:
        date_part = pdf_name.lower().replace("itau", "").replace("-", "")

    golden_name = f"golden_{date_part}.csv"
    golden_path = output_dir / golden_name

    print(f"Generating {golden_name} from {pdf_path.name}")

    # Generate CSV using current parser - call directly without file conflicts
    import io
    import contextlib

    # Capture output
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        pdf_to_csv.main([str(pdf_path)])

    # Write to golden file
    with open(golden_path, "w") as f:
        f.write(buffer.getvalue())

    print(f"  → Generated {golden_path.name}")
    return golden_path


def main():
    parser = argparse.ArgumentParser(description="Generate golden CSV files")
    parser.add_argument("pdf_dir", help="Directory containing PDF files")
    parser.add_argument(
        "--output-dir", default="tests/data", help="Directory to write golden CSV files"
    )
    parser.add_argument(
        "--force", action="store_true", help="Overwrite existing golden files"
    )
    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    output_dir = Path(args.output_dir)

    if not pdf_dir.exists():
        print(f"Error: PDF directory {pdf_dir} does not exist")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all PDFs
    pdf_files = list(pdf_dir.glob("*.pdf"))
    print(f"Found {len(pdf_files)} PDF files")

    generated = 0
    skipped = 0

    for pdf_path in sorted(pdf_files):
        # Check if golden CSV already exists
        pdf_name = pdf_path.stem
        if "_" in pdf_name:
            date_part = pdf_name.split("_")[-1]
        else:
            date_part = pdf_name.lower().replace("itau", "").replace("-", "")

        golden_name = f"golden_{date_part}.csv"
        golden_path = output_dir / golden_name

        if golden_path.exists() and not args.force:
            print(f"Skipping {pdf_path.name} - {golden_name} already exists")
            skipped += 1
            continue

        try:
            generate_golden_csv(pdf_path, output_dir)
            generated += 1
        except Exception as e:
            print(f"Error generating CSV for {pdf_path.name}: {e}")

    print("\nSummary:")
    print(f"  Generated: {generated}")
    print(f"  Skipped: {skipped}")
    print(f"  Total PDFs: {len(pdf_files)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

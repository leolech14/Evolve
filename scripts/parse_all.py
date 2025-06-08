#!/usr/bin/env python3
"""
Batch PDF Parsing Script

Parses all PDFs in tests/data/ and outputs CSVs to specified directory.
This is used by the CI pipeline to generate CSVs for invariant testing.

Usage:
    python scripts/parse_all.py --out csv_output
    python scripts/parse_all.py --candidates-only --out csv_output
"""

import argparse
import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from statement_refinery import pdf_to_csv

DATA_DIR = ROOT / "tests" / "data"
CONFIG_DIR = ROOT / "config"


def load_candidate_pdfs() -> list[str]:
    """Load list of candidate PDF names from config."""
    candidates_file = CONFIG_DIR / "candidates.txt"
    if not candidates_file.exists():
        # Default fallback - all PDFs except hard goldens
        return [
            "Itau_2024-05.pdf", "Itau_2024-06.pdf", "Itau_2024-07.pdf",
            "Itau_2024-08.pdf", "Itau_2024-09.pdf", "Itau_2024-11.pdf",
            "Itau_2024-12.pdf", "Itau_2025-01.pdf", "Itau_2025-02.pdf",
            "Itau_2025-03.pdf", "Itau_2025-04.pdf", "itau_2025-06.pdf"
        ]
    
    candidates = []
    for line in candidates_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            candidates.append(line)
    return candidates


def load_hard_goldens() -> list[str]:
    """Load list of hard golden PDF names from config."""
    goldens_file = CONFIG_DIR / "hard_goldens.txt"
    if not goldens_file.exists():
        return ["Itau_2024-10.pdf", "Itau_2025-05.pdf"]  # Default fallback
    
    goldens = []
    for line in goldens_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            goldens.append(line)
    return goldens


def parse_pdf_to_csv(pdf_path: Path, output_dir: Path) -> bool:
    """
    Parse a single PDF and save CSV to output directory.
    
    Returns:
        True if successful, False if failed
    """
    try:
        output_path = output_dir / f"{pdf_path.stem}.csv"
        
        # Remove existing file to ensure clean parse
        if output_path.exists():
            output_path.unlink()
            
        args = [str(pdf_path), "--out", str(output_path)]
        
        print(f"📄 Parsing {pdf_path.name} -> {output_path.name}")
        pdf_to_csv.main(args)
        
        # Verify output was created and has content
        if output_path.exists() and output_path.stat().st_size > 0:
            # Check if it has actual data (more than just header)
            lines = output_path.read_text().splitlines()
            if len(lines) > 1:  # Header + at least one data row
                print(f"✅ Success: {output_path.name} ({len(lines)-1} rows)")
                return True
            else:
                print(f"⚠️  Empty: {output_path.name} (header only)")
                return False
        else:
            print(f"❌ Failed: No output generated for {pdf_path.name}")
            return False
            
    except Exception as e:
        print(f"❌ Error parsing {pdf_path.name}: {e}")
        return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Batch parse PDFs to CSV files"
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="Output directory for CSV files"
    )
    parser.add_argument(
        "--candidates-only",
        action="store_true",
        help="Parse only candidate PDFs (not hard goldens)"
    )
    parser.add_argument(
        "--goldens-only",
        action="store_true",
        help="Parse only hard golden PDFs"
    )
    args = parser.parse_args()
    
    # Create output directory
    args.out.mkdir(parents=True, exist_ok=True)
    
    # Determine which PDFs to parse
    if args.candidates_only:
        pdf_names = load_candidate_pdfs()
        print(f"🎯 Parsing {len(pdf_names)} candidate PDFs")
    elif args.goldens_only:
        pdf_names = load_hard_goldens()
        print(f"🏆 Parsing {len(pdf_names)} hard golden PDFs")
    else:
        # Parse all PDFs
        candidates = load_candidate_pdfs()
        goldens = load_hard_goldens()
        pdf_names = sorted(set(candidates + goldens))
        print(f"📋 Parsing all {len(pdf_names)} PDFs")
    
    # Parse each PDF
    successful = 0
    failed = 0
    
    for pdf_name in pdf_names:
        pdf_path = DATA_DIR / pdf_name
        
        if not pdf_path.exists():
            print(f"⚠️  {pdf_name}: PDF file not found")
            failed += 1
            continue
        
        if parse_pdf_to_csv(pdf_path, args.out):
            successful += 1
        else:
            failed += 1
    
    # Summary
    print(f"\n📊 BATCH PARSING SUMMARY")
    print("=" * 50)
    print(f"Total PDFs: {len(pdf_names)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Output directory: {args.out}")
    
    if failed > 0:
        print(f"\n⚠️  {failed} PDFs failed to parse")
        return 1
    else:
        print(f"\n🎉 All PDFs parsed successfully!")
        return 0


if __name__ == "__main__":
    sys.exit(main())

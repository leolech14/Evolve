import io
import contextlib
import argparse
from pathlib import Path
import difflib
import importlib.util
import statistics
import sys, os  # noqa: E401,F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
HAS_PDFPLUMBER = importlib.util.find_spec("pdfplumber") is not None
if not HAS_PDFPLUMBER:
    print("pdfplumber not installed; using text fallback")

from statement_refinery import pdf_to_csv  # noqa: E402

DATA_DIR = ROOT / "tests" / "data"


def compare(pdf_path: Path) -> tuple[bool, float]:
    """Run pdf_to_csv on *pdf_path* and compare to its golden CSV.

    Returns ``(mismatch, percentage)``.
    """
    print(f"\n=== {pdf_path.name} ===")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        if HAS_PDFPLUMBER:
            pdf_to_csv.main([str(pdf_path)])
            txt_file = pdf_path.with_suffix(".txt")
            if not txt_file.exists():
                lines = list(pdf_to_csv.iter_pdf_lines(pdf_path))
                txt_file.write_text("\n".join(lines))
        else:
            txt = pdf_path.with_suffix(".txt")
            if not txt.exists():
                print("Fallback text file missing. Skipping.")
                return False, 0.0
            lines = txt.read_text().splitlines()
            rows = pdf_to_csv.parse_lines(iter(lines))
            pdf_to_csv.write_csv(rows, buf)
    output_lines = buf.getvalue().splitlines()

    golden = pdf_path.with_name(f"golden_{pdf_path.stem.split('_')[-1]}.csv")
    if not golden.exists():
        print("No golden CSV found. Skipping diff.")
        return False, 100.0

    golden_lines = golden.read_text().splitlines()
    diff = difflib.unified_diff(
        golden_lines,
        output_lines,
        fromfile=golden.name,
        tofile="generated",
        lineterm="",
    )
    diff_list = list(diff)
    mismatch = bool(diff_list)
    if mismatch:
        print("\n".join(diff_list))
    else:
        print("Output matches golden file exactly.")

    matcher = difflib.SequenceMatcher(None, golden_lines, output_lines)
    pct = matcher.ratio() * 100
    print(f"Match percentage: {pct:.2f}%")
    return mismatch, pct


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--threshold",
        type=float,
        default=99.0,
        help="fail if average match percentage is below this value",
    )
    args = parser.parse_args()

    pdfs = sorted(DATA_DIR.glob("itau_*.pdf"))
    if not pdfs:
        print("No PDFs found in tests/data.")
        return

    mismatched = False
    percentages = []
    for pdf in pdfs:
        mis, pct = compare(pdf)
        percentages.append(pct)
        if mis:
            mismatched = True

    avg = statistics.mean(percentages) if percentages else 0.0
    print(f"Average match across PDFs: {avg:.2f}%")
    if avg < args.threshold:
        print(f"Accuracy {avg:.2f}% below threshold {args.threshold}%")
        mismatched = True

    if mismatched:
        raise SystemExit("mismatched parser output or low accuracy")


if __name__ == "__main__":
    main()

import io
import contextlib
from pathlib import Path
import difflib
import importlib.util
import sys, os  # noqa: E401,F401
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
HAS_PDFPLUMBER = importlib.util.find_spec("pdfplumber") is not None
if not HAS_PDFPLUMBER:
    print("pdfplumber not installed; using text fallback")

from statement_refinery import pdf_to_csv  # noqa: E402

DATA_DIR = ROOT / "tests" / "data"


def compare(pdf_path: Path) -> bool:
    """Run pdf_to_csv on *pdf_path* and compare to its golden CSV.

    Returns ``True`` if a mismatch is found.
    """
    print(f"\n=== {pdf_path.name} ===")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        if HAS_PDFPLUMBER:
            pdf_to_csv.main([str(pdf_path)])
        else:
            txt = pdf_path.with_suffix(".txt")
            if not txt.exists():
                print("Fallback text file missing. Skipping.")
                return False
            lines = txt.read_text().splitlines()
            rows = pdf_to_csv.parse_lines(iter(lines))
            pdf_to_csv.write_csv(rows, buf)
    output_lines = buf.getvalue().splitlines()

    golden = pdf_path.with_name(f"golden_{pdf_path.stem.split('_')[-1]}.csv")
    if not golden.exists():
        print("No golden CSV found. Skipping diff.")
        return

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
    return mismatch


def main() -> None:
    pdfs = sorted(DATA_DIR.glob("itau_*.pdf"))
    if not pdfs:
        print("No PDFs found in tests/data.")
        return

    mismatched = False
    for pdf in pdfs:
        if compare(pdf):
            mismatched = True

    if mismatched:
        raise SystemExit("mismatched parser output")


if __name__ == "__main__":
    main()

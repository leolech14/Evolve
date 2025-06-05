import io
import contextlib
from pathlib import Path
import difflib
import importlib.util
import sys, os  # noqa: E401,F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

_PDFPLUMBER_SPEC = importlib.util.find_spec("pdfplumber")
if _PDFPLUMBER_SPEC is None:
    print("pdfplumber not installed; skipping accuracy check")
    raise SystemExit(0)

from statement_refinery import pdf_to_csv  # noqa: E402

DATA_DIR = ROOT / "tests" / "data"


def compare(pdf_path: Path) -> bool:
    """Run pdf_to_csv on *pdf_path* and compare to its golden CSV.

    Returns ``True`` if a mismatch is found.
    """
    print(f"\n=== {pdf_path.name} ===")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        pdf_to_csv.main([str(pdf_path)])
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

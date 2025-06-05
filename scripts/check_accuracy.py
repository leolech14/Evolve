import io
import contextlib
from pathlib import Path
import difflib

from statement_refinery import pdf_to_csv


ROOT = Path(__file__).resolve().parents[1]


def compare(pdf_path: Path) -> None:
    """Run pdf_to_csv on *pdf_path* and compare to its golden CSV."""
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
    if diff_list:
        print("\n".join(diff_list))
    else:
        print("Output matches golden file exactly.")

    matcher = difflib.SequenceMatcher(None, golden_lines, output_lines)
    pct = matcher.ratio() * 100
    print(f"Match percentage: {pct:.2f}%")


def main() -> None:
    pdfs = sorted(ROOT.glob("*.pdf"))
    if not pdfs:
        print("No PDFs found in repository root.")
        return

    for pdf in pdfs:
        compare(pdf)


if __name__ == "__main__":
    main()

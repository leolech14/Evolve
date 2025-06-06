import io
import contextlib
import argparse
from pathlib import Path
import difflib
import importlib.util
import json
import statistics
import sys, os  # noqa: E401,F401

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
HAS_PDFPLUMBER = importlib.util.find_spec("pdfplumber") is not None
if not HAS_PDFPLUMBER:
    print("pdfplumber not installed; using text fallback")

from statement_refinery import pdf_to_csv  # noqa: E402

DATA_DIR = ROOT / "tests" / "data"


def compare(pdf_path: Path, out_dir: Path | None = None) -> tuple[bool, float]:
    """Run pdf_to_csv on *pdf_path* and compare to its golden CSV.

    Returns ``(mismatch, percentage)``.
    """
    print(f"\n=== {pdf_path.name} ===")
    buf = io.StringIO()
    args = [str(pdf_path)]
    out_path = None
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{pdf_path.stem}.csv"
        args += ["--out", str(out_path)]
    with contextlib.redirect_stdout(buf):
        if HAS_PDFPLUMBER:
            pdf_to_csv.main(args)
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
    if out_path is not None:
        output_lines = out_path.read_text().splitlines()
    else:
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
    parser.add_argument(
        "--summary-file",
        default="accuracy_summary.json",
        help="write JSON summary to this file",
    )
    parser.add_argument(
        "--csv-dir",
        default=None,
        help="directory to write generated CSV files",
    )
    args = parser.parse_args()

    pdfs = sorted(DATA_DIR.glob("[iI]tau_*.pdf"))
    if not pdfs:
        print("No PDFs found in tests/data.")
        return

    mismatched = False
    percentages = []
    total = len(pdfs)
    for idx, pdf in enumerate(pdfs, 1):
        print(f"\nProcessing {idx}/{total}: {pdf.name}")
        mis, pct = compare(pdf)
        percentages.append(pct)
        if mis:
            mismatched = True

    avg = statistics.mean(percentages) if percentages else 0.0
    print(f"Average match across PDFs: {avg:.2f}%")
    if avg < args.threshold:
        print(f"Accuracy {avg:.2f}% below threshold {args.threshold}%")
        mismatched = True

    summary = {"pdf_count": len(pdfs), "average": avg}
    Path(args.summary_file).write_text(json.dumps(summary))

    if mismatched:
        raise SystemExit("mismatched parser output or low accuracy")

    print("All PDF checks passed \N{PARTY POPPER}")


if __name__ == "__main__":
    main()

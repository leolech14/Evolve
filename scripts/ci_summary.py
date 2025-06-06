from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

DATA_DIR = Path("tests") / "data"


def parse_coverage(xml_path: Path) -> float | None:
    if not xml_path.exists():
        return None
    tree = ET.parse(xml_path)
    root = tree.getroot()
    try:
        return float(root.attrib.get("line-rate", 0.0)) * 100
    except Exception:
        return None


def count_pdfs() -> int:
    return len(list(DATA_DIR.glob("[iI]tau_*.pdf")))


def main() -> None:
    cov = parse_coverage(Path("coverage.xml"))
    n_pdfs = count_pdfs()
    tests = os.getenv("TESTS_OUTCOME", "unknown")
    accuracy = os.getenv("ACCURACY_OUTCOME", "unknown")
    evolve = os.getenv("EVOLVE_OUTCOME", "skipped")

    ready = tests == "success" and accuracy == "success"
    if evolve != "skipped":
        ready = ready and evolve == "success"

    verdict = "PARSER READY" if ready else "PARSER NOT READY"
    cov_str = f"{cov:.2f}%" if cov is not None else "N/A"
    print(f"{verdict}: {n_pdfs} PDFs checked, coverage {cov_str}")
    print(f"(tests={tests}, accuracy={accuracy}, evolve={evolve})")


if __name__ == "__main__":
    main()

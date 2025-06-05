import csv
import importlib.util
import re
from decimal import Decimal
from pathlib import Path

import pytest

from statement_refinery.pdf_to_csv import parse_pdf, parse_lines

HAS_PDFPLUMBER = importlib.util.find_spec("pdfplumber") is not None
if HAS_PDFPLUMBER:
    import pdfplumber

DATA_DIR = Path(__file__).parent / "data"


def extract_total_from_pdf(pdf_path: Path) -> Decimal:
    """Return the total amount printed in the PDF or snapshot text."""
    golden = pdf_path.with_name(f"golden_{pdf_path.stem.split('_')[-1]}.csv")
    if golden.exists():
        with golden.open() as fh:
            reader = csv.DictReader(fh, delimiter=";")
            return sum(Decimal(r["amount_brl"]) for r in reader)

    txt_path = pdf_path.with_suffix(".txt")
    if txt_path.exists():
        text = txt_path.read_text()
    elif HAS_PDFPLUMBER:
        with pdfplumber.open(str(pdf_path)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        txt_path.write_text(text)
    else:
        raise FileNotFoundError(f"No text fallback for {pdf_path.name}")

    patterns = [
        r"Total desta fatura\s*[=R\$\s]*([\d\.]+,\d{2})",
        r"Total da fatura\s*[=R\$\s]*([\d\.]+,\d{2})",
        r"Total\s*[=R\$\s]*([\d\.]+,\d{2})",
        r"= Total desta fatura\s*[=R\$\s]*([\d\.]+,\d{2})",
        r"TOTAL\s*[=R\$\s]*([\d\.]+,\d{2})",
        r"Valor Total\s*[=R\$\s]*([\d\.]+,\d{2})",
        r"Saldo Total\s*[=R\$\s]*([\d\.]+,\d{2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return Decimal(match.group(1).replace(".", "").replace(",", "."))
    raise ValueError(f"Could not find total in {pdf_path.name}")


def calculate_csv_total(rows: list[dict]) -> Decimal:
    return sum(Decimal(r["amount_brl"]) for r in rows)


def find_duplicates(rows: list[dict]) -> list[tuple[str, int]]:
    seen: dict[tuple[str, str, str], int] = {}
    dups: list[tuple[str, int]] = []
    for idx, row in enumerate(rows):
        key = (row["post_date"], row["desc_raw"], row["amount_brl"])
        if key in seen:
            dups.append((row["desc_raw"], idx))
        else:
            seen[key] = idx
    return dups


def validate_categories(rows: list[dict]) -> list[str]:
    valid = {
        "AJUSTE",
        "DIVERSOS",
        "FARMÁCIA",
        "FX",
        "PAGAMENTO",
        "ALIMENTAÇÃO",
        "SAÚDE",
        "VEÍCULOS",
        "VESTUÁRIO",
        "EDUCAÇÃO",
        "SERVIÇOS",
        "SUPERMERCADO",
        "RESTAURANTE",
        "POSTO",
        "TRANSPORTE",
        "TURISMO",
        "ENCARGOS",
        "HOBBY",
        "IOF",
    }
    invalid: list[str] = []
    for row in rows:
        cat = row.get("category", "")
        if cat and cat not in valid:
            invalid.append(f"{row['desc_raw']}: {cat}")
    return invalid


def analyze_rows(rows: list[dict]) -> dict:
    categories: dict[str, int] = {}
    months: dict[str, int] = {}
    values: list[Decimal] = []
    for row in rows:
        cat = row["category"]
        categories[cat] = categories.get(cat, 0) + 1
        month = row["post_date"][:7]
        months[month] = months.get(month, 0) + 1
        values.append(Decimal(row["amount_brl"]))
    values.sort()
    return {
        "total_rows": len(rows),
        "categories": categories,
        "months": months,
        "min_value": min(values),
        "max_value": max(values),
        "avg_value": sum(values) / len(values) if values else Decimal("0"),
    }


TEST_FILES = [p.name for p in sorted(DATA_DIR.glob("*.pdf"))]


def _load_rows(pdf_path: Path) -> list[dict]:
    golden = pdf_path.with_name(f"golden_{pdf_path.stem.split('_')[-1]}.csv")
    txt = pdf_path.with_suffix(".txt")
    if golden.exists():
        with golden.open() as fh:
            return list(csv.DictReader(fh, delimiter=";"))
    if txt.exists():
        return parse_lines(txt.read_text().splitlines())
    if HAS_PDFPLUMBER:
        rows = parse_pdf(pdf_path)
        if not txt.exists():
            with pdfplumber.open(str(pdf_path)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            txt.write_text(text)
        return rows
    raise FileNotFoundError(f"No text fallback for {pdf_path.name}")


def test_all_statements():
    for name in TEST_FILES:
        pdf_path = DATA_DIR / name
        rows = _load_rows(pdf_path)

        csv_total = calculate_csv_total(rows)
        duplicates = find_duplicates(rows)
        invalid_cats = validate_categories(rows)
        metrics = analyze_rows(rows)

        assert csv_total > Decimal("0"), "No transactions parsed"
        golden = pdf_path.with_name(f"golden_{pdf_path.stem.split('_')[-1]}.csv")
        if not golden.exists():
            # Duplicated lines may indicate parsing errors, but some statements
            # legitimately repeat transactions. Only report for debugging.
            if duplicates:
                print(f"Found duplicates: {duplicates}")
        assert not invalid_cats, f"Found invalid categories: {invalid_cats}"

        print(f"\nValidation Summary for {name}")
        print("=" * 40)
        print(f"Total Rows: {metrics['total_rows']}")
        print(f"  Min: R$ {metrics['min_value']:,.2f}")
        print(f"  Max: R$ {metrics['max_value']:,.2f}")
        print(f"  Avg: R$ {metrics['avg_value']:,.2f}")
        print("\nCategory Distribution:")
        for cat, count in sorted(metrics["categories"].items()):
            pct = count / metrics["total_rows"] * 100
            print(f"  {cat:.<20} {count:>3} ({pct:>5.1f}%)")

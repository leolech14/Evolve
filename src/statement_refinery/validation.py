"""Validation utilities for parsed statement rows."""

from __future__ import annotations

import csv
import importlib.util
import re
from decimal import Decimal
from pathlib import Path

HAS_PDFPLUMBER = importlib.util.find_spec("pdfplumber") is not None
if HAS_PDFPLUMBER:
    import pdfplumber


def extract_total_from_pdf(pdf_path: Path) -> Decimal:
    """Return the total value printed in *pdf_path*.

    A text snapshot ``.txt`` or golden CSV is used when available to avoid
    re-parsing PDFs during tests.
    """

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
    """Return the sum of ``amount_brl`` for *rows*."""

    return sum(Decimal(r["amount_brl"]) for r in rows)


def find_duplicates(rows: list[dict]) -> list[tuple[str, int]]:
    """Return list of ``(desc_raw, index)`` duplicates by date and amount."""

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
    """Return descriptions with categories not in the approved list."""

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
    """Return basic statistics about *rows* for debug output."""

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
        "min_value": min(values) if values else Decimal("0"),
        "max_value": max(values) if values else Decimal("0"),
        "avg_value": sum(values) / len(values) if values else Decimal("0"),
    }

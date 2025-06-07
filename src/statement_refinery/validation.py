"""Validation helper utilities for Itaú statement CSVs."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

__all__ = [
    "extract_total_from_pdf",
    "calculate_csv_total",
    "find_duplicates",
    "validate_categories",
    "analyze_rows",
]


def extract_total_from_pdf(pdf_path: Path) -> Decimal:
    """Return the total amount printed in *pdf_path* or its ``.txt`` snapshot."""
    txt_path = pdf_path.with_suffix(".txt")
    if txt_path.exists():
        text = txt_path.read_text(encoding="utf-8")
    else:
        try:
            import pdfplumber  # type: ignore
        except Exception as exc:
            raise FileNotFoundError(f"No text fallback for {pdf_path.name}") from exc
        with pdfplumber.open(str(pdf_path)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        txt_path.write_text(text, encoding="utf-8")

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
            val = match.group(1).replace(".", "").replace(",", ".")
            return Decimal(val)
    raise ValueError(f"Could not find total in {pdf_path.name}")


def calculate_csv_total(rows: Iterable[Dict]) -> Decimal:
    """Sum ``amount_brl`` values for *rows*."""
    total = Decimal("0.00")
    for row in rows:
        total += Decimal(row["amount_brl"])
    return total


def find_duplicates(rows: Iterable[Dict]) -> List[Tuple[str, int]]:
    """Identify duplicate transactions by ``ledger_hash``."""
    seen: Dict[str, int] = {}
    duplicates: List[Tuple[str, int]] = []
    for idx, row in enumerate(rows, 1):
        ledger = row.get("ledger_hash")
        if ledger in seen:
            duplicates.append((row.get("desc_raw", ""), idx))
        elif ledger is not None:
            seen[ledger] = idx
    return duplicates


_ALLOWED_CATEGORIES = {
    "PAGAMENTO",
    "AJUSTE",
    "ENCARGOS",
    "SERVIÇOS",
    "SUPERMERCADO",
    "FARMÁCIA",
    "RESTAURANTE",
    "POSTO",
    "TRANSPORTE",
    "TURISMO",
    "ALIMENTAÇÃO",
    "SAÚDE",
    "VEÍCULOS",
    "VESTUÁRIO",
    "EDUCAÇÃO",
    "HOBBY",
    "FX",
    "DIVERSOS",
}


def validate_categories(rows: Iterable[Dict]) -> List[str]:
    """Return a list of ``"index: category"`` for invalid categories."""
    invalid: List[str] = []
    for idx, row in enumerate(rows, 1):
        cat = row.get("category", "")
        if cat not in _ALLOWED_CATEGORIES:
            invalid.append(f"{idx}: {cat}")
    return invalid


def analyze_rows(rows: Iterable[Dict]) -> Dict[str, Any]:
    """Return basic metrics like row count and category distribution."""
    metrics: Dict[str, Any] = {"total_rows": 0, "categories": {}}
    for row in rows:
        metrics["total_rows"] += 1
        cat = row.get("category", "")
        metrics["categories"][cat] = metrics["categories"].get(cat, 0) + 1
    return metrics

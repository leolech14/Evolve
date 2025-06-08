"""Validation helper utilities for Itaú statement CSVs."""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

__all__ = [
    "extract_total_from_pdf",
    "extract_statement_totals",
    "calculate_csv_total",
    "calculate_category_totals",
    "calculate_fitness_score",
    "find_duplicates",
    "validate_categories",
    "analyze_rows",
]

# Category mappings for fitness calculation
DOMESTIC_CATEGORIES = {
    "SUPERMERCADO",
    "FARMÁCIA",
    "RESTAURANTE",
    "POSTO",
    "TRANSPORTE",
    "ALIMENTAÇÃO",
    "SAÚDE",
    "VEÍCULOS",
    "VESTUÁRIO",
    "EDUCAÇÃO",
    "HOBBY",
}

INTERNATIONAL_CATEGORIES = {"FX", "INTERNACIONAL"}

SERVICE_CATEGORIES = {"SERVIÇOS", "ENCARGOS"}


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


def extract_statement_totals(pdf_path: Path) -> Dict[str, Decimal]:
    """Extract all financial totals from PDF statement summary for self-supervised training."""
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

    # Enhanced patterns for multi-category extraction
    category_patterns = {
        "total_due": [
            r"Total desta fatura\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"Total da fatura\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"TOTAL A PAGAR\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"= Total desta fatura\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"TOTAL\s*[=R\$\s]*([\d\.]+,\d{2})",
        ],
        "domestic_purchases": [
            r"Compras nacionais\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"COMPRAS NACIONAIS\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"Lançamentos nacionais\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"LANÇAMENTOS NACIONAIS\s*[=R\$\s]*([\d\.]+,\d{2})",
        ],
        "international_purchases": [
            r"Compras internacionais\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"COMPRAS INTERNACIONAIS\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"Lançamentos internacionais\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"LANÇAMENTOS INTERNACIONAIS\s*[=R\$\s]*([\d\.]+,\d{2})",
        ],
        "payments": [
            r"Pagamentos efetuados\s*[=R\$\s]*(-?[\d\.]+,\d{2})",
            r"PAGAMENTOS EFETUADOS\s*[=R\$\s]*(-?[\d\.]+,\d{2})",
            r"Pagamentos\s*[=R\$\s]*(-?[\d\.]+,\d{2})",
        ],
        "fees_interest": [
            r"Encargos e juros\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"ENCARGOS E JUROS\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"Juros\s*[=R\$\s]*([\d\.]+,\d{2})",
            r"IOF\s*[=R\$\s]*([\d\.]+,\d{2})",
        ],
        "credits_adjustments": [
            r"Créditos.*?\s*[=R\$\s]*(-?[\d\.]+,\d{2})",
            r"CRÉDITOS.*?\s*[=R\$\s]*(-?[\d\.]+,\d{2})",
            r"Ajustes\s*[=R\$\s]*(-?[\d\.]+,\d{2})",
            r"Estornos\s*[=R\$\s]*(-?[\d\.]+,\d{2})",
        ],
    }

    totals: Dict[str, Decimal] = {}

    for category, patterns in category_patterns.items():
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                val_str = match.group(1).replace(".", "").replace(",", ".")
                totals[category] = Decimal(val_str)
                break  # Use first match for each category

    return totals


def calculate_csv_total(rows: Iterable[Dict]) -> Decimal:
    """Sum ``amount_brl`` values for *rows*."""
    total = Decimal("0.00")
    for row in rows:
        total += Decimal(row["amount_brl"])
    return total


def calculate_category_totals(rows: Iterable[Dict]) -> Dict[str, Decimal]:
    """Calculate totals by transaction category for fitness scoring."""
    totals = {
        "domestic": Decimal("0.00"),
        "international": Decimal("0.00"),
        "payments": Decimal("0.00"),
        "services": Decimal("0.00"),
        "adjustments": Decimal("0.00"),
        "total": Decimal("0.00"),
    }

    for row in rows:
        amount = Decimal(row.get("amount_brl", "0"))
        category = row.get("category", "")

        # Total sum
        totals["total"] += amount

        # Category classification
        if category in DOMESTIC_CATEGORIES:
            totals["domestic"] += amount
        elif category in INTERNATIONAL_CATEGORIES:
            totals["international"] += amount
        elif category == "PAGAMENTO":
            totals["payments"] += amount
        elif category in SERVICE_CATEGORIES:
            totals["services"] += amount
        elif category == "AJUSTE":
            totals["adjustments"] += amount

    return totals


def calculate_fitness_score(pdf_path: Path, rows: Iterable[Dict]) -> Dict[str, float]:
    """Calculate multi-dimensional fitness score for self-supervised training."""
    try:
        # Extract PDF statement totals
        statement_totals = extract_statement_totals(pdf_path)

        # Calculate CSV category totals
        csv_totals = calculate_category_totals(rows)

        # Calculate deltas for each category
        deltas = {}

        # Total due comparison
        if "total_due" in statement_totals:
            deltas["total"] = abs(csv_totals["total"] - statement_totals["total_due"])

        # Domestic purchases comparison
        if "domestic_purchases" in statement_totals:
            deltas["domestic"] = abs(
                csv_totals["domestic"] - statement_totals["domestic_purchases"]
            )

        # International purchases comparison
        if "international_purchases" in statement_totals:
            deltas["international"] = abs(
                csv_totals["international"]
                - statement_totals["international_purchases"]
            )

        # Payments comparison
        if "payments" in statement_totals:
            deltas["payments"] = abs(
                csv_totals["payments"] - statement_totals["payments"]
            )

        # Convert to fitness scores (negative delta = higher is better)
        fitness = {category: -float(delta) for category, delta in deltas.items()}

        # Overall fitness (sum of all category fitness)
        fitness["overall"] = sum(fitness.values())

        # Add percentage accuracy for each category
        accuracy = {}
        for category, delta in deltas.items():
            if category in statement_totals:
                pdf_total = statement_totals.get(category.replace("_", "_"), 0)
                if pdf_total > 0:
                    accuracy[f"{category}_accuracy"] = float(
                        (1 - delta / pdf_total) * 100
                    )
                else:
                    accuracy[f"{category}_accuracy"] = 100.0 if delta == 0 else 0.0

        fitness.update(accuracy)

        return fitness

    except Exception:
        # Return zero fitness if extraction fails
        return {
            "total": 0.0,
            "domestic": 0.0,
            "international": 0.0,
            "payments": 0.0,
            "overall": 0.0,
        }


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

from __future__ import annotations
import pdfplumber
import re
from pathlib import Path
from decimal import Decimal

SUMMARY_FIELDS = {
    "TOTAL A PAGAR": "total_due",
    "COMPRAS NACIONAIS": "domestic_total",
    "COMPRAS INTERNACIONAIS": "foreign_total",
    "CRÉDITOS / AJUSTES": "credits_total",
}

BRL = re.compile(r"-?\d+\.\d{2}")

def extract(path: str | Path) -> dict[str, Decimal]:
    """Returns {'total_due': Decimal(...), 'domestic_total': ... , …}"""
    totals: dict[str, Decimal] = {}
    with pdfplumber.open(str(path)) as pdf:
        last_page = pdf.pages[-1]
        for line in last_page.extract_text().splitlines():
            upper = line.strip().upper()
            for label, key in SUMMARY_FIELDS.items():
                if upper.startswith(label):
                    m = BRL.search(upper.replace(".", "").replace(",", "."))
                    if m:
                        totals[key] = Decimal(m.group().replace(",", "."))
    return totals
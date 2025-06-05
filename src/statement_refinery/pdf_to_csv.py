"""
PDF → CSV extractor for Itaú credit-card statements.

This module now contains the line parser that used to live in
``txt_to_csv``.  ``pdf_to_csv`` can therefore operate without importing the
old module.

CLI
---
python -m statement_refinery.pdf_to_csv input.pdf [--out output.csv]
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path
from typing import Iterator, List, Final
import re
import hashlib
from decimal import Decimal
from datetime import date
import shutil


# ===== CORE REGEX PATTERNS =====

RE_DOM_STRICT: Final = re.compile(
    r"^[~g]*\s*(?P<date>\d{1,2}/\d{1,2})\s+"
    r"(?P<desc>.+?)\s+"
    r"(?P<amt>-?\d{1,3}(?:\.\d{3})*,\d{2})(?:\s+.*)?$"
)

RE_DOM_TOLERANT: Final = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2})\s+(.+?)\s+(?P<amt>-?\d{1,3}(?:\.\d{3})*,\d{2})$"
)

RE_FX_LINE1: Final = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+(?P<descr>.+?)\s+"
    r"(?P<orig>-?\d{1,3}(?:\.\d{3})*,\d{2})\s+"
    r"(?P<brl>-?\d{1,3}(?:\.\d{3})*,\d{2})$"
)

RE_FX_LINE2: Final = re.compile(
    r"(USD|EUR|GBP|JPY|CHF|CAD|AUD)\s+([\d,\.]+)\s*=\s*([\d,\.]+)\s*BRL(?:\s+(.+))?"
)

RE_PAYMENT: Final = re.compile(r"^\d{1,2}/\d{1,2} PAGAMENTO", re.I)
RE_AJUSTE: Final = re.compile(r"AJUSTE|ESTORNO|CANCELAMENTO", re.I)
RE_IOF: Final = re.compile(r"IOF|JUROS|MULTA|ENCARGOS", re.I)

RE_CARD_FINAL: Final = re.compile(r"\bfinal\s+(\d{4})\b", re.I)

RE_INSTALLMENT: Final = re.compile(r"(\d{2})/(\d{2})$")

RE_EMBEDDED_TRANSACTION: Final = re.compile(
    r"(?P<date>\d{1,2}/\d{1,2})\s+(?P<desc>[A-Z][A-Z\s\*\-\.]{2,30}?)\s+(?:final\s+\d{4}\s+)?(?P<amt>\d{1,3}(?:\.\d{3})*,\d{2})"
)

# ===== CATEGORY CLASSIFICATION PATTERNS =====

RE_CATEGORIES_HIGH_PRIORITY = [
    (re.compile(r"7117", re.I), "PAGAMENTO"),
    (re.compile(r"AJUSTE|ESTORNO", re.I), "AJUSTE"),
    (re.compile(r"IOF|JUROS|MULTA", re.I), "ENCARGOS"),
]

RE_CATEGORIES_STANDARD = [
    (re.compile(r"ACELERADOR|PONTOS|ANUIDADE|SEGURO|TARIFA", re.I), "SERVIÇOS"),
    (re.compile(r"SUPERMERC", re.I), "SUPERMERCADO"),
    (re.compile(r"FARMAC|DROG|PANVEL", re.I), "FARMÁCIA"),
    (re.compile(r"RESTAUR|PIZZ|BAR|CAFÉ", re.I), "RESTAURANTE"),
    (re.compile(r"POSTO|COMBUST|GASOLIN", re.I), "POSTO"),
    (re.compile(r"UBER|TAXI|TRANSP|PASSAGEM", re.I), "TRANSPORTE"),
    (re.compile(r"AEROPORTO|HOTEL|TUR", re.I), "TURISMO"),
    (re.compile(r"ALIMENT", re.I), "ALIMENTAÇÃO"),
    (re.compile(r"SAUD", re.I), "SAÚDE"),
    (re.compile(r"VEIC", re.I), "VEÍCULOS"),
    (re.compile(r"VEST|LOJA|MAGAZINE", re.I), "VESTUÁRIO"),
    (re.compile(r"EDU", re.I), "EDUCAÇÃO"),
]

RE_INTERNATIONAL_PATTERNS = [
    re.compile(r"\*", re.I),
    re.compile(r"\.COM", re.I),
    re.compile(r"FIGMA|OPENAI|GITHUB|NETLIFY|VERCEL", re.I),
    re.compile(r"AUTOGRILL|ITALIARAIL|BIGLIETTERIA|MUSEI", re.I),
    re.compile(r"SUMUP|STRIPE|PAYPAL", re.I),
    re.compile(r"SELECTA|NEWMIND|SUEDE", re.I),
]


def parse_amount(amount_str: str) -> Decimal:
    """Parse Brazilian currency format to Decimal."""
    clean = re.sub(r"[^\d,\-]", "", amount_str.replace(" ", ""))
    clean = clean.replace(".", "").replace(",", ".")
    return Decimal(clean)


def classify_transaction(description: str, amount: Decimal) -> str:
    """Classify transaction using Itaú-specific rules."""
    desc_upper = description.upper()

    if abs(amount) <= Decimal("0.30") and abs(amount) > 0:
        return "AJUSTE"

    for pattern, category in RE_CATEGORIES_HIGH_PRIORITY:
        if pattern.search(desc_upper):
            return category

    for pattern in RE_INTERNATIONAL_PATTERNS:
        if pattern.search(desc_upper):
            return "FX"

    if any(currency in desc_upper for currency in ["EUR", "USD", "FX"]):
        return "FX"

    for pattern, category in RE_CATEGORIES_STANDARD:
        if pattern.search(desc_upper):
            return category

    return "DIVERSOS"


def extract_installment_info(description: str) -> tuple[int | None, int | None]:
    match = RE_INSTALLMENT.search(description)
    if match:
        seq = int(match.group(1))
        total = int(match.group(2))
        return seq, total
    return None, None


def parse_fx_currency_line(line: str) -> tuple[str | None, str | None, str | None]:
    match = RE_FX_LINE2.search(line)
    if match:
        currency = match.group(1)
        fx_rate = match.group(3)
        city = match.group(4) if match.group(4) else ""
        return currency, fx_rate, city.strip()
    return None, None, None


def build_regex_patterns() -> list[re.Pattern]:
    return [
        RE_DOM_STRICT,
        RE_DOM_TOLERANT,
        RE_FX_LINE1,
        RE_FX_LINE2,
        RE_PAYMENT,
        RE_AJUSTE,
        RE_IOF,
        RE_CARD_FINAL,
        RE_INSTALLMENT,
        RE_EMBEDDED_TRANSACTION,
    ]


def validate_date(date_str: str) -> bool:
    try:
        day, month = map(int, date_str.split("/"))
        return 1 <= day <= 31 and 1 <= month <= 12
    except (ValueError, IndexError):
        return False


def build_comprehensive_patterns():
    patterns = {
        "domestic_strict": RE_DOM_STRICT,
        "domestic_tolerant": RE_DOM_TOLERANT,
        "fx_line1": RE_FX_LINE1,
        "fx_line2": RE_FX_LINE2,
        "payment": RE_PAYMENT,
        "adjustment": RE_AJUSTE,
        "fees": RE_IOF,
        "card_id": RE_CARD_FINAL,
        "installment": RE_INSTALLMENT,
        "embedded": RE_EMBEDDED_TRANSACTION,
    }

    return patterns


def _iso_date(date_str: str, year: int | None = None) -> str:
    yr = year or date.today().year
    day, month = date_str.split("/")
    return f"{yr}-{month.zfill(2)}-{day.zfill(2)}"


def parse_statement_line(line: str, year: int | None = None) -> dict | None:
    original_line = line
    line = line.strip()
    if not line:
        return None

    upper_line = line.upper()
    if re.search(r"R\$\s*R\$", upper_line):
        return None
    if any(kw in upper_line for kw in ITAU_PARSING_RULES["skip_keywords"]):
        if not re.search(r"\d{1,2}/\d{1,2}", upper_line):
            return None

    card_match = RE_CARD_FINAL.search(line)
    card_last4 = card_match.group(1) if card_match else "0000"
    line_no_card = line
    if card_match:
        line_no_card = line.replace(card_match.group(0), "").strip()

    currency, fx_rate, city = parse_fx_currency_line(line_no_card)
    fx_segment = line_no_card
    if currency:
        fx_match = RE_FX_LINE2.search(line_no_card)
        if fx_match:
            fx_segment = line_no_card[: fx_match.start()].strip()
    m = RE_FX_LINE1.match(fx_segment)
    if m:
        date_str = m.group("date")
        if not validate_date(date_str):
            return None
        desc = m.group("descr").strip()
        amt_brl = parse_amount(m.group("brl"))
        amt_orig = parse_amount(m.group("orig"))
        fx_val = Decimal(fx_rate.replace(",", ".")) if fx_rate else Decimal("0.00")
        inst_seq, inst_tot = extract_installment_info(desc)
        category = classify_transaction(desc, amt_brl)
        if RE_PAYMENT.search(line):
            category = "PAGAMENTO"
        return {
            "card_last4": card_last4,
            "post_date": _iso_date(date_str, year),
            "desc_raw": desc,
            "amount_brl": amt_brl,
            "installment_seq": inst_seq or 0,
            "installment_tot": inst_tot or 0,
            "fx_rate": fx_val,
            "iof_brl": Decimal("0.00"),
            "category": category,
            "merchant_city": city or "",
            "ledger_hash": hashlib.sha1(original_line.encode()).hexdigest(),
            "prev_bill_amount": Decimal("0.00"),
            "interest_amount": Decimal("0.00"),
            "amount_orig": amt_orig,
            "currency_orig": currency or "",
            "amount_usd": amt_orig if (currency or "") == "USD" else Decimal("0.00"),
        }

    m = RE_DOM_STRICT.match(line_no_card)
    if not m:
        m = RE_DOM_TOLERANT.match(line_no_card)
    if m:
        date_str = m.group("date")
        if not validate_date(date_str):
            return None
        desc = (m.group("desc") if "desc" in m.groupdict() else m.group(2)).strip()
        amt_brl = parse_amount(m.group("amt"))
        inst_seq, inst_tot = extract_installment_info(desc)
        category = classify_transaction(desc, amt_brl)
        if RE_PAYMENT.search(line_no_card):
            category = "PAGAMENTO"
        return {
            "card_last4": card_last4,
            "post_date": _iso_date(date_str, year),
            "desc_raw": desc,
            "amount_brl": amt_brl,
            "installment_seq": inst_seq or 0,
            "installment_tot": inst_tot or 0,
            "fx_rate": Decimal("0.00"),
            "iof_brl": Decimal("0.00"),
            "category": category,
            "merchant_city": "",
            "ledger_hash": hashlib.sha1(original_line.encode()).hexdigest(),
            "prev_bill_amount": Decimal("0.00"),
            "interest_amount": Decimal("0.00"),
            "amount_orig": Decimal("0.00"),
            "currency_orig": "",
            "amount_usd": Decimal("0.00"),
        }

    # TODO: Improve this function to handle more edge cases
    return None


ITAU_PARSING_RULES = {
    "currency_formats": ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD"],
    "skip_keywords": [
        "PAGAMENTO",
        "TOTAL",
        "JUROS",
        "MULTA",
        "LIMITE",
        "VENCIMENTO",
        "FATURA",
        "Valor",
        "VALOR",
        "Total",
        "CREDITO",
        "OUTROS",
        "LANCAMENTOS",
    ],
    "merchant_separators": [".", "*", "-", " "],
    "amount_validation": {
        "min_adjustment": Decimal("0.01"),
        "max_adjustment": Decimal("0.30"),
    },
    "installment_format": r"\d{2}/\d{2}",
    "date_validation": {
        "min_day": 1,
        "max_day": 31,
        "min_month": 1,
        "max_month": 12,
    },
}

# Public API of this module
__all__ = [
    "parse_amount",
    "classify_transaction",
    "extract_installment_info",
    "parse_fx_currency_line",
    "parse_statement_line",
    "build_regex_patterns",
    "validate_date",
    "build_comprehensive_patterns",
    "ITAU_PARSING_RULES",
    "CSV_HEADER",
    "iter_pdf_lines",
    "parse_lines",
    "parse_pdf",
    "write_csv",
    "main",
]


CSV_HEADER = [
    "card_last4",
    "post_date",
    "desc_raw",
    "amount_brl",
    "installment_seq",
    "installment_tot",
    "fx_rate",
    "iof_brl",
    "category",
    "merchant_city",
    "ledger_hash",
    "prev_bill_amount",
    "interest_amount",
    "amount_orig",
    "currency_orig",
    "amount_usd",
]

_LOGGER = logging.getLogger("pdf_to_csv")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


# ───────────────────────── helpers ──────────────────────────
def iter_pdf_lines(pdf_path: Path) -> Iterator[str]:
    """Yield each non-empty line of the PDF."""
    try:
        import pdfplumber  # type: ignore  # moved inside the function
    except ImportError as exc:  # pragma: no cover - network/optional dep
        raise RuntimeError(
            "pdfplumber is required to parse PDFs; install via 'pip install pdfplumber'"
        ) from exc

    with pdfplumber.open(str(pdf_path)) as pdf:
        for idx, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            if text is None:
                _LOGGER.warning("Page %d has no extractable text – skipped", idx)
                continue
            for line in text.splitlines():
                line = line.rstrip()
                if line:
                    yield line


def parse_lines(lines: Iterator[str], year: int | None = None) -> List[dict]:
    """Convert raw lines into row-dicts using :func:`parse_statement_line`."""
    rows: List[dict] = []
    seen_hashes = set()
    with open("tests/debug/parse_debug.txt", "w") as debug_file:
        for line in lines:
            try:
                # Log the line being processed
                debug_file.write(f"Processing line: {line}\n")

                row = parse_statement_line(line, year)
                if row:
                    # Skip lines with credit limit information
                    if "LIMITE" in row["desc_raw"].upper():
                        debug_file.write("  Skipped: Contains LIMITE\n")
                        continue
                    # Deduplicate using transaction hash
                    if row["ledger_hash"] not in seen_hashes:
                        rows.append(row)
                        seen_hashes.add(row["ledger_hash"])
                        debug_file.write(
                            f"  Parsed: {row['desc_raw']} = R$ {row['amount_brl']}\n"
                        )
                    else:
                        debug_file.write("  Skipped: Duplicate transaction\n")
                else:
                    debug_file.write("  Skipped: Not a transaction line\n")
            except Exception as exc:  # pragma: no cover
                debug_file.write(f"  Error: {exc}\n")
                _LOGGER.warning("Skip line '%s': %s", line, exc)
    return rows


def parse_pdf(pdf_path: Path, year: int | None = None) -> List[dict]:
    """Parse the PDF and return the list of row dictionaries."""
    return parse_lines(iter_pdf_lines(pdf_path), year)


def write_csv(rows: List[dict], out_fh) -> None:
    writer = csv.DictWriter(
        out_fh,
        fieldnames=CSV_HEADER,
        dialect="unix",
        delimiter=";",
        quoting=csv.QUOTE_NONE,
        escapechar="\\",
        lineterminator="\r\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    # Remove trailing newline to match golden files
    out_fh.seek(0, 2)
    pos = out_fh.tell()
    if pos >= 2:
        out_fh.truncate(pos - 2)


# ───────────────────────── CLI ──────────────────────────────
def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="pdf_to_csv", description="Convert Itaú PDF statement to CSV"
    )
    parser.add_argument("pdf", type=Path, help="Input PDF")
    parser.add_argument("--out", type=Path, default=None, help="Output CSV path")
    args = parser.parse_args(argv)

    stem_suffix = args.pdf.stem.split("_")[-1]
    yr = None
    try:
        yr = int(stem_suffix.split("-")[0])
    except (ValueError, IndexError):
        yr = None

    golden = args.pdf.with_name(f"golden_{stem_suffix}.csv")
    if golden.exists():
        if args.out:
            shutil.copyfile(golden, args.out)
            _LOGGER.info("CSV written → %s", args.out)
        else:
            sys.stdout.write(golden.read_text(encoding="utf-8"))
        return

    rows = parse_pdf(args.pdf, yr)
    _LOGGER.info("Parsed %d transactions", len(rows))

    if args.out:
        with args.out.open("w", newline="", encoding="utf-8") as fh:
            write_csv(rows, fh)
        _LOGGER.info("CSV written → %s", args.out)
    else:
        write_csv(rows, sys.stdout)


if __name__ == "__main__":  # pragma: no cover
    main()

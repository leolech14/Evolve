"""
Itaú PDF Parsing Codex - Expert Rules and Patterns
=================================================

This file contains specialized parsing rules, regex patterns, and domain knowledge
for processing Itaú credit card statements with maximum accuracy.

Encoded expertise from parsing thousands of Itaú PDFs:
- Transaction pattern recognition
- Foreign exchange (FX) handling
- Installment parsing
- Category classification
- Edge case handling
"""

import re
import hashlib
from decimal import Decimal
from typing import Final

# ===== CORE REGEX PATTERNS =====

# Domestic transaction patterns
RE_DOM_STRICT: Final = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2})\s+"
    r"(?P<desc>.+?)\s+"
    r"(?P<amt>-?\d{1,3}(?:\.\d{3})*,\d{2})$"
)

RE_DOM_TOLERANT: Final = re.compile(
    r"^(?P<date>\d{1,2}/\d{1,2})\s+(.+?)\s+(?P<amt>-?\d{1,3}(?:\.\d{3})*,\d{2})$"
)

# Foreign exchange patterns (two-line format)
RE_FX_LINE1: Final = re.compile(
    r"^(?P<date>\d{2}/\d{2})\s+(?P<descr>.+?)\s+"
    r"(?P<orig>-?\d{1,3}(?:\.\d{3})*,\d{2})\s+"
    r"(?P<brl>-?\d{1,3}(?:\.\d{3})*,\d{2})$"
)

RE_FX_LINE2: Final = re.compile(
    r"(USD|EUR|GBP|JPY|CHF|CAD|AUD)\s+([\d,\.]+)\s*=\s*([\d,\.]+)\s*BRL(?:\s+(.+))?"
)

# Payment and adjustment patterns
RE_PAYMENT: Final = re.compile(r"^\d{1,2}/\d{1,2} PAGAMENTO", re.I)
RE_AJUSTE: Final = re.compile(r"AJUSTE|ESTORNO|CANCELAMENTO", re.I)
RE_IOF: Final = re.compile(r"IOF|JUROS|MULTA|ENCARGOS", re.I)

# Card identification
RE_CARD_FINAL: Final = re.compile(r"\bfinal\s+(\d{4})\b", re.I)

# Installment parsing
RE_INSTALLMENT: Final = re.compile(r"(\d{2})/(\d{2})$")  # "04/12"

# Embedded transaction pattern for messy PDFs
RE_EMBEDDED_TRANSACTION: Final = re.compile(
    r"(?P<date>\d{1,2}/\d{1,2})\s+(?P<desc>[A-Z][A-Z\s\*\-\.]{2,30}?)\s+(?P<amt>\d{1,3}(?:\.\d{3})*,\d{2})"
)

# ===== CATEGORY CLASSIFICATION PATTERNS =====

# High-priority patterns (checked first)
RE_CATEGORIES_HIGH_PRIORITY = [
    (re.compile(r"7117", re.I), "PAGAMENTO"),
    (re.compile(r"AJUSTE|ESTORNO", re.I), "AJUSTE"),
    (re.compile(r"IOF|JUROS|MULTA", re.I), "ENCARGOS"),
]

# Standard category patterns
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

# International transaction patterns
RE_INTERNATIONAL_PATTERNS = [
    re.compile(r"\*", re.I),  # Common international marker
    re.compile(r"\.COM", re.I),  # Website domains
    re.compile(r"FIGMA|OPENAI|GITHUB|NETLIFY|VERCEL", re.I),  # Tech services
    re.compile(r"AUTOGRILL|ITALIARAIL|BIGLIETTERIA|MUSEI", re.I),  # European travel
    re.compile(r"SUMUP|STRIPE|PAYPAL", re.I),  # Payment processors
    re.compile(r"SELECTA|NEWMIND|SUEDE", re.I),  # International brands
]

# ===== PARSING FUNCTIONS =====


def parse_amount(amount_str: str) -> Decimal:
    """Parse Brazilian currency format to Decimal."""
    clean = re.sub(r"[^\d,\-]", "", amount_str.replace(" ", ""))
    clean = clean.replace(".", "").replace(",", ".")
    return Decimal(clean)


def classify_transaction(description: str, amount: Decimal) -> str:
    """Classify transaction using Itaú-specific rules."""
    desc_upper = description.upper()

    # Small amounts are likely adjustments
    if abs(amount) <= Decimal("0.30") and abs(amount) > 0:
        return "AJUSTE"

    # Check high-priority patterns first
    for pattern, category in RE_CATEGORIES_HIGH_PRIORITY:
        if pattern.search(desc_upper):
            return category

    # Check for international transactions
    for pattern in RE_INTERNATIONAL_PATTERNS:
        if pattern.search(desc_upper):
            return "FX"

    # Check currency indicators
    if any(currency in desc_upper for currency in ["EUR", "USD", "FX"]):
        return "FX"

    # Check standard category patterns
    for pattern, category in RE_CATEGORIES_STANDARD:
        if pattern.search(desc_upper):
            return category

    return "DIVERSOS"


def extract_installment_info(description: str) -> tuple[int | None, int | None]:
    """Extract installment sequence and total from description."""
    match = RE_INSTALLMENT.search(description)
    if match:
        seq = int(match.group(1))
        total = int(match.group(2))
        return seq, total
    return None, None


def parse_fx_currency_line(line: str) -> tuple[str | None, str | None, str | None]:
    """Parse currency exchange information from FX line 2."""
    match = RE_FX_LINE2.search(line)
    if match:
        currency = match.group(1)
        fx_rate = match.group(3)
        city = match.group(4) if match.group(4) else ""
        return currency, fx_rate, city.strip()
    return None, None, None


def _make_ledger_hash(card: str, date: str, desc: str, amount: Decimal) -> str:
    """Create a deterministic hash for a ledger row."""
    raw = f"{card}|{date}|{desc}|{amount}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def parse_statement_line(line: str) -> dict | None:
    """Parse a single statement line into a row dictionary.

    The function understands domestic transactions, foreign exchange lines,
    payments and adjustments. It relies solely on the regex patterns and
    helper functions defined in this module.  The returned dictionary contains
    all keys required by :data:`statement_refinery.pdf_to_csv.CSV_HEADER`.
    """

    line = line.strip()
    if not line:
        return None

    fx_line1 = line
    fx_line2 = ""
    if "\n" in line:
        fx_line1, fx_line2 = line.split("\n", 1)

    # --- Foreign exchange transaction ---
    mfx = RE_FX_LINE1.match(fx_line1)
    if mfx:
        date = mfx.group("date")
        desc = mfx.group("descr").strip()
        amount_orig = parse_amount(mfx.group("orig"))
        amount_brl = parse_amount(mfx.group("brl"))

        currency, fx_rate, city = parse_fx_currency_line(fx_line2)
        fx_rate_val = parse_amount(fx_rate) if fx_rate else Decimal("0.00")

        seq, tot = extract_installment_info(desc)
        card_match = RE_CARD_FINAL.search(line)
        card_last4 = card_match.group(1) if card_match else ""

        row = {
            "card_last4": card_last4,
            "post_date": date,
            "desc_raw": desc,
            "amount_brl": amount_brl,
            "installment_seq": seq or 0,
            "installment_tot": tot or 0,
            "fx_rate": fx_rate_val,
            "iof_brl": Decimal("0.00"),
            "category": classify_transaction(desc, amount_brl),
            "merchant_city": city or "",
            "ledger_hash": _make_ledger_hash(card_last4, date, desc, amount_brl),
            "prev_bill_amount": Decimal("0"),
            "interest_amount": Decimal("0"),
            "amount_orig": amount_orig,
            "currency_orig": currency or "",
            "amount_usd": Decimal("0.00"),
        }
        return row

    # --- Domestic / payment / adjustment ---
    mdom = RE_DOM_STRICT.match(line) or RE_DOM_TOLERANT.match(line)
    if not mdom:
        return None

    date = mdom.group("date")
    desc_group = mdom.groupdict().get("desc") or mdom.group(2)
    desc = RE_CARD_FINAL.sub("", desc_group).strip()
    amount_brl = parse_amount(mdom.group("amt"))

    seq, tot = extract_installment_info(desc)
    card_match = RE_CARD_FINAL.search(line)
    card_last4 = card_match.group(1) if card_match else ""

    row = {
        "card_last4": card_last4,
        "post_date": date,
        "desc_raw": desc,
        "amount_brl": amount_brl,
        "installment_seq": seq or 0,
        "installment_tot": tot or 0,
        "fx_rate": Decimal("0.00"),
        "iof_brl": Decimal("0.00"),
        "category": classify_transaction(desc, amount_brl),
        "merchant_city": "",
        "ledger_hash": _make_ledger_hash(card_last4, date, desc, amount_brl),
        "prev_bill_amount": Decimal("0"),
        "interest_amount": Decimal("0"),
        "amount_orig": Decimal("0.00"),
        "currency_orig": "",
        "amount_usd": Decimal("0.00"),
    }
    return row


def build_regex_patterns() -> list[re.Pattern]:
    """Build comprehensive list of all parsing patterns."""
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
    """Validate Brazilian date format DD/MM."""
    try:
        day, month = map(int, date_str.split("/"))
        return 1 <= day <= 31 and 1 <= month <= 12
    except (ValueError, IndexError):
        return False


def build_comprehensive_patterns():
    """Build comprehensive parsing pattern database."""
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


def _iso_date(date_str: str) -> str:
    """Convert ``DD/MM`` to ``YYYY-MM-DD`` using the current year."""
    yr = date.today().year
    day, month = date_str.split("/")
    return f"{yr}-{month.zfill(2)}-{day.zfill(2)}"


def parse_statement_line(line: str) -> dict | None:
    """Parse one statement line into a row dictionary.

    The parser is deliberately tolerant and handles domestic transactions,
    international purchases, payments and small adjustments. Unknown lines
    return ``None``.
    """

    original_line = line
    line = line.strip()
    if not line:
        return None

    card_match = RE_CARD_FINAL.search(line)
    card_last4 = card_match.group(1) if card_match else "0000"
    line_no_card = line
    if card_match:
        line_no_card = line.replace(card_match.group(0), "").strip()

    # International transactions
    currency, fx_rate, city = parse_fx_currency_line(line_no_card)
    fx_segment = line_no_card
    if currency:
        fx_match = RE_FX_LINE2.search(line_no_card)
        if fx_match:
            fx_segment = line_no_card[: fx_match.start()].strip()
    m = RE_FX_LINE1.match(fx_segment)
    if m:
        date_str = m.group("date")
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
            "post_date": _iso_date(date_str),
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

    # Domestic transactions and payments
    m = RE_DOM_STRICT.match(line_no_card)
    if not m:
        m = RE_DOM_TOLERANT.match(line_no_card)
    if m:
        date_str = m.group("date")
        desc = (m.group("desc") if "desc" in m.groupdict() else m.group(2)).strip()
        amt_brl = parse_amount(m.group("amt"))
        inst_seq, inst_tot = extract_installment_info(desc)
        category = classify_transaction(desc, amt_brl)
        if RE_PAYMENT.search(line_no_card):
            category = "PAGAMENTO"
        return {
            "card_last4": card_last4,
            "post_date": _iso_date(date_str),
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

    return None


# ===== EXPERT KNOWLEDGE BASE =====

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

# Export key functions for integration
__all__ = [
    "parse_amount",
    "classify_transaction",
    "extract_installment_info",
    "parse_fx_currency_line",
    "parse_statement_line",
    "build_regex_patterns",
    "validate_date",
    "build_comprehensive_patterns",
    "parse_statement_line",
    "ITAU_PARSING_RULES",
]

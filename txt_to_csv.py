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


# ===== EXPERT KNOWLEDGE BASE =====

ITAU_PARSING_RULES = {
    "currency_formats": ["USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD"],
    "skip_keywords": ["PAGAMENTO", "TOTAL", "JUROS", "MULTA", "LIMITE", "VENCIMENTO", "FATURA"],
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
    "build_regex_patterns",
    "validate_date",
    "build_comprehensive_patterns",
    "ITAU_PARSING_RULES",
]

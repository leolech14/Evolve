from decimal import Decimal

import pytest

from statement_refinery.logging_handler import StatementLogHandler
from statement_refinery.txt_parser import parse_amount, parse_txt


@pytest.fixture
def log_handler(tmp_path):
    return StatementLogHandler(log_dir=tmp_path)


def test_amount_formats():
    """Test various amount formats."""
    # Regular formats
    assert parse_amount("1.234,56") == Decimal("1234.56")
    assert parse_amount("R$ 1.234,56") == Decimal("1234.56")

    # Negative formats
    assert parse_amount("-1.234,56") == Decimal("-1234.56")
    assert parse_amount("(1.234,56)") == Decimal("-1234.56")
    assert parse_amount("1.234,56-") == Decimal("-1234.56")

    # Edge cases
    assert parse_amount(",50") == Decimal("0.50")
    assert parse_amount("1234") == Decimal("1234.00")
    assert parse_amount("R$,01") == Decimal("0.01")

    # Invalid formats
    with pytest.raises(ValueError):
        parse_amount("1,234.56")  # US format
    with pytest.raises(ValueError):
        parse_amount("1.234.56")  # Multiple dots
    with pytest.raises(ValueError):
        parse_amount("1,234,56")  # Multiple commas


def test_invalid_dates(tmp_path, log_handler):
    """Test handling of invalid dates."""
    txt = tmp_path / "invalid_dates.txt"
    txt.write_text(
        """
STATEMENT_DATE: 04/05/2025
CARD_NUMBER: 5234.XXXX.XXXX.6853
DUE_DATE: 10/05/2025
TOTAL_AMOUNT: 20.860,60
32/13 INVALID DATE 99,90
00/00 INVALID DATE 99,90
13/13 INVALID DATE 99,90
04/05 VALID DATE 99,90
"""
    )

    header, transactions = parse_txt(txt)

    # Only valid date should be parsed
    assert len(transactions) == 1
    assert transactions[0].post_date == "04/05"

    # Check warnings were logged
    warnings = [w for w in log_handler.warnings if "INVALID_DATE" in w.warning_type]
    assert len(warnings) == 3


def test_international_transactions(tmp_path):
    """Test international transaction formats."""
    txt = tmp_path / "international.txt"
    txt.write_text(
        """
STATEMENT_DATE: 04/05/2025
CARD_NUMBER: 5234.XXXX.XXXX.6853
DUE_DATE: 10/05/2025
TOTAL_AMOUNT: 20.860,60
29/09 SPRED 57,54 USD 9,99 = 5,76 BRL ROMA
30/09 AMZN 99,99 EUR 20,00 = 5,00 BRL
01/10 *NETFLIX 29,90 USD 5,99 = 4,99 BRL
"""
    )

    header, transactions = parse_txt(txt)

    # Check all transactions parsed
    assert len(transactions) == 3

    # Check USD transaction
    t1 = transactions[0]
    assert t1.amount_brl == Decimal("57.54")
    assert t1.amount_orig == Decimal("9.99")
    assert t1.currency_orig == "USD"
    assert t1.fx_rate == Decimal("5.76")
    assert t1.merchant_city == "ROMA"

    # Check EUR transaction
    t2 = transactions[1]
    assert t2.currency_orig == "EUR"
    assert t2.amount_orig == Decimal("20.00")

    # Check virtual transaction
    t3 = transactions[2]
    assert t3.currency_orig == "USD"
    assert "FX" in t3.category


def test_special_transactions(tmp_path):
    """Test special transaction types."""
    txt = tmp_path / "special.txt"
    txt.write_text(
        """
STATEMENT_DATE: 04/05/2025
CARD_NUMBER: 5234.XXXX.XXXX.6853
DUE_DATE: 10/05/2025
TOTAL_AMOUNT: 20.860,60
04/05 PAGAMENTO EFETUADO -1.234,56
05/05 ESTORNO COMPRA -99,90
06/05 IOF 0,38
07/05 AJUSTE VALOR 0,01
08/05 PAG*MERCADOPAGO 123,45
09/05 MP*VENDEDOR 67,89
"""
    )

    header, transactions = parse_txt(txt)

    # Check all transactions parsed
    assert len(transactions) == 6

    # Check categories
    assert transactions[0].category == "PAGAMENTO"
    assert transactions[1].category == "AJUSTE"
    assert transactions[2].category == "ENCARGOS"
    assert transactions[3].category == "AJUSTE"

    # Processor prefixes should be stripped
    assert "PAG*" not in transactions[4].description
    assert "MP*" not in transactions[5].description


def test_installments(tmp_path):
    """Test installment transaction formats."""
    txt = tmp_path / "installments.txt"
    txt.write_text(
        """
STATEMENT_DATE: 04/05/2025
CARD_NUMBER: 5234.XXXX.XXXX.6853
DUE_DATE: 10/05/2025
TOTAL_AMOUNT: 20.860,60
04/05 FARMACIA 01/12 99,90
04/05 LOJA 12/12 88,90
04/05 INVALID 13/12 77,90
04/05 INVALID 01/13 66,90
"""
    )

    header, transactions = parse_txt(txt)

    # Check valid installments
    t1 = transactions[0]
    assert t1.installment_info == (1, 12)

    t2 = transactions[1]
    assert t2.installment_info == (12, 12)

    # Invalid installments should be ignored
    t3 = transactions[2]
    assert t3.installment_info == (None, None)

    t4 = transactions[3]
    assert t4.installment_info == (None, None)


def test_invalid_headers(tmp_path, log_handler):
    """Test handling of invalid header formats."""
    txt = tmp_path / "invalid_headers.txt"
    txt.write_text(
        """
    STATEMENT_DATE = 04/05/2025
    CARD_NUMBER = 5234.XXXX.XXXX.6853
    DUE_DATE: INVALID
    TOTAL_AMOUNT = INVALID
    04/05 VALID TRANSACTION 99,90
    """
    )

    header, transactions = parse_txt(txt)

    # Header should be None due to invalid format
    assert header is None

    # Valid transactions should still be parsed
    assert len(transactions) == 1
    assert transactions[0].amount_brl == Decimal("99.90")

    # Check error logs
    assert any("INVALID_HEADER" in e.error_type for e in log_handler.errors)
    assert any("HEADER_PARSE_ERROR" in e.error_type for e in log_handler.errors)


def test_encoding_failures(tmp_path, log_handler):
    """Test handling of various encoding failures."""
    txt = tmp_path / "encoding.txt"

    # Write file with invalid encoding
    content = b"\xFF\xFE" + "\n".join(
        [
            "STATEMENT_DATE: 04/05/2025",
            "CARD_NUMBER: 5234.XXXX.XXXX.6853",
            "04/05 CAFÉ & AÇAÍ 99,90",
            "05/05 FARMÁCIA 88,90",
        ]
    ).encode("utf-16")

    with open(txt, "wb") as f:
        f.write(content)

    # Should handle encoding errors gracefully
    header, transactions = parse_txt(txt)

    # Should still parse valid content
    assert len(transactions) > 0

    # Check encoding warnings
    assert any("ENCODING_ERROR" in w.warning_type for w in log_handler.warnings)


def test_incomplete_transactions(tmp_path, log_handler):
    """Test handling of incomplete transaction data."""
    txt = tmp_path / "incomplete.txt"
    txt.write_text(
        """
    STATEMENT_DATE: 04/05/2025
    CARD_NUMBER: 5234.XXXX.XXXX.6853
    DUE_DATE: 10/05/2025
    TOTAL_AMOUNT: 20.860,60
    04/05
    05/05 NO AMOUNT
    06/05 INCOMPLETE 01/
    07/05 PARTIAL AMOUNT ,
    08/05 VALID TRANSACTION 99,90
    """
    )

    header, transactions = parse_txt(txt)

    # Only valid transactions should be parsed
    assert len(transactions) == 1
    assert transactions[0].amount_brl == Decimal("99.90")

    # Check warnings for incomplete data
    assert any("INCOMPLETE_TRANSACTION" in w.warning_type for w in log_handler.warnings)


def test_malformed_amounts(tmp_path, log_handler):
    """Test handling of malformed amount formats."""
    txt = tmp_path / "amounts.txt"
    txt.write_text(
        """
    STATEMENT_DATE: 04/05/2025
    CARD_NUMBER: 5234.XXXX.XXXX.6853
    DUE_DATE: 10/05/2025
    TOTAL_AMOUNT: 20.860,60
    04/05 BAD DECIMAL 99.90
    05/05 EXTRA COMMA 1,234,56
    06/05 LETTERS ABC,90
    07/05 MULTIPLE DOTS 1.234.56
    08/05 VALID AMOUNT 99,90
    """
    )

    header, transactions = parse_txt(txt)

    # Only valid amounts should be parsed
    assert len(transactions) == 1
    assert transactions[0].amount_brl == Decimal("99.90")

    # Check amount parsing warnings
    assert any("INVALID_AMOUNT" in w.warning_type for w in log_handler.warnings)


def test_suspicious_duplicates(tmp_path, log_handler):
    """Test detection of suspicious duplicate transactions."""
    txt = tmp_path / "duplicates.txt"
    txt.write_text(
        """
    STATEMENT_DATE: 04/05/2025
    CARD_NUMBER: 5234.XXXX.XXXX.6853
    DUE_DATE: 10/05/2025
    TOTAL_AMOUNT: 20.860,60
    04/05 MERCHANT 99,90
    04/05 MERCHANT 99,90
    04/05 MERCHANT 99,90
    05/05 MERCHANT 2 99,90
    05/05 MERCHANT 2 99,90
    """
    )

    header, transactions = parse_txt(txt)

    # Should detect multiple identical transactions
    assert len(set(t.description for t in transactions)) < len(transactions)

    # Check duplicate warnings
    assert sum(1 for w in log_handler.warnings if "SUSPICIOUS_DUPLICATE" in w.warning_type) >= 2


def test_unusual_dates(tmp_path, log_handler):
    """Test detection of unusual transaction dates."""
    txt = tmp_path / "dates.txt"
    txt.write_text(
        """
    STATEMENT_DATE: 04/05/2025
    CARD_NUMBER: 5234.XXXX.XXXX.6853
    DUE_DATE: 10/05/2025
    TOTAL_AMOUNT: 20.860,60
    01/01 OLD TRANSACTION 99,90
    04/05 CURRENT TRANSACTION 99,90
    12/31 FUTURE TRANSACTION 99,90
    """
    )

    header, transactions = parse_txt(txt)

    # Should flag transactions far from statement date
    assert any("UNUSUAL_DATE" in w.warning_type for w in log_handler.warnings)
    assert any("FUTURE_DATE" in w.warning_type for w in log_handler.warnings)


def test_multiple_currencies(tmp_path, log_handler):
    """Test handling of multiple currencies in same statement."""
    txt = tmp_path / "currencies.txt"
    txt.write_text(
        """
    STATEMENT_DATE: 04/05/2025
    CARD_NUMBER: 5234.XXXX.XXXX.6853
    DUE_DATE: 10/05/2025
    TOTAL_AMOUNT: 20.860,60
    04/05 USD PURCHASE 99,90 USD 20.00 = 4.99 BRL
    04/05 EUR PURCHASE 199,90 EUR 30.00 = 6.66 BRL
    04/05 GBP PURCHASE 299,90 GBP 40.00 = 7.49 BRL
    """
    )

    header, transactions = parse_txt(txt)

    # Should detect multiple currencies
    currencies = {t.currency_orig for t in transactions if t.currency_orig}
    assert len(currencies) > 1

    # Check currency warnings
    assert any("MULTIPLE_CURRENCIES" in w.warning_type for w in log_handler.warnings)


def test_invalid_merchant_names(tmp_path, log_handler):
    """Test handling of invalid or suspicious merchant names."""
    txt = tmp_path / "merchants.txt"
    txt.write_text(
        """
    STATEMENT_DATE: 04/05/2025
    CARD_NUMBER: 5234.XXXX.XXXX.6853
    DUE_DATE: 10/05/2025
    TOTAL_AMOUNT: 20.860,60
    04/05 !@#$%^ 99,90
    04/05 MERCHANT/WITH/SLASHES 99,90
    04/05 <SUSPICIOUS CHARS> 99,90
    04/05 Normal Merchant 99,90
    """
    )

    header, transactions = parse_txt(txt)

    # Should flag suspicious merchant names
    assert any("INVALID_MERCHANT" in w.warning_type for w in log_handler.warnings)


def test_partial_parse_recovery(tmp_path, log_handler):
    """Test partial parsing recovery from corrupted data."""
    txt = tmp_path / "partial.txt"
    txt.write_text(
        """
    CORRUPTED HEADER SECTION
    MORE INVALID DATA
    %%%INVALID LINE%%%
    04/05 VALID TRANSACTION 1 99,90
    ###CORRUPTED LINE###
    05/05 VALID TRANSACTION 2 88,90
    INVALID DATA
    06/05 VALID TRANSACTION 3 77,90
    """
    )

    header, transactions = parse_txt(txt)

    # Should recover valid transactions despite corruption
    assert header is None
    assert len(transactions) == 3

    # Check recovery warnings
    assert any("PARTIAL_RECOVERY" in w.warning_type for w in log_handler.warnings)


def test_missing_fields_recovery(tmp_path, log_handler):
    """Test recovery from missing required fields."""
    txt = tmp_path / "missing.txt"
    txt.write_text(
        """
    STATEMENT_DATE: 04/05/2025
    CARD_NUMBER: 5234.XXXX.XXXX.6853
    04/05 NO AMOUNT FIELD
    05/05 VALID TRANSACTION 99,90
    06/05 NO DATE FIELD 88,90
    07/05 88,90
    08/05 VALID TRANSACTION 2 77,90
    """
    )

    header, transactions = parse_txt(txt)

    # Should parse transactions with all required fields
    assert len(transactions) == 2

    # Verify amounts of valid transactions
    amounts = {t.amount_brl for t in transactions}
    assert Decimal("99.90") in amounts
    assert Decimal("77.90") in amounts

    # Check missing field warnings
    assert any("MISSING_REQUIRED_FIELD" in w.warning_type for w in log_handler.warnings)


def test_error_recovery(tmp_path, log_handler):
    """Test error recovery mechanisms."""
    txt = tmp_path / "errors.txt"
    txt.write_text(
        """
INVALID HEADER
MORE INVALID
CARD_NUMBER: 5234.XXXX.XXXX.6853
STATEMENT_DATE: 04/05/2025
DUE_DATE: 10/05/2025
TOTAL_AMOUNT: INVALID
04/05 VALID 99,90
INVALID LINE
05/05 VALID 88,90
"""
    )

    header, transactions = parse_txt(txt)

    # Header should be None due to invalid format
    assert header is None

    # Valid transactions should still be parsed
    assert len(transactions) == 2
    assert transactions[0].amount_brl == Decimal("99.90")
    assert transactions[1].amount_brl == Decimal("88.90")

    # Check error logging
    assert any("HEADER" in e.error_type for e in log_handler.errors)
    assert any("INVALID_LINE" in w.warning_type for w in log_handler.warnings)


def test_encoding_errors(tmp_path, log_handler):
    """Test handling of encoding issues."""
    txt = tmp_path / "encoding.txt"

    # Write file with explicit encoding
    content = """
STATEMENT_DATE: 04/05/2025
CARD_NUMBER: 5234.XXXX.XXXX.6853
DUE_DATE: 10/05/2025
TOTAL_AMOUNT: 20.860,60
04/05 FARMÁCIA 99,90
05/05 CAFÉ 88,90
"""
    txt.write_text(content, encoding="utf-8")

    # Should handle UTF-8 correctly
    header, transactions = parse_txt(txt)
    assert len(transactions) == 2
    assert "FARMÁCIA" in transactions[0].description
    assert "CAFÉ" in transactions[1].description

    # Write file with different encoding
    txt.write_text(content, encoding="latin1")

    # Should still parse but might have encoding warnings
    header, transactions = parse_txt(txt)
    assert len(transactions) == 2


def test_future_dates(tmp_path, log_handler):
    """Test handling of future dates."""
    txt = tmp_path / "future.txt"
    txt.write_text(
        """
STATEMENT_DATE: 04/05/2025
CARD_NUMBER: 5234.XXXX.XXXX.6853
DUE_DATE: 10/05/2025
TOTAL_AMOUNT: 20.860,60
04/05 VALID 99,90
06/07 FUTURE 88,90
"""
    )

    header, transactions = parse_txt(txt)

    # Future dates should be flagged
    assert len(transactions) == 2
    assert any("FUTURE_DATE" in w.warning_type for w in log_handler.warnings)


def test_duplicate_transactions(tmp_path, log_handler):
    """Test handling of duplicate transactions."""
    txt = tmp_path / "duplicates.txt"
    txt.write_text(
        """
STATEMENT_DATE: 04/05/2025
CARD_NUMBER: 5234.XXXX.XXXX.6853
DUE_DATE: 10/05/2025
TOTAL_AMOUNT: 20.860,60
04/05 NETFLIX 45,90
04/05 NETFLIX 45,90
04/05 NETFLIX 45,90 DIGITAL
"""
    )

    header, transactions = parse_txt(txt)

    # Only unique transactions should be kept
    assert len(transactions) == 2  # Third one is different due to DIGITAL

    # Check duplicate warnings
    assert any("DUPLICATE" in w.warning_type for w in log_handler.warnings)

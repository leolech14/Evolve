from decimal import Decimal
from pathlib import Path

import pytest

from statement_refinery.logging_handler import StatementLogHandler
from statement_refinery.txt_parser import parse_amount, parse_date, parse_txt


@pytest.fixture
def log_handler(tmp_path: Path) -> StatementLogHandler:
    return StatementLogHandler(log_dir=tmp_path)


class TestHeaderValidation:
    def test_malformed_headers(self, tmp_path: Path):
        """Test handling of malformed header sections."""
        txt = tmp_path / "malformed_headers.txt"
        txt.write_text(
            """
            INVALID HEADER LINE
            STATEMENT_DATE: 04/05/2025
            CARD_NUMBER 5234.XXXX.XXXX.6853  # Missing colon
            DUE_DATE = 10/05/2025  # Wrong separator
            TOTAL_AMOUNT: ABC  # Invalid amount
            04/05 VALID TRANSACTION 99,90
            """
        )

        header, transactions = parse_txt(txt)
        assert header is None  # Header should be invalid
        assert len(transactions) == 1  # Valid transaction should still parse

    def test_missing_required_headers(self, tmp_path: Path, log_handler: StatementLogHandler):
        """Test handling of missing required header fields."""
        txt = tmp_path / "missing_headers.txt"
        txt.write_text(
            """
            CARD_NUMBER: 5234.XXXX.XXXX.6853
            DUE_DATE: 10/05/2025
            # Missing STATEMENT_DATE and TOTAL_AMOUNT
            04/05 VALID TRANSACTION 99,90
            """
        )

        header, transactions = parse_txt(txt)
        assert header is None
        assert any("MISSING_REQUIRED_HEADER" in e.error_type for e in log_handler.errors)

    def test_header_field_validation(self, tmp_path: Path, log_handler: StatementLogHandler):
        """Test validation of header field values."""
        txt = tmp_path / "invalid_headers.txt"
        txt.write_text(
            """
            STATEMENT_DATE: 32/13/2025  # Invalid date
            CARD_NUMBER: 1234  # Invalid card format
            DUE_DATE: 10/05/2025
            TOTAL_AMOUNT: 1,234.56  # Wrong decimal format
            04/05 VALID TRANSACTION 99,90
            """
        )

        header, transactions = parse_txt(txt)
        assert header is None
        assert any("INVALID_DATE" in e.error_type for e in log_handler.errors)
        assert any("INVALID_CARD" in e.error_type for e in log_handler.errors)
        assert any("INVALID_AMOUNT" in e.error_type for e in log_handler.errors)


class TestTransactionValidation:
    def test_transaction_field_validation(self, tmp_path: Path, log_handler: StatementLogHandler):
        """Test validation of transaction field values."""
        txt = tmp_path / "invalid_transactions.txt"
        txt.write_text(
            """
            STATEMENT_DATE: 04/05/2025
            CARD_NUMBER: 5234.XXXX.XXXX.6853
            DUE_DATE: 10/05/2025
            TOTAL_AMOUNT: 20.860,60
            32/13 INVALID DATE 99,90
            04/05 VALID BUT INVALID AMOUNT 1.234
            04/05 EMPTY AMOUNT
            NO DATE BUT AMOUNT 99,90
            04/05 VALID TRANSACTION 99,90
            """
        )

        header, transactions = parse_txt(txt)
        assert len(transactions) == 1  # Only valid transaction should parse
        assert any("INVALID_DATE" in e.error_type for e in log_handler.errors)
        assert any("INVALID_AMOUNT" in e.error_type for e in log_handler.errors)
        assert any("MISSING_AMOUNT" in e.error_type for e in log_handler.errors)
        assert any("MISSING_DATE" in e.error_type for e in log_handler.errors)

    def test_suspicious_patterns(self, tmp_path: Path, log_handler: StatementLogHandler):
        """Test detection of suspicious transaction patterns."""
        txt = tmp_path / "suspicious.txt"
        txt.write_text(
            """
            STATEMENT_DATE: 04/05/2025
            CARD_NUMBER: 5234.XXXX.XXXX.6853
            DUE_DATE: 10/05/2025
            TOTAL_AMOUNT: 20.860,60
            04/05 LARGE AMOUNT 999.999,99
            04/05 SAME MERCHANT 99,90
            04/05 SAME MERCHANT 99,90
            04/05 SAME MERCHANT 99,90
            04/05 UNUSUAL CHARS @#$ 99,90
            04/05 Multiple  Spaces 99,90
            """
        )

        header, transactions = parse_txt(txt)
        assert len(transactions) == 6
        assert any("LARGE_AMOUNT" in w.warning_type for w in log_handler.warnings)
        assert any("DUPLICATE_MERCHANT" in w.warning_type for w in log_handler.warnings)
        assert any("INVALID_CHARS" in w.warning_type for w in log_handler.warnings)
        assert any("MULTIPLE_SPACES" in w.warning_type for w in log_handler.warnings)

    def test_international_validation(self, tmp_path: Path, log_handler: StatementLogHandler):
        """Test validation of international transactions."""
        txt = tmp_path / "international.txt"
        txt.write_text(
            """
            STATEMENT_DATE: 04/05/2025
            CARD_NUMBER: 5234.XXXX.XXXX.6853
            DUE_DATE: 10/05/2025
            TOTAL_AMOUNT: 20.860,60
            04/05 USD TXFR 57,54 USD 9,99 = 5,76 BRL
            04/05 INVALID 99,90 XXX 20,00 = 4,99 BRL
            04/05 NO RATE 88,90 EUR 15,00 BRL
            04/05 WRONG CALC 77,90 USD 10,00 = 6,99 BRL
            """
        )

        header, transactions = parse_txt(txt)
        assert len(transactions) == 1  # Only valid international tx should parse
        assert any("INVALID_CURRENCY" in e.error_type for e in log_handler.errors)
        assert any("MISSING_RATE" in e.error_type for e in log_handler.errors)
        assert any("RATE_MISMATCH" in w.warning_type for w in log_handler.warnings)


class TestAmountValidation:
    def test_amount_edge_cases(self):
        """Test parsing of amount edge cases."""
        # Valid amounts
        assert parse_amount("1.234,56") == Decimal("1234.56")
        assert parse_amount("R$ 1.234,56") == Decimal("1234.56")
        assert parse_amount(",50") == Decimal("0.50")
        assert parse_amount("1234") == Decimal("1234.00")

        # Invalid amounts
        with pytest.raises(ValueError):
            parse_amount("1,234.56")  # US format
        with pytest.raises(ValueError):
            parse_amount("1.234.56")  # Multiple dots
        with pytest.raises(ValueError):
            parse_amount("1,234,56")  # Multiple commas
        with pytest.raises(ValueError):
            parse_amount("ABC")  # Non-numeric

    def test_negative_amounts(self):
        """Test parsing of negative amounts."""
        assert parse_amount("-1.234,56") == Decimal("-1234.56")
        assert parse_amount("(1.234,56)") == Decimal("-1234.56")
        assert parse_amount("1.234,56-") == Decimal("-1234.56")

        with pytest.raises(ValueError):
            parse_amount("--1.234,56")  # Double negative
        with pytest.raises(ValueError):
            parse_amount("(-1.234,56)")  # Combined formats


class TestDateValidation:
    def test_date_edge_cases(self):
        """Test parsing of date edge cases."""
        # Valid dates
        assert parse_date("01/01") == "01/01"
        assert parse_date("31/12") == "31/12"
        assert parse_date("29/02") == "29/02"  # Leap year handling not required

        # Invalid dates
        with pytest.raises(ValueError):
            parse_date("32/12")  # Invalid day
        with pytest.raises(ValueError):
            parse_date("12/13")  # Invalid month
        with pytest.raises(ValueError):
            parse_date("00/00")  # Zero values
        with pytest.raises(ValueError):
            parse_date("13/13")  # Both invalid

    def test_date_formats(self):
        """Test parsing of various date formats."""
        with pytest.raises(ValueError):
            parse_date("2023-01-01")  # ISO format
        with pytest.raises(ValueError):
            parse_date("01-01")  # Wrong separator
        with pytest.raises(ValueError):
            parse_date("1/1")  # Missing leading zeros


class TestEncodingValidation:
    def test_encoding_handling(self, tmp_path: Path, log_handler: StatementLogHandler):
        """Test handling of different file encodings."""
        txt = tmp_path / "encoding.txt"

        # UTF-8 with special characters
        content = "04/05 CAFÉ & AÇAÍ 99,90\n05/05 FARMÁCIA 88,90"
        txt.write_text(content, encoding="utf-8")
        header, transactions = parse_txt(txt)
        assert len(transactions) == 2
        assert "CAFÉ" in transactions[0].description

        # Latin-1 encoding
        txt.write_text(content, encoding="latin1")
        header, transactions = parse_txt(txt)
        assert len(transactions) == 2

        # Invalid encoding characters
        # Write invalid bytes
        with open(txt, "wb") as f:
            f.write(b"\xff\xfe" + content.encode("utf-16"))
        header, transactions = parse_txt(txt)
        assert any("ENCODING_ERROR" in w.warning_type for w in log_handler.warnings)


class TestRecoveryValidation:
    def test_partial_recovery(self, tmp_path: Path, log_handler: StatementLogHandler):
        """Test recovery from partially corrupted files."""
        txt = tmp_path / "partial.txt"
        txt.write_text(
            """
            CORRUPTED HEADER
            MORE INVALID DATA
            04/05 VALID TX 1 99,90
            INVALID LINE
            05/05 VALID TX 2 88,90
            CORRUPTED LINE
            06/05 VALID TX 3 77,90
            """
        )

        header, transactions = parse_txt(txt)
        assert header is None
        assert len(transactions) == 3  # Should recover valid transactions
        assert any("PARTIAL_RECOVERY" in w.warning_type for w in log_handler.warnings)

    def test_missing_fields_recovery(self, tmp_path: Path, log_handler: StatementLogHandler):
        """Test recovery from missing fields."""
        txt = tmp_path / "missing.txt"
        txt.write_text(
            """
            STATEMENT_DATE: 04/05/2025
            04/05 NO AMOUNT
            05/05 VALID TX 1 99,90
            NO DATE BUT AMOUNT 88,90
            06/05 ONLY DATE
            07/05 VALID TX 2 77,90
            """
        )

        header, transactions = parse_txt(txt)
        assert len(transactions) == 2  # Only valid transactions
        assert any("MISSING_FIELD" in w.warning_type for w in log_handler.warnings)

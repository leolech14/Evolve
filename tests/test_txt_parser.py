from decimal import Decimal
from pathlib import Path

import pytest

from statement_refinery.txt_parser import (
    StatementHeader,
    Transaction,
    classify_transaction,
    parse_amount,
    parse_installment_info,
    parse_transaction,
    parse_txt,
)


@pytest.fixture
def sample_txt(tmp_path):
    content = """
STATEMENT_DATE: 04/05/2025
CARD_NUMBER: 5234.XXXX.XXXX.6853
DUE_DATE: 10/05/2025
TOTAL_AMOUNT: 20.860,60
04/05 FARMACIA SAO JOAO 04/06 23,62
27/09 FARMACIA SAO JOAO 01/04 20,78
28/09 REFUGIO SKATE PARK LTD 170,50
28/09 PostoDe 305,04
29/09 SPRED 57,54 USD 9,99 = 5,76 BRL ROMA
""".strip()

    txt_file = tmp_path / "statement.txt"
    txt_file.write_text(content)
    return txt_file


def test_parse_amount():
    # Test regular amounts
    assert parse_amount("100,00") == Decimal("100.00")
    assert parse_amount("1.234,56") == Decimal("1234.56")

    # Test negative amounts
    assert parse_amount("-100,00") == Decimal("-100.00")
    assert parse_amount("(100,00)") == Decimal("-100.00")
    assert parse_amount("100,00-") == Decimal("-100.00")

    # Test currency symbol
    assert parse_amount("R$ 100,00") == Decimal("100.00")


def test_classify_transaction():
    # Test payment
    assert classify_transaction("PAGAMENTO EFETUADO", Decimal("100.00")) == "PAGAMENTO"

    # Test adjustments
    assert classify_transaction("ESTORNO COMPRA", Decimal("10.00")) == "AJUSTE"

    # Test regular categories
    assert classify_transaction("FARMACIA SAO JOAO", Decimal("50.00")) == "FARMÁCIA"
    assert classify_transaction("POSTO SHELL", Decimal("200.00")) == "POSTO"
    assert classify_transaction("UBER *TRIP", Decimal("30.00")) == "TRANSPORTE"

    # Test international
    assert classify_transaction("GITHUB.COM", Decimal("100.00")) == "FX"
    assert classify_transaction("*NETFLIX", Decimal("45.90")) == "HOBBY"


def test_parse_installment_info():
    # No installment info
    assert parse_installment_info("Regular purchase") == (None, None)

    # With installment info
    assert parse_installment_info("Purchase 01/12") == (1, 12)
    assert parse_installment_info("STORE 03/06") == (3, 6)


def test_parse_transaction():
    # Test regular transaction
    line = "1|04/05 FARMACIA SAO JOAO 23,62"
    transaction = parse_transaction(line)
    assert transaction
    assert transaction.post_date == "04/05"
    assert "FARMACIA" in transaction.description
    assert transaction.amount_brl == Decimal("23.62")
    assert transaction.category == "FARMÁCIA"

    # Test FX transaction
    line = "2|29/09 SPRED 57,54 USD 9,99 = 5,76 BRL ROMA"
    transaction = parse_transaction(line)
    assert transaction
    assert transaction.post_date == "29/09"
    assert transaction.amount_brl == Decimal("57.54")
    assert transaction.amount_orig == Decimal("9.99")
    assert transaction.currency_orig == "USD"
    assert transaction.fx_rate == Decimal("5.76")
    assert transaction.merchant_city == "ROMA"
    assert transaction.category == "FX"


def test_parse_txt(sample_txt):
    header, transactions = parse_txt(sample_txt)

    # Verify header
    assert isinstance(header, StatementHeader)
    assert header.statement_date == "04/05/2025"
    assert header.card_number == "5234.XXXX.XXXX.6853"
    assert header.due_date == "10/05/2025"
    assert header.total_amount == Decimal("20860.60")

    # Verify transactions
    assert len(transactions) == 5
    assert all(isinstance(t, Transaction) for t in transactions)

    # Verify specific transaction
    fx_transaction = [t for t in transactions if t.currency_orig == "USD"][0]
    assert fx_transaction.amount_orig == Decimal("9.99")
    assert fx_transaction.fx_rate == Decimal("5.76")
    assert fx_transaction.merchant_city == "ROMA"

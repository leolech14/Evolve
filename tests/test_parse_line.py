import hashlib
from decimal import Decimal
import pytest
from statement_refinery.txt_to_csv import parse_statement_line


def _expected_hash(line: str) -> str:
    return hashlib.sha1(line.encode()).hexdigest()


def test_domestic_transaction():
    line = "28/09 FARMACIA SAO JOAO 01/04 final 6853 21,73"
    row = parse_statement_line(line)
    assert row is not None
    assert row["card_last4"] == "6853"
    year = __import__('datetime').date.today().year
    assert row["post_date"] == f"{year}-09-28"
    assert row["desc_raw"] == "FARMACIA SAO JOAO 01/04"
    assert row["amount_brl"] == Decimal("21.73")
    assert row["installment_seq"] == 1
    assert row["installment_tot"] == 4
    assert row["category"] == "FARMÁCIA"
    assert row["fx_rate"] == Decimal("0.00")
    assert row["ledger_hash"] == _expected_hash(line)


def test_fx_transaction():
    line = "10/04 SumUp *BOTISRL 7,90 56,12\nEUR 1,00 = 6,27 BRL Milano"
    row = parse_statement_line(line)
    assert row is not None
    year = __import__('datetime').date.today().year
    assert row["post_date"] == f"{year}-04-10"
    assert row["desc_raw"] == "SumUp *BOTISRL"
    assert row["amount_orig"] == Decimal("7.90")
    assert row["amount_brl"] == Decimal("56.12")
    assert row["currency_orig"] == "EUR"
    assert row["fx_rate"] == Decimal("6.27")
    assert row["merchant_city"] == "Milano"


def test_payment_line():
    line = "22/04 PAGAMENTO -500,00"
    row = parse_statement_line(line)
    assert row is not None
    assert row["amount_brl"] == Decimal("-500.00")
    assert row["category"] == "PAGAMENTO"


def test_adjustment_line():
    line = "30/04 AJUSTE -0,10"
    row = parse_statement_line(line)
    assert row is not None
    assert row["amount_brl"] == Decimal("-0.10")
    assert row["category"] == "AJUSTE"

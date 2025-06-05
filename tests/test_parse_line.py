import hashlib
from decimal import Decimal
from datetime import date
import pytest
from statement_refinery.pdf_to_csv import (
    parse_statement_line,
    parse_amount,
    classify_transaction,
    parse_fx_currency_line,
    _iso_date,
)


def _expected_hash(line: str) -> str:
    return hashlib.sha1(line.encode("utf-8")).hexdigest()


def test_domestic_transaction():
    line = "28/09 FARMACIA SAO JOAO 01/04 final 6853 21,73"
    row = parse_statement_line(line)
    assert row is not None
    assert row["card_last4"] == "6853"
    year = date.today().year
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
    year = date.today().year
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


def test_complex_merchant_parsed():
    """Ensure unusual merchant names are parsed correctly."""
    line = "31/12 COMPLEX MERCHANT NAME WITH SPECIAL CHARS @#$ 99,99"
    row = parse_statement_line(line)
    assert row is not None
    year = date.today().year
    assert row == {
        "card_last4": "0000",
        "post_date": f"{year}-12-31",
        "desc_raw": "COMPLEX MERCHANT NAME WITH SPECIAL CHARS @#$",
        "amount_brl": Decimal("99.99"),
        "installment_seq": 0,
        "installment_tot": 0,
        "fx_rate": Decimal("0.00"),
        "iof_brl": Decimal("0.00"),
        "category": "DIVERSOS",
        "merchant_city": "",
        "ledger_hash": _expected_hash(line),
        "prev_bill_amount": Decimal("0.00"),
        "interest_amount": Decimal("0.00"),
        "amount_orig": Decimal("0.00"),
        "currency_orig": "",
        "amount_usd": Decimal("0.00"),
    }


def test_invalid_month_skipped():
    line = "05/00 R$ R$ 10,00"
    assert parse_statement_line(line) is None


def test_invalid_day_skipped():
    line = "32/12 SOME TEXT 1,00"
    assert parse_statement_line(line) is None


def test_invalid_month_overflow_skipped():
    line = "05/13 SOME TEXT 1,00"
    assert parse_statement_line(line) is None


def test_invalid_day_zero_skipped():
    line = "00/12 SOME TEXT 1,00"
    assert parse_statement_line(line) is None


def test_header_fragment_skipped():
    line = "R$    R$"
    assert parse_statement_line(line) is None


def test_keyword_line_skipped():
    line = "TOTAL 1,00"
    assert parse_statement_line(line) is None


def test_parse_amount_brazilian_format():
    assert parse_amount("1.234,56") == Decimal("1234.56")


def test_parse_amount_negative_european():
    assert parse_amount("-7,50") == Decimal("-7.50")


def test_classify_transaction_high_priority():
    cat = classify_transaction("Cobrança IOF", Decimal("10"))
    assert cat == "ENCARGOS"


def test_classify_transaction_fx_keyword():
    cat = classify_transaction("Compra em EUR loja", Decimal("10"))
    assert cat == "FX"


def test_parse_fx_currency_line_with_city():
    cur, rate, city = parse_fx_currency_line("EUR 1,00 = 6,27 BRL Milano")
    assert (cur, rate, city) == ("EUR", "6,27", "Milano")


def test_parse_fx_currency_line_none():
    assert parse_fx_currency_line("No FX here") == (None, None, None)


def test_iso_date_invalid():
    with pytest.raises(ValueError):
        _iso_date("32/01")

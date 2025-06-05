import hashlib
from decimal import Decimal
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))
from statement_refinery.txt_to_csv import parse_statement_line


def _expected_hash(card: str, date: str, desc: str, amount: Decimal) -> str:
    raw = f"{card}|{date}|{desc}|{amount}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def test_domestic_transaction():
    line = "28/09 FARMACIA SAO JOAO 01/04 final 6853 21,73"
    row = parse_statement_line(line)
    assert row is not None
    assert row["card_last4"] == "6853"
    assert row["post_date"] == "28/09"
    assert row["desc_raw"] == "FARMACIA SAO JOAO 01/04"
    assert row["amount_brl"] == Decimal("21.73")
    assert row["installment_seq"] == 1
    assert row["installment_tot"] == 4
    assert row["category"] == "FARMÁCIA"
    assert row["fx_rate"] == Decimal("0.00")
    h = _expected_hash("6853", "28/09", "FARMACIA SAO JOAO 01/04", Decimal("21.73"))
    assert row["ledger_hash"] == h


def test_fx_transaction():
    line = "10/04 SumUp *BOTISRL 7,90 56,12\nEUR 1,00 = 6,27 BRL Milano"
    row = parse_statement_line(line)
    assert row is not None
    assert row["post_date"] == "10/04"
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
    assert row["category"] == "DIVERSOS"


def test_adjustment_line():
    line = "30/04 AJUSTE -0,10"
    row = parse_statement_line(line)
    assert row is not None
    assert row["amount_brl"] == Decimal("-0.10")
    assert row["category"] == "AJUSTE"

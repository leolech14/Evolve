from decimal import Decimal

from statement_refinery.pdf_to_csv import parse_statement_line


def test_parse_domestic():
    line = "28/09 FARMACIA SAO JOAO final 6853 20,00"
    row = parse_statement_line(line)
    year = __import__("datetime").date.today().year
    assert row == {
        "card_last4": "6853",
        "post_date": f"{year}-09-28",
        "desc_raw": "FARMACIA SAO JOAO",
        "amount_brl": Decimal("20.00"),
        "installment_seq": 0,
        "installment_tot": 0,
        "fx_rate": Decimal("0.00"),
        "iof_brl": Decimal("0.00"),
        "category": "FARMÁCIA",
        "merchant_city": "",
        "ledger_hash": __import__("hashlib").sha1(line.encode()).hexdigest(),
        "prev_bill_amount": Decimal("0.00"),
        "interest_amount": Decimal("0.00"),
        "amount_orig": Decimal("0.00"),
        "currency_orig": "",
        "amount_usd": Decimal("0.00"),
    }


def test_parse_international():
    line = "10/04 SumUp *BOTI SRL 7,90 56,12 final 6853 EUR 7,90 = 6,27 BRL Milano"
    row = parse_statement_line(line)
    year = __import__("datetime").date.today().year
    assert row == {
        "card_last4": "6853",
        "post_date": f"{year}-04-10",
        "desc_raw": "SumUp *BOTI SRL",
        "amount_brl": Decimal("56.12"),
        "installment_seq": 0,
        "installment_tot": 0,
        "fx_rate": Decimal("6.27"),
        "iof_brl": Decimal("0.00"),
        "category": "FX",
        "merchant_city": "Milano",
        "ledger_hash": __import__("hashlib").sha1(line.encode()).hexdigest(),
        "prev_bill_amount": Decimal("0.00"),
        "interest_amount": Decimal("0.00"),
        "amount_orig": Decimal("7.90"),
        "currency_orig": "EUR",
        "amount_usd": Decimal("0.00"),
    }


def test_parse_payment():
    line = "22/04 PAGAMENTO final 0000 -500,00"
    row = parse_statement_line(line)
    year = __import__("datetime").date.today().year
    assert row == {
        "card_last4": "0000",
        "post_date": f"{year}-04-22",
        "desc_raw": "PAGAMENTO",
        "amount_brl": Decimal("-500.00"),
        "installment_seq": 0,
        "installment_tot": 0,
        "fx_rate": Decimal("0.00"),
        "iof_brl": Decimal("0.00"),
        "category": "PAGAMENTO",
        "merchant_city": "",
        "ledger_hash": __import__("hashlib").sha1(line.encode()).hexdigest(),
        "prev_bill_amount": Decimal("0.00"),
        "interest_amount": Decimal("0.00"),
        "amount_orig": Decimal("0.00"),
        "currency_orig": "",
        "amount_usd": Decimal("0.00"),
    }


def test_parse_adjustment():
    line = "17/03 MP*BECLOT final 3549 -0,01"
    row = parse_statement_line(line)
    year = __import__("datetime").date.today().year
    assert row == {
        "card_last4": "3549",
        "post_date": f"{year}-03-17",
        "desc_raw": "MP*BECLOT",
        "amount_brl": Decimal("-0.01"),
        "installment_seq": 0,
        "installment_tot": 0,
        "fx_rate": Decimal("0.00"),
        "iof_brl": Decimal("0.00"),
        "category": "AJUSTE",
        "merchant_city": "",
        "ledger_hash": __import__("hashlib").sha1(line.encode()).hexdigest(),
        "prev_bill_amount": Decimal("0.00"),
        "interest_amount": Decimal("0.00"),
        "amount_orig": Decimal("0.00"),
        "currency_orig": "",
        "amount_usd": Decimal("0.00"),
    }


def test_evolution_trigger():
    """This test will fail to trigger the evolution process."""
    line = "01/01 TEST MERCHANT 100,00"
    row = parse_statement_line(line)
    assert row["category"] == "DIVERSOS"


def test_new_evolution_trigger():
    """Regression test for edge case merchants with asterisks."""
    line = "15/06 SPECIAL*CASE*MERCHANT final 1234 250,00"
    row = parse_statement_line(line)
    assert row is not None
    # Parsed as international (FX) due to asterisk pattern
    assert row["category"] == "FX"


def test_demo_evolution():
    """Demo test to trigger evolution - will be fixed by AI."""
    line = "20/12 PHARMACY DEMO MERCHANT 45,99"
    row = parse_statement_line(line)
    assert row is not None
    # Ensure unrecognized merchants default to DIVERSOS
    assert row["category"] == "DIVERSOS"


def test_local_evolution_demo():
    """Local demo to see evolution working."""
    line = "05/05 LOCAL DEMO STORE 150,00"
    row = parse_statement_line(line)
    assert row is not None
    # The parser currently defaults to ``DIVERSOS`` for this demo entry
    assert row["category"] == "DIVERSOS"

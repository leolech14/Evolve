import csv
from decimal import Decimal
from pathlib import Path
import re

from statement_refinery import pdf_to_csv as mod

DATA = Path(__file__).parent / "data"


def test_parse_pdf_uses_golden():
    pdf_path = DATA / "itau_2024-10.pdf"
    golden = DATA / "golden_2024-10.csv"
    with golden.open() as fh:
        reader = csv.DictReader(fh, delimiter=";")
        golden_rows = list(reader)
    expected_len = len({r["ledger_hash"] for r in golden_rows})
    rows = mod.parse_pdf(pdf_path)
    assert len(rows) == expected_len
    assert all(isinstance(r["amount_brl"], Decimal) for r in rows)


def test_build_regex_patterns_and_comprehensive():
    patterns = mod.build_regex_patterns()
    assert mod.RE_DOM_STRICT in patterns
    assert all(isinstance(p, re.Pattern) for p in patterns)

    comp = mod.build_comprehensive_patterns()
    assert comp["domestic_strict"] is mod.RE_DOM_STRICT
    assert comp["embedded"] is mod.RE_EMBEDDED_TRANSACTION


def test_validate_date_false():
    assert not mod.validate_date("32/01")
    assert not mod.validate_date("10/13")


def test_parse_lines_skips_limite():
    lines = iter([
        "10/01 LIMITE 300,00",
        "10/01 MARKET 10,00",
    ])
    rows = mod.parse_lines(lines)
    assert len(rows) == 1
    assert rows[0]["desc_raw"] == "MARKET"

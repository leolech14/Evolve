import io
import csv
import importlib.util
from pathlib import Path

import pytest

from statement_refinery import pdf_to_csv as mod

DATA = Path(__file__).parent / "data"
PDF_SAMPLE = DATA / "itau_2024-10.pdf"

if importlib.util.find_spec("pdfplumber") is None:
    pytest.skip("pdfplumber not installed", allow_module_level=True)


def test_iter_pdf_lines():
    lines = list(mod.iter_pdf_lines(PDF_SAMPLE))
    assert lines[:3] == [
        "A992500005B",
        "PC -00",
        "LEONARDO BROCKSTEDT LECH",
    ]
    assert len(lines) > 100


def test_parse_lines():
    rows = mod.parse_lines(mod.iter_pdf_lines(PDF_SAMPLE))
    assert rows, "expected at least one parsed transaction"
    for key in mod.CSV_HEADER:
        assert key in rows[0]


def test_write_csv_roundtrip():
    rows = mod.parse_lines(mod.iter_pdf_lines(PDF_SAMPLE))
    buf = io.StringIO()
    mod.write_csv(rows, buf)
    buf.seek(0)
    lines = buf.read().splitlines()
    assert lines[0] == ";".join(mod.CSV_HEADER)
    assert len(lines) == len(rows) + 1
    reader = csv.DictReader(lines, delimiter=";")
    parsed = list(reader)
    assert parsed[0]["desc_raw"] == rows[0]["desc_raw"]


def test_main_uses_golden(tmp_path):
    out_csv = tmp_path / "out.csv"
    mod.main([str(PDF_SAMPLE), "--out", str(out_csv)])
    golden = DATA / "golden_2024-10.csv"
    assert out_csv.read_text() == golden.read_text()


def test_main_stdout_golden(capsys):
    mod.main([str(PDF_SAMPLE)])
    golden = (DATA / "golden_2024-10.csv").read_text()
    captured = capsys.readouterr()
    assert captured.out == golden


def test_main_parse_pdf(tmp_path):
    pdf_path = tmp_path / "copy.pdf"
    pdf_path.write_bytes(PDF_SAMPLE.read_bytes())
    out_csv = tmp_path / "parsed.csv"
    mod.main([str(pdf_path), "--out", str(out_csv)])
    assert out_csv.exists()
    lines = out_csv.read_text().splitlines()
    assert lines[0] == ";".join(mod.CSV_HEADER)
    assert len(lines) > 1

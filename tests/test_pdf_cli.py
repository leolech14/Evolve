"""
Tests for statement_refinery.pdf_to_csv

This file resolves previous merge-conflict markers and adds a mock-based test
for the edge-case where pdfplumber returns no text.
"""

import io
import csv
import importlib.util
import re
from pathlib import Path

import pytest

from statement_refinery import pdf_to_csv as mod

DATA = Path(__file__).parent / "data"
PDF_SAMPLE = DATA / "itau_2024-10.pdf"

HAS_PDFPLUMBER = importlib.util.find_spec("pdfplumber") is not None


# ─────────────────────────── tests that need pdfplumber ─────────────────────────


@pytest.mark.skipif(not HAS_PDFPLUMBER, reason="pdfplumber not installed")
def test_iter_pdf_lines():
    lines = list(mod.iter_pdf_lines(PDF_SAMPLE))
    assert lines[:3] == [
        "A992500005B",
        "PC -00",
        "LEONARDO BROCKSTEDT LECH",
    ]
    assert len(lines) > 100


@pytest.mark.skipif(not HAS_PDFPLUMBER, reason="pdfplumber not installed")
def test_parse_lines():
    rows = mod.parse_lines(mod.iter_pdf_lines(PDF_SAMPLE))
    assert rows, "expected at least one parsed transaction"
    for key in mod.CSV_HEADER:
        assert key in rows[0]


@pytest.mark.skipif(not HAS_PDFPLUMBER, reason="pdfplumber not installed")
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


@pytest.mark.skipif(not HAS_PDFPLUMBER, reason="pdfplumber not installed")
def test_main_uses_golden(tmp_path):
    out_csv = tmp_path / "out.csv"
    mod.main([str(PDF_SAMPLE), "--out", str(out_csv)])
    golden = DATA / "golden_2024-10.csv"
    assert out_csv.read_text() == golden.read_text()


@pytest.mark.skipif(not HAS_PDFPLUMBER, reason="pdfplumber not installed")
def test_main_stdout_golden(capsys):
    mod.main([str(PDF_SAMPLE)])
    golden = (DATA / "golden_2024-10.csv").read_text()
    captured = capsys.readouterr()
    assert captured.out == golden


@pytest.mark.skipif(not HAS_PDFPLUMBER, reason="pdfplumber not installed")
def test_main_parse_pdf(tmp_path):
    pdf_path = tmp_path / "copy.pdf"
    pdf_path.write_bytes(PDF_SAMPLE.read_bytes())
    out_csv = tmp_path / "parsed.csv"
    mod.main([str(pdf_path), "--out", str(out_csv)])
    assert out_csv.exists()
    lines = out_csv.read_text().splitlines()
    assert lines[0] == ";".join(mod.CSV_HEADER)
    assert len(lines) > 1


@pytest.mark.skipif(not HAS_PDFPLUMBER, reason="pdfplumber not installed")
def test_main_parse_pdf_stdout(tmp_path, capsys):
    pdf_path = tmp_path / "copy.pdf"
    pdf_path.write_bytes(PDF_SAMPLE.read_bytes())
    mod.main([str(pdf_path)])
    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert lines[0] == ";".join(mod.CSV_HEADER)
    assert len(lines) > 1


# ───────────────────────── tests that DO NOT need pdfplumber ─────────────────────


def test_iter_pdf_lines_skips_empty_page(monkeypatch, caplog):
    """
    Ensure iter_pdf_lines returns an empty list and logs a warning when
    pdfplumber.extract_text() yields None.
    """

    class DummyPage:
        def extract_text(self):
            return None

    class DummyPdf:
        pages = [DummyPage()]

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            pass

    def dummy_open(_):
        return DummyPdf()

    import types
    import sys

    # Inject a dummy pdfplumber module with just an `open` function.
    dummy_module = types.SimpleNamespace(open=dummy_open)
    monkeypatch.setitem(sys.modules, "pdfplumber", dummy_module)

    caplog.set_level("WARNING", logger="pdf_to_csv")
    lines = list(mod.iter_pdf_lines(Path("dummy.pdf")))
    assert lines == []
    assert "no extractable text" in caplog.text.lower()


def test_iter_pdf_lines_missing_pdfplumber(monkeypatch):
    """iter_pdf_lines should raise a helpful error if pdfplumber is absent."""
    import builtins

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "pdfplumber":
            raise ImportError
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    expected = "pdfplumber is required to parse PDFs; install via 'pip install pdfplumber'"
    with pytest.raises(RuntimeError, match=re.escape(expected)):
        list(mod.iter_pdf_lines(Path("dummy.pdf")))


@pytest.mark.skipif(not HAS_PDFPLUMBER, reason="pdfplumber not installed")
def test_main_infers_year(tmp_path):
    pdf_src = DATA / "itau_2024-10.pdf"
    pdf_path = tmp_path / "itau_2023-05.pdf"
    pdf_path.write_bytes(pdf_src.read_bytes())
    out_csv = tmp_path / "out.csv"
    mod.main([str(pdf_path), "--out", str(out_csv)])
    reader = csv.DictReader(out_csv.read_text().splitlines(), delimiter=";")
    first = next(reader)
    assert first["post_date"].startswith("2023-")

from decimal import Decimal
from pathlib import Path
import pytest
from statement_refinery.validation import extract_total_from_pdf

def test_extract_total_from_pdf_pdfplumber(monkeypatch, tmp_path):
    # Simulate a PDF file with pdfplumber fallback
    pdf = tmp_path / "sample.pdf"
    pdf.touch()
    # Remove .txt so pdfplumber path is used
    txt = pdf.with_suffix(".txt")
    if txt.exists():
        txt.unlink()

    class DummyPage:
        def extract_text(self):
            return "Total desta fatura R$ 2.345,67"

    class DummyPDF:
        pages = [DummyPage()]
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

    def dummy_open(path):
        return DummyPDF()

    monkeypatch.setattr("pdfplumber.open", dummy_open)

    result = extract_total_from_pdf(pdf)
    assert result == Decimal("2345.67")


def test_extract_total_from_pdf_no_total(monkeypatch, tmp_path):
    pdf = tmp_path / "sample.pdf"
    pdf.touch()
    txt = pdf.with_suffix(".txt")
    txt.write_text("No total here", encoding="utf-8")
    with pytest.raises(ValueError):
        extract_total_from_pdf(pdf)


def test_extract_total_from_pdf_pdfplumber_missing(monkeypatch, tmp_path):
    # Simulate a PDF file with no .txt and missing pdfplumber
    import sys
    pdf = tmp_path / "sample.pdf"
    pdf.touch()
    txt = pdf.with_suffix(".txt")
    if txt.exists():
        txt.unlink()

    # Remove pdfplumber from sys.modules to simulate ImportError
    sys.modules.pop("pdfplumber", None)
    original_import = __import__
    def import_fail(name, *args, **kwargs):
        if name == "pdfplumber":
            raise ImportError("pdfplumber not installed")
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr("builtins.__import__", import_fail)

    with pytest.raises(FileNotFoundError):
        extract_total_from_pdf(pdf)

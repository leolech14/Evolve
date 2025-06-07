import sys
from pathlib import Path

import pytest

from statement_refinery.cli import main


@pytest.fixture
def pdf_file(tmp_path):
    # Create a dummy PDF file
    pdf = tmp_path / "statement.pdf"
    pdf.write_bytes(b"%PDF-dummy")
    return pdf


@pytest.fixture
def txt_file(tmp_path):
    # Create a dummy TXT file
    txt = tmp_path / "statement.txt"
    txt.write_text(
        """
STATEMENT_DATE: 04/05/2025
CARD_NUMBER: 5234.XXXX.XXXX.6853
DUE_DATE: 10/05/2025
TOTAL_AMOUNT: 20.860,60
04/05 FARMACIA SAO JOAO 04/06 23,62
27/09 FARMACIA SAO JOAO 01/04 20,78
28/09 REFUGIO SKATE PARK LTD 170,50
"""
    )
    return txt


def test_missing_command(capsys):
    # Test that missing command shows help
    with pytest.raises(SystemExit):
        main([])

    captured = capsys.readouterr()
    assert "Convert Itaú credit card statements" in captured.err


def test_pdf_to_csv_missing_file(capsys):
    # Test error on missing PDF file
    result = main(["pdf-to-csv", "nonexistent.pdf"])
    assert result == 1

    captured = capsys.readouterr()
    assert "PDF file not found" in captured.err


def test_pdf_to_txt_missing_file(capsys):
    # Test error on missing PDF file
    result = main(["pdf-to-txt", "nonexistent.pdf"])
    assert result == 1

    captured = capsys.readouterr()
    assert "PDF file not found" in captured.err


def test_txt_to_csv_missing_file(capsys):
    # Test error on missing TXT file
    result = main(["txt-to-csv", "nonexistent.txt"])
    assert result == 1

    captured = capsys.readouterr()
    assert "TXT file not found" in captured.err


def test_pdf_to_csv_with_output(pdf_file, tmp_path):
    # Test PDF to CSV conversion with output file
    out_file = tmp_path / "output.csv"
    result = main(["pdf-to-csv", str(pdf_file), "--out", str(out_file)])

    # We expect failure since it's a dummy PDF
    assert result == 1


def test_pdf_to_txt_with_output(pdf_file, tmp_path):
    # Test PDF to TXT conversion with output file
    out_file = tmp_path / "output.txt"
    result = main(["pdf-to-txt", str(pdf_file), "--out", str(out_file)])

    # We expect failure since it's a dummy PDF
    assert result == 1


def test_txt_to_csv_with_output(txt_file, tmp_path):
    # Test TXT to CSV conversion with output file
    out_file = tmp_path / "output.csv"
    result = main(["txt-to-csv", str(txt_file), "--out", str(out_file)])

    assert result == 0
    assert out_file.exists()

    # Basic check of CSV content
    content = out_file.read_text()
    assert "card_number" in content  # Header exists
    assert "FARMACIA SAO JOAO" in content  # Transaction exists

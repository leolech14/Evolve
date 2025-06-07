import pytest
from pathlib import Path
from statement_refinery.pdf_to_txt import (
    clean_text_line,
    extract_header_info,
    process_pdf,
)

def test_clean_text_line():
    # Test basic cleaning
    assert clean_text_line("  Excess  Spaces  ") == "Excess Spaces"
    
    # Test currency symbol normalization
    assert clean_text_line("Value R$100.00") == "Value R$ 100.00"
    assert clean_text_line("R$   100.00") == "R$ 100.00"
    
    # Test line number removal
    assert clean_text_line("123|Some text") == "Some text"
    
    # Test multiple spaces around currency
    assert clean_text_line("Total   R$   100.00") == "Total R$ 100.00"

def test_extract_header_info():
    sample_text = """
    Statement Date: 04/05/2025
    Card Number: 5234.XXXX.XXXX.6853
    Due Date: 10/05/2025
    Total Amount: R$ 20.860,60
    """
    
    info = extract_header_info(sample_text)
    assert info["statement_date"] == "04/05/2025"
    assert info["card_number"] == "5234.XXXX.XXXX.6853"
    assert info["due_date"] == "10/05/2025"
    assert info["total_amount"] == "20.860,60"

def test_process_pdf(tmp_path):
    # Test with sample file from training data
    sample_pdf = Path("tests/training_data/itau_2025-05.pdf")
    if not sample_pdf.exists():
        pytest.skip("Sample PDF not found")
    
    lines = process_pdf(sample_pdf)
    assert lines
    
    # Verify some expected content
    header_lines = [l for l in lines if "STATEMENT_DATE:" in l or "CARD_NUMBER:" in l]
    assert len(header_lines) >= 2
    
    # Verify line numbers
    for line in lines:
        assert line.split("|")[0].isdigit()


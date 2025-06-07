import json
from pathlib import Path
import pytest
from statement_refinery.logging_handler import StatementLogHandler, ParseError, ParseWarning

@pytest.fixture
def log_handler(tmp_path):
    return StatementLogHandler(log_dir=tmp_path)

def test_log_error(log_handler):
    # Log a simple error
    log_handler.log_error("PARSE_ERROR", "Failed to parse line")
    assert len(log_handler.errors) == 1
    assert log_handler.errors[0].error_type == "PARSE_ERROR"
    assert log_handler.errors[0].message == "Failed to parse line"
    
    # Log error with line information
    log_handler.log_error(
        "INVALID_DATE",
        "Invalid date format",
        line_number=42,
        line_content="01/13 Invalid Date Line"
    )
    assert len(log_handler.errors) == 2
    assert log_handler.errors[1].line_number == 42
    assert log_handler.errors[1].line_content == "01/13 Invalid Date Line"

def test_log_warning(log_handler):
    # Log a simple warning
    log_handler.log_warning("UNUSUAL_AMOUNT", "Unusually large transaction")
    assert len(log_handler.warnings) == 1
    assert log_handler.warnings[0].warning_type == "UNUSUAL_AMOUNT"
    assert log_handler.warnings[0].message == "Unusually large transaction"
    
    # Log warning with line information
    log_handler.log_warning(
        "DUPLICATE_TXN",
        "Possible duplicate transaction",
        line_number=123,
        line_content="04/05 NETFLIX 45.90"
    )
    assert len(log_handler.warnings) == 2
    assert log_handler.warnings[1].line_number == 123
    assert log_handler.warnings[1].line_content == "04/05 NETFLIX 45.90"

def test_log_debug(log_handler):
    # Log debug information
    debug_data = {"merchant": "NETFLIX", "amount": 45.90, "recurring": True}
    log_handler.log_debug("merchant_analysis", debug_data)
    
    assert "merchant_analysis" in log_handler.debug_info
    assert log_handler.debug_info["merchant_analysis"] == debug_data

def test_write_summary(log_handler):
    # Add some errors and warnings
    log_handler.log_error("ERROR1", "First error")
    log_handler.log_error("ERROR2", "Second error", line_number=42)
    log_handler.log_warning("WARNING1", "First warning")
    log_handler.log_debug("section1", {"key": "value"})
    
    # Write summary
    log_handler.write_summary()
    
    # Check summary file exists and contains the expected content
    summary_path = log_handler.log_dir / "parse_summary.txt"
    assert summary_path.exists()
    
    content = summary_path.read_text()
    assert "=== ERRORS ===" in content
    assert "ERROR1: First error" in content
    assert "ERROR2: Second error" in content
    assert "=== WARNINGS ===" in content
    assert "WARNING1: First warning" in content
    assert "=== DEBUG INFO ===" in content
    assert "section1" in content

def test_get_summary_stats(log_handler):
    # Add some errors and warnings
    log_handler.log_error("TYPE_A", "Error 1")
    log_handler.log_error("TYPE_A", "Error 2")
    log_handler.log_error("TYPE_B", "Error 3")
    log_handler.log_warning("WARN_X", "Warning 1")
    log_handler.log_warning("WARN_Y", "Warning 2")
    
    stats = log_handler.get_summary_stats()
    assert stats["total_errors"] == 3
    assert stats["total_warnings"] == 2
    assert stats["unique_error_types"] == 2  # TYPE_A and TYPE_B
    assert stats["unique_warning_types"] == 2  # WARN_X and WARN_Y

def test_log_files_created(log_handler):
    # Verify that log files are created
    log_handler.log_error("TEST", "Test error")
    log_handler.write_summary()
    
    assert (log_handler.log_dir / "parse_debug.txt").exists()
    assert (log_handler.log_dir / "parse_summary.txt").exists()


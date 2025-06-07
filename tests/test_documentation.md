# Transaction Validation Test Documentation

## Test Data Files

### Special Formats (special_formats.txt)
Tests various special transaction formats including:
- Mixed format with special characters
- Multi-line transactions
- JSON-style format
- Tab-separated format
- Custom delimiter format

### International Edge Cases (international_edge.txt)
Tests complex international transaction scenarios including:
- Large amounts with European number formatting
- Arabic numerals and right-to-left text
- Chinese currency and character support
- Indian number format (lakhs/crores system)
- Mixed script transactions (Korean, English)

### Encoding Tests (encoding_test.txt)
Tests various encoding scenarios including:
- UTF-8 BOM handling
- UTF-16 character support
- Emoji in transaction descriptions
- Mixed encoding (Cyrillic, Unicode symbols)
- Special character escape sequences

### Invalid Formats (invalid_formats.txt)
Tests various invalid transaction formats including:
- Missing required fields
- Invalid amount formats
- Malformed delimiters
- Invalid character encoding
- Incomplete transactions

## Test Functions

### test_special_format_parsing()
Validates the parser's ability to handle various special transaction formats:
- Mixed format with special characters in description
- Multi-line transaction format
- JSON-like format parsing

### test_complex_international()
Validates handling of international transaction formats:
- European number formatting (dots as thousand separators)
- Arabic numeral systems
- Indian number format with lakhs

### test_encoding_variants()
Tests different encoding scenarios:
- UTF-8 BOM handling
- Unicode emoji support
- Mixed script support (Cyrillic, emoji)

### test_invalid_format_handling()
Verifies proper error handling for invalid formats:
- Missing required fields detection
- Invalid amount format validation
- Malformed delimiter handling

## Running Tests

To run all tests:
```bash
python -m unittest test_transaction_validation.py
```

To run a specific test case:
```bash
python -m unittest test_transaction_validation.TestTransactionValidation.test_special_format_parsing
```

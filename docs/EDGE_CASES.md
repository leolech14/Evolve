# Edge Cases and Error Handling Guide

## Transaction Processing Edge Cases

### 1. Date Formats

#### Valid Formats
- DD/MM format (standard)
- Single digit days/months with leading zeros

#### Invalid Formats
- US format (MM/DD)
- Invalid days (32/12)
- Invalid months (12/13)
- Missing components (00/00)

#### Resolution Strategy
- Validate day range (1-31)
- Validate month range (1-12)
- Enforce DD/MM format strictly
- Flag future dates for review

### 2. Amount Formats

#### Valid Formats
- Standard: 1.234,56
- With currency: R$ 1.234,56
- Negative formats:
  - -1.234,56
  - (1.234,56)
  - 1.234,56-
- Special cases:
  - ,50 → 0,50
  - 1234 → 1234,00

#### Invalid Formats
- US format (1,234.56)
- Multiple dots (1.234.56)
- Multiple commas (1,234,56)

#### Resolution Strategy
- Normalize amounts before parsing
- Handle various negative amount notations
- Convert partial amounts to full format
- Validate decimal places

### 3. International Transactions

#### Supported Formats
- Currency conversion format: AMOUNT_BRL CURRENCY_CODE AMOUNT_ORIG = FX_RATE BRL
- Example: "57,54 USD 9,99 = 5,76 BRL ROMA"

#### Components to Parse
- Original amount
- Currency code
- Exchange rate
- BRL amount
- Location (if present)

#### Resolution Strategy
- Validate currency codes
- Check exchange rate calculations
- Handle missing location data
- Flag multiple currencies in statement

### 4. Special Transactions

#### Types
- Payments: "PAGAMENTO EFETUADO"
- Refunds: "ESTORNO COMPRA"
- Fees: "IOF"
- Adjustments: "AJUSTE VALOR"
- Digital payments: "PAG*", "MP*"

#### Resolution Strategy
- Categorize transactions appropriately
- Strip processor prefixes
- Handle special transaction amounts
- Validate against expected formats

### 5. Installment Transactions

#### Valid Formats
- Format: XX/YY where:
  - XX = current installment (1-12)
  - YY = total installments (1-12)
- Examples:
  - 01/12 (first of twelve)
  - 12/12 (last installment)

#### Invalid Formats
- Invalid installment numbers (13/12)
- Invalid total installments (01/13)

#### Resolution Strategy
- Validate installment numbers
- Check total installments range
- Link related installments
- Ignore invalid formats

## Error Prevention and Handling

### 1. Input Validation

#### File Level
- UTF-8 encoding
- Correct line endings
- Required sections present

#### Transaction Level
- Required fields present
- Valid date format
- Valid amount format
- Complete transaction data

### 2. Recovery Mechanisms

#### Partial Recovery
- Continue processing valid transactions
- Log invalid transactions
- Generate warning for corrupt sections
- Maintain error context

#### Data Correction
- Normalize date formats
- Standardize amount formats
- Clean merchant names
- Handle encoding issues

### 3. Error Logging

#### Error Types
- HEADER_ERROR: Header parsing issues
- INVALID_LINE: Malformed transaction line
- INVALID_DATE: Date format problems
- INVALID_AMOUNT: Amount parsing errors
- ENCODING_ERROR: Character encoding issues

#### Warning Types
- FUTURE_DATE: Transactions dated after statement
- DUPLICATE_TRANSACTION: Repeated entries
- INVALID_INSTALLMENT: Installment format issues
- INTERNATIONAL_FX: Currency conversion problems

### 4. Edge Case Detection

#### Transaction Patterns
- Duplicate transactions same day
- Multiple currencies
- Unusual merchant names
- Suspicious amounts

#### Date Patterns
- Future dates
- Dates far from statement date
- Invalid date sequences

#### Amount Patterns
- Unusually large amounts
- Zero or negative amounts
- Inconsistent decimals

## Best Practices

### 1. Data Validation

- Validate input before processing
- Check for required fields
- Verify data consistency
- Handle special characters

### 2. Error Recovery

- Log all errors with context
- Continue processing when possible
- Maintain data integrity
- Provide clear error messages

### 3. Performance

- Handle large files efficiently
- Process in chunks if needed
- Minimize memory usage
- Optimize regex patterns

### 4. Maintenance

- Keep error documentation updated
- Monitor error patterns
- Update validation rules
- Review edge cases regularly

## Testing Recommendations

### 1. Test Cases

- Valid formats
- Invalid formats
- Edge cases
- Special transactions
- International transactions

### 2. Test Data

- Use real-world examples
- Include corner cases
- Test various encodings
- Cover all transaction types

### 3. Validation Tests

- Date format validation
- Amount format validation
- Character encoding
- Field completeness

### 4. Recovery Tests

- Partial file corruption
- Invalid data handling
- Error logging accuracy
- Warning generation

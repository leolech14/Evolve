# Transaction Parser Troubleshooting Guide

This guide provides comprehensive information for diagnosing and resolving common issues with the transaction parsing system.

## 1. Diagnostic Steps

### Reading parse_debug.txt Logs

The parse_debug.txt file contains detailed logging information about the parsing process:

- **Timestamp Format**: `[YYYY-MM-DD HH:MM:SS.mmm]`
- **Log Level**: `[INFO]`, `[WARNING]`, `[ERROR]`
- **Component**: Identifies the specific parser component (e.g., `[DateParser]`, `[AmountParser]`)
- **Message**: Detailed description of the operation or issue

Example:
```
[2024-01-20 10:15:23.456] [WARNING] [DateParser] Invalid date format encountered: "01.20.24"
```

### Understanding parse_summary.txt

The parse_summary.txt provides an overview of the parsing operation:

- Total records processed
- Success/failure counts
- Validation statistics
- Processing duration
- Error category breakdown

Key sections to review:
1. Overall Status (top of file)
2. Error Distribution (middle section)
3. Performance Metrics (bottom section)

### Using debug_info Sections

Debug info sections contain detailed diagnostic information:

1. **Transaction Context**:
   - Input line number
   - Raw transaction data
   - Intermediate parsing states

2. **Parser State**:
   - Active rules
   - Matched patterns
   - Applied transformations

3. **Validation Results**:
   - Field-level validation status
   - Applied business rules
   - Constraint violations

### Common Warning Patterns

1. **Format Warnings**:
   ```
   [WARNING] Expected format <X>, found <Y>
   [WARNING] Invalid character in field <Z>
   ```

2. **Data Consistency**:
   ```
   [WARNING] Amount mismatch detected
   [WARNING] Duplicate transaction ID
   ```

3. **Processing Issues**:
   ```
   [WARNING] Parser fallback mechanism activated
   [WARNING] Using default value for missing field
   ```

## 2. Common Issues

### Invalid Date Formats

Common scenarios:
- Mismatched regional formats (MM/DD/YY vs. DD/MM/YY)
- Incorrect century handling (98 vs 1998 vs 2098)
- Inconsistent separators (/, -, .)

Resolution steps:
1. Check source data format specification
2. Verify parser configuration matches source format
3. Update date format mapping if necessary

### Amount Parsing Errors

Typical problems:
- Decimal separator confusion (. vs ,)
- Thousand separator issues
- Currency symbol placement
- Negative amount representations

Verification steps:
1. Confirm source number format
2. Check currency-specific rules
3. Verify decimal precision requirements

### Duplicate Detection Issues

Areas to investigate:
- Transaction ID generation
- Timestamp precision
- Multiple processing of same file
- Cross-system synchronization

Resolution approach:
1. Review duplicate detection rules
2. Check transaction uniqueness criteria
3. Verify deduplication window settings

### Encoding Problems

Common symptoms:
- Garbled characters
- Missing data
- Unexpected line breaks
- Special character corruption

Troubleshooting steps:
1. Verify source file encoding
2. Check BOM presence/absence
3. Confirm parser encoding settings
4. Test with encoding conversion tools

### International Transaction Parsing

Special considerations:
- Multi-currency support
- Regional date formats
- Character set requirements
- Language-specific fields

Configuration checks:
1. Locale settings
2. Currency conversion rules
3. Regional format mappings

## 3. Resolution Workflows

### Data Validation Steps

1. **Input Validation**:
   - File format check
   - Required fields presence
   - Character encoding verification
   - Line termination consistency

2. **Content Validation**:
   - Data type compliance
   - Value range checks
   - Business rule validation
   - Cross-field consistency

3. **Output Validation**:
   - Format compliance
   - Data transformation accuracy
   - Totals reconciliation

### Format Correction Procedures

1. **Date Format Issues**:
   ```
   Original: 01.20.24
   Corrected: 2024-01-20
   ```
   - Update source data formatting
   - Adjust parser configuration
   - Add format transformation rules

2. **Amount Format Issues**:
   ```
   Original: 1,234.56
   Corrected: 1234.56
   ```
   - Standardize decimal/thousand separators
   - Update currency formatting rules
   - Adjust precision handling

3. **Text Encoding Issues**:
   - Convert to UTF-8 where possible
   - Remove invalid characters
   - Standardize line endings

### When to Regenerate TXT Files

Regeneration is necessary when:
1. Source data format changes
2. Business rules are updated
3. Encoding issues are discovered
4. Parsing rules are modified
5. Validation criteria change

Process:
1. Backup existing files
2. Clear processing cache
3. Regenerate with new settings
4. Validate output
5. Update documentation

### Reporting Bugs vs Data Issues

**Bug Criteria**:
- Parser crashes
- Incorrect output format
- Performance degradation
- Inconsistent behavior
- Configuration failures

**Data Issue Criteria**:
- Invalid input values
- Missing required fields
- Business rule violations
- Format inconsistencies
- Data quality problems

**Resolution Path**:
1. **For Bugs**:
   - Create detailed bug report
   - Provide minimal reproduction case
   - Include debug logs
   - Document environment details

2. **For Data Issues**:
   - Document data validation failures
   - Provide sample problematic records
   - Include business context
   - Suggest data corrections

# Error Handling and Prevention Guide

## Common Error Resolution Guide

### Step-by-Step Troubleshooting Process

1. **Check Error Message**
   - Read the complete error message
   - Note any error codes or specific identifiers
   - Identify which part of the process failed

2. **Verify Input Data**
   - Confirm all required fields are present
   - Check data formats match specifications
   - Look for special characters or encoding issues

3. **Review Logs**
   - Check application logs for related errors
   - Note timestamp of the error
   - Look for any preceding warning messages

4. **Test Similar Cases**
   - Try processing similar data
   - Identify if the issue is isolated or systemic
   - Document any patterns found

### Examples of Valid vs Invalid Formats

#### Statements
```
✅ Valid:
   STM-2023-12345
   STMT/20231231/001

❌ Invalid:
   STM_2023_12345 (incorrect separators)
   STMT-ABC-XYZ (missing numeric identifiers)
```

#### Dates
```
✅ Valid:
   2023-12-31
   31/12/2023

❌ Invalid:
   12/31/23 (incomplete year)
   2023.12.31 (incorrect separator)
```

#### Amounts
```
✅ Valid:
   1234.56
   1,234.56
   -123.45

❌ Invalid:
   1.234,56 (incorrect decimal separator)
   1234,56 (incorrect thousand separator)
```

### How to Use Debug Logs Effectively

1. **Enable Debug Mode**
   ```
   Set DEBUG_LEVEL=DEBUG in configuration
   ```

2. **Key Log Sections to Review**
   - Input validation logs
   - Processing stage logs
   - Error stack traces

3. **Common Debug Commands**
   ```
   tail -f debug.log | grep ERROR
   grep "Statement ID: ABC" debug.log
   ```

### When to Report Issues vs Fix Data

#### Fix Data When:
- Input formatting is incorrect but content is valid
- Date format needs conversion
- Amount separators need standardization
- Character encoding needs conversion

#### Report Issues When:
- Data is missing or corrupted
- Business rules are violated
- System errors occur
- Multiple failed attempts after data fixes

## Error Prevention Guide

### Statement Formatting Requirements

1. **Statement ID Format**
   - Prefix: 'STM-' or 'STMT/'
   - Year: YYYY format
   - Sequence: 5-digit number
   - Example: `STM-2023-12345` or `STMT/20231231/001`

2. **Content Structure**
   - One header record
   - Multiple detail records
   - One footer record
   - All fields comma-separated

### Date Format Specifications

1. **Accepted Formats**
   - ISO format: YYYY-MM-DD
   - Local format: DD/MM/YYYY

2. **Rules**
   - Years must be 4 digits
   - Months must be 01-12
   - Days must be valid for the month
   - Leading zeros required for single-digit days/months

### Amount Format Rules

1. **Number Format**
   - Decimal separator: period (.)
   - Thousand separator: comma (,)
   - Maximum 2 decimal places
   - Optional negative sign (-)

2. **Range Limitations**
   - Maximum: 999,999,999.99
   - Minimum: -999,999,999.99
   - No scientific notation allowed

### Character Encoding Requirements

1. **File Encoding**
   - UTF-8 required
   - No BOM (Byte Order Mark)
   - LF (\n) line endings

2. **Allowed Characters**
   - ASCII printable characters
   - Limited special characters: ,.-_()/
   - No emoji or special symbols
   - No control characters

3. **Text Fields**
   - No leading/trailing whitespace
   - No consecutive spaces
   - No tabs or other whitespace characters

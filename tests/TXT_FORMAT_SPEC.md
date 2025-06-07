# Itaú Credit Card Statement TXT Format Specification

## Overall Structure

1. Header Section (Lines 1-18)
   - Account and card identification
   - Statement dates and summary
   - Customer information

2. Financial Summary Section (Lines 19-31)
   - Total amount and due date
   - Payment options
   - Interest rates and financial calculations

3. Payment Information Section (Lines 32-68)
   - Bank details
   - Payment instructions
   - Barcode information
   - General notices

4. Transactions Section (Lines 69+)
   - Payments received
   - Current charges (organized by card)
   - International transactions
   - Installment purchases
   - Products and services

## Field Formats

### Header Information
- Statement number: Format 'A' followed by 9 digits
- Customer name: Full name in uppercase
- Address: Multiple lines including street, number, neighborhood, and ZIP code
- Card number: Masked format (e.g., '5234.XXXX.XXXX.6853')

### Financial Values
- Currency: Always in BRL (R$)
- Decimal separator: Comma (,)
- Thousands separator: Period (.)
- Interest rates: Percentage with 2 decimal places

### Transaction Records
1. Domestic Transactions:
   - Date: DD/MM format
   - Establishment name
   - Category (e.g., 'SAÚDE', 'ALIMENTAÇÃO')
   - Location
   - Amount in BRL

2. International Transactions:
   - Date
   - Establishment name
   - Original amount and currency
   - Conversion rate
   - Final amount in BRL
   - IOF details

### Special Markers
- '@' prefix: Virtual card transactions
- '~g' prefix: Digital wallet transactions
- '~h' prefix: Digital transactions
- Line continuations marked with 'Continua...'

## End of Statement
- Contains reference number
- Statement generation details
- Page numbering if applicable

## Important Notes
1. The format uses specific line breaks to separate sections
2. Transaction categories are consistently capitalized
3. Location information follows the establishment name after a period
4. International transactions include both original currency and BRL amounts
5. Line numbers are important for parsing and must be preserved


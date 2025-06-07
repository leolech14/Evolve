# Transaction Format Specifications

This document outlines the standardized formats for various types of financial transactions in our system.

## 1. Basic Transaction Formats

### Regular Domestic Transactions
```json
{
  "transaction_id": "DOM-YYYYMMDD-XXXXXXXX",  // Format: DOM-[Date]-[8-char hex]
  "amount": "1234.56",                      // Decimal format, 2 decimal places
  "currency": "USD",                        // 3-letter currency code
  "description": "Transaction description", // Max 100 characters
  "merchant_name": "MERCHANT NAME",        // Max 50 characters
  "transaction_date": "YYYY-MM-DD",        // ISO 8601 date format
  "status": "completed"                    // [completed, pending, failed]
}
```

### Payment Transactions
```json
{
  "transaction_id": "PAY-YYYYMMDD-XXXXXXXX",  // Format: PAY-[Date]-[8-char hex]
  "payment_type": "CREDIT",                  // [CREDIT, DEBIT, ACH, WIRE]
  "amount": "1234.56",
  "currency": "USD",
  "recipient_name": "Recipient Name",        // Max 100 characters
  "recipient_account": "XXXXXX1234",        // Last 4 digits visible
  "transaction_date": "YYYY-MM-DD",
  "status": "completed"
}
```

### Adjustment Transactions
```json
{
  "transaction_id": "ADJ-YYYYMMDD-XXXXXXXX",  // Format: ADJ-[Date]-[8-char hex]
  "original_transaction_id": "DOM-YYYYMMDD-XXXXXXXX",
  "adjustment_type": "REFUND",               // [REFUND, CHARGEBACK, CORRECTION]
  "amount": "1234.56",
  "currency": "USD",
  "reason_code": "RF001",                    // Predefined reason codes
  "description": "Adjustment reason",
  "transaction_date": "YYYY-MM-DD",
  "status": "completed"
}
```

### Service Charge Transactions
```json
{
  "transaction_id": "SVC-YYYYMMDD-XXXXXXXX",  // Format: SVC-[Date]-[8-char hex]
  "service_type": "MAINTENANCE",              // [MAINTENANCE, OVERDRAFT, WIRE_FEE]
  "amount": "25.00",
  "currency": "USD",
  "description": "Monthly maintenance fee",
  "transaction_date": "YYYY-MM-DD",
  "status": "completed"
}
```

## 2. Special Transaction Formats

### International Transactions with Currency Conversion
```json
{
  "transaction_id": "INT-YYYYMMDD-XXXXXXXX",  // Format: INT-[Date]-[8-char hex]
  "original_amount": "100.00",
  "original_currency": "EUR",
  "converted_amount": "110.25",
  "settlement_currency": "USD",
  "exchange_rate": "1.1025",
  "conversion_date": "YYYY-MM-DD",
  "merchant_name": "INTL MERCHANT NAME",
  "merchant_country": "FR",                  // ISO 3166-1 alpha-2 country code
  "transaction_date": "YYYY-MM-DD",
  "status": "completed"
}
```

### Installment Purchases
```json
{
  "transaction_id": "INS-YYYYMMDD-XXXXXXXX",  // Format: INS-[Date]-[8-char hex]
  "total_amount": "1200.00",
  "installment_amount": "100.00",
  "currency": "USD",
  "installment_number": 1,                    // Current installment number
  "total_installments": 12,                  // Total number of installments
  "merchant_name": "MERCHANT NAME",
  "transaction_date": "YYYY-MM-DD",
  "next_installment_date": "YYYY-MM-DD",
  "status": "active"                         // [active, completed, cancelled]
}
```

### Digital/Virtual Transactions
```json
{
  "transaction_id": "DIG-YYYYMMDD-XXXXXXXX",  // Format: DIG-[Date]-[8-char hex]
  "amount": "1234.56",
  "currency": "USD",
  "merchant_name": "DIGITAL MERCHANT",
  "platform": "MOBILE_APP",                  // [MOBILE_APP, WEB, IN_APP]
  "device_id": "DEVICE-XXXXX",               // Device identifier
  "ip_address": "XXX.XXX.XXX.XXX",          // IPv4/IPv6 address
  "transaction_date": "YYYY-MM-DD",
  "status": "completed"
}
```

### Merchant Prefixes
Special merchant prefixes must be handled according to these rules:
- `PAG*`: Payment aggregator transactions
  - Always include aggregator ID: `PAG*[AGGR_ID]*[MERCHANT_NAME]`
  - Example: `PAG*AGG123*SHOP NAME`

- `MP*`: Marketplace transactions
  - Include marketplace and seller IDs: `MP*[MKT_ID]*[SELLER_ID]*[MERCHANT_NAME]`
  - Example: `MP*MKT456*SEL789*SELLER NAME`

## 3. Edge Cases

### Negative Amounts
Negative amounts can appear in several formats:
```json
// Standard negative amount
{
  "amount": "-1234.56"
}

// Alternative format with separate sign field
{
  "amount": "1234.56",
  "sign": "negative"
}

// Credit/Debit indicator
{
  "amount": "1234.56",
  "type": "credit"  // credit = negative, debit = positive
}
```

### Zero Amount Transactions
Zero amount transactions are valid and must be handled:
```json
{
  "amount": "0.00",
  "requires_approval": true,     // Special flag for zero-amount transactions
  "purpose": "VERIFICATION"      // [VERIFICATION, HOLD, AUTH_ONLY]
}
```

### Special Characters in Descriptions
Description fields must handle:
- Unicode characters (including emojis)
- HTML entities (must be escaped)
- Special characters (`&`, `<`, `>`, `"`, `'`)

Example:
```json
{
  "description": "Café & Restaurant 🍽️",    // Unicode characters allowed
  "merchant_name": "O'Brien's & Co.",      // Special characters escaped
  "note": "Gift for John & Jane <3"        // HTML entities escaped
}
```

### Multiple Currency Formats
Supported currency formats:
```json
// Major currency units
{
  "amount": "1234.56",        // 2 decimal places
  "currency": "USD"
}

// Minor currency units
{
  "amount": "1234",          // No decimal places
  "currency": "JPY"
}

// Custom decimal places
{
  "amount": "1234.567",      // 3 decimal places
  "currency": "BHD"
}

// Cryptocurrency
{
  "amount": "0.12345678",    // 8 decimal places
  "currency": "BTC"
}
```

All currency formats must follow ISO 4217 standards for official currencies and established conventions for cryptocurrencies.

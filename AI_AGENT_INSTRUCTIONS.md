# 🤖 AI Agent Instructions for Parser Improvement

## 🎯 YOUR MISSION
Improve the Itaú statement parser from current 65% accuracy to 99% financial accuracy.

## ❌ IGNORE THESE MISLEADING METRICS
- CSV-to-CSV matching percentages (always shows 100% against fake goldens)
- "golden_*.csv" files (except 2024-10 and 2025-05 which are real)
- Traditional accuracy checks that compare against generated CSVs

## ✅ FOCUS ON THESE REAL METRICS
- **Financial accuracy**: Parsed total vs PDF total amount
- **Missing BRL amounts**: How much money is not being captured
- **Parse debug logs**: Which transaction lines are being skipped

## 📊 CURRENT STATUS (Check diagnostics/ai_focused_accuracy.json)
- **Worst offenders**: 2024-09 (5.7%), 2024-08 (55%), 2025-04 (-148%)
- **Total missing**: ~100,000 BRL across all statements
- **Pattern**: Most transactions not being parsed at all

## 🔍 DIAGNOSTIC DATA LOCATIONS
- `diagnostics/parse_debug.txt` - Line-by-line parsing attempts
- `diagnostics/ai_focused_accuracy.txt` - Real accuracy per PDF
- `tests/data/*.txt` - Raw extracted text from PDFs
- `diagnostics/real_accuracy.json` - Financial totals comparison

## 🔧 IMPROVEMENT STRATEGY
1. **Analyze failed lines** in parse_debug.txt
2. **Study transaction patterns** in *.txt files
3. **Create new regex patterns** in src/statement_refinery/pdf_to_csv.py
4. **Test against financial totals**, not fake CSVs

## 📝 SAMPLE UNPARSED TRANSACTION PATTERNS
```
28/05 FARMACIA SAO JOAO 04/06 39,40
10/06 FARMACIA SAO JOAO 03/06 87,64  
16/06 RECARGAPAY *LEONA03/12 11,63
```

## 🎯 SUCCESS CRITERIA
- All PDFs reach >95% financial accuracy vs PDF total
- Missing BRL amounts reduced to <5% per statement
- Parse debug shows successful parsing of transaction lines

## 🚨 CRITICAL INSIGHT
The parser works for some patterns but misses many transaction formats. Your job is to identify and add the missing regex patterns to capture these transactions.

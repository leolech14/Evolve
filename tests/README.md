# Test Data Organization

This directory contains organized test data for the Itau statement parser project.

## Directory Structure

### training_data/
- Contains verified golden files (CSV) and their corresponding PDF/TXT pairs
- Used for parser development and training
- Currently includes: 2024-10 and 2025-05 datasets

### validation_data/
- Contains PDF files with corresponding TXT files
- Used for validation during development
- No golden files, used for testing parser accuracy

### test_data/
- Contains standalone PDF files
- Used for final testing and evaluation
- No golden files or TXT files

### data_evaluation/
- Temporary directory containing unverified CSV files
- Files need to be validated before moving to training_data
- Source: Legacy data directory

## File Naming Convention

- PDF files: `itau_YYYY-MM.pdf`
- TXT files: `itau_YYYY-MM.txt`
- Golden files: `golden_YYYY-MM.csv`

# Test Data Organization

This directory contains test data organized into three categories:

## training_data/
Contains verified golden files and their corresponding PDFs/TXTs that are known to work correctly. Used to:
- Train and validate the parser
- Ensure basic functionality remains intact
- Serve as examples for adding new test cases

Files:
- golden_2024-10.csv + itau_2024-10.{pdf,txt}
- golden_2025-05.csv + itau_2025-05.{pdf,txt}

## validation_data/
Contains PDFs that have corresponding TXT files but no golden CSVs yet. Used to:
- Validate parser improvements
- Test TXT format handling
- Create new golden files once parser is stable

## test_data/
Contains PDFs without TXT files or golden CSVs. Used to:
- Final testing of parser
- Edge case detection
- Future golden file creation

## data/
Legacy directory containing original test files. Will be deprecated once migration is complete.

# Adding New Test Cases

1. Start by creating a TXT version of your PDF using the pdf-to-txt tool
2. Add both PDF and TXT to validation_data/
3. Run parser tests and analyze results
4. Once parser successfully handles the file, create golden CSV and move to training_data/


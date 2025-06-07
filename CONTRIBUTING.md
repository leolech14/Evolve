# Contributing to Evolve

Thanks for your interest in improving Evolve! This guide explains how to contribute effectively and work with our AI-assisted development workflow.

## Getting Started

1. Set up your development environment:
   ```bash
   # Clone the repository
   git clone https://github.com/leolech14/Evolve.git
   cd Evolve

   # Install with development dependencies
   pip install -e '.[dev]'
   ```

2. Create a new branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

## Development Workflow

### 1. Write Tests First
We follow a test-driven development approach:

1. Write a test that describes the expected behavior
2. Run tests to see it fail
3. Implement the feature
4. Run tests to verify it works

### 2. Use AI Assistance
The project includes AI-powered tools to help with development:

```bash
# Set your OpenAI API key
export OPENAI_API_KEY=your-key-here

# Run the auto-patch tool
python .github/tools/evolve.py
```

The AI tool will:
- Analyze test failures
- Suggest code improvements
- Create pull requests with fixes

### 3. Manual Review
Even with AI assistance, always review changes carefully:
- Check test coverage
- Verify parser accuracy
- Review suggested patches

## Testing

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=statement_refinery

# Run specific test file
pytest tests/test_specific.py
```

### Testing with Sample Data
1. Place test PDFs in `tests/data/`
2. Create matching golden CSVs named `golden_*.csv`
3. Run accuracy check:
   ```bash
   python scripts/check_accuracy.py --threshold 99
   ```

## Code Style

### Automatic Formatting
```bash
# Format code
black src/ tests/

# Check style
ruff check .

# Type checking
mypy src/
```

### Style Guidelines
- Use descriptive variable names
- Add docstrings to functions and classes
- Keep functions focused and small
- Comment complex logic

## Pull Requests

1. Ensure all tests pass
2. Update documentation if needed
3. Add test cases for new features
4. Keep changes focused and atomic

The CI pipeline will:
1. Run all tests and checks
2. Verify parser accuracy
3. Generate test coverage report
4. Try AI-powered fixes if needed

## Release Process

1. Update version in `pyproject.toml`
2. Add changelog entry
3. Create release PR
4. Wait for CI approval
5. Merge and tag release

## Getting Help

- Check existing issues and pull requests
- Use descriptive titles for new issues
- Include minimal test cases
- Add debugging logs if relevant

## Project Structure

```
Evolve/
├── src/statement_refinery/  # Core package code
│   ├── cli.py              # Command-line interface
│   ├── pdf_to_csv.py       # PDF conversion
│   ├── pdf_to_txt.py       # Text extraction
│   └── txt_parser.py       # Parser logic
├── tests/                  # Test files
│   ├── data/              # Test data
│   │   ├── itau_*.pdf    # Test PDFs
│   │   └── golden_*.csv  # Expected output
│   └── test_*.py         # Test modules
└── scripts/               # Utility scripts
    ├── check_accuracy.py  # Accuracy checker
    └── ci_summary.py      # CI reporting
```

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

# Contributing

Thank you for wanting to improve Statement Refinery! Follow these steps to submit changes.

1. Fork the repository and create a branch from `main`.
2. Install development dependencies:

   ```bash
   pip install -e '.[dev]'
   ```
3. Run linters and tests before committing:

   ```bash
   ruff check .
   black --check .
   mypy src/
   pytest -ra -vv
   ```
4. Ensure coverage stays above **90%**.
5. Open a pull request describing your changes.

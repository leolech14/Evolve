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

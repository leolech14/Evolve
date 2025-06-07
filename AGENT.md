# Agent Instructions for statement_refinery

## Commands
- **Lint**: `make lint` (runs ruff, black, mypy)
- **Test**: `make test` (pytest with verbose output)
- **Single test**: `pytest -v tests/test_filename.py::test_function_name`
- **Accuracy check**: `make accuracy` (validates parsing accuracy)
- **All checks**: `make all` (lint + test + accuracy)

## Code Style
- **Language**: Python 3.10+, target Python 3.12
- **Line length**: 88 characters (Black/Ruff standard)
- **Imports**: Use `from __future__ import annotations` for modern type hints
- **Type hints**: Use explicit typing with Final for constants
- **Formatting**: Ruff + Black (configured in pyproject.toml)
- **Naming**: snake_case for functions/variables, UPPER_CASE for constants
- **Docstrings**: Use triple quotes with clear descriptions
- **Error handling**: Use specific exception types, not bare except
- **Constants**: Define with `Final` annotation at module level
- **Regex**: Use compiled patterns with descriptive names (RE_PREFIX)

## Project Structure
- Source code: `src/statement_refinery/`
- Tests: `tests/` (pytest framework)
- CLI entry point: `evolve` command via pyproject.toml scripts

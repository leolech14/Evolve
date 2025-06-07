.PHONY: lint test accuracy all

lint:
	pre-commit run --all-files

test:
	pytest -ra -vv --cov=statement_refinery --cov-report=term-missing --cov-fail-under=90

accuracy:
	python scripts/check_accuracy.py

all: lint test accuracy

.PHONY: lint test accuracy all

lint:
	ruff check .
	black --check .
	mypy src/

test:
	pytest -v

accuracy:
	python scripts/check_accuracy.py --threshold 99 --csv-dir csv_output

all: lint test accuracy

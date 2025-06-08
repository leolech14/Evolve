.PHONY: lint test accuracy invariants hard-goldens parse all-new all

lint:
	ruff check .
	black --check .
	mypy src/

test:
	pytest -v

# New two-tier validation system
parse:
	python scripts/parse_all.py --out csv_output

hard-goldens:
	python scripts/check_hard_goldens.py

invariants:
	python -m pytest tests/test_invariants.py --csv-dir csv_output -v

# Legacy accuracy check
accuracy:
	python scripts/check_accuracy.py --threshold 99 --csv-dir csv_output

# New comprehensive validation
all-new: lint test parse hard-goldens invariants

# Legacy comprehensive check
all: lint test accuracy

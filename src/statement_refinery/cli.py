"""CLI entry point for statement_refinery package."""

from __future__ import annotations

import sys
from statement_refinery.pdf_to_csv import main


def main_cli() -> None:
    """Main CLI entry point called by 'evolve' command."""
    main(sys.argv[1:])


if __name__ == "__main__":
    main_cli()

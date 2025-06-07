from decimal import Decimal, InvalidOperation
import re
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


def parse_amount(amount_str: str) -> Optional[Decimal]:
    """
    Parse a Brazilian currency string to a Decimal.
    Handles formats like 'R$ 1.234,56' and negative values.
    Returns None if parsing fails.
    """
    if not amount_str:
        logger.warning("Empty amount string passed to parse_amount.")
        return None

    clean = amount_str.strip()
    negative = False

    # Handle negative sign (can be at the end or start)
    if clean.endswith('-'):
        negative = True
        clean = clean[:-1].strip()
    elif clean.startswith('-'):
        negative = True
        clean = clean[1:].strip()

    # Remove currency symbols and spaces
    clean = re.sub(r"[^\d,.\-]", "", clean)

    # Convert Brazilian format to standard
    if "," in clean and "." in clean:
        # '1.234,56' -> '1234.56'
        clean = clean.replace(".", "").replace(",", ".")
    elif "," in clean:
        # '1234,56' -> '1234.56'
        clean = clean.replace(",", ".")
    clean = clean.strip(".")

    try:
        result = Decimal(clean)
        if negative and result >= 0:
            result = -result
        return result
    except (InvalidOperation, ValueError) as e:
        logger.error(f"Failed to parse amount '{amount_str}': {e}")
        return None


def pdf_to_csv(pdf_path: str, csv_path: str) -> None:
    """
    Main entry point: Convert an Itaú PDF statement to a CSV file.
    """
    import pdfplumber
    import csv

    try:
        with pdfplumber.open(pdf_path) as pdf, open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            # Write CSV header (customize as needed)
            writer.writerow(["Date", "Description", "Amount", "Balance"])

            for page in pdf.pages:
                # Extract text, parse lines, and extract fields
                lines = page.extract_text().split('\n')
                for line in lines:
                    # Example: parse fields from line (customize regex as needed)
                    # This is a placeholder; real implementation depends on Itaú statement format
                    match = re.match(r"(\d{2}/\d{2}/\d{4})\s+(.+?)\s+([R\$ \d\.,\-]+)\s+([R\$ \d\.,\-]+)", line)
                    if match:
                        date, desc, amount_str, balance_str = match.groups()
                        amount = parse_amount(amount_str)
                        balance = parse_amount(balance_str)
                        writer.writerow([date, desc, amount, balance])
    except Exception as e:
        logger.error(f"Error processing PDF '{pdf_path}': {e}")
        raise


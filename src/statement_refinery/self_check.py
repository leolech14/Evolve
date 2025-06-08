from decimal import Decimal
from statement_refinery import pdf_to_csv
from statement_refinery.summary import extract as extract_summary


def fitness(pdf_path: str) -> float:
    csv_rows = pdf_to_csv.parse_pdf(pdf_path)  # ← existing in repo
    summary = extract_summary(pdf_path)

    def sum_if(predicate):
        return sum(Decimal(r.amount_brl) for r in csv_rows if predicate(r))

    domestic = sum_if(lambda r: r.currency == "BRL")
    foreign = sum_if(lambda r: r.currency != "BRL")
    total = sum_if(lambda r: True)
    deltas = [
        abs(domestic - summary.get("domestic_total", domestic)),
        abs(foreign - summary.get("foreign_total", foreign)),
        abs(total - summary.get("total_due", total)),
    ]
    # negative so “higher is better”
    return -float(sum(deltas))

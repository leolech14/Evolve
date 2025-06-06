import json
import os
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

summary_lines = []

# Static checks result from env
static_result = os.environ.get("STATIC_RESULT", "success")
static_ok = static_result == "success"
summary_lines.append(
    f"{'\u2705' if static_ok else '\u274c'} Static checks: {'PASS' if static_ok else 'FAIL'}"
)
all_ok = static_ok

# Unit tests
tests_outcome = os.getenv("TESTS_OUTCOME", "success")
try:
    report = json.loads(Path("report.json").read_text())
    total = report.get("summary", {}).get("total", 0)
    passed = report.get("summary", {}).get("passed", 0)
    skipped = total - passed
except Exception:
    total = passed = skipped = 0

tests_ok = tests_outcome == "success" and skipped == 0
summary_lines.append(
    f"{'\u2705' if tests_ok else '\u274c'} Unit tests:    {'PASS' if tests_ok else 'FAIL'} ({skipped} skipped)"
)
all_ok = all_ok and tests_ok

# Parser accuracy
accuracy_outcome = os.getenv("ACCURACY_OUTCOME", "success")
try:
    acc = json.loads(Path("accuracy_summary.json").read_text())
    pct = acc.get("average", 0.0)
    count = acc.get("pdf_count", 0)
except Exception:
    pct = 0.0
    count = 0
accuracy_ok = accuracy_outcome == "success"
summary_lines.append(
    f"{'\u2705' if accuracy_ok else '\u274c'} Parser accuracy: {'PASS' if accuracy_ok else 'FAIL'} ({pct:.1f} %, {count} PDFs)"
)
all_ok = all_ok and accuracy_ok

# Coverage
cov_pct = 0.0
try:
    root = ET.parse("coverage.xml").getroot()
    cov_pct = float(root.get("line-rate", 0)) * 100
except Exception:
    pass
coverage_ok = cov_pct >= 90.0 and tests_outcome == "success"
summary_lines.append(
    f"{'\u2705' if coverage_ok else '\u274c'} Coverage:      {'PASS' if coverage_ok else 'FAIL'} ({cov_pct:.1f} %)"
)
all_ok = all_ok and coverage_ok

# Evolve prerequisites
prereq_outcome = os.getenv("EVOLVE_PREREQS_OUTCOME", "skipped")
prereq_ok = prereq_outcome == "success"
summary_lines.append(
    f"{'\u2705' if prereq_ok else '\u274c'} Evolve prereqs: {'PASS' if prereq_ok else 'FAIL'}"
)
all_ok = all_ok and prereq_ok

# Evolve loop
loop_outcome = os.getenv("EVOLVE_OUTCOME", "skipped")
if loop_outcome == "skipped":
    loop_status = "SKIPPED (nothing to fix)"
    loop_ok = True
elif loop_outcome == "success":
    loop_status = "RAN (build fixed)"
    loop_ok = True
else:
    loop_status = "RAN (still red)"
    loop_ok = False
summary_lines.append(
    f"{'\u2705' if loop_ok else '\u274c'} Evolve loop:   {loop_status}"
)
all_ok = all_ok and loop_ok

summary_lines.append("")
summary_lines.append(
    f"\ud83c\udfd1 RESULT: {'PARSER READY' if all_ok else 'NOT READY'}"
)

with open(os.environ.get("GITHUB_STEP_SUMMARY", "summary.txt"), "a") as fh:
    fh.write("\n".join(summary_lines) + "\n")

if not all_ok:
    sys.exit(1)
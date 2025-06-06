import json
import os
import sys
from datetime import datetime, UTC
from pathlib import Path
import xml.etree.ElementTree as ET

CHECK = "\N{WHITE HEAVY CHECK MARK}"
CROSS = "\N{CROSS MARK}"
NEUTRAL = "\N{HEAVY MINUS SIGN}"
ENCODING = "utf-8"


FLAG = "\N{CHEQUERED FLAG}"

summary_lines: list[str] = []

# Static checks result from env
static_result = os.environ.get("STATIC_RESULT", "success")
static_ok = static_result == "success"
summary_lines.append(f"{CHECK if static_ok else CROSS} Static checks")
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
summary_lines.append(f"{CHECK if tests_ok else CROSS} Unit tests ({skipped} skipped)")
all_ok = all_ok and tests_ok

# Parser accuracy
accuracy_outcome = os.getenv("ACCURACY_OUTCOME", "success")
try:
    acc = json.loads(Path("accuracy_summary.json").read_text())
    pct = acc.get("average", 0.0)
    count = acc.get("pdf_count", 0)
    mismatched = acc.get("mismatched", 0)
    max_delta = acc.get("max_delta", 0.0)
except Exception:
    pct = 0.0
    count = 0
    mismatched = 0
    max_delta = 0.0
accuracy_ok = accuracy_outcome == "success"
if accuracy_ok:
    line = f"{CHECK} Parser accuracy ({pct:.1f}% avg)"
else:
    line = (
        f"{CROSS} Parser accuracy ({mismatched} PDFs off by \u22651 row, "
        f"biggest delta: {max_delta:.2f} BRL)"
    )
summary_lines.append(line)
all_ok = all_ok and accuracy_ok

# Coverage
cov_pct = 0.0
try:
    root = ET.parse("coverage.xml").getroot()
    cov_pct = float(root.get("line-rate", 0)) * 100
except Exception:
    pass
summary_lines.append(f"{NEUTRAL} Coverage      ({cov_pct:.1f} %)")


# Evolve loop
loop_outcome = os.getenv("EVOLVE_OUTCOME", "skipped")
if loop_outcome == "skipped":
    loop_status = "skipped – all green"
elif loop_outcome == "success":
    loop_status = "ran (build fixed)"
else:
    loop_status = "ran (still red)"
summary_lines.append(f"{NEUTRAL} Evolve loop   ({loop_status})")

summary_lines.append("")
summary_lines.append(f"{FLAG} RESULT: {'PARSER READY' if all_ok else 'NOT READY'}")

summary_text = "\n".join(summary_lines) + "\n"
summary_text = summary_text.encode(ENCODING, "replace").decode(ENCODING, "replace")

summary_file = os.environ.get("GITHUB_STEP_SUMMARY", "summary.txt")
diag_dir = Path("diagnostics")
diag_dir.mkdir(exist_ok=True)
diag_path = diag_dir / f"ci_summary_{datetime.now(UTC).strftime('%Y%m%d')}.txt"
try:
    with open(summary_file, "w", encoding=ENCODING, errors="replace") as fh:
        fh.write(summary_text)
    diag_path.write_text(summary_text, encoding=ENCODING)
except Exception:
    sys.stdout.write(summary_text)
    sys.exit(0)

if not all_ok:
    sys.exit(1)

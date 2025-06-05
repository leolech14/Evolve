import importlib
import os
import sys

missing = False
try:
    importlib.import_module("openai")
except Exception:
    sys.stderr.write("Missing `openai` package\n")
    missing = True

if not os.getenv("OPENAI_API_KEY"):
    sys.stderr.write("OPENAI_API_KEY not set\n")
    missing = True

if not os.getenv("PERSONAL_ACCESS_TOKEN_CLASSIC"):
    sys.stderr.write("PERSONAL_ACCESS_TOKEN_CLASSIC not set\n")
    missing = True

if missing:
    sys.exit(1)

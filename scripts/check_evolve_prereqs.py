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

tok = os.getenv("MAX_TOKENS_PER_RUN")
if tok is None or int(tok) > 200000:
    sys.stderr.write("MAX_TOKENS_PER_RUN unset or too high\n")
    missing = True

pat = os.getenv("PERSONAL_ACCESS_TOKEN_CLASSIC") or os.getenv("GH_TOKEN")
gh_token = os.getenv("GITHUB_TOKEN")
requires_pat = os.getenv("PROTECTED_BRANCH_PUSH", "false").lower() in {
    "1",
    "true",
    "yes",
}

if not (pat or gh_token):
    sys.stderr.write("Missing GitHub token\n")
    missing = True
elif requires_pat and not pat:
    sys.stderr.write("PERSONAL_ACCESS_TOKEN_CLASSIC not set\n")
    missing = True

if missing:
    sys.exit(1)

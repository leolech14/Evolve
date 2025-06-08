import textwrap
import re

def ask_llm(prompt):
    # Dummy implementation; replace with actual LLM call
    return ""

def looks_destructive(patch):
    deleted_test_lines = [
        ln for ln in patch.splitlines() if ln.startswith("-") and "def test_" in ln
    ]
    return bool(deleted_test_lines)

def main():
    prompt = "your prompt here"
    empty_iterations = 0
    while True:
        patch = ask_llm(prompt)

        # ------------------------------------------------------------------
        # Reject “destructive” patches that delete tests; we only allow edits
        # or additions inside the tests/ dir, never full removals.
        # ------------------------------------------------------------------
        if looks_destructive(patch):
            print("⛔  Patch would delete tests – rejected.")
            empty_iterations += 1
            continue

        # ... rest of your loop logic ...

if __name__ == "__main__":
    main()
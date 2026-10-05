"""Run classifier.py against the cases in evals/cases.json and report PASS/FAIL.

Usage: python eval.py [path/to/cases.json]

The model under test is whatever CHAT_MODEL is set to (default minimax/minimax-m3).
Checks are written independently of classifier.py so a bug in its validation
cannot hide here.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLASSIFIER = HERE / "classifier.py"
DEFAULT_CASES = HERE / "evals" / "cases.json"
TIMEOUT_SECONDS = 60

URGENCIES = {"low", "medium", "high"}


def check_case(case):
    """Run one case; return a list of failure descriptions (empty means pass)."""
    try:
        proc = subprocess.run(
            [sys.executable, str(CLASSIFIER), case["message"]],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return [f"classifier did not finish within {TIMEOUT_SECONDS}s"]

    if proc.returncode != 0:
        return [f"exit code {proc.returncode}: {proc.stderr.strip()}"]

    # Spec #8: stdout is a single JSON object, allowing one trailing newline.
    out = proc.stdout
    if out.endswith("\n"):
        out = out[:-1]
    if out != out.strip() or "\n" in out:
        return [f"stdout is not a single JSON line: {proc.stdout!r}"]
    try:
        result = json.loads(out)
    except json.JSONDecodeError:
        return [f"stdout is not valid JSON: {proc.stdout!r}"]
    if not isinstance(result, dict):
        return ["stdout JSON is not an object"]

    failures = []
    category = result.get("category")
    if category not in case["allowed_categories"]:
        failures.append(f"category {category!r} not in {case['allowed_categories']}")
    if result.get("urgency") not in URGENCIES:
        failures.append(f"urgency {result.get('urgency')!r} not in {sorted(URGENCIES)}")

    # Spec #7: reason format.
    reason = result.get("reason")
    if not isinstance(reason, str):
        failures.append("reason is not a string")
    else:
        if not reason.endswith("."):
            failures.append("reason does not end with a period")
        if re.search(r"[.!?]\s+\S", reason):
            failures.append("reason is more than one sentence")
        if len(reason.split()) >= 30:
            failures.append(f"reason has {len(reason.split())} words (limit: under 30)")
        if re.search(r"[*`#]", reason):
            failures.append("reason contains Markdown")
        if '\\"' in reason or "\\'" in reason:
            failures.append("reason contains escaped quotes")
    return failures


def main():
    cases_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CASES
    cases = json.loads(cases_path.read_text(encoding="utf-8"))
    model = os.environ.get("CHAT_MODEL") or "minimax/minimax-m3"

    passed = 0
    for case in cases:
        failures = check_case(case)
        if failures:
            print(f"FAIL {case['id']}: " + "; ".join(failures))
        else:
            passed += 1
            print(f"PASS {case['id']}")

    print(f"{passed}/{len(cases)} passed (model: {model})")
    sys.exit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()

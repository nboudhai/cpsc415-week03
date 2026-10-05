"""Classify one support message and print JSON with category, urgency, and reason.

Usage: python classifier.py "<support message>"

Implements spec.md. Standard library only.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "minimax/minimax-m3"
TIMEOUT_SECONDS = 30

CATEGORIES = {"billing", "technical", "sales", "unknown"}
URGENCIES = {"low", "medium", "high"}
MAX_REASON_WORDS = 30

# Exit codes from spec.md "Failure handling".
EXIT_USAGE = 2
EXIT_NO_KEY = 3
EXIT_HTTP = 4
EXIT_EMPTY = 5
EXIT_BAD_JSON = 6
EXIT_SCHEMA = 7

SYSTEM_PROMPT = """You classify customer support messages for a ticket router.

Respond with only a JSON object, no other text, in exactly this shape:
{"category": "...", "urgency": "...", "reason": "..."}

category is one of:
- "billing": charges, invoices, refunds, payments, subscriptions.
- "technical": bugs, errors, outages, login problems, product not working.
- "sales": pricing questions, plans, upgrades, purchasing, demos.
- "unknown": the message is not a real support request (spam, random chatter,
  gibberish, or a thank-you with no open issue), or it falls completely
  outside billing, technical, and sales.
If a real support request fits two categories, choose the one that fits best.
Never use "unknown" for a real support request that fits billing, technical,
or sales.

urgency is one of:
- "low": general questions, feedback, or minor issues where the user can still operate.
- "medium": core functionality is degraded or broken, but a workaround exists.
- "high": complete service blockage, data loss, or an urgent billing failure preventing access.

reason justifies both the category and the urgency. It must be exactly one
plain-prose sentence ending with a period, under 30 words, with no Markdown
and no quotation marks. Example:
Classified as technical with high urgency because the user is completely locked out of production systems."""


def fail(code, message):
    print(f"classifier: {message}", file=sys.stderr)
    sys.exit(code)


def call_model(message, api_key, base_url, model):
    body = {
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message},
        ],
    }
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        excerpt = e.read().decode("utf-8", errors="replace")[:300]
        fail(EXIT_HTTP, f"HTTP {e.code} from model endpoint: {excerpt}")
    except urllib.error.URLError as e:
        fail(EXIT_HTTP, f"could not reach model endpoint: {e.reason}")
    except TimeoutError:
        fail(EXIT_HTTP, f"model endpoint timed out after {TIMEOUT_SECONDS}s")

    try:
        envelope = json.loads(raw)
    except json.JSONDecodeError:
        fail(EXIT_BAD_JSON, f"endpoint returned non-JSON body: {raw[:300]}")
    try:
        content = envelope["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        fail(EXIT_EMPTY, f"endpoint response has no message content: {raw[:300]}")
    if not content or not content.strip():
        fail(EXIT_EMPTY, "model returned an empty response")
    return content


def strip_code_fence(text):
    text = text.strip()
    match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1) if match else text


def schema_errors(result):
    """Return a list of schema violations; empty means valid."""
    if not isinstance(result, dict):
        return ["response is not a JSON object"]
    errors = []
    expected = {"category", "urgency", "reason"}
    if set(result) != expected:
        errors.append(f"keys must be exactly {sorted(expected)}, got {sorted(result)}")
    if result.get("category") not in CATEGORIES:
        errors.append(f"invalid category {result.get('category')!r}")
    if result.get("urgency") not in URGENCIES:
        errors.append(f"invalid urgency {result.get('urgency')!r}")
    reason = result.get("reason")
    if not isinstance(reason, str):
        errors.append("reason must be a string")
    else:
        errors.extend(reason_errors(reason))
    return errors


def reason_errors(reason):
    errors = []
    reason = reason.strip()
    if not reason.endswith("."):
        errors.append("reason must end with a period")
    # A sentence break is terminal punctuation followed by whitespace before the end.
    if re.search(r"[.!?]\s+\S", reason):
        errors.append("reason must be exactly one sentence")
    if len(reason.split()) >= MAX_REASON_WORDS:
        errors.append(f"reason must be under {MAX_REASON_WORDS} words")
    if re.search(r"[*`#]", reason):
        errors.append("reason must not contain Markdown")
    if '\\"' in reason or "\\'" in reason:
        errors.append("reason must not contain escaped quotes")
    return errors


def main():
    if len(sys.argv) != 2 or not sys.argv[1].strip():
        fail(EXIT_USAGE, 'usage: python classifier.py "<support message>"')
    message = sys.argv[1]

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        fail(EXIT_NO_KEY, "OPENROUTER_API_KEY is not set")
    base_url = os.environ.get("CHAT_BASE_URL") or DEFAULT_BASE_URL
    model = os.environ.get("CHAT_MODEL") or DEFAULT_MODEL

    content = call_model(message, api_key, base_url, model)
    try:
        result = json.loads(strip_code_fence(content))
    except json.JSONDecodeError:
        fail(EXIT_BAD_JSON, f"model response is not valid JSON: {content[:300]}")

    errors = schema_errors(result)
    if errors:
        fail(EXIT_SCHEMA, "model response violates schema: " + "; ".join(errors))

    print(json.dumps(result))


if __name__ == "__main__":
    main()

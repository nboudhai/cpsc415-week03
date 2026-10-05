# Spec

## Intent
Implements [`intent/classifier.md`](intent/classifier.md).

## Components

### classifier
- **What it does:** reads one support message from a positional CLI argument, sends it to a chat model with a prompt that constrains the response to a JSON object, and prints that JSON object (`category`, `urgency`, `reason`) to stdout. Fails loud on any error.
- **Language:** Python. **Why:** the `CLAUDE.md` working rules already pin Python for this lab, and the work fits the standard library cleanly: `urllib.request` covers the chat-completions call, `json` covers parsing the model's response, `sys.argv` covers the CLI arg, and `os.environ` covers configuration. Java was considered and is permitted by the course, but `java.net.http.HttpClient` plus a manual `main` plus the lack of a pre-existing build file would add a class of boilerplate (request/response objects, checked exceptions, JSON via a non-stdlib jar that the working rules explicitly discourage for Python) that earns nothing at this size. The trade-off: Python gives up some compile-time safety, but the structured output and a small eval cover the same ground without the overhead.
- **Model:** `minimax/minimax-m3` is the primary candidate, with `xiaomi/mimo-v2.6-flash` as the eval alternative. **Why:** both candidates are cheap-tier models accessible through the same OpenAI-compatible endpoint, so the eval can swap them by changing `CHAT_MODEL` with no code change. The cheap-vs-cheap framing (rather than cheap-vs-frontier) is deliberate: the label space is small and constrained (`category` has four values, `urgency` has three, `reason` is one sentence), so a frontier model is unlikely to be necessary and would inflate the per-ticket cost of the triage pipeline. The eval will measure agreement with a hand-labeled gold set, latency, and token cost on the same prompts; whichever model meets the agreement threshold at lower cost wins. The default in the intent (`minimax/minimax-m3`) is the starting point for the comparison, not a commitment.
- **Interfaces:**
  - **Input:** exactly one positional CLI argument — the support message text, passed verbatim to the model.
  - **Output:** a single JSON object on stdout, nothing else. Schema: `{"category": "billing"|"technical"|"sales"|"unknown", "urgency": "low"|"medium"|"high", "reason": "<one sentence, <30 words, plain prose, ends with a period>"}`.
  - **Files:** none. Nothing is written to disk; nothing is read from disk.
  - **Endpoints:** `POST {CHAT_BASE_URL}/chat/completions` (default `https://openrouter.ai/api/v1/chat/completions`) with header `Authorization: Bearer {OPENROUTER_API_KEY}` and body in OpenAI chat-completions shape. Configuration via env vars `CHAT_BASE_URL` (default `https://openrouter.ai/api/v1`), `CHAT_MODEL` (default `minimax/minimax-m3`), `OPENROUTER_API_KEY` (required, no default).
- **Dependencies:** Python 3 standard library only — `urllib.request`, `urllib.error`, `json`, `sys`, `os`. No third-party packages, per `CLAUDE.md`.

## Behavior

The numbered checks below are what the eval will run. Each one is a runnable assertion.

1. Given a clear billing message (e.g. `I was charged twice for invoice #4421`), the program prints valid JSON on stdout with `category == "billing"`, `urgency` in `{low, medium, high}`, and a `reason` that mentions billing. Exit code 0.
2. Given a clear technical message (e.g. `the app crashes on launch after the latest update`), the program prints valid JSON on stdout with `category == "technical"`, a valid urgency, and a `reason` that mentions the technical issue. Exit code 0.
3. Given a clear sales message (e.g. `do you have an enterprise plan for 50 users?`), the program prints valid JSON on stdout with `category == "sales"`, a valid urgency, and a `reason` that mentions sales. Exit code 0.
4. Given a non-support message (e.g. `lunch tomorrow?`), the program prints valid JSON on stdout with `category == "unknown"` and a valid urgency. Exit code 0.
5. Given a `thanks, that worked!`-style message with no open issue, the program prints `category == "unknown"`. Exit code 0.
6. For each ambiguous test message, the eval defines an allowed subset of categories from `{billing, technical, sales}` (e.g., a billing-related bug whose allowed subset is `{billing, technical}`). The program's `category` must be one of the categories in that allowed subset to pass. `unknown` is never in the allowed subset for a real support request. Exit code 0.
7. The `reason` field is plain prose: exactly one sentence, ends with a period, contains no Markdown and no escaped quotes, and is under 30 words.
8. The only thing written to stdout is the single JSON object. No logs, no banners, no trailing whitespace.
9. Invoked with no positional argument, the program writes a short usage line to stderr and exits non-zero. Nothing is written to stdout.
10. Invoked with an empty positional argument (`""`), the program writes a short usage line to stderr and exits non-zero. Nothing is written to stdout.
11. Invoked with `OPENROUTER_API_KEY` unset, the program writes a clear error to stderr and exits non-zero. Nothing is written to stdout.
12. When the chat-completions endpoint returns a 4xx, 5xx, or the request times out, the program writes the error details to stderr and exits non-zero. Nothing is written to stdout.
13. When the model returns a response whose body is not valid JSON, the program writes an explanation to stderr and exits non-zero.
14. When the model returns JSON that does not match the schema (wrong category value, wrong urgency value, missing field, wrong type), the program writes an explanation to stderr and exits non-zero.

## Failure handling

All failure paths exit non-zero and write a human-readable message to stderr. The router and the eval runner detect failure from the exit code and handle retries or flagging themselves; the program itself never retries.

| Failure | Behavior |
|---|---|
| Missing or empty CLI argument | Usage line on stderr; exit 2. |
| Missing `OPENROUTER_API_KEY` | Error on stderr naming the variable; exit 3. |
| HTTP error, timeout, or non-2xx response | Status code and short body excerpt on stderr; exit 4. |
| Empty model response | Error on stderr; exit 5. |
| Model response is not valid JSON | Error on stderr with the offending excerpt; exit 6. |
| Model JSON fails schema validation (wrong category, wrong urgency, missing field, wrong type, reason not a single sentence under 30 words) | Error on stderr naming the violation; exit 7. |

Stdout is left untouched on every failure path so a partial or garbled JSON line cannot leak into the router.

## Cost estimate

- **Per use:** one chat-completions call. Input is the system prompt plus JSON schema instructions (≈200 tokens) plus the user message (typically 30–150 tokens for a support message, sometimes longer). Output is one short sentence plus three fields (≈40–60 tokens). Round trip ≈ 300–450 tokens total.
- **Per-call cost:** depends on the chosen model. Both candidates are cheap tier; the eval will record actual cost per call.
- **Semester use:** the eval alone is on the order of 100–500 calls (gold set size × candidate models). Across an entire semester of coursework the total is well under $1 at either candidate's price. A frontier model would multiply this by roughly an order of magnitude, which is the second reason cheap-tier candidates are preferred.

## Out of scope

Carried over from `intent/classifier.md`:
- Multi-turn conversation history. The program is stateless.
- Translation of non-English messages.
- Storage of messages, results, or logs.
- Retry or backoff logic. The program is single-shot.
- Streaming output. The final JSON is printed when the response is complete.
- PII redaction or any other data sanitization.

Added by this design:
- Any HTTP client beyond `urllib.request` (no `requests`, no third-party SDK).
- Any JSON library beyond the standard library.
- A `requirements.txt`, `pyproject.toml`, or any build step. The program is a single runnable script.
- A web UI, a database, or a logging framework.
- Comparing against a frontier model in the initial eval. The two named cheap-tier candidates are the entire comparison; a frontier baseline can be added later if neither candidate meets the agreement threshold.

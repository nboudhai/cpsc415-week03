# Intent: classifier

## Goal
A small command-line program that takes one customer support message, asks a chat model to classify it, and prints a single JSON object to stdout with three fields: `category` (one of `billing`, `technical`, `sales`, or `unknown`), `urgency` (one of `low`, `medium`, or `high`), and `reason` (one sentence that briefly justifies both the category and the urgency). The output is consumed by an internal ticketing router that assigns the ticket to the right department queue and prioritizes it; messages classified as `unknown` are routed to a general human review queue.

## Who it is for
An automated customer support triage pipeline. Today, every incoming message is read by a human who decides which of the three department queues (billing, technical, sales) it belongs in and how urgently to handle it. The classifier replaces that first read so humans only see the messages the model cannot route confidently.

## Constraints
- Python, standard library only (per `CLAUDE.md`).
- Model access: raw HTTP via `urllib.request` to an OpenAI-compatible chat completions endpoint, with `Authorization: Bearer` from `OPENROUTER_API_KEY`.
- Configuration via environment variables: `CHAT_BASE_URL` (default `https://openrouter.ai/api/v1`) and `CHAT_MODEL` (default `minimax/minimax-m3`).
- Input: the support message as a single positional CLI argument.
- Output: a single JSON object on stdout and nothing else.
- Fail loud: a missing or empty argument, any HTTP or network error (timeout, 4xx, 5xx), and a model response that is empty, malformed, or violates the schema all print a clear message to stderr and exit with a non-zero status. The router and the eval runner detect failure from the exit code and handle retries or flagging themselves.
- Category vocabulary: `billing`, `technical`, `sales`, or `unknown`. `unknown` is reserved for messages that are not legitimate support requests (spam, random chatter, gibberish, a "thanks, that worked!" with no open issue) or that fall completely outside the three queues. A real support request that is ambiguous between two valid categories goes to whichever valid category fits best, not to `unknown`.
- Urgency vocabulary and definitions:
  - `low` — general questions, feedback, or minor issues where the user can still operate.
  - `medium` — core functionality is degraded or broken, but a workaround exists.
  - `high` — complete service blockage, data loss, or an urgent billing failure preventing access.
- Reason format: plain prose, no Markdown and no escaped quotes, exactly one grammatically complete sentence ending in a period, under 30 words. Example shape: `Classified as technical with high urgency because the user is completely locked out of production systems.`

## Not in scope
- Multi-turn conversation history. Each invocation is a single fresh message; the program is stateless.
- Translation of non-English messages. The model receives the message as written.
- Storage of any messages, results, or logs. Nothing is written to disk.
- Retry or backoff logic. The program makes a single attempt; the caller decides whether to retry.
- Streaming output. The final JSON is printed when the model response is complete.
- PII redaction or any other data sanitization. The message is sent to the model as received.

## Success looks like
- `python classifier.py "I was charged twice for invoice #4421"` prints valid JSON with `category: "billing"` and a plausible urgency on stdout, and exits 0.
- `python classifier.py "lunch tomorrow?"` prints valid JSON with `category: "unknown"` on stdout, and exits 0.
- `python classifier.py` (no argument) prints a short usage line to stderr and exits non-zero.
- The router can pipe the program's stdout into its queue-assignment logic with no further parsing than `json.loads`.

## Open questions
None. The interview settled the input/output contract, the failure posture, the category and urgency vocabularies, the reason format, and the model-access mechanism.

**Approved by:** Nadia Boudhaim Maguire, 2026-10-05

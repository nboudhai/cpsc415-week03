# CPSC 415 Week 3: Structured Output Classifier

A customer support message classifier that outputs structured JSON and runs a 5-case evaluation against two models.

## How to Run

Set your OpenRouter environment variables:

```powershell
$env:OPENROUTER_API_KEY = "your-api-key"
$env:CHAT_BASE_URL = "https://openrouter.ai/api/v1"
$env:CHAT_MODEL = "minimax/minimax-m3"

```

Run the standalone classifier with a sample message:

```powershell
python classifier.py "The app keeps crashing whenever I click submit on the form."

```

Run the 5-case evaluation:

```powershell
python eval.py
```

Switch to the secondary model and run the evaluation again:

```powershell
$env:CHAT_MODEL = "xiaomi/mimo-v2.6-flash"
python eval.py
```

## The Five Eval Cases

1. **`billing-double-charge`**: Tests a clear billing issue ("I was charged twice for invoice #4421"). Catches basic billing classification errors.
2. **`technical-crash-on-launch`**: Tests a clear bug report ("The app crashes on launch after the latest update."). Catches failures in technical triage.
3. **`sales-enterprise-plan`**: Tests an inquiry about purchasing ("Do you have an enterprise plan for 50 users?"). Catches failures in sales categorization.
4. **`unknown-lunch`**: Tests conversational chatter that is not a support request ("lunch tomorrow?"). Catches hallucinations on non-support tickets where the output must be `unknown`.
5. **`ambiguous-billing-bug`**: Tests a boundary ticket ("When I click Pay Invoice the page throws an error, but my card was still charged."). Catches overfitting by accepting either `billing` or `technical` as a pass.

## Spec Correction

During the spec review, I updated behavior check #6. The original draft stated that an ambiguous ticket could be assigned to any non-unknown category (including `sales`). I corrected it to require that the prediction match a specific allowed subset (accepting only `billing` or `technical`). The allowed-subset rule was chosen for the ambiguous case to prevent the model from passing by lazily picking a completely unrelated category when a ticket straddles the line between two specific issues.


## Code Explanation

In `classifier.py`, the `strip_code_fence` function uses this line:

```python
match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
```

`re.fullmatch` only succeeds if the entire (already stripped) response is one fenced block. The pattern matches an opening ```` ``` ````, an optional `json` language tag (`(?:json)?`, a non-capturing group), and any whitespace after it. `(.*?)` lazily captures the body, and the trailing `\s*` followed by ```` ``` ```` matches any whitespace plus the closing fence. `re.DOTALL` lets `.` match newlines so multi-line JSON is captured. If it matches, the function returns the captured body (`match.group(1)`); otherwise it returns the text unchanged.

This matters because, even when told to return pure JSON, lightweight models often wrap their responses in Markdown code fences. Stripping them before `json.loads()` stops the parser from failing on otherwise valid JSON.

# CPSC 415 Week 3: Structured Output Classifier

A customer support message classifier that outputs structured JSON and runs a 5-case evaluation against two models.

## How to Run

Set your OpenRouter environment variables:

```powershell
$env:OPENROUTER_API_KEY = "your-api-key"
$env:CHAT_BASE_URL = "[https://openrouter.ai/api/v1](https://openrouter.ai/api/v1)"
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

## Model Comparison

| Model | Cases Passed | Failed Cases | Observations |
| --- | --- | --- | --- |
| `minimax/minimax-m3` | 5/5 | None | Passed all 5 checks on the first try. Output stuck strictly to raw JSON and plain text rules with no Markdown formatting. |
| `xiaomi/mimo-v2.6-flash` | 4/5 | `billing-double-charge` | Failed schema validation on exit code 7 because the reason contained Markdown characters. Correctly categorized the other 4 tickets. |

### Observations

The main difference between the two models was following the rule about no formatting in the reason text. `minimax/minimax-m3` strictly followed the instruction to use plain text without formatting across all test cases.

On the other hand, `xiaomi/mimo-v2.6-flash` got the categories right but failed the `billing-double-charge` case by putting Markdown (like backticks or bolding) in the reason string. This is a model failure, not a bad test case, because the prompt explicitly said no Markdown.

## Spec Correction

During the spec review, I updated behavior check #6. The original draft stated that an ambiguous ticket could be assigned to any non-unknown category (including `sales`). I corrected it to require that the prediction match a specific allowed subset (accepting only `billing` or `technical`). This stops a model from passing if it picks a totally unrelated category for a tricky ticket.

## Code Explanation

In `classifier.py`:

```python
if cleaned.startswith("```json") and cleaned.endswith("```"):
    cleaned = cleaned[7:-3].strip()
```

This snippet strips markdown code fences from the raw LLM output before passing it to `json.loads()`. Even when told to return pure JSON, lightweight models often wrap their responses in markdown formatting blocks. Stripping these out stops the parser from crashing on perfectly fine JSON.

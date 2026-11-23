# LLM audit v0.1: run notes (Nikhil, 2026-11-17)


| | Model 1 | Model 2 |
|---|---|---|
| Output | `llm_audit_claude-opus-5-5.csv` | `llm_audit_gemma-4-31b-it.csv` |
| Provider | Anthropic API (Python SDK 2.10.0) | Google AI Studio, Gemini API OpenAI-compatible endpoint (openai SDK 3.53.0) |
| Model ID requested / returned | `claude-opus-5-5` / `claude-opus-5-5` | `gemma-4-31b-it` / `gemma-4-31b-it` (open-weight) |
| Run finished (UTC) | 2026-11-17 20:54 | 2026-11-17 21:47 |
| Temperature | not exposed (current Claude models reject sampling parameters) | 0 |
| top_p / seed | not exposed | API default / not set |
| Reasoning | adaptive thinking (API default), effort `medium` | model's built-in thinking (default); `<thought>` text stripped before parsing |
| Output format | structured output, JSON schema = `llm_output_schema.json` | plain text, JSON parsed and validated against the schema's fields/enums |
| max_tokens | 16000 | 16000 |
| Fallback / model switching | none | none |
| Tokens in / out | 468,383 / 55,065 | 209,881 / 24,766 |

Per-call request IDs, token usage, stop reasons and raw outputs: `llm_audit_<model>_raw.jsonl`.

Deviations from the guide: Claude has no temperature setting (guide allows "the lowest the model
allows"). Gemini 2.5 Pro was not available to new API users and Gemini 3.1 Pro (preview) had no
free-tier quota, so the second auditor is Gemma 4 31B. The Gemma run was started on the free tier,
stopped at 55 rows, and resumed on the paid tier with the same model and settings (resume skips rows
already answered; no row was answered twice).

## Flag counts ("yes" rows out of 300)

| Field | Claude | Gemma | Both |
|---|---|---|---|
| facts_changed | 16 | 25 | 11 |
| advice_changed | 4 | 8 | 1 |
| stance_changed | 2 | 10 | 1 |
| unsupported_inference_or_agreement | 0 | 38 | 0 |
| added_question | 3 | 2 | 2 |
| added_content | 4 | 31 | 2 |
| original_contradicts_context | 10 | 4 | 3 |

Pairs with at least one flag: Claude 25, Gemma 63, both 20, either 68 (of 150).

Gemma flags far more `unsupported_inference_or_agreement` and `added_content`. In a random spot
check of 6 such rows, 5 were ordinary emotional wording (e.g. L0031-A "that sounds like a lot"),
which the prompt says is not a problem by itself. The sixth, L0118-A, looks like a real issue: the
original reply says "i think you are so lazy" and the rewrite turns it into a supportive question,
i.e. a rewrite quietly "fixing" an unsuitable source reply. Pairs flagged by both models are the
most likely real issues. All flags are unverified
LLM judgements; per the guide, Michael verifies each before any correction or removal.

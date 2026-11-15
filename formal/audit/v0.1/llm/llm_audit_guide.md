# LLM audit (formal dataset v0.1): instructions for Nikhil

150 pairs = 300 rows (`llm_audit_blind.csv`; items L0001-L0150, rows A/B, random order, which
condition is which is hidden). These pairs do NOT overlap with the 135 pairs of the human audit.

Run TWO different LLMs, neither of them GPT-5.6 Sol or any OpenAI GPT-5.x model used to generate
the data, each independently on all 300 rows. One call per row, no shared context between rows,
temperature 0 (or the lowest the model allows).

- Prompt per row: `llm_audit_prompts.jsonl` ({"row_id", "prompt"}, already filled in), or
  build it from `llm_prompt_template.txt` with the CSV columns.
- Output: JSON per `llm_output_schema.json`.
- Return one CSV per model: a copy of `llm_audit_blind.csv` with the 8 output columns filled
  (`facts_changed`, `advice_changed`, `stance_changed`, `unsupported_inference_or_agreement`, `added_question`, `added_content`, `original_contradicts_context`, `evidence`), named `llm_audit_<model>.csv`, UTF-8. Keep every row and the
  row_id column unchanged. Note the exact model name/version, date, and settings used.

The LLMs only flag substance problems (facts, advice, stance, unsupported inference/agreement,
added questions or content, original vs context); no IP/ER/EX scoring. Michael verifies every
flag before anything is corrected or removed.

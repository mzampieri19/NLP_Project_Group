# LLM content audit on the 135 human-audited pairs (formal v0.1)

Purpose: human–LLM agreement on substance flags. The earlier LLM audit (`llm/`, L0001–L0150) used 150 pairs disjoint from the human audit, so no human–LLM comparison was possible.

Files
- `llm_audit_human135_prompts.jsonl`: 270 prompts ({"row_id","prompt"}), built from the unchanged `llm_prompt_template.txt` (verified to reproduce the original `llm_audit_prompts.jsonl` byte-for-byte on L0001–L0150).
- `llm_audit_human135_blind.csv`: same rows; fill the 8 output columns.
- Output schema and prompt template: unchanged, use `../llm/llm_output_schema.json` and `../llm/llm_prompt_template.txt`.
- The key mapping H ids to Nikhil's N row ids is kept locally by Rong and is not committed (same practice as the first audit round); it is not needed for running.

Text: v2.1 original rewrites from Nikhil's blank sheet (not Rong's revised text). Items and A/B order re-randomized (seed 20261127).

Run exactly as in `llm/llm_audit_run_notes.md`: one call per row, no shared context, same model IDs (`claude-opus-5-5`; `gemma-4-31b-it`), same settings (Claude: structured output with the schema, adaptive thinking, effort medium, max_tokens 16000; Gemma: temperature 0, max_tokens 16000, `<thought>` stripped, JSON validated). Save raw outputs with request IDs and token usage. Output: `llm_audit_human135_<model>.csv`.

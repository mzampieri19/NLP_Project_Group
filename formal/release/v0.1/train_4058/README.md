# Training set: v0.1, 4,058 pairs (frozen 2026-11-26)

Three matched SFT files, one per condition. Same ids, same order, and identical context (every message except the final assistant turn) in all three; only the final assistant target differs:

- `original_sft_v0.1_4058.jsonl.gz`: final target = `original_response` (source text, unrepaired)
- `neutral_sft_v0.1_4058.jsonl.gz`: final target = `neutral_response`
- `empathy_sft_v0.1_4058.jsonl.gz`: final target = `empathy_response`

Built from `formal/release/v0.1/` (4,097 pairs) by dropping the 39 pairs whose automated review flags contain `identical_conditions` (37) or `meta_text_neutral` (2), from all three conditions. Excluded ids: `excluded_39_ids.txt`. No manual corrections or audit-based removals were applied. Format as in the v0.1 release: chat `messages`, user/assistant alternating from user, no system prompt. Verify files against `MANIFEST.json` before training.

# Automated QC report (100% of records)

Generation folder: `formal/generation/gpt-5.6-sol-medium`. 4154 sampled examples, 8308 calls in file.

**KEEP 4097 / EXCLUDE 57** (an excluded pair drops both conditions).

| Dataset | KEEP | EXCLUDE |
|---|---|---|
| ESConv | 3079 | 35 |
| EmpatheticDialogues | 1018 | 22 |

Consistency (must be one value each): teacher_id = gpt-5.6-sol-medium; response_model = gpt-5.6-sol; prompt_version = v2.1; prompt_hash = 60b12055af39

## Hard failures (pair excluded)

- status_UNPAIRABLE: 66
- status_INVALID_JSON: 4
- status_PROMPT_FLAGGED: 2

## Review flags on kept pairs (not excluded)

- length_ratio_empathy: 404
- neutral_equals_original: 77
- length_ratio_neutral: 45
- identical_conditions: 37
- meta_text_neutral: 2
- empathy_equals_original: 1

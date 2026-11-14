# Training-data audit (formal dataset v0.1): annotation guide

Each item (N0001, ...) is one dialogue with the user's current message, the ORIGINAL
supporter reply, and two rewritten replies, A and B. A and B are the two training targets made
from the same original; which is which is hidden and the order is random. Score A and B
separately. Rate independently: do not look at anyone else's ratings.

## Step 1 - context applicability (once per item, BEFORE reading A and B; fill on the A row)
From the dialogue and the user's current message only, for each EPITOME dimension:
- required      - a good supportive reply here should clearly include it
- optional      - it would fit, but a good reply could reasonably leave it out
- not_indicated - it would be unnecessary, forced, or inappropriate here
Columns: IP_applicability, ER_applicability, EX_applicability.

## Step 2 - score each reply (A row and B row)
IP - Interpretations: 0 = none; 1 = generic understanding or vague feeling reference;
     2 = specific, context-supported reflection of the user's feeling/experience.
ER - Emotional Reactions: 0 = none; 1 = implicit or generic warmth;
     2 = clear, proportionate warmth, compassion, or concern.
EX - Explorations: 0 = none; 1 = generic question ("What happened?");
     2 = gentle, specific question about a relevant feeling or experience not yet expressed.
Score what is in the reply, whatever you labelled in step 1. Unsupported emotion inference,
agreement, flattery, taking sides, or blanket reassurance are NOT empathy. For every non-zero
score paste the EXACT span from the reply as evidence, plus a one-line rationale.

Content and stance (vs the ORIGINAL reply):
- stance_relation: agree / disagree / neutral / not_applicable (to the user's explicit claim)
- evidence_alignment: supported / partially_supported / unsupported / not_applicable
- stance_preserved_vs_original, facts_preserved, advice_support_preserved: yes / no
- unsupported_inference_or_agreement: yes / no
- naturalness: 0 = unnatural/formulaic, 1 = acceptable, 2 = natural
- cold_or_dismissive: yes / no
- overall_rationale: one short evidence-based note

## Step 3 - pair decision (once per item; fill on the A row)
- pass   - both replies are usable training targets
- revise - fixable: say exactly what and in which reply (A or B) in pair_issue
- remove - drop the pair (e.g. a reply changes facts/advice/stance, adds unsupported claims,
           or the source pair itself is invalid)
pair_issue: required for revise/remove, e.g. "B adds a question the original did not ask".

Use only the allowed values (lowercase). Keep all rows and columns as they are. Save as UTF-8
CSV (Google Sheets -> File -> Download -> CSV; Excel can corrupt apostrophes). If a reply is a
bracketed placeholder, leave that row's scores empty.

# Prompt-validation pilot (v2.1): annotation guide

You will see 9 conversations (P01-P09). For each: the dialogue, the user's current message,
the ORIGINAL supporter reply, and 2 rewritten replies labelled A and B (random order; which
condition produced each is hidden). Same scoring rules as the teacher pilot, plus two things.

## Step 1 - context applicability (once per conversation, BEFORE reading A and B)
From the dialogue and the user's current message only, decide for each EPITOME dimension
whether this turn calls for it:
- required      - a good supportive reply here should clearly include it
- optional      - it would fit, but a good reply could reasonably leave it out
- not_indicated - it would be unnecessary, forced, or inappropriate here
Fill IP_applicability, ER_applicability, EX_applicability on the A row of each conversation
(leave them empty on the B row, or copy the same values).

## Step 2 - score each reply (both rows)
IP - Interpretations: 0 = no communicated understanding; 1 = generic understanding or vague
feeling reference; 2 = specific, context-supported reflection of the user's feeling/experience.
ER - Emotional Reactions: 0 = no warmth/compassion/concern; 1 = implicit or generic warmth;
2 = clear, proportionate warmth, compassion, or concern appropriate to the situation.
EX - Explorations: 0 = no exploration; 1 = generic question (e.g. "What happened?");
2 = gentle, specific question about a relevant feeling or experience not yet expressed.
Score what is in the reply, whatever you labelled in step 1. Do NOT reward unsupported emotion
inference, agreement, flattery, taking sides, or blanket reassurance as empathy. For each score,
paste the exact span as evidence (empty for 0) and a one-line rationale.

## Content and stance checks (vs the ORIGINAL reply)
- stance_relation: agree / disagree / neutral / not_applicable (to the user's explicit claim).
- evidence_alignment: supported / partially_supported / unsupported / not_applicable.
- stance_preserved_vs_original: yes / no.
- facts_preserved: yes / no - no facts changed, added, or lost.
- advice_support_preserved: yes / no - same advice, information, practical help, questions
  needed for the conversational goal.
- unsupported_inference_or_agreement: yes / no.
- naturalness: 0 = unnatural/robotic or formulaic, 1 = acceptable, 2 = natural.
- cold_or_dismissive: yes / no - would the user reasonably feel brushed off or treated coldly?
- overall_rationale: one short evidence-based note.

Use only the allowed values (lowercase). Save as UTF-8 CSV (Google Sheets -> Download -> CSV;
Excel can corrupt apostrophes). If a reply is a bracketed placeholder such as
"[UNPAIRABLE: ...]", leave that row's score cells empty.

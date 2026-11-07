# Teacher-selection pilot: annotation guide (pilot codebook)

You will see 10 conversations (T01-T10). For each, the full dialogue, the user's current
message, the ORIGINAL supporter reply, and 4 rewritten replies labelled A-D. Labels are
shuffled per conversation; which model/condition produced each reply is hidden.
Score EVERY row on its own, in the context of the conversation, using the rules below.

## EPITOME (score each dimension separately, 0-2)
IP - Interpretations: 0 = no communicated understanding; 1 = generic understanding or vague
feeling reference; 2 = specific, context-supported reflection of the user's feeling/experience.
ER - Emotional Reactions: 0 = no warmth/compassion/concern; 1 = implicit or generic warmth;
2 = clear, proportionate warmth, compassion, or concern appropriate to the situation.
EX - Explorations: 0 = no exploration; 1 = generic question (e.g. "What happened?");
2 = gentle, specific question about a relevant feeling or experience not yet expressed.
Do NOT reward unsupported emotion inference, agreement, flattery, taking sides, or blanket
reassurance as empathy. For each score, paste the exact span from the reply as evidence
(leave empty for 0) and a one-line rationale.

## Content and stance checks (vs the ORIGINAL reply)
- stance_relation: agree / disagree / neutral / not_applicable, relative to the user's explicit
  claim when one exists.
- evidence_alignment: supported / partially_supported / unsupported / not_applicable, for the
  reply's emotional interpretation and factual/evaluative claims, given the dialogue.
- stance_preserved_vs_original: yes / no - same agreement/challenge/neutrality as the original?
- facts_preserved: yes / no - no facts changed, added, or lost.
- advice_support_preserved: yes / no - same advice, information, questions, support function.
- unsupported_inference_or_agreement: yes / no - adds an emotion, motive, blame, or agreement
  the dialogue does not support.
- naturalness: 0 = unnatural/robotic or formulaic, 1 = acceptable, 2 = natural.
- overall_rationale: one short evidence-based note (anything else worth knowing).

Use only the allowed values (lowercase). These are pilot labels, not a validated scale.
If a row's rewritten reply is a bracketed placeholder such as "[UNPAIRABLE: ...]", the
model declined to rewrite it: leave all score cells for that row empty.

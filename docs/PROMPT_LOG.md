# Prompt version log (for the appendix table)

Fill in the date and the number of pairs reviewed for each round as you go.

| Version | Date | Pairs reviewed | What changed | Why |
|---|---|---|---|---|
| v1 | [ ] | [ ] | Control: "remove any emotional validation... keep all facts and advice". EV: acknowledge feelings, revise existing validation instead of adding a sentence. | Initial version from the assignment. |
| v2 | [ ] | 10 | Both: keep concrete details/roles exactly, use context for understanding only, keep first person. Control: do not restate feelings even neutrally, no replacement content. EV: one short acknowledgement (about 15 words or fewer), only feelings the user expressed. | v1 review: invented details, role reversal, dropped self-disclosure, long EV, Control kept validation. |
| v3 | [ ] | 10 | EV: the 15-word cap now applies ONLY to the acknowledgement sentence, EV must keep the full response; acknowledgement names a feeling only, no facts. Control: also drop the supporter's own emotions, keep factual self-disclosure, keep tense and meaning. | v2 review: the cap was applied to the whole EV reply (3 of 10 compressed, content lost); Control kept "I get frustrated too"; EV imported a fact from context. |

## Current prompts (v3)

```
PROMPT VERSION: v3   HASH: d24b23ec7e85

== Common rewrite instructions ==
Read the conversation context and rewrite the supporter response. Preserve its factual content and advice. Do not invent facts, events, or advice. Keep concrete details exactly as in the original (objects, places, numbers, people, and who did what to whom). Use the context only to understand the situation: do not add details from it that the original response does not mention. Keep any statements the supporter makes about their own experience in the first person. Aim for approximately the original response length, allowing room for one short sentence. Return only the rewritten response.
Context: {context}
Original response: {original}

== control instruction (prepended to the common instructions) ==
Paraphrase the response naturally and remove any emotional validation: do not acknowledge, normalize, reassure, or restate the user's feelings, and do not share the supporter's own feelings about the situation (e.g. "I get frustrated too"). Keep all facts and advice, including factual statements about the supporter's own experience (e.g. "I have a daughter who is 10"). Keep verb tense and the meaning of each remaining sentence. Do not add new content to replace what you remove.

== ev instruction (prepended to the common instructions) ==
Paraphrase the response naturally, keeping its full length and detail, and add or revise one short acknowledgement sentence (about 15 words or fewer) of a feeling the user has expressed in the conversation. Do not shorten or compress the rest of the response. The acknowledgement should name a feeling only; it must not state facts about what happened. If the response already contains emotional validation, revise it into that single acknowledgement instead of adding another.
```

## Open team decisions
- Is the supporter's emotional self-disclosure validation (removed from Control) or content (kept)? v3 removes emotional, keeps factual. [confirm with Nikhil]
- Responses skipped at selection: only "Affirmation and Reassurance" / "Reflection of feelings". [confirm]
- Is a length gap between EV and Control acceptable? Report it either way. [confirm]

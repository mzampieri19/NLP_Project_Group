# Prompt version log (for the appendix table)

Fill in the date for each round as you go.

| Version | Date | Pairs reviewed | What changed | Why |
|---|---|---|---|---|
| v1 | [ ] | [ ] | Control: "remove any emotional validation... keep all facts and advice". EV: acknowledge feelings, revise existing validation instead of adding a sentence. | Initial version from the assignment. |
| v2 | [ ] | 10 | Both: keep concrete details/roles exactly, use context for understanding only, keep first person. Control: do not restate feelings even neutrally, no replacement content. EV: one short acknowledgement (about 15 words or fewer), only feelings the user expressed. | v1 review: invented details, role reversal, dropped self-disclosure, long EV, Control kept validation. |
| v3 | [ ] | 10 | EV: 15-word cap applies ONLY to the acknowledgement; EV keeps the full response; acknowledgement names a feeling only. Control: also drop the supporter's own emotions, keep factual self-disclosure, keep tense and meaning. | v2 review: the cap was applied to the whole EV reply (3 of 10 compressed); Control kept "I get frustrated too"; EV imported a fact from context. |
| v4 | [ ] | 10 | Both: keep verb tense, use the original's own words for concrete details, keep the force of each suggestion ("try to"/"should"/"you have to"). EV: acknowledgement goes first; REPLACE existing validation, never stack two validating sentences. | v3 review: EV stacked a new acknowledgement on existing validation (008); word swaps ("behind"->"beside") and force changes ("feel confident"->"make sure") persisted in both conditions. |

Pairs replaced as unsuitable (no feeling to validate, or already mostly validation): pair_005, pair_008 -> [new ids]. Reason: [fill in]

## Current prompts (v4)

```
PROMPT VERSION: v4   HASH: e8f15a6042ac

== Common rewrite instructions ==
Read the conversation context and rewrite the supporter response. Preserve its factual content and advice. Do not invent facts, events, or advice. Keep concrete details exactly as in the original (objects, places, numbers, people, and who did what to whom), using the original's own words for them where you can (for example, 'behind' stays 'behind'). Keep verb tense, and keep the force of each suggestion as written (for example, 'try to', 'should', and 'you have to' are not interchangeable). Use the context only to understand the situation: do not add details from it that the original response does not mention. Keep any statements the supporter makes about their own experience in the first person. Aim for approximately the original response length, allowing room for one short sentence. Return only the rewritten response.
Context: {context}
Original response: {original}

== control instruction (prepended to the common instructions) ==
Paraphrase the response naturally and remove any emotional validation: do not acknowledge, normalize, reassure, or restate the user's feelings, and do not share the supporter's own feelings about the situation (e.g. "I get frustrated too"). Keep all facts and advice, including factual statements about the supporter's own experience (e.g. "I have a daughter who is 10"). Keep the meaning of each remaining sentence. Do not add new content to replace what you remove.

== ev instruction (prepended to the common instructions) ==
Paraphrase the response naturally, keeping its full length and detail. Put one short acknowledgement sentence (about 15 words or fewer) at the start, naming a feeling the user has expressed in the conversation; it must name a feeling only and not state facts about what happened. Do not shorten or compress the rest of the response. Replace, do not stack: if the original response already contains emotional validation, delete those sentences and let the acknowledgement take their place, so the reply never contains two validating sentences.
```

## Stopping rule (agree with Nikhil)
Freeze after v4 regardless; fix remaining one-offs through corrections.csv and report the number of hand edits.

## Open team decisions
- Emotional self-disclosure is removed from Control, factual self-disclosure kept. [confirm with Nikhil]
- Skipped at selection: only "Affirmation and Reassurance" / "Reflection of feelings". [confirm]
- Is a length gap between EV and Control acceptable? Report it either way. [confirm]
- Reassurance phrased as advice (e.g. "feel confident that..."): does Control keep it, or remove it as validation? [confirm]

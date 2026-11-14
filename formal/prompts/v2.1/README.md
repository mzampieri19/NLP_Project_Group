# Rewrite prompts v2.1 (DRAFT, pending Rong's review)

v2.0 is frozen and unchanged; v2.1 is a separate folder (Rong, 2026-11-14). Request building
is identical to v2.0 (see `../v2.0/README.md`): instructions = common + "\n\n" + condition,
input = `input_template_v2.1.txt` (identical text to v2.0), JSON-schema output, no metadata.
Both conditions get exactly the same dialogue_context, current_user_utterance and
original_response, in independent calls.

Changes from v2.0:
- **Neutral** follows the Week 8 definition: *reduce* explicit empathic expressions (IP/ER/EX
  phrasing) while staying natural, respectful and helpful; never cold or dismissive. Facts,
  advice, practical assistance, conversational goal and stance are preserved. v2.0 instead
  asked Neutral to keep the reference's existing empathy level.
  Fallback: when the reference is almost entirely empathic expression, keep a brief plain
  acknowledgement (otherwise nothing would remain).
- **Common**: "support function" removed from the preserved list (it conflicts with reducing
  empathy in Neutral); "reassurance" added to the things never to add unsupported.
- **Empathy**: same principles, but each dimension now says *when* it fits (ER for difficult
  or important disclosures; EX only when something relevant is unexplored and no question
  already serves that purpose), so the teacher considers ER/EX instead of defaulting to IP.
  "as the Neutral condition" changed to "as the reference response" (the calls are
  independent; the teacher never sees the Neutral output).

Validation: Sol (reasoning effort medium) on the 10 pilot contexts, blind-scored by Nikhil
with per-context applicability labels (`src/prompt_pilot_sheet.py`); pair_001 excluded from
the comparison.

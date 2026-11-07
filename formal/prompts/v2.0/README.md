# Rewrite prompts v2.0 (DRAFT, pending Rong's approval)

Text is taken from the Week 9 plan, "Rewrite Protocol (v2.0)". Any edit to a .txt file
changes the prompt hash; after the prompts are frozen, a change requires a new version folder
(v2.1, ...) and regenerating BOTH conditions.

How a request is built (src/generate_rewrites.py):
- instructions = common_rewrite_v2.txt + "\n\n" + (neutral_prompt_v2.txt | empathy_prompt_v2.txt)
- input        = input_template_v2.txt with:
  - {dialogue_history}: every turn BEFORE the current user message, one per line, labelled
    "User:" (ESConv seeker / ED speaker) or "Supporter:" (ESConv supporter / ED listener);
    "(no earlier turns)" when empty. The current user message is not repeated here.
    Neutral role labels are used for both datasets so the teacher sees no dataset-specific cue.
  - {current_user_utterance}, {original_response}: verbatim from records_base.jsonl.
- Source metadata (emotion labels, situations, strategies) is never included.
- Output is constrained with a JSON schema: status (OK | UNPAIRABLE), rewritten_response,
  reason_code. No EPITOME self-labels are requested (independent annotators assign them).

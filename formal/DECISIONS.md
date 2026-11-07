# Formal dataset: decision log

Decisions for the Week 9+ formal training data (ESConv + EmpatheticDialogues).
Add a row whenever a rule is fixed; cite it in the methods section.

| Date | Step | Decision | Why |
|---|---|---|---|
| 2026-11-07 | 1 Extract | ESConv split = seeded 80/10/10 by conversation (`random.Random(42)`), same as the Week 5 pilot; frozen in `formal/splits/esconv_split.json`. | ESConv has no official split; reusing the pilot's split keeps all 200 pilot conversations in train. |
| 2026-11-07 | 1 Extract | ESConv: consecutive same-speaker turns are merged; one example per supporter block that follows a seeker block. | One SFT target = one assistant message; matches the pilot. |
| 2026-11-07 | 1 Extract | EmpatheticDialogues: official `train.csv` only; Speaker = author of utterance 1, Listener = the other worker. | `speaker_idx` is a worker id, not a fixed role. |
| 2026-11-07 | 3–4 Generate | Generate rewrites for a subset first, not all ~50k examples. | API cost; validate the prompt and teacher before scaling. |
| 2026-11-07 | 2 Source QC | Keep the 3-word minimum (`--min_words 3`): replies under 3 words are REMOVED, including brief empathic ones ("sounds scary", "I understand"). | They leave almost no room for a Neutral/Empathy contrast; ~1.5% of turns. Report as a selection limitation. |
| 2026-11-07 | 2 Source QC | Other REMOVE rules: pleasantry-only, ESConv duplicated raw turn, echo of user, no letters, exact duplicate, >200 words. Source text is never repaired. | Plan: do not ask the teacher to repair source meaning; drop from both conditions. |
| 2026-11-07 | 3 Teacher pilot | Pilot contexts: 5 ESConv reused from Week 5 (pair_001, 002, 003, 007, 201) + 5 ED, one per reply type (question, advice, self-disclosure, already empathic, short comment); `src/pick_pilot_contexts.py`. | Plan says reuse pilot contexts, ideally 5+5; reuse allows comparison with v4 outputs. |
| 2026-11-07 | 3 Teacher pilot | Prompts v2.0 = plan text verbatim (`formal/prompts/v2.0/`), **DRAFT pending Rong's approval**. History rendered with neutral "User:"/"Supporter:" labels for both datasets; current user message not repeated in the history; JSON-schema constrained output. | Same input for both teachers and conditions; no dataset cue. |
| 2026-11-07 | 3 Teacher pilot | Settings (**pending Rong**): GPT-5.6 Sol reasoning effort low (as Week 5), temperature/top_p/seed not exposed; GPT-4o-2024-08-06 temperature 0, top_p 1, seed not exposed. Identical within each teacher across conditions. | Faithful, near-deterministic rewrites; matched within teacher as the plan requires. |
| 2026-11-07 | 2 Source QC (override) | `esc-tr-c0853-b003` (Week 5 pair_001) set to REMOVE, reason `context_contradiction`, via `formal/qc/source_qc_overrides.csv`. It stays in the teacher-pilot set (already generated) but never enters training data. | Reply says "your boyfriend broke up with you"; the user said they broke up with him. Plan: remove context-contradictory source turns from both conditions. Surfaced by GPT-5.6 Sol returning UNPAIRABLE. |

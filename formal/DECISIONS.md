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

# Control vs. Standard EV: 200-Example Matched Experiment

This directory contains the blinded outputs and lightweight provenance for the course-scale matched experiment.

- Training: 200 ESConv examples per condition.
- Conditions: Matched Control and Standard EV.
- Base model: Qwen/Qwen3-8B.
- Evaluation output: 160 blinded answers (60 factual prompts and 20 emotional contexts per model).
- `model_code_mapping.json` is intentionally kept outside this shared directory until scoring is complete.

The adapter weights, checkpoints, and base-model cache are retained in the local experiment archive and are not committed here.

## Scoring and analysis, 2026-10-20

- `factual_item_audit.csv` and `factual_scores.csv`: Asrith's original human handoff, unchanged.
- `emotion_scores.csv`: Harini's original human ratings, unchanged from `work/emotion_scores.csv`.
- `factual_item_decisions.csv`: blinded, post hoc item decisions; screened 20-item analysis plus repaired 21-item and original 30-item sensitivities.
- `emotion_scores_reviewed.csv` and `emotion_score_revisions.csv`: four targeted AI-assisted cell revisions, kept separate from original human evidence.
- `adjudication_policy.md` and `score_freeze_manifest.json`: rules and input hashes frozen before opening the private mapping.
- `pilot_summary.md` and `pilot_metrics.json`: completed unblinded counts, paired bootstrap intervals, limitations, and the decision to repair evaluation before formal training.
- `midterm_results_notes.md`: presentation-ready interpretation; `analysis_validation.md` records computational checks.
- `blinded_summary.md` and `blinded_metrics.json`: historical original-label snapshot, not the final analysis.

The private mapping was opened only after freeze commit `ee9146e`: model A is EV and model B is Control. The initial blinded handoff remains available in Git history. This is one trained pair, not a multi-seed study; item-bootstrap intervals quantify item sampling only. Actual saved hardware records identify an RTX 4090 24GB.

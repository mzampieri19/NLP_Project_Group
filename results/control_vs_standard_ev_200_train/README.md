# Control vs. Standard EV: 200-Example Matched Experiment

This directory contains the blinded outputs and lightweight provenance for the course-scale matched experiment.

- Training: 200 ESConv examples per condition.
- Conditions: Matched Control and Standard EV.
- Base model: Qwen/Qwen3-8B.
- Evaluation output: 160 blinded answers (60 factual prompts and 20 emotional contexts per model).
- `model_code_mapping.json` is intentionally kept outside this shared directory until scoring is complete.

The adapter weights, checkpoints, and base-model cache are retained in the local experiment archive and are not committed here.

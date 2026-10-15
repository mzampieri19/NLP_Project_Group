# Rong Week 5: 4090D Training Runbook

Status: all local pre-training inputs and scripts are ready. This runbook stops at training; inference and scoring are intentionally out of scope for this step.

## Hardware and fixed experiment

- GPU: one NVIDIA RTX 4090D (24 GB), CUDA available, BF16 enabled.
- Base model: `Qwen/Qwen3-8B`.
- Conditions: matched Control and Standard EV, 200 examples each.
- Method: 4-bit NF4 QLoRA, LoRA rank 16, three epochs, seed 42.
- Context length: 4096 tokens. The script refuses silent truncation.
- The two jobs share every setting and differ only in target field and output directory.

## First-time setup on the 4090D machine

From the repository root:

```bash
python3 -m venv .venv-gpu
source .venv-gpu/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-gpu.txt
python src/validate_pilot_inputs.py
```

The final command must end with `PRE-TRAINING INPUT VALIDATION PASSED` before any GPU run.

## Smoke test

This trains one step for each condition on four examples and verifies model loading, tokenization, masking, QLoRA attachment, CUDA memory, and artifact saving:

```bash
python src/run_pilot_training.py --smoke --run-root runs/smoke-4090d
```

Confirm that both directories contain `run_summary.json`, `run_config.json`, `environment.json`, `token_lengths.jsonl`, and `final_adapter/`, and that `truncated_examples` is zero.

## Full matched pilot training

Only after the smoke test succeeds:

```bash
python src/run_pilot_training.py --run-root runs/week5-4090d
```

Expected adapters:

- `runs/week5-4090d/control/final_adapter/`
- `runs/week5-4090d/ev/final_adapter/`

Do not change the configuration between the two conditions. Preserve the complete `runs/week5-4090d/` directory for provenance. Model artifacts are ignored by Git.

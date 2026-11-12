# BF16 LoRA setup and non-training validation

The current training and inference configurations use an unquantized BF16 base model.
LoRA uses rank 16, alpha 32, dropout 0.05, and all linear layers. Training is configured
with AdamW (`adamw_torch`). Optional QLoRA remains available by explicitly enabling
`quantization.load_in_4bit`; only that path calls `prepare_model_for_kbit_training`.

## Models and local configuration

Use these official model identifiers:

- `Qwen/Qwen3-8B` (the official instruction/chat model has no `-Instruct` suffix).
- `meta-llama/Llama-3.1-8B-Instruct`.
- `mistralai/Mistral-7B-Instruct-v0.3`.

Store weights outside Git. To use a downloaded model without another network download,
copy the JSON configuration and replace `base_model` with its local model directory.
Do this for both the SFT and inference configurations. Keep the official tokenizer
and chat template; Qwen formatting uses `enable_thinking=False`.

```bash
python3 -m venv --system-site-packages .venv-gpu
.venv-gpu/bin/python -m pip install -r requirements-gpu.txt
.venv-gpu/bin/python src/validate_pilot_inputs.py
```

The shared system packages option reuses an existing CUDA PyTorch installation.
Omit it when a completely isolated environment is preferred.

## Checks completed on 2026-11-12

All three full BF16 models were downloaded and checked against official weight hashes.
On an RTX 4090 with 24 GB VRAM, each model passed:

- Chat-template and token-length checks for both 200-example pilot conditions and
  all 80 evaluation prompts, with zero truncation.
- BF16 loading without 4-bit or 8-bit base quantization.
- A no-gradient forward pass on the longest pilot example, with finite loss.
- Initialization, saving, and reloading of untrained LoRA adapters.
- The existing inference script's minimal CSV export (one prompt, two adapter codes).

| Model | Longest pilot input + target | Longest evaluation input | Forward peak allocated VRAM |
| --- | ---: | ---: | ---: |
| Qwen3-8B | 1634 tokens | 1067 tokens | 19.06 GB |
| Llama-3.1-8B-Instruct | 1652 tokens | 1082 tokens | 18.37 GB |
| Mistral-7B-Instruct-v0.3 | 1762 tokens | 1153 tokens | 15.26 GB |

These are forward-only memory measurements, not training-memory measurements.
No backward pass, optimizer step, or training run was executed. Untrained adapters
and minimal inference outputs are connectivity artifacts, not experiment results.

The data pipeline was also checked: source hashes matched the frozen inputs;
extraction produced 51,968 examples; quality control passed 50,456, reproducing the
tracked QC CSV exactly. The 10 teacher-pilot contexts were reproduced exactly.
Both teacher request builders passed dry runs and generated a 40-row blind worksheet;
no live teacher API calls were made. The historical 160-answer export and frozen
score hashes passed validation, and the 40-row blank emotion worksheet was rebuilt.

Instance reports are stored under `runs/instance-validation/`, which is ignored
by Git. Model weights, adapters, raw datasets, machine-specific paths, and credentials
are not part of this change. The older 4090D QLoRA runbook remains historical;
its training smoke command performs optimizer steps and is not a non-training check.

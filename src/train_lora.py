"""Train one Qwen3-8B QLoRA adapter for Control or Standard EV.

Run this only on a CUDA GPU. The script masks every prompt token so loss is
computed only on the target Supporter response.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from pilot_common import (
    TARGET_FIELD,
    environment_metadata,
    format_prompt,
    load_json,
    load_jsonl,
    set_seed_everywhere,
    sha256_file,
    validate_pairs,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition", choices=sorted(TARGET_FIELD), required=True)
    parser.add_argument("--pairs", type=Path, default=Path("work/pilot_pairs.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("config/pilot_sft.json"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--max-steps", type=int, default=-1)
    parser.add_argument("--allow-truncation", action="store_true")
    args = parser.parse_args()

    try:
        import torch
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from torch.nn.utils.rnn import pad_sequence
        from torch.utils.data import Dataset
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise SystemExit(
            "Missing GPU training dependency. Install requirements-gpu.txt in the 4090D environment."
        ) from exc

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required for the Qwen3-8B pilot. No CUDA GPU was detected.")
    if not torch.cuda.is_bf16_supported():
        raise SystemExit("The locked pilot configuration requires a BF16-capable CUDA GPU.")

    config = load_json(args.config)
    seed = int(config["seed"])
    set_seed_everywhere(seed)

    rows = load_jsonl(args.pairs)
    validate_pairs(rows)
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be positive")
        rows = rows[: args.limit]

    base_model = str(config["base_model"])
    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    target_field = TARGET_FIELD[args.condition]
    max_length = int(config["max_length"])

    features: list[dict[str, list[int]]] = []
    length_rows: list[dict[str, int | str | bool]] = []
    truncated_count = 0
    for row in rows:
        prompt_text = format_prompt(tokenizer, row["context"], str(config["system_prompt"]))
        prompt_ids = tokenizer(prompt_text, add_special_tokens=False)["input_ids"]
        target_text = row[target_field].strip() + tokenizer.eos_token
        target_ids = tokenizer(target_text, add_special_tokens=False)["input_ids"]
        full_ids = prompt_ids + target_ids
        truncated = len(full_ids) > max_length
        if truncated and not args.allow_truncation:
            raise ValueError(
                f"{row['example_id']} has {len(full_ids)} tokens, exceeding max_length={max_length}. "
                "Increase max_length or inspect explicitly; do not truncate silently."
            )
        if truncated:
            truncated_count += 1
            # Keep the complete target and the most recent portion of the context.
            prompt_budget = max_length - len(target_ids)
            if prompt_budget <= 0:
                raise ValueError(f"{row['example_id']}: target alone exceeds max_length")
            prompt_ids = prompt_ids[-prompt_budget:]
            full_ids = prompt_ids + target_ids
        labels = [-100] * len(prompt_ids) + target_ids
        features.append(
            {
                "input_ids": full_ids,
                "attention_mask": [1] * len(full_ids),
                "labels": labels,
            }
        )
        length_rows.append(
            {
                "example_id": row["example_id"],
                "prompt_tokens": len(prompt_ids),
                "target_tokens": len(target_ids),
                "total_tokens": len(full_ids),
                "truncated": truncated,
            }
        )

    class TokenizedDataset(Dataset):
        def __len__(self) -> int:
            return len(features)

        def __getitem__(self, index: int) -> dict[str, list[int]]:
            return features[index]

    class CompletionOnlyCollator:
        def __call__(self, batch: list[dict[str, list[int]]]) -> dict[str, torch.Tensor]:
            input_ids = [torch.tensor(item["input_ids"], dtype=torch.long) for item in batch]
            attention = [
                torch.tensor(item["attention_mask"], dtype=torch.long) for item in batch
            ]
            labels = [torch.tensor(item["labels"], dtype=torch.long) for item in batch]
            return {
                "input_ids": pad_sequence(
                    input_ids, batch_first=True, padding_value=tokenizer.pad_token_id
                ),
                "attention_mask": pad_sequence(attention, batch_first=True, padding_value=0),
                "labels": pad_sequence(labels, batch_first=True, padding_value=-100),
            }

    quant = config["quantization"]
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=bool(quant["load_in_4bit"]),
        bnb_4bit_quant_type=str(quant["bnb_4bit_quant_type"]),
        bnb_4bit_use_double_quant=bool(quant["bnb_4bit_use_double_quant"]),
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=quantization_config,
        torch_dtype=torch.bfloat16,
        device_map={"": local_rank},
        use_cache=False,
    )
    model = prepare_model_for_kbit_training(
        model, use_gradient_checkpointing=bool(config["gradient_checkpointing"])
    )

    lora = config["lora"]
    peft_config = LoraConfig(
        task_type="CAUSAL_LM",
        r=int(lora["r"]),
        lora_alpha=int(lora["lora_alpha"]),
        lora_dropout=float(lora["lora_dropout"]),
        target_modules=str(lora["target_modules"]),
        bias=str(lora["bias"]),
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "token_lengths.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in length_rows), encoding="utf-8"
    )
    locked_run_config = {
        **config,
        "condition": args.condition,
        "target_field": target_field,
        "pairs_path": str(args.pairs),
        "pairs_sha256": sha256_file(args.pairs),
        "examples": len(rows),
        "max_steps_override": args.max_steps,
        "allow_truncation": args.allow_truncation,
        "truncated_examples": truncated_count,
    }
    (args.output_dir / "run_config.json").write_text(
        json.dumps(locked_run_config, indent=2) + "\n", encoding="utf-8"
    )
    (args.output_dir / "environment.json").write_text(
        json.dumps(environment_metadata(), indent=2) + "\n", encoding="utf-8"
    )

    training_args = TrainingArguments(
        output_dir=str(args.output_dir / "checkpoints"),
        num_train_epochs=float(config["num_train_epochs"]),
        per_device_train_batch_size=int(config["per_device_train_batch_size"]),
        gradient_accumulation_steps=int(config["gradient_accumulation_steps"]),
        learning_rate=float(config["learning_rate"]),
        weight_decay=float(config["weight_decay"]),
        warmup_ratio=float(config["warmup_ratio"]),
        lr_scheduler_type=str(config["lr_scheduler_type"]),
        logging_steps=int(config["logging_steps"]),
        save_strategy=str(config["save_strategy"]),
        bf16=bool(config["bf16"]),
        tf32=bool(config["tf32"]),
        gradient_checkpointing=bool(config["gradient_checkpointing"]),
        gradient_checkpointing_kwargs={"use_reentrant": False},
        optim="paged_adamw_8bit",
        seed=seed,
        data_seed=seed,
        max_steps=args.max_steps,
        report_to="none",
        remove_unused_columns=False,
        ddp_find_unused_parameters=False,
        save_total_limit=3,
        logging_dir=str(args.output_dir / "logs"),
    )
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=TokenizedDataset(),
        data_collator=CompletionOnlyCollator(),
        processing_class=tokenizer,
    )

    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    result = trainer.train()
    runtime_seconds = time.perf_counter() - started
    final_adapter = args.output_dir / "final_adapter"
    trainer.save_model(str(final_adapter))
    tokenizer.save_pretrained(final_adapter)

    summary = {
        "condition": args.condition,
        "examples": len(rows),
        "runtime_seconds": runtime_seconds,
        "peak_gpu_memory_bytes": torch.cuda.max_memory_allocated(),
        "peak_gpu_memory_reserved_bytes": torch.cuda.max_memory_reserved(),
        "train_metrics": result.metrics,
        "final_adapter": str(final_adapter),
        "truncated_examples": truncated_count,
    }
    (args.output_dir / "run_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

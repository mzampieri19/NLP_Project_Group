"""Generate the blinded 160-answer Week 5 pilot export."""

from __future__ import annotations

import argparse
import csv
import gc
import json
import random
import time
from pathlib import Path

from pilot_common import (
    environment_metadata,
    load_emotion_prompts,
    load_factual_prompts,
    load_json,
    set_seed_everywhere,
)
from validate_answers import FIELDS, validate_answers


def build_prompts(work: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in load_factual_prompts(work / "factual_pilot.csv"):
        for prompt_type, field in (
            ("no_belief", "no_belief_prompt"),
            ("false_belief", "false_belief_prompt"),
        ):
            rows.append(
                {
                    "item_id": item["item_id"],
                    "prompt_type": prompt_type,
                    "prompt": item[field],
                    "source_item_id": item["source_item_id"],
                    "kind": "factual",
                }
            )
    for item in load_emotion_prompts(
        work / "emotion_pilot.jsonl", work / "conversation_ids_to_exclude.json"
    ):
        rows.append(
            {
                "item_id": item["item_id"],
                "prompt_type": "emotion",
                "prompt": item["context"],
                "source_item_id": str(item["conversation_id"]),
                "kind": "emotion",
            }
        )
    if len(rows) != 80:
        raise ValueError(f"expected 80 prompts, found {len(rows)}")
    return rows


def load_or_create_mapping(path: Path, seed: int) -> dict[str, str]:
    if path.exists():
        mapping = json.loads(path.read_text(encoding="utf-8"))
    else:
        conditions = ["control", "ev"]
        random.Random(seed).shuffle(conditions)
        mapping = {"model_A": conditions[0], "model_B": conditions[1]}
        path.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    if set(mapping) != {"model_A", "model_B"} or set(mapping.values()) != {"control", "ev"}:
        raise ValueError("invalid model-code mapping")
    return mapping


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("config/pilot_inference.json"))
    parser.add_argument("--work", type=Path, default=Path("work"))
    parser.add_argument("--adapter-root", type=Path, default=Path("runs/week5-4090d"))
    parser.add_argument("--run-root", type=Path, default=Path("runs/week5-4090d/inference"))
    parser.add_argument("--out", type=Path, default=Path("work/answers.csv"))
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    except ImportError as exc:
        raise SystemExit("Install requirements-gpu.txt before running inference.") from exc

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is required for Qwen3-8B inference.")
    if not torch.cuda.is_bf16_supported():
        raise SystemExit("A BF16-capable CUDA GPU is required.")

    config = load_json(args.config)
    seed = int(config["seed"])
    set_seed_everywhere(seed)
    prompts = build_prompts(args.work)
    if args.limit is not None:
        if args.limit < 1:
            raise ValueError("--limit must be positive")
        prompts = prompts[: args.limit]

    args.run_root.mkdir(parents=True, exist_ok=True)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    partial_path = args.run_root / "answers.partial.csv"
    mapping_path = args.run_root / "model_code_mapping.json"
    mapping = load_or_create_mapping(mapping_path, seed)

    if args.out.exists() and not args.resume:
        raise FileExistsError(f"refusing to overwrite {args.out}; use --resume or move it")
    if partial_path.exists():
        if not args.resume:
            raise FileExistsError(f"partial output exists at {partial_path}; use --resume")
        completed = validate_answers(partial_path, require_complete=False)
    elif args.out.exists() and args.resume:
        completed = validate_answers(args.out, require_complete=False)
    else:
        completed = []
    completed_keys = {
        (row["item_id"], row["model_code"], row["prompt_type"]) for row in completed
    }

    (args.run_root / "inference_config.json").write_text(
        json.dumps(config, indent=2) + "\n", encoding="utf-8"
    )
    (args.run_root / "environment.json").write_text(
        json.dumps(environment_metadata(), indent=2) + "\n", encoding="utf-8"
    )

    base_model = str(config["base_model"])
    tokenizer = AutoTokenizer.from_pretrained(base_model, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    quantization = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16,
    )
    started = time.perf_counter()

    for model_code in ("model_A", "model_B"):
        condition = mapping[model_code]
        adapter_path = args.adapter_root / condition / "final_adapter"
        if not adapter_path.is_dir():
            raise FileNotFoundError(f"missing adapter: {adapter_path}")
        pending = [
            item
            for item in prompts
            if (item["item_id"], model_code, item["prompt_type"]) not in completed_keys
        ]
        if not pending:
            continue

        base = AutoModelForCausalLM.from_pretrained(
            base_model,
            quantization_config=quantization,
            torch_dtype=torch.bfloat16,
            device_map={"": 0},
            use_cache=True,
        )
        model = PeftModel.from_pretrained(base, str(adapter_path))
        model.eval()

        for item in pending:
            system_prompt = config[
                "factual_system_prompt" if item["kind"] == "factual" else "emotion_system_prompt"
            ]
            text = tokenizer.apply_chat_template(
                [
                    {"role": "system", "content": str(system_prompt)},
                    {"role": "user", "content": item["prompt"]},
                ],
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=False,
            )
            encoded = tokenizer(text, return_tensors="pt", add_special_tokens=False)
            input_length = encoded["input_ids"].shape[1]
            if input_length > int(config["max_input_length"]):
                raise ValueError(
                    f"{item['item_id']} {item['prompt_type']} has {input_length} input tokens"
                )
            encoded = {key: value.to(model.device) for key, value in encoded.items()}
            generation_args = {
                "max_new_tokens": int(config["max_new_tokens"]),
                "do_sample": bool(config["do_sample"]),
                "pad_token_id": tokenizer.pad_token_id,
                "eos_token_id": tokenizer.eos_token_id,
            }
            with torch.inference_mode():
                output = model.generate(**encoded, **generation_args)
            answer = tokenizer.decode(output[0, input_length:], skip_special_tokens=True).strip()
            if not answer:
                raise ValueError(f"empty answer for {item['item_id']} {model_code}")
            completed.append(
                {
                    "item_id": item["item_id"],
                    "model_code": model_code,
                    "prompt_type": item["prompt_type"],
                    "answer": answer,
                    "source_item_id": item["source_item_id"],
                    "adapter_path": f"blinded:{model_code}",
                    "base_model": base_model,
                    "seed": str(seed),
                    "max_new_tokens": str(config["max_new_tokens"]),
                    "temperature": str(config["temperature"]),
                    "top_p": str(config["top_p"]),
                }
            )
            completed_keys.add((item["item_id"], model_code, item["prompt_type"]))
            write_rows(partial_path, completed)

        del model, base
        gc.collect()
        torch.cuda.empty_cache()

    require_complete = args.limit is None
    validate_answers(partial_path, require_complete=require_complete)
    write_rows(args.out, completed)
    summary = {
        "rows": len(completed),
        "runtime_seconds": time.perf_counter() - started,
        "answers": str(args.out),
        "mapping_file": str(mapping_path),
        "complete": require_complete,
    }
    (args.run_root / "inference_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

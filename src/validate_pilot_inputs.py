"""Run all non-model checks required before the pilot training starts."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from pilot_common import (
    load_emotion_prompts,
    load_factual_prompts,
    load_json,
    load_jsonl,
    sha256_file,
    validate_pairs,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--work", type=Path, default=Path("work"))
    args = parser.parse_args()

    pairs_path = args.work / "pilot_pairs.jsonl"
    pairs = load_jsonl(pairs_path)
    validate_pairs(pairs)

    exclusions = load_json(args.work / "conversation_ids_to_exclude.json")
    pair_conversations = {row["conversation_id"] for row in pairs}
    if len(exclusions) != 200 or set(exclusions) != pair_conversations:
        raise ValueError("conversation exclusion list does not exactly match training pairs")

    factual = load_factual_prompts(args.work / "factual_pilot.csv")
    emotional = load_emotion_prompts(
        args.work / "emotion_pilot.jsonl", args.work / "conversation_ids_to_exclude.json"
    )

    with (args.work / "corrections.csv").open(encoding="utf-8", newline="") as stream:
        corrections = list(csv.DictReader(stream))
    with (args.work / "change_log.csv").open(encoding="utf-8", newline="") as stream:
        change_log = list(csv.DictReader(stream))
    if len(corrections) != len(change_log):
        raise ValueError(
            f"corrections/change-log mismatch: {len(corrections)} versus {len(change_log)}"
        )

    with (args.work / "audit.csv").open(encoding="utf-8", newline="") as stream:
        audit = list(csv.DictReader(stream))
    if len(audit) != 600:
        raise ValueError(f"expected 600 audit rows, found {len(audit)}")
    if Counter(row["condition"] for row in audit) != {
        "original": 200,
        "control": 200,
        "ev": 200,
    }:
        raise ValueError("audit does not contain 200 rows for each condition")

    required_files = [
        args.work / "rubric.txt",
        args.work / "prompts.txt",
        args.work / "generation_settings.json",
        args.work / "audit_summary.md",
    ]
    missing = [str(path) for path in required_files if not path.is_file()]
    if missing:
        raise ValueError(f"missing required files: {missing}")

    print("PRE-TRAINING INPUT VALIDATION PASSED")
    print(f"  training pairs: {len(pairs)}")
    print(f"  factual items/prompts: {len(factual)}/{len(factual) * 2}")
    print(f"  emotional items: {len(emotional)}")
    print(f"  corrections: {len(corrections)}")
    print(f"  audit rows: {len(audit)}")
    print(f"  training data sha256: {sha256_file(pairs_path)}")


if __name__ == "__main__":
    main()

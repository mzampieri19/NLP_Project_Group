"""Validate the 160-row blinded Week 5 inference export."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

FIELDS = [
    "item_id",
    "model_code",
    "prompt_type",
    "answer",
    "source_item_id",
    "adapter_path",
    "base_model",
    "seed",
    "max_new_tokens",
    "temperature",
    "top_p",
]


def validate_answers(path: Path, require_complete: bool = True) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != FIELDS:
            raise ValueError(f"unexpected columns: {reader.fieldnames}")
        rows = list(reader)

    keys = [(row["item_id"], row["model_code"], row["prompt_type"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate item/model/prompt rows")
    if any(not row["answer"].strip() for row in rows):
        raise ValueError("empty answer found")

    if require_complete:
        if len(rows) != 160:
            raise ValueError(f"expected 160 rows, found {len(rows)}")
        codes = sorted({row["model_code"] for row in rows})
        if len(codes) != 2:
            raise ValueError(f"expected two blinded model codes, found {codes}")
        if Counter(row["model_code"] for row in rows) != Counter({codes[0]: 80, codes[1]: 80}):
            raise ValueError("each model must have 80 answers")
        for code in codes:
            subset = [row for row in rows if row["model_code"] == code]
            counts = Counter(row["prompt_type"] for row in subset)
            expected = Counter({"no_belief": 30, "false_belief": 30, "emotion": 20})
            if counts != expected:
                raise ValueError(f"{code}: expected {dict(expected)}, found {dict(counts)}")

    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, nargs="?", default=Path("work/answers.csv"))
    parser.add_argument("--partial", action="store_true")
    args = parser.parse_args()
    rows = validate_answers(args.path, require_complete=not args.partial)
    print(f"ANSWER VALIDATION PASSED: {len(rows)} rows")


if __name__ == "__main__":
    main()

"""Build the 30-item factual sycophancy pilot from the Nature warmth release.

The output contains ten items each from TriviaQA, TruthfulQA, and MedQA.  Every
item uses the release's unmodified ``original_neutral`` prompt as the no-belief
condition and the matching unmodified ``incorrect`` prompt as the false-belief
condition.  The sampling is deterministic.

Examples:
    python3 src/build_factual_pilot.py --out work/factual_pilot.csv
    python3 src/build_factual_pilot.py --source-dir /path/to/warm_ai_2025/eval_data
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import random
import urllib.request
from pathlib import Path

SOURCE_REPOSITORY = "https://github.com/lujainibrahim/warm_ai_2025"
SOURCE_COMMIT = "d82496879894d14c98cda4d4130f79f2b992e3ae"
RAW_ROOT = f"https://raw.githubusercontent.com/lujainibrahim/warm_ai_2025/{SOURCE_COMMIT}/eval_data"
DATASETS = {
    "trivia": {"filename": "trivia.json", "label": "TriviaQA", "seed_offset": 0},
    "truthfulqa": {"filename": "truthfulqa.json", "label": "TruthfulQA", "seed_offset": 1},
    "medqa": {"filename": "medqa.json", "label": "MedQA", "seed_offset": 2},
}
FIELDS = [
    "item_id",
    "source",
    "source_item_id",
    "no_belief_prompt",
    "false_belief_prompt",
    "correct_answer",
    "planted_false_answer",
    "source_repository",
    "source_commit",
]


def read_jsonl_text(dataset: dict[str, object], source_dir: Path | None) -> str:
    filename = str(dataset["filename"])
    if source_dir is not None:
        return (source_dir / filename).read_text(encoding="utf-8")
    url = f"{RAW_ROOT}/{filename}"
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - pinned HTTPS URL
        return response.read().decode("utf-8")


def content_key(row: dict[str, object], dataset_name: str) -> str:
    if dataset_name == "medqa":
        return str(row["question"])
    return str(row["content_key"])


def template_name(row: dict[str, object], dataset_name: str) -> str:
    if dataset_name == "medqa":
        return str(row["prompt_type"])
    return str(row["prompt_template"])


def answer_fields(row: dict[str, object], dataset_name: str) -> tuple[str, str]:
    if dataset_name == "medqa":
        return str(row["answer"]), str(row["wrong_answer"])
    return str(row["correct_answer"]), str(row["incorrect_answer"])


def load_pairs(text: str, dataset_name: str) -> list[dict[str, str]]:
    grouped: dict[str, dict[str, dict[str, object]]] = {}
    order: list[str] = []
    for raw_line in io.StringIO(text):
        if not raw_line.strip():
            continue
        row = json.loads(raw_line)
        if row.get("amendment_type") != "unmodified":
            continue
        template = template_name(row, dataset_name)
        if template not in {"original_neutral", "incorrect"}:
            continue
        key = content_key(row, dataset_name)
        if key not in grouped:
            grouped[key] = {}
            order.append(key)
        if template in grouped[key]:
            raise ValueError(f"duplicate {template} row for {dataset_name}: {key[:80]}")
        grouped[key][template] = row

    pairs: list[dict[str, str]] = []
    for source_index, key in enumerate(order, start=1):
        variants = grouped[key]
        if set(variants) != {"original_neutral", "incorrect"}:
            continue
        neutral = variants["original_neutral"]
        incorrect = variants["incorrect"]
        correct_answer, false_answer = answer_fields(neutral, dataset_name)
        false_correct, false_false = answer_fields(incorrect, dataset_name)
        if (correct_answer, false_answer) != (false_correct, false_false):
            raise ValueError(f"answer mismatch for {dataset_name}: {key[:80]}")

        false_belief = str(incorrect["prompt"]).strip()
        no_belief = str(neutral["prompt"]).strip()
        # The release's MedQA ``original_neutral`` variant adds a conversational
        # preamble that is absent from its ``incorrect`` variant.  Use the
        # ``question`` field carried by the same incorrect row so the pilot pair
        # differs only by the appended false belief, as required by the design.
        if dataset_name == "medqa":
            no_belief = str(incorrect["question"]).strip()
        if not false_belief.startswith(no_belief):
            raise ValueError(f"prompts are not a strict pair for {dataset_name}: {key[:80]}")
        suffix = false_belief[len(no_belief) :].strip()
        if not suffix:
            raise ValueError(f"false-belief suffix is empty for {dataset_name}: {key[:80]}")

        key_hash = hashlib.sha256(f"{dataset_name}\0{key}".encode()).hexdigest()[:12]
        pairs.append(
            {
                "source_item_id": f"{dataset_name}_{source_index:04d}_{key_hash}",
                "no_belief_prompt": no_belief,
                "false_belief_prompt": false_belief,
                "correct_answer": correct_answer,
                "planted_false_answer": false_answer,
            }
        )
    return pairs


def build_rows(source_dir: Path | None, seed: int, per_source: int) -> list[dict[str, str]]:
    selected: list[tuple[str, dict[str, str]]] = []
    for dataset_name, dataset in DATASETS.items():
        text = read_jsonl_text(dataset, source_dir)
        pairs = load_pairs(text, dataset_name)
        if len(pairs) < per_source:
            raise ValueError(f"{dataset_name}: need {per_source} pairs, found {len(pairs)}")
        rng = random.Random(seed + int(dataset["seed_offset"]))
        for pair in rng.sample(pairs, per_source):
            selected.append((str(dataset["label"]), pair))

    rows: list[dict[str, str]] = []
    for index, (source, pair) in enumerate(selected, start=1):
        rows.append(
            {
                "item_id": f"factual_{index:03d}",
                "source": source,
                **pair,
                "source_repository": SOURCE_REPOSITORY,
                "source_commit": SOURCE_COMMIT,
            }
        )
    return rows


def validate(rows: list[dict[str, str]], per_source: int) -> None:
    expected = per_source * len(DATASETS)
    if len(rows) != expected:
        raise ValueError(f"expected {expected} rows, found {len(rows)}")
    ids = [row["item_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate item_id")
    source_ids = [row["source_item_id"] for row in rows]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("duplicate source_item_id")
    for row in rows:
        if list(row) != FIELDS:
            raise ValueError(f"unexpected field order for {row['item_id']}")
        if any(not row[field].strip() for field in FIELDS):
            raise ValueError(f"empty field in {row['item_id']}")
        if not row["false_belief_prompt"].startswith(row["no_belief_prompt"]):
            raise ValueError(f"unpaired prompts in {row['item_id']}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("work/factual_pilot.csv"))
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--per-source", type=int, default=10)
    args = parser.parse_args()

    rows = build_rows(args.source_dir, args.seed, args.per_source)
    validate(rows, args.per_source)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} paired factual items to {args.out}")


if __name__ == "__main__":
    main()

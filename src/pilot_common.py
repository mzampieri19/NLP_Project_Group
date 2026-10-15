"""Shared data, formatting, and reproducibility helpers for the course pilot."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import platform
import random
import subprocess
from pathlib import Path
from typing import Any

PAIR_FIELDS = [
    "example_id",
    "conversation_id",
    "context",
    "original_response",
    "control_response",
    "ev_response",
]
TARGET_FIELD = {"control": "control_response", "ev": "ev_response"}


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream)


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {exc}") from exc
    return rows


def validate_pairs(rows: list[dict[str, Any]], expect: int = 200) -> None:
    if len(rows) != expect:
        raise ValueError(f"expected {expect} training pairs, found {len(rows)}")
    ids = [row.get("example_id") for row in rows]
    conversations = [row.get("conversation_id") for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate example_id in training pairs")
    if len(conversations) != len(set(conversations)):
        raise ValueError("training pairs are not conversation-unique")
    for row in rows:
        if list(row) != PAIR_FIELDS:
            raise ValueError(f"{row.get('example_id')}: expected fields {PAIR_FIELDS}, got {list(row)}")
        for field in PAIR_FIELDS[2:]:
            if not isinstance(row[field], str) or not row[field].strip():
                raise ValueError(f"{row['example_id']}: empty {field}")
        if not row["context"].rstrip().splitlines()[-1].startswith("Seeker:"):
            raise ValueError(f"{row['example_id']}: context does not end with a Seeker turn")


def training_messages(context: str, system_prompt: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": context},
    ]


def format_prompt(tokenizer: Any, context: str, system_prompt: str) -> str:
    return tokenizer.apply_chat_template(
        training_messages(context, system_prompt),
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def set_seed_everywhere(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass
    try:
        import torch

        torch.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def package_versions(names: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in names:
        try:
            module = __import__(name)
            versions[name] = str(getattr(module, "__version__", "unknown"))
        except ImportError:
            versions[name] = "not installed"
    return versions


def git_state() -> dict[str, str]:
    def run(*args: str) -> str:
        try:
            return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return "unavailable"

    return {
        "commit": run("git", "rev-parse", "HEAD"),
        "branch": run("git", "branch", "--show-current"),
        "status": run("git", "status", "--short"),
    }


def environment_metadata() -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": package_versions(
            ["torch", "transformers", "datasets", "peft", "accelerate", "bitsandbytes"]
        ),
        "git": git_state(),
    }
    try:
        import torch

        metadata["cuda_available"] = torch.cuda.is_available()
        metadata["cuda_version"] = torch.version.cuda
        metadata["gpu"] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
    except ImportError:
        metadata["cuda_available"] = False
        metadata["cuda_version"] = None
        metadata["gpu"] = None
    return metadata


def load_factual_prompts(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    required = {
        "item_id",
        "source",
        "source_item_id",
        "no_belief_prompt",
        "false_belief_prompt",
        "correct_answer",
        "planted_false_answer",
    }
    if len(rows) != 30:
        raise ValueError(f"expected 30 factual items, found {len(rows)}")
    if set(rows[0]) < required:
        raise ValueError(f"factual file missing columns: {sorted(required - set(rows[0]))}")
    if len({row["item_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate factual item_id")
    for row in rows:
        if not row["false_belief_prompt"].startswith(row["no_belief_prompt"]):
            raise ValueError(f"{row['item_id']}: prompts do not form a strict pair")
    return rows


def load_emotion_prompts(
    path: str | Path, excluded_conversations_path: str | Path
) -> list[dict[str, Any]]:
    rows = load_jsonl(path)
    excluded = set(load_json(excluded_conversations_path))
    if len(rows) != 20:
        raise ValueError(f"expected 20 emotional items, found {len(rows)}")
    if len({row["item_id"] for row in rows}) != len(rows):
        raise ValueError("duplicate emotional item_id")
    overlap = excluded & {row["conversation_id"] for row in rows}
    if overlap:
        raise ValueError(f"emotional evaluation overlaps training conversations: {sorted(overlap)}")
    for row in rows:
        if set(row) != {"item_id", "conversation_id", "context"}:
            raise ValueError(f"{row.get('item_id')}: unexpected emotional fields")
        if not row["context"].rstrip().splitlines()[-1].startswith("Seeker:"):
            raise ValueError(f"{row['item_id']}: context does not end with a Seeker turn")
    return rows

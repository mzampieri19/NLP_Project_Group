"""Run the matched Control and EV jobs with one locked configuration."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/pilot_sft.json")
    parser.add_argument("--pairs", default="work/pilot_pairs.jsonl")
    parser.add_argument("--run-root", type=Path, default=Path("runs/pilot"))
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    for condition in ("control", "ev"):
        output_dir = args.run_root / condition
        command = [
            sys.executable,
            "src/train_lora.py",
            "--condition",
            condition,
            "--pairs",
            args.pairs,
            "--config",
            args.config,
            "--output-dir",
            str(output_dir),
        ]
        if args.smoke:
            command.extend(["--limit", "4", "--max-steps", "1"])
        print("Running:", " ".join(command), flush=True)
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()

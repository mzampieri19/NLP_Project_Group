"""Freeze the project's ESConv conversation-level 80/10/10 split.

ESConv ships no official split. The team agreed (Week 9) to use the same seeded split as the
Week 5 pilot: shuffle conversation indices 0..N-1 with random.Random(42); the first 80% are
train, the next 10% validation, the last 10% test. This reproduces exactly the Week 5 train
set used by select_turns.py, so every Week 5 pilot conversation is in train.

conversation_id = position of the conversation in ESConv.json, so everyone must use the same
file (its sha256 is recorded in the output).

Usage:
  python3 src/make_splits.py --esconv data/ESConv.json --out formal/splits/esconv_split.json
"""

import argparse
import hashlib
import json
import os
import random

SEED = 42


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esconv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pilot_ids", default="work/conversation_ids_to_exclude.json",
                    help="Week 5 pilot conversation ids; checked to be inside train")
    a = ap.parse_args()

    n = len(json.load(open(a.esconv, encoding="utf-8")))
    ids = list(range(n))
    random.Random(SEED).shuffle(ids)
    n_tr, n_va = int(0.8 * n), int(0.1 * n)
    split = {"train": sorted(ids[:n_tr]),
             "validation": sorted(ids[n_tr:n_tr + n_va]),
             "test": sorted(ids[n_tr + n_va:])}

    allids = split["train"] + split["validation"] + split["test"]
    assert len(allids) == len(set(allids)) == n, "split is not a partition"
    if os.path.exists(a.pilot_ids):
        pilot = set(json.load(open(a.pilot_ids)))
        outside = sorted(pilot - set(split["train"]))
        assert not outside, f"Week 5 pilot conversations outside train: {outside}"
        print(f"All {len(pilot)} Week 5 pilot conversations are in train.")

    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump({"dataset": "ESConv", "source_file": a.esconv, "source_sha256": sha256(a.esconv),
               "n_conversations": n, "method": "random.Random(42).shuffle(range(N)); "
               "first 80% train, next 10% validation, rest test (same as Week 5 pilot)",
               "seed": SEED, "counts": {k: len(v) for k, v in split.items()}, **split},
              open(a.out, "w"), indent=1)
    print(f"Wrote {a.out}: " + ", ".join(f"{k} {len(v)}" for k, v in split.items()))


if __name__ == "__main__":
    main()

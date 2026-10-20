"""Select 20 held-out ESConv contexts for the emotional-validation evaluation (Harini).

Usage:
  python3 src/select_emotion_contexts.py --esconv data/ESConv.json --out work \
      [--exclude work/conversation_ids_to_exclude.json] [--n 20]

Instruction followed, verbatim:
  "Select 20 held-out ESConv contexts from conversations that do not appear in
   Michael's training file. Save the full preceding context and conversation ID;
   do not use the target supporter answer as part of the prompt."

How that maps to code (no content filtering, no truncation of 'long' contexts):
  - Held-out = the 20% of conversations NOT in the seeded 80/10/10 training split
    (seed 42, identical to select_turns.py), minus any id in Michael's training
    file (--exclude). The two are already disjoint; the exclude is a safety assert.
  - Consecutive same-speaker turns are merged into one block, exactly as
    select_turns.py does, so a "supporter answer" is one unit.
  - The FULL preceding context = the whole conversation truncated to end at its
    LAST seeker block, so the prompt ends on the user and the model is asked to
    reply as the supporter. The target supporter answer (the supporter's trailing
    block, if any) is dropped and never written out. Nothing is cut for length.
  - A seeded sample of --n conversations is drawn from the held-out pool.

Outputs:
  work/emotion_pilot.jsonl          item_id, conversation_id, context   (send to Rong)
  work/emotion_selection_info.json  settings, for the methods write-up
"""
import argparse
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(__file__))
from select_turns import blocks, fmt, SEED  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esconv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude")
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    convs = json.load(open(a.esconv))
    n = len(convs)

    # same split as select_turns.py: held-out = non-train 20%
    rng = random.Random(SEED)
    ids = list(range(n))
    rng.shuffle(ids)
    train = set(ids[: int(0.8 * n)])
    heldout = sorted(set(ids) - train)

    excluded = set(json.load(open(a.exclude))) if a.exclude else set()
    bad = excluded & set(heldout)
    assert not bad, f"excluded training ids unexpectedly in held-out pool: {sorted(bad)}"
    pool = [c for c in heldout if c not in excluded]

    rng.shuffle(pool)
    rows = []
    for cid in pool:
        bs = blocks(convs[cid]["dialog"], merge=True)
        # full preceding context = whole conversation up to its last seeker block;
        # the supporter's trailing answer (if any) is the withheld target.
        seeker_idx = [i for i, b in enumerate(bs) if b["speaker"] == "seeker"]
        if not seeker_idx:
            continue
        end = seeker_idx[-1] + 1            # include the last seeker block
        rows.append({"conversation_id": cid, "context": fmt(bs[:end])})
        if len(rows) == a.n:
            break

    assert len(rows) == a.n, f"only found {len(rows)} usable held-out conversations"
    for k, r in enumerate(rows, 1):
        r["item_id"] = f"emotion_{k:03d}"

    with open(f"{a.out}/emotion_pilot.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps({"item_id": r["item_id"],
                                "conversation_id": r["conversation_id"],
                                "context": r["context"]}) + "\n")
    with open(f"{a.out}/emotion_selection_info.json", "w") as f:
        json.dump({"seed": SEED, "n": a.n, "n_convs": n,
                   "held_out_pool": len(heldout), "held_out_after_exclude": len(pool),
                   "split_source": "seeded 80/10/10 (seed 42), held-out = non-train 20%",
                   "rule": "full preceding context = conversation truncated to its last "
                           "seeker block; target supporter answer dropped; no content filtering"},
                  f, indent=2)
        f.write("\n")
    print(f"Selected {len(rows)} held-out contexts from {len({r['conversation_id'] for r in rows})} "
          f"conversations (pool of {len(pool)}). Wrote {a.out}/emotion_pilot.jsonl")


if __name__ == "__main__":
    main()

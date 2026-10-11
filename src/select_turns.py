"""Select 200 supporter responses from ESConv's TRAINING split.

Usage:
  python select_turns.py --esconv ESConv.json --out work/ [--train_ids train_ids.json]
                         [--no_merge] [--keep_pure_affirmation] [--n 200]
"""

import argparse
import json
import os
import random

SEED = 42
MIN_W, MAX_W = 8, 120
CUES = (
    "hello",
    "hi ",
    "hi,",
    "hey",
    "good morning",
    "good evening",
    "bye",
    "goodbye",
    "take care",
    "have a great",
    "have a good",
    "thank you for",
    "thanks for",
)
PURE_AFFIRM = {"Affirmation and Reassurance"}


def norm(s):
    return " ".join(s.split())


def blocks(dialog, merge):
    out = []
    for t in dialog:
        sp, txt = t["speaker"], norm(t["content"])
        strat = t.get("annotation", {}).get("strategy")
        if merge and out and out[-1]["speaker"] == sp:
            out[-1]["text"] += " " + txt
            if strat:
                out[-1]["strategies"].append(strat)
        else:
            out.append({"speaker": sp, "text": txt, "strategies": [strat] if strat else []})
    return out


def fmt(bs):
    return "\n".join(
        f"{'Seeker' if b['speaker'] == 'seeker' else 'Supporter'}: {b['text']}" for b in bs
    )


def usable(bs, i, keep_affirm):
    b = bs[i]
    if b["speaker"] != "supporter" or i < 3 or i >= len(bs) - 2:
        return False
    if bs[i - 1]["speaker"] != "seeker":
        return False
    if not (MIN_W <= len(b["text"].split()) <= MAX_W):
        return False
    if b["text"].lower().startswith(CUES):
        return False
    if not keep_affirm and b["strategies"] and set(b["strategies"]) <= PURE_AFFIRM:
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esconv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--train_ids")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--no_merge", action="store_true")
    ap.add_argument("--keep_pure_affirmation", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    rng = random.Random(SEED)

    convs = json.load(open(a.esconv))
    if a.train_ids:
        train, split_src = list(json.load(open(a.train_ids))), f"file:{a.train_ids}"
    else:
        ids = list(range(len(convs)))
        rng.shuffle(ids)
        train = sorted(ids[: int(0.8 * len(ids))])
        split_src = "seeded random 80/10/10 fallback (seed 42)"
    rng.shuffle(train)

    rows = []
    for cid in train:
        bs = blocks(convs[cid]["dialog"], merge=not a.no_merge)
        cands = [i for i in range(len(bs)) if usable(bs, i, a.keep_pure_affirmation)]
        if not cands:
            continue
        i = rng.choice(cands)
        rows.append(
            {
                "conversation_id": cid,
                "turn_index": i,
                "context": fmt(bs[:i]),
                "original_response": bs[i]["text"],
                "original_strategies": bs[i]["strategies"],
            }
        )
        if len(rows) == a.n:
            break

    assert len(rows) == a.n, f"only found {len(rows)} usable conversations"
    for k, r in enumerate(rows, 1):
        r["example_id"] = f"pair_{k:03d}"
    assert len({r["example_id"] for r in rows}) == a.n

    with open(f"{a.out}/selected_turns.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    json.dump(
        sorted(r["conversation_id"] for r in rows),
        open(f"{a.out}/conversation_ids_to_exclude.json", "w"),
    )
    json.dump(
        {
            "seed": SEED,
            "split_source": split_src,
            "n": a.n,
            "speakers": "seeker/supporter",
            "merge_consecutive_turns": not a.no_merge,
            "skip_pure_affirmation": not a.keep_pure_affirmation,
            "filters": f"supporter block after seeker block; {MIN_W}-{MAX_W} words; "
            "block index>=3; not last 2 blocks; not greeting/farewell",
        },
        open(f"{a.out}/selection_info.json", "w"),
        indent=2,
    )
    print(
        "Selected",
        a.n,
        "responses from",
        len({r["conversation_id"] for r in rows}),
        "conversations",
    )


if __name__ == "__main__":
    main()

"""Select 200 supporter responses from ESConv's TRAINING split.

Usage:
  python select_turns.py --esconv ESConv.json --out work/ [--train_ids train_ids.json]
                         [--no_merge] [--skip_strategies ...] [--n 200]

Verified against a real ESConv record:
  - File = JSON list of conversations. Each has "dialog": a list of
    {"speaker": "seeker" | "supporter", "annotation": {...}, "content": str}
    plus emotion_type, problem_type, situation, etc.
  - Supporter turns carry annotation["strategy"] (Question, Providing Suggestions,
    Information, Affirmation and Reassurance, Self-disclosure, ...).
  - The SAME speaker often has several consecutive turns, e.g.
      supporter: "I can understand that."
      supporter: "Is there another job that would pay you close to what you make?"
    By default consecutive same-speaker turns are MERGED into one block, so a
    "response" is everything the supporter said before the seeker spoke again.
    (--no_merge treats every raw turn as its own response.)
  - Records have no ID field, so conversation_id = index in the list. Everyone
    must use the SAME ESConv.json file version for IDs to line up.

Design choices (confirm with the team):
  - One response per conversation -> Harini excludes exactly 200 conversations.
  - Responses whose strategies are ONLY "Affirmation and Reassurance" and/or
    "Reflection of feelings" are skipped by default: they are validation, so Control
    (validation removed) has nothing to keep, and EV has little to add. Change the
    list with --skip_strategies, or pass the flag with no values to skip nothing.
    Mixed responses (e.g. reassurance + a suggestion) are kept.
  - "Training split": pass --train_ids if the team has an official list; otherwise
    a seeded random 80/10/10 conversation split is used.
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
DEFAULT_SKIP = ["Affirmation and Reassurance", "Reflection of feelings"]


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


def usable(bs, i, skip):
    b = bs[i]
    if b["speaker"] != "supporter" or i < 3 or i >= len(bs) - 2:
        return False
    if bs[i - 1]["speaker"] != "seeker":
        return False
    if not (MIN_W <= len(b["text"].split()) <= MAX_W):
        return False
    if b["text"].lower().startswith(CUES):
        return False
    if skip and b["strategies"] and set(b["strategies"]) <= skip:
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esconv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--train_ids")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--no_merge", action="store_true")
    ap.add_argument(
        "--skip_strategies",
        nargs="*",
        default=DEFAULT_SKIP,
        help="skip responses whose strategies are ALL in this list; "
        "pass the flag with no values to skip nothing",
    )
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
        cands = [i for i in range(len(bs)) if usable(bs, i, set(a.skip_strategies))]
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
        )  # kept here only; not in final export
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
            "skip_strategies_if_only": a.skip_strategies,
            "filters": f"supporter block after seeker block; {MIN_W}-{MAX_W} words; "
            "block index>=3; not last 2 blocks; not greeting/farewell",
        },
        open(f"{a.out}/selection_info.json", "w"),
        indent=2,
    )
    print(
        f"Selected {a.n} responses from {len({r['conversation_id'] for r in rows})} conversations"
    )


if __name__ == "__main__":
    main()

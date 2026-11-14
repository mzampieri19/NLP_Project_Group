"""Week 10: conversation-first, stratified sampling of the formal training set (Rong, 2026-11-14).

Usage:
  python3 src/sample_formal.py --out formal/sample/v0.1 [--exclude_convs held_out.txt]

Pool: source-QC PASS examples from the training splits only (ESConv project split, seed 42;
EmpatheticDialogues official train). REMOVE rows (incl. pair_001, invalid targets and exact
duplicates) never enter the pool. --exclude_convs drops held-out evaluation conversations
(one ESConv conversation_id per line, e.g. "853"; lines starting with "#" are ignored).

ESConv: every eligible training conversation (>=1 PASS supporter response). Each response is
placed in a stage by the relative position of its first raw turn in the dialogue
(early < 1/3 <= middle < 2/3 <= late). Up to three responses per conversation: one random PASS
response per stage that has one (seeded). Support-strategy coverage is reported, not forced.

EmpatheticDialogues: as many conversations as there are ESConv conversations in the sample
(conversations, not responses). Allocated across the 32 emotion labels in proportion to the
eligible pool (largest remainder), conversations drawn at random within each emotion, then one
random PASS Listener response per conversation.

The final size follows from these rules; nothing is rounded to a target number. Selection never
looks at rewrites or EPITOME scores.

Outputs (in --out):
  sample_ids.jsonl               one line per selected example (input to generate_rewrites.py)
  sampling_manifest.csv          selected examples with conversation/turn ids and stratum
  conversation_manifest.csv      every training conversation: eligible?, #valid, #selected,
                                 exclusion reason
  sampling_summary.json          seed, criteria, input hashes, per-source counts, exclusion
                                 counts, stage / strategy / emotion coverage
"""

import argparse
import collections
import csv
import datetime
import hashlib
import json
import os
import random

SEED = 42
STAGES = ("early", "middle", "late")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def stage_of(pos):
    return STAGES[min(int(pos * 3), 2)]


def largest_remainder(sizes, total):
    """Split `total` across strata in proportion to `sizes` (dict), capped at each size."""
    n = sum(sizes.values())
    quota = {k: total * v / n for k, v in sizes.items()}
    alloc = {k: min(int(q), sizes[k]) for k, q in quota.items()}
    for k in sorted(quota, key=lambda k: (-(quota[k] - int(quota[k])), k)):
        if sum(alloc.values()) >= total:
            break
        if alloc[k] < sizes[k]:
            alloc[k] += 1
    return alloc


def shares(counter):
    n = sum(counter.values())
    return {k: {"n": v, "share": round(v / n, 4)} for k, v in counter.most_common()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", default="formal/extract/records_base.jsonl")
    ap.add_argument("--metadata", default="formal/extract/source_metadata.jsonl")
    ap.add_argument("--qc", default="formal/qc/source_qc.csv")
    ap.add_argument("--split", default="formal/splits/esconv_split.json")
    ap.add_argument("--esconv", default="data/ESConv.json")
    ap.add_argument("--exclude_convs", help="held-out ESConv conversation ids, one per line")
    ap.add_argument("--out", default="formal/sample/v0.1")
    a = ap.parse_args()

    qc = {r["example_id"]: r for r in csv.DictReader(open(a.qc, encoding="utf-8"))}
    meta = {}
    for line in open(a.metadata, encoding="utf-8"):
        m = json.loads(line)
        meta[m["example_id"]] = m
    recs = [json.loads(line) for line in open(a.records, encoding="utf-8")]
    split = json.load(open(a.split))
    train_ids = {str(i) for i in split["train"]}
    convs = json.load(open(a.esconv, encoding="utf-8"))
    held_out = set()
    if a.exclude_convs:
        held_out = {ln.strip() for ln in open(a.exclude_convs) if ln.strip()
                    and not ln.startswith("#")}
        unknown = held_out - {str(i) for i in range(len(convs))}
        assert not unknown, f"unknown ESConv conversation ids: {sorted(unknown)[:5]}"

    by_conv = collections.defaultdict(list)  # (dataset, conv) -> records
    for r in recs:
        assert r["source_split"] == "train", r["example_id"]
        by_conv[(r["source_dataset"], r["conversation_id"])].append(r)

    rng = random.Random(SEED)
    selected, conv_rows = [], []
    excl = collections.Counter()

    # ---------------- ESConv
    for cid in sorted(train_ids, key=int):
        rs = by_conv.get(("ESConv", cid), [])
        valid = [r for r in rs if qc[r["example_id"]]["status"] == "PASS"]
        reason = ("held_out_evaluation" if cid in held_out
                  else "no_valid_supporter_response" if not valid else "")
        picked = []
        if not reason:
            n_turns = len(convs[int(cid)]["dialog"])
            by_stage = collections.defaultdict(list)
            for r in valid:
                pos = meta[r["example_id"]]["target_raw_turn_indices"][0] / n_turns
                by_stage[stage_of(pos)].append((r, pos))
            for st in STAGES:
                if by_stage[st]:
                    r, pos = rng.choice(by_stage[st])
                    picked.append(r)
                    selected.append({"example_id": r["example_id"], "source_dataset": "ESConv",
                                     "conversation_id": cid, "turn_id": r["turn_id"],
                                     "stratum": st, "relative_position": round(pos, 3),
                                     "support_strategy": "|".join(
                                         meta[r["example_id"]]["target_support_strategy"])})
        else:
            excl[f"ESConv/{reason}"] += 1
        conv_rows.append({"source_dataset": "ESConv", "conversation_id": cid,
                          "n_responses": len(rs), "n_valid": len(valid),
                          "n_selected": len(picked), "exclusion_reason": reason})
    n_esc_convs = sum(1 for c in conv_rows if c["n_selected"])
    assert not held_out & {s["conversation_id"] for s in selected}

    # ---------------- EmpatheticDialogues
    ed_pool = collections.defaultdict(list)  # emotion -> [conv ids]
    ed_valid = {}
    for (ds, cid), rs in sorted(by_conv.items()):
        if ds != "EmpatheticDialogues":
            continue
        valid = [r for r in rs if qc[r["example_id"]]["status"] == "PASS"]
        ed_valid[cid] = (rs, valid)
        if valid:
            ed_pool[meta[valid[0]["example_id"]]["emotion_label"]].append(cid)
        else:
            excl["EmpatheticDialogues/no_valid_listener_response"] += 1
    alloc = largest_remainder({e: len(c) for e, c in ed_pool.items()}, n_esc_convs)
    chosen = set()
    for emo in sorted(ed_pool):
        for cid in rng.sample(ed_pool[emo], alloc[emo]):
            chosen.add(cid)
            r = rng.choice(ed_valid[cid][1])
            selected.append({"example_id": r["example_id"], "source_dataset": "EmpatheticDialogues",
                             "conversation_id": cid, "turn_id": r["turn_id"], "stratum": emo,
                             "relative_position": "", "support_strategy": ""})
    for cid, (rs, valid) in ed_valid.items():
        conv_rows.append({"source_dataset": "EmpatheticDialogues", "conversation_id": cid,
                          "n_responses": len(rs), "n_valid": len(valid),
                          "n_selected": int(cid in chosen),
                          "exclusion_reason": "" if valid else "no_valid_listener_response"})

    ids = [s["example_id"] for s in selected]
    assert len(ids) == len(set(ids))
    assert all(qc[i]["status"] == "PASS" for i in ids)

    # ---------------- outputs
    os.makedirs(a.out, exist_ok=True)
    with open(f"{a.out}/sample_ids.jsonl", "w") as f:
        for s in selected:
            f.write(json.dumps({"example_id": s["example_id"]}) + "\n")
    for name, rows in (("sampling_manifest.csv", selected),
                       ("conversation_manifest.csv", conv_rows)):
        with open(f"{a.out}/{name}", "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    esc = [s for s in selected if s["source_dataset"] == "ESConv"]
    ed = [s for s in selected if s["source_dataset"] == "EmpatheticDialogues"]
    pool_strat = collections.Counter(
        st for r in recs if r["source_dataset"] == "ESConv"
        and qc[r["example_id"]]["status"] == "PASS" and r["conversation_id"] not in held_out
        for st in meta[r["example_id"]]["target_support_strategy"])
    samp_strat = collections.Counter(st for s in esc for st in s["support_strategy"].split("|"))
    per_conv = collections.Counter(c["n_selected"] for c in conv_rows
                                   if c["source_dataset"] == "ESConv" and c["n_selected"])
    summary = {
        "script": "src/sample_formal.py", "seed": SEED,
        "run_utc": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "inputs": {p: sha256(p) for p in (a.records, a.qc, a.split)},
        "held_out_file": a.exclude_convs, "n_held_out_convs": len(held_out),
        "criteria": {
            "pool": "source-QC PASS, training splits only (ESConv project split seed 42; ED "
                    "official train); held-out evaluation conversations excluded",
            "esconv": "all eligible train conversations; up to 3 responses each, one random "
                      "PASS per stage (early/middle/late by relative position of the first "
                      "raw turn, tertiles)",
            "ed": "number of conversations = number of sampled ESConv conversations; "
                  "proportional allocation over emotion labels (largest remainder); one "
                  "random PASS Listener response per conversation"},
        "counts": {
            "ESConv": {"conversations": n_esc_convs, "responses": len(esc),
                       "conversations_by_n_selected": dict(sorted(per_conv.items())),
                       "by_stage": dict(collections.Counter(s["stratum"] for s in esc))},
            "EmpatheticDialogues": {"conversations": len(ed), "responses": len(ed),
                                    "by_emotion": dict(sorted(collections.Counter(
                                        s["stratum"] for s in ed).items()))},
            "total_examples": len(selected), "total_generation_calls": 2 * len(selected)},
        "conversation_exclusions": dict(excl),
        "esconv_strategy_coverage": {"pool": shares(pool_strat), "sample": shares(samp_strat)},
    }
    json.dump(summary, open(f"{a.out}/sampling_summary.json", "w"), indent=2)
    ce, cd = summary["counts"]["ESConv"], summary["counts"]["EmpatheticDialogues"]
    print(f"ESConv: {ce['conversations']} conversations, {len(esc)} responses "
          f"{ce['by_stage']}; per conversation {ce['conversations_by_n_selected']}")
    print(f"ED: {len(ed)} conversations/responses over {len(cd['by_emotion'])} emotions")
    print(f"Total {len(selected)} examples -> {2 * len(selected)} generation calls. "
          f"Exclusions: {dict(excl)}")
    print("Strategy share pool -> sample:")
    for k, v in summary["esconv_strategy_coverage"]["pool"].items():
        s = summary["esconv_strategy_coverage"]["sample"].get(k, {"share": 0})
        print(f"  {k:<28} {v['share']:.3f} -> {s['share']:.3f}")
    print(f"Wrote {a.out}/")


if __name__ == "__main__":
    main()

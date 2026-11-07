"""Week 9 Step 1: extract every supporter/listener target turn from the TRAIN splits of
ESConv and EmpatheticDialogues (ED) into one shared record format.

Usage:
  python3 src/extract_turns.py \
      --esconv data/ESConv.json --esconv_split formal/splits/esconv_split.json \
      --ed_dir data/empatheticdialogues/empatheticdialogues --out formal/extract
  optional: --esconv_exclude ids.json   (ESConv conversation ids that must NOT be used for
            training, e.g. Harini's held-out evaluation conversations; they are dropped and
            listed in the summary)

Rules (from the Week 8/9 plan, decisions confirmed Nov 7):
  ESConv
    - Project split = seeded 80/10/10 (make_splits.py); only "train" conversations are used.
    - Consecutive turns by the same speaker are MERGED into one block (same as the pilot), so
      one target = everything the supporter says before the seeker speaks again.
    - One example for every supporter block that has a seeker block before it (supporter
      openers with no seeker turn before them have no user message to answer, so no example).
  ED
    - Official train.csv only. Rows grouped by conv_id, sorted by utterance_idx.
    - The Speaker is whoever wrote utterance 1 (their speaker_idx); the other participant is the
      Listener. speaker_idx is a crowdworker id, NOT a fixed 0/1 role.
    - One example for every Listener utterance. "_comma_" is decoded to ",".
  Both
    - dialogue_context = every actual turn before the target, in order (the last one is the
      current user turn); current_user_utterance = the immediately preceding user turn.
    - Pre-chat fields (ESConv situation/emotion/problem/experience, ED emotion label and prompt)
      are written ONLY to source_metadata.jsonl, never into the records that feed the teacher.
    - No quality filtering here; that is Step 2 (source_qc.py). original_response is kept
      exactly (whitespace-normalized only).

Outputs (in --out):
  records_base.jsonl        one record per target turn (provenance + context + target)
  source_metadata.jsonl     example_id -> source-specific metadata (never sent to the teacher)
  source_manifest.csv       one row per example with provenance and length stats
  extraction_summary.json   counts, input hashes, integrity-check results
"""

import argparse
import collections
import csv
import datetime
import hashlib
import json
import os

SCRIPT_VERSION = "1.0"
ROLES = {"ESConv": ("seeker", "supporter"), "EmpatheticDialogues": ("speaker", "listener")}


def norm(s):
    return " ".join(s.split())


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def nwords(s):
    return len(s.split())


# ---------------------------------------------------------------- ESConv
def esconv_blocks(dialog):
    """Merge consecutive same-speaker turns. Keeps raw turn indices and strategies."""
    out = []
    for i, t in enumerate(dialog):
        sp, txt = t["speaker"], norm(t.get("content", ""))
        strat = (t.get("annotation") or {}).get("strategy")
        if out and out[-1]["speaker"] == sp:
            b = out[-1]
            b["text"] = norm(b["text"] + " " + txt)
            b["raw_turns"].append(i)
            if strat:
                b["strategies"].append(strat)
        else:
            out.append({"speaker": sp, "text": txt, "raw_turns": [i],
                        "strategies": [strat] if strat else []})
    return out


def extract_esconv(path, split_path, exclude):
    convs = json.load(open(path, encoding="utf-8"))
    split = json.load(open(split_path))
    assert split["n_conversations"] == len(convs), "split file was made from a different ESConv"
    assert split["source_sha256"] == sha256(path), "ESConv.json differs from the split's file"
    train = [c for c in split["train"] if c not in exclude]
    stats = collections.Counter()
    recs, metas = [], []
    for cid in train:
        c = convs[cid]
        speakers = {t["speaker"] for t in c["dialog"]}
        assert speakers <= {"seeker", "supporter"}, f"conv {cid}: unexpected speakers {speakers}"
        bs = esconv_blocks(c["dialog"])
        stats["conversations"] += 1
        for bi, b in enumerate(bs):
            if b["speaker"] != "supporter":
                continue
            stats["supporter_blocks"] += 1
            if bi == 0:
                stats["skipped_opener_no_user_turn"] += 1
                continue
            prev = bs[bi - 1]
            assert prev["speaker"] == "seeker"  # guaranteed by merging
            eid = f"esc-tr-c{cid:04d}-b{bi:03d}"
            recs.append({
                "example_id": eid, "source_dataset": "ESConv", "source_split": "train",
                "conversation_id": str(cid), "turn_id": f"b{bi:03d}", "target_role": "supporter",
                "dialogue_context": [{"speaker": x["speaker"], "text": x["text"]} for x in bs[:bi]],
                "current_user_utterance": prev["text"],
                "original_response": b["text"]})
            metas.append({
                "example_id": eid, "source_dataset": "ESConv",
                "problem_type": c.get("problem_type"), "emotion_type": c.get("emotion_type"),
                "experience_type": c.get("experience_type"), "situation": c.get("situation"),
                "target_support_strategy": b["strategies"] or None,
                "target_raw_turn_indices": b["raw_turns"],
                "n_raw_turns_merged": len(b["raw_turns"])})
            stats["merged_targets"] += len(b["raw_turns"]) > 1
    return recs, metas, stats


# ---------------------------------------------------------------- EmpatheticDialogues
ED_FIELDS = ["conv_id", "utterance_idx", "context", "prompt", "speaker_idx", "utterance",
             "selfeval", "tags"]


def ed_text(s):
    return norm(s.replace("_comma_", ","))


def read_ed(path):
    """ED CSVs are not standard CSV (commas inside fields are written as _comma_). train.csv has
    exactly 8 fields per line; valid/test add a 9th candidates field. Split on the first 7
    commas so a stray comma can only land in the last field."""
    rows = []
    with open(path, encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split(",")
        assert header[:8] == ED_FIELDS, f"unexpected ED header {header}"
        for ln, line in enumerate(f, start=2):
            line = line.rstrip("\n")
            if not line:
                continue
            p = line.split(",", 7)
            assert len(p) == 8, f"{path}:{ln}: malformed row"
            rows.append(dict(zip(ED_FIELDS, p, strict=True)))
    return rows


def extract_ed(ed_dir):
    rows = read_ed(os.path.join(ed_dir, "train.csv"))
    heldout = set()
    for s in ("valid", "test"):
        p = os.path.join(ed_dir, f"{s}.csv")
        if os.path.exists(p):
            heldout |= {r["conv_id"] for r in read_ed(p)}
    convs = collections.defaultdict(list)
    for r in rows:
        convs[r["conv_id"]].append(r)
    leak = sorted(set(convs) & heldout)
    assert not leak, f"ED train conv_ids also in valid/test: {leak[:5]}"

    stats = collections.Counter()
    recs, metas = [], []
    for conv_id in sorted(convs, key=lambda k: tuple(int(x.split(":")[1]) for x in k.split("_"))):
        rs = sorted(convs[conv_id], key=lambda r: int(r["utterance_idx"]))
        idxs = [int(r["utterance_idx"]) for r in rs]
        assert idxs == list(range(1, len(rs) + 1)), f"{conv_id}: utterance_idx gaps {idxs}"
        assert len({(r["context"], r["prompt"]) for r in rs}) == 1, f"{conv_id}: mixed labels"
        speaker_worker = rs[0]["speaker_idx"]
        workers = {r["speaker_idx"] for r in rs}
        assert len(workers) <= 2, f"{conv_id}: more than two participants"
        turns = [{"speaker": "speaker" if r["speaker_idx"] == speaker_worker else "listener",
                  "text": ed_text(r["utterance"]), "row": r} for r in rs]
        stats["conversations"] += 1
        stats["single_participant_conversations"] += len(workers) == 1
        for i, t in enumerate(turns):
            if t["speaker"] != "listener":
                continue
            stats["listener_utterances"] += 1
            prev = turns[i - 1]
            if prev["speaker"] != "speaker":  # never seen in train; guard anyway
                stats["skipped_listener_after_listener"] += 1
                continue
            r = t["row"]
            hit, conv = conv_id.split("_")
            uidx = int(r["utterance_idx"])
            eid = f"ed-tr-{hit.replace(':', '')}-{conv.replace(':', '')}-u{uidx:02d}"
            recs.append({
                "example_id": eid, "source_dataset": "EmpatheticDialogues", "source_split": "train",
                "conversation_id": conv_id, "turn_id": r["utterance_idx"],
                "target_role": "listener",
                "dialogue_context": [{"speaker": x["speaker"], "text": x["text"]}
                                     for x in turns[:i]],
                "current_user_utterance": prev["text"],
                "original_response": t["text"]})
            metas.append({
                "example_id": eid, "source_dataset": "EmpatheticDialogues",
                "emotion_label": rs[0]["context"], "situation_prompt": ed_text(rs[0]["prompt"]),
                "speaker_idx": r["speaker_idx"], "speaker_role_worker_idx": speaker_worker,
                "utterance_idx": int(r["utterance_idx"]), "selfeval": rs[0]["selfeval"] or None})
    stats["heldout_conv_ids_checked"] = len(heldout)
    return recs, metas, stats


# ---------------------------------------------------------------- integrity checks
def check(recs, metas, esconv_split):
    problems = []
    ids = [r["example_id"] for r in recs]
    if len(ids) != len(set(ids)):
        problems.append("duplicate example_id")
    if [m["example_id"] for m in metas] != ids:
        problems.append("metadata not aligned with records")
    held = set(esconv_split["validation"]) | set(esconv_split["test"])
    user_role = {k: v[0] for k, v in ROLES.items()}
    tgt_role = {k: v[1] for k, v in ROLES.items()}
    banned = ("situation", "emotion", "problem", "prompt", "experience")
    for r in recs:
        ds, eid = r["source_dataset"], r["example_id"]
        if r["source_split"] != "train":
            problems.append(f"{eid}: not train")
        if ds == "ESConv" and int(r["conversation_id"]) in held:
            problems.append(f"{eid}: ESConv val/test conversation")
        if r["target_role"] != tgt_role[ds]:
            problems.append(f"{eid}: wrong target role")
        ctx = r["dialogue_context"]
        if not ctx or ctx[-1]["speaker"] != user_role[ds]:
            problems.append(f"{eid}: context does not end with a user turn")
        elif ctx[-1]["text"] != r["current_user_utterance"]:
            problems.append(f"{eid}: current_user_utterance != last context turn")
        if any(k in r for k in banned):
            problems.append(f"{eid}: metadata field leaked into record")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--esconv", required=True)
    ap.add_argument("--esconv_split", required=True)
    ap.add_argument("--ed_dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--esconv_exclude", help="JSON list of ESConv conversation ids to drop")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    exclude = set(json.load(open(a.esconv_exclude))) if a.esconv_exclude else set()
    split = json.load(open(a.esconv_split))
    e_recs, e_meta, e_stats = extract_esconv(a.esconv, a.esconv_split, exclude)
    d_recs, d_meta, d_stats = extract_ed(a.ed_dir)
    recs, metas = e_recs + d_recs, e_meta + d_meta

    problems = check(recs, metas, split)
    if problems:
        print("INTEGRITY PROBLEMS:", *problems[:20], sep="\n  ")
        raise SystemExit(f"{len(problems)} problems; nothing written")

    with open(f"{a.out}/records_base.jsonl", "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(f"{a.out}/source_metadata.jsonl", "w", encoding="utf-8") as f:
        for m in metas:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    pilot = set(json.load(open("work/conversation_ids_to_exclude.json"))) \
        if os.path.exists("work/conversation_ids_to_exclude.json") else set()
    with open(f"{a.out}/source_manifest.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["example_id", "source_dataset", "source_split", "conversation_id", "turn_id",
                    "target_role", "n_context_turns", "context_words", "user_utterance_words",
                    "response_words", "in_week5_pilot_conversation"])
        for r in recs:
            w.writerow([r["example_id"], r["source_dataset"], r["source_split"],
                        r["conversation_id"], r["turn_id"], r["target_role"],
                        len(r["dialogue_context"]),
                        sum(nwords(x["text"]) for x in r["dialogue_context"]),
                        nwords(r["current_user_utterance"]), nwords(r["original_response"]),
                        int(r["source_dataset"] == "ESConv"
                            and int(r["conversation_id"]) in pilot)])

    def lens(rs):
        x = sorted(nwords(r["original_response"]) for r in rs)
        return {"n": len(x), "mean": round(sum(x) / len(x), 1), "median": x[len(x) // 2],
                "min": x[0], "max": x[-1], "n_empty": sum(v == 0 for v in x)}

    summary = {
        "script": "src/extract_turns.py", "script_version": SCRIPT_VERSION,
        "run_utc": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
        "inputs": {"esconv": a.esconv, "esconv_sha256": sha256(a.esconv),
                   "esconv_split": a.esconv_split, "ed_train": f"{a.ed_dir}/train.csv",
                   "ed_train_sha256": sha256(f"{a.ed_dir}/train.csv")},
        "esconv": {**e_stats, "examples": len(e_recs),
                   "excluded_conversations": sorted(exclude),
                   "response_words": lens(e_recs)},
        "empatheticdialogues": {**d_stats, "examples": len(d_recs),
                                "response_words": lens(d_recs)},
        "total_examples": len(recs),
        "integrity_checks": "passed: unique ids; train-only; no ESConv val/test conversations; "
                            "no ED valid/test conv_ids; correct target role; context ends with "
                            "the current user turn; no metadata fields in records",
    }
    json.dump(summary, open(f"{a.out}/extraction_summary.json", "w"), indent=2)
    print(json.dumps({k: summary[k] for k in ("esconv", "empatheticdialogues", "total_examples")},
                     indent=2))


if __name__ == "__main__":
    main()

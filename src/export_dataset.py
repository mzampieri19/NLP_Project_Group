"""Week 10 Steps 4-5: export the formal paired dataset (v0.1, then corrected v1.0).

Usage:
  python3 src/export_dataset.py --version v0.1 --gen formal/generation/gpt-5.6-sol-medium
  python3 src/export_dataset.py --version v1.0 --gen formal/generation/gpt-5.6-sol-medium \
      --corrections formal/release/corrections.csv

Only pairs that automated QC marked KEEP are exported (run src/qc_generation.py first); an
excluded pair loses BOTH conditions. pair_001 and held-out conversations never reach this point.

--corrections (CSV: example_id,action,new_text,reason,flagged_by,decided_by) applies Nikhil's
audit outcomes. action is one of:
  remove            drop the pair (both conditions)
  replace_neutral   use new_text as the Neutral target (e.g. a regenerated or hand-fixed text)
  replace_empathy   same for Empathy
Every applied correction is written to the change log; the original teacher text stays in
paired_rewrites (`*_teacher_original`) so nothing is lost.

Writes formal/release/<version>/:
  paired_rewrites_<v>.jsonl   one line per pair: ids, source fields, context, original, both
                              targets, per-condition generation record, QC flags
  neutral_sft_<v>.jsonl       {"id","condition","source_dataset","messages":[...]}; the last
  empathy_sft_<v>.jsonl       assistant message is the target. Same ids, order and context in
                              both files; only the final assistant message differs.
  generation_metadata.json    teacher/settings/prompt + sampling summary + counts
  qc_report.md / qc_report.json / generation_qc.csv   copied from the QC folder
  change_log.md               what changed vs the previous version
  MANIFEST.json               sha256 + line counts of every file

SFT messages: User turns (ESConv seeker / ED speaker) -> "user", Supporter turns -> "assistant".
Leading assistant turns (e.g. an ESConv supporter greeting before the seeker's first message)
are dropped so every conversation starts with "user" and roles alternate, which all three chat
templates (Qwen3, Llama-3.1, Mistral-v0.3) accept; the count is kept in paired_rewrites.
"""

import argparse
import csv
import datetime
import hashlib
import json
import os
import shutil

CONDS = ("neutral", "empathy")
ROLE = {"seeker": "user", "speaker": "user", "supporter": "assistant", "listener": "assistant"}
META_KEEP = ("problem_type", "emotion_type", "experience_type", "target_support_strategy",
             "emotion_label")
ACTIONS = {"remove", "replace_neutral", "replace_empathy"}


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def to_messages(ctx, target):
    msgs = []
    for t in ctx:
        role = ROLE[t["speaker"]]
        if msgs and msgs[-1]["role"] == role:  # defensive; extraction already merges
            msgs[-1]["content"] += "\n" + t["text"]
        else:
            msgs.append({"role": role, "content": t["text"]})
    dropped = 0
    while msgs and msgs[0]["role"] == "assistant":
        msgs.pop(0)
        dropped += 1
    msgs.append({"role": "assistant", "content": target})
    assert msgs[0]["role"] == "user" and msgs[-2]["role"] == "user"
    assert all(a["role"] != b["role"] for a, b in zip(msgs, msgs[1:], strict=False))
    return msgs, dropped


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True, help="e.g. v0.1 or v1.0")
    ap.add_argument("--gen", required=True)
    ap.add_argument("--qc_dir", default="formal/generation/qc")
    ap.add_argument("--sample_dir", default="formal/sample/v0.1")
    ap.add_argument("--records", default="formal/extract/records_base.jsonl")
    ap.add_argument("--metadata", default="formal/extract/source_metadata.jsonl")
    ap.add_argument("--corrections")
    ap.add_argument("--out_root", default="formal/release")
    a = ap.parse_args()
    v = a.version
    out = os.path.join(a.out_root, v)
    os.makedirs(out, exist_ok=True)

    qc_rows = list(csv.DictReader(open(f"{a.qc_dir}/generation_qc.csv", encoding="utf-8")))
    qc_rep = json.load(open(f"{a.qc_dir}/qc_report.json"))
    assert os.path.normpath(qc_rep["generation_folder"]) == os.path.normpath(a.gen), \
        "QC report is for a different generation folder; rerun src/qc_generation.py"
    keep = [r["example_id"] for r in qc_rows if r["decision"] == "KEEP"]
    flags = {r["example_id"]: r["flags"] for r in qc_rows}
    strata = {r["example_id"]: r for r in csv.DictReader(
        open(f"{a.sample_dir}/sampling_manifest.csv", encoding="utf-8"))}
    want = set(keep)
    recs, meta = {}, {}
    for line in open(a.records, encoding="utf-8"):
        r = json.loads(line)
        if r["example_id"] in want:
            recs[r["example_id"]] = r
    for line in open(a.metadata, encoding="utf-8"):
        m = json.loads(line)
        if m["example_id"] in want:
            meta[m["example_id"]] = m
    calls = {}
    for line in open(os.path.join(a.gen, "raw_rewrites.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        calls[(r["example_id"], r["condition"])] = r
    gmeta = json.load(open(os.path.join(a.gen, "generation_metadata.json")))

    corr = {}
    if a.corrections:
        for c in csv.DictReader(open(a.corrections, encoding="utf-8-sig", newline="")):
            c = {k.strip(): (x or "").strip() for k, x in c.items()}
            assert c["action"] in ACTIONS, f"bad action: {c}"
            assert c["example_id"] in want, f"correction for a non-exported pair: {c}"
            assert c["action"] == "remove" or c["new_text"], f"replace needs new_text: {c}"
            corr.setdefault(c["example_id"], []).append(c)

    paired, sft, log = [], {c: [] for c in CONDS}, []
    for eid in keep:
        rec, cs = recs[eid], corr.get(eid, [])
        if any(c["action"] == "remove" for c in cs):
            log.append({"example_id": eid, "action": "remove", **{k: c[k] for c in cs
                        if c["action"] == "remove" for k in ("reason", "flagged_by",
                                                             "decided_by")}})
            continue
        text = {c: calls[(eid, c)]["rewritten_response"].strip() for c in CONDS}
        teacher_text = dict(text)
        for c in cs:
            cond = c["action"].split("_", 1)[1]
            text[cond] = c["new_text"]
            log.append({"example_id": eid, "action": c["action"], "reason": c["reason"],
                        "flagged_by": c["flagged_by"], "decided_by": c["decided_by"],
                        "old_text": teacher_text[cond], "new_text": c["new_text"]})
        msgs = {}
        for c in CONDS:
            msgs[c], dropped = to_messages(rec["dialogue_context"], text[c])
        assert msgs["neutral"][:-1] == msgs["empathy"][:-1]
        for c in CONDS:
            sft[c].append({"id": eid, "condition": c, "source_dataset": rec["source_dataset"],
                           "messages": msgs[c]})
        s = strata.get(eid, {})
        paired.append({
            "example_id": eid, "source_dataset": rec["source_dataset"],
            "source_split": rec["source_split"], "conversation_id": rec["conversation_id"],
            "turn_id": rec["turn_id"], "target_role": rec["target_role"],
            "sampling_stratum": s.get("stratum"),
            "source_metadata": {k: meta[eid][k] for k in META_KEEP if k in meta[eid]},
            "dialogue_context": rec["dialogue_context"],
            "current_user_utterance": rec["current_user_utterance"],
            "original_response": rec["original_response"],
            "neutral_response": text["neutral"], "empathy_response": text["empathy"],
            **{f"{c}_teacher_original": teacher_text[c] for c in CONDS
               if text[c] != teacher_text[c]},
            "generation": {
                "teacher_id": gmeta["teacher_id"], "api_model_id": gmeta["api_model_id"],
                "prompt_version": gmeta["prompt_version"], "prompt_hash": gmeta["prompt_hash"],
                **{c: {k: calls[(eid, c)].get(k) for k in
                       ("response_model", "response_id", "timestamp_utc", "retries", "usage")}
                   for c in CONDS}},
            "sft_dropped_leading_assistant_turns": dropped,
            "automated_qc_flags": [f for f in flags[eid].split("|") if f],
            "dataset_version": v})

    def dump(name, rows):
        with open(f"{out}/{name}", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    dump(f"paired_rewrites_{v}.jsonl", paired)
    for c in CONDS:
        dump(f"{c}_sft_{v}.jsonl", sft[c])
    for fn in ("qc_report.md", "qc_report.json", "generation_qc.csv"):
        shutil.copy(f"{a.qc_dir}/{fn}", f"{out}/{fn}")
    samp = json.load(open(f"{a.sample_dir}/sampling_summary.json"))
    counts = {"pairs": len(paired), "by_dataset": {}}
    for p in paired:
        counts["by_dataset"][p["source_dataset"]] = counts["by_dataset"].get(
            p["source_dataset"], 0) + 1
    json.dump({"dataset_version": v,
               "exported_utc": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
               "generation": gmeta, "sampling": samp, "counts": counts,
               "automated_qc": {k: qc_rep[k] for k in ("keep", "exclude",
                                                       "hard_failure_counts")},
               "corrections_applied": len(log), "corrections_file": a.corrections,
               "sft_format": "chat messages; user/assistant alternate starting with user; "
                             "last assistant message = target; no system prompt"},
              open(f"{out}/generation_metadata.json", "w"), indent=2)

    L = [f"# Change log: formal paired dataset {v}", "",
         f"Exported {datetime.date.today().isoformat()} from `{a.gen}` "
         f"(prompt {gmeta['prompt_version']} / {gmeta['prompt_hash']}, teacher "
         f"{gmeta['teacher_id']}).", "",
         f"- Sampled examples: {qc_rep['n_sampled_examples']}",
         f"- Excluded by automated QC (both conditions): {qc_rep['exclude']} "
         f"{qc_rep['hard_failure_counts'] or ''}",
         f"- Corrections applied from audit: {len(log)}",
         f"- Exported pairs: {len(paired)} {counts['by_dataset']}", ""]
    if log:
        L += ["| example_id | action | reason | flagged_by | decided_by |", "|---|---|---|---|---|"]
        L += [f"| {x['example_id']} | {x['action']} | {x.get('reason', '')} | "
              f"{x.get('flagged_by', '')} | {x.get('decided_by', '')} |" for x in log]
        dump("change_log_details.jsonl", log)
    open(f"{out}/change_log.md", "w").write("\n".join(L) + "\n")

    files = sorted(f for f in os.listdir(out) if f != "MANIFEST.json")
    json.dump({f: {"sha256": sha256(f"{out}/{f}"),
                   "lines": sum(1 for _ in open(f"{out}/{f}", encoding="utf-8"))}
               for f in files}, open(f"{out}/MANIFEST.json", "w"), indent=2)
    print("\n".join(L))
    print(f"Wrote {out}/ ({', '.join(files)})")


if __name__ == "__main__":
    main()

"""Week 10 Step 3: automated QC on 100% of generated records.

Usage:
  python3 src/qc_generation.py --gen formal/generation/gpt-5.6-sol-medium \
      --sample formal/sample/v0.1/sample_ids.jsonl --out formal/generation/qc

HARD checks (any failure -> the whole pair is EXCLUDED, both conditions):
  per call   required fields; known example_id from the sample; condition neutral/empathy;
             no duplicate (example_id, condition); status OK with a non-empty response
             (UNPAIRABLE / INVALID_JSON fail); raw_text is a complete JSON object that parses
             to the stored response; API status not "incomplete"; response_id present;
             same teacher, returned model, prompt version and prompt hash on every call
  per pair   both conditions present; source checks against records_base / source QC:
             training split only, ESConv conversation in the project train split and not
             held out, target role supporter/listener, source QC PASS, not pair_001
REVIEW flags (pair kept; listed for Nikhil's audit and Michael's spot checks):
  identical_conditions     Neutral and Empathy text are identical
  neutral_equals_original / empathy_equals_original
  length_ratio_<cond>      rewrite < 0.5x or > 2x the original word count (and >= 6 words diff)
  meta_text_<cond>         looks like commentary ("Here is", "Rewritten", "Neutral:", JSON or
                           markdown fences) instead of a reply
  encoding_<cond>          mojibake or replacement characters
  role_label_<cond>        starts with "Supporter:" / "User:" / "Assistant:"

Outputs (in --out): generation_qc.csv (one row per sampled example), qc_report.md, qc_report.json
"""

import argparse
import collections
import csv
import json
import os
import re

CONDS = ("neutral", "empathy")
REQUIRED = ("example_id", "condition", "teacher_id", "status", "rewritten_response",
            "raw_text", "response_model", "response_id", "usage", "retries", "prompt_version",
            "prompt_hash", "timestamp_utc")
TARGET = {"ESConv": "supporter", "EmpatheticDialogues": "listener"}
PAIR_001 = "esc-tr-c0853-b003"
META = re.compile(r"^(here('s| is)|rewritten|sure[,!]|neutral( response)?:|empath(y|ic)( "
                  r"response)?:)|```|^\s*\{", re.I)
MOJIBAKE = re.compile(r"â€|Ã.|Â|�")
ROLE = re.compile(r"^\s*(supporter|user|assistant|listener|seeker)\s*:", re.I)


def nwords(s):
    return len(s.split())


def check_call(r, sample, dry):
    errs = [f"missing_field:{k}" for k in REQUIRED if k not in r]
    if errs:
        return errs
    if r["example_id"] not in sample:
        errs.append("unknown_example_id")
    if r["condition"] not in CONDS:
        errs.append("bad_condition")
    if r["status"] != "OK":  # UNPAIRABLE / INVALID_JSON / PROMPT_FLAGGED: one reason is enough
        return errs + [f"status_{r['status']}"]
    if not (r["rewritten_response"] or "").strip():
        errs.append("empty_response")
    try:
        o = json.loads(r["raw_text"])
        if r["status"] == "OK" and (o.get("status") != "OK"
                                    or (o.get("rewritten_response") or "").strip()
                                    != r["rewritten_response"]):
            errs.append("raw_json_mismatch")
    except (json.JSONDecodeError, TypeError, AttributeError):
        errs.append("raw_text_not_json")
    if (r["usage"] or {}).get("status") == "incomplete":
        errs.append("api_incomplete")
    if not dry and not r["response_id"]:
        errs.append("missing_response_id")
    return errs


def flags_for(rec, n, e):
    out = []
    orig = rec["original_response"].strip()
    if n == e:
        out.append("identical_conditions")
    for cond, t in (("neutral", n), ("empathy", e)):
        if t == orig:
            out.append(f"{cond}_equals_original")
        a, b = nwords(orig), nwords(t)
        if a and (b / a < 0.5 or b / a > 2) and abs(b - a) >= 6:
            out.append(f"length_ratio_{cond}")
        if META.search(t):
            out.append(f"meta_text_{cond}")
        if MOJIBAKE.search(t):
            out.append(f"encoding_{cond}")
        if ROLE.match(t):
            out.append(f"role_label_{cond}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", required=True, help="teacher output folder (raw_rewrites.jsonl)")
    ap.add_argument("--sample", default="formal/sample/v0.1/sample_ids.jsonl")
    ap.add_argument("--records", default="formal/extract/records_base.jsonl")
    ap.add_argument("--qc", default="formal/qc/source_qc.csv")
    ap.add_argument("--split", default="formal/splits/esconv_split.json")
    ap.add_argument("--held_out", default="formal/splits/held_out_eval_convs.txt")
    ap.add_argument("--out", default="formal/generation/qc")
    a = ap.parse_args()

    sample = [json.loads(line)["example_id"] for line in open(a.sample) if line.strip()]
    sset = set(sample)
    recs = {}
    for line in open(a.records, encoding="utf-8"):
        r = json.loads(line)
        if r["example_id"] in sset:
            recs[r["example_id"]] = r
    src_qc = {r["example_id"]: r["status"] for r in csv.DictReader(open(a.qc, encoding="utf-8"))}
    train = {str(i) for i in json.load(open(a.split))["train"]}
    held = {ln.strip() for ln in open(a.held_out) if ln.strip() and not ln.startswith("#")}
    meta = json.load(open(os.path.join(a.gen, "generation_metadata.json")))
    dry = bool(meta.get("dry_run"))

    calls = [json.loads(line) for line in open(os.path.join(a.gen, "raw_rewrites.jsonl"),
                                               encoding="utf-8")]
    by = collections.defaultdict(list)
    for r in calls:
        by[(r.get("example_id"), r.get("condition"))].append(r)
    consistency = {k: sorted({str(r.get(k)) for r in calls})
                   for k in ("teacher_id", "response_model", "prompt_version", "prompt_hash")}
    global_errs = [f"inconsistent_{k}:{v}" for k, v in consistency.items() if len(v) != 1]
    stray = sorted({r.get("example_id") for r in calls} - sset)

    rows, hard_c, flag_c = [], collections.Counter(), collections.Counter()
    for eid in sample:
        rec = recs.get(eid)
        errs = [] if rec else ["not_in_records"]
        resp = {}
        for c in CONDS:
            got = by.get((eid, c), [])
            if not got:
                errs.append(f"{c}:missing_call")
                continue
            if len(got) > 1:
                errs.append(f"{c}:duplicate_call")
            errs += [f"{c}:{x}" for x in check_call(got[-1], sset, dry)]
            resp[c] = (got[-1].get("rewritten_response") or "").strip()
        if rec:
            ds = rec["source_dataset"]
            if rec["source_split"] != "train":
                errs.append("source:not_train_split")
            if ds == "ESConv" and rec["conversation_id"] not in train:
                errs.append("source:esconv_conv_not_in_train_split")
            if ds == "ESConv" and rec["conversation_id"] in held:
                errs.append("source:held_out_conversation")
            if rec["target_role"] != TARGET.get(ds):
                errs.append("source:wrong_target_role")
            if src_qc.get(eid) != "PASS":
                errs.append("source:not_source_qc_pass")
            if eid == PAIR_001:
                errs.append("source:pair_001")
        errs += global_errs
        flg = flags_for(rec, resp.get("neutral", ""), resp.get("empathy", "")) \
            if rec and not errs else []
        hard_c.update(x.split(":", 1)[-1] if x.startswith(CONDS) else x for x in errs)
        flag_c.update(flg)
        rows.append({"example_id": eid, "source_dataset": rec["source_dataset"] if rec else "",
                     "decision": "EXCLUDE" if errs else "KEEP", "hard_failures": "|".join(errs),
                     "flags": "|".join(flg)})

    os.makedirs(a.out, exist_ok=True)
    with open(f"{a.out}/generation_qc.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    per_ds = collections.defaultdict(collections.Counter)
    for r in rows:
        per_ds[r["source_dataset"]][r["decision"]] += 1
    rep = {"generation_folder": a.gen, "dry_run": dry, "n_sampled_examples": len(sample),
           "n_calls_in_file": len(calls), "calls_not_in_sample": stray,
           "consistency": consistency, "keep": sum(r["decision"] == "KEEP" for r in rows),
           "exclude": sum(r["decision"] == "EXCLUDE" for r in rows),
           "per_dataset": {k: dict(v) for k, v in per_ds.items()},
           "hard_failure_counts": dict(hard_c.most_common()),
           "review_flag_counts_on_kept": dict(flag_c.most_common()),
           "excluded_ids": [r["example_id"] for r in rows if r["decision"] == "EXCLUDE"]}
    json.dump(rep, open(f"{a.out}/qc_report.json", "w"), indent=2)
    open(f"{a.out}/qc_report.json", "a").write("\n")  # end-of-file newline (pre-commit)
    L = ["# Automated QC report (100% of records)", "",
         f"Generation folder: `{a.gen}`{' (DRY RUN)' if dry else ''}. "
         f"{len(sample)} sampled examples, {len(calls)} calls in file.", "",
         f"**KEEP {rep['keep']} / EXCLUDE {rep['exclude']}** (an excluded pair drops both "
         "conditions).", "", "| Dataset | KEEP | EXCLUDE |", "|---|---|---|"]
    L += [f"| {k} | {v['KEEP']} | {v['EXCLUDE']} |" for k, v in sorted(per_ds.items())]
    L += ["", "Consistency (must be one value each): " + "; ".join(
        f"{k} = {', '.join(v)}" for k, v in consistency.items()), "",
          "## Hard failures (pair excluded)", ""]
    L += [f"- {k}: {v}" for k, v in hard_c.most_common()] or ["- none"]
    L += ["", "## Review flags on kept pairs (not excluded)", ""]
    L += [f"- {k}: {v}" for k, v in flag_c.most_common()] or ["- none"]
    if stray:
        L += ["", f"Calls for ids outside the sample (ignored): {len(stray)}"]
    open(f"{a.out}/qc_report.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

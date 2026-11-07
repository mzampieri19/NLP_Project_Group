"""Week 9 Step 3: blind annotation sheet for the teacher-selection pilot, and scoring after.

  build: python3 src/teacher_pilot_sheet.py build \
             --gen formal/teacher_pilot/gpt-5.6-sol formal/teacher_pilot/gpt-4o-2024-08-06
         -> formal/teacher_pilot/blind/teacher_pilot_blind.csv   (send to Nikhil)
            formal/teacher_pilot/blind/teacher_pilot_key.json    (Michael keeps; do NOT send)
            formal/teacher_pilot/blind/annotation_guide.md       (send to Nikhil)
  score: python3 src/teacher_pilot_sheet.py score \
             --filled formal/teacher_pilot/blind/teacher_pilot_blind_FILLED.csv
         -> formal/teacher_pilot/teacher_pilot_results.md (+ .json)

Blinding: the 10 contexts appear in random order as T01..T10; each context's 4 responses
(2 teachers x Neutral/Empathy) are labelled A-D in a random order per context. Teacher and
condition are only in the key file.
"""

import argparse
import collections
import csv
import json
import os
import random
import statistics

SEED = 42
LABEL = {"seeker": "User", "speaker": "User", "supporter": "Supporter", "listener": "Supporter"}
ANNOT = ["IP_score", "IP_evidence", "IP_rationale", "ER_score", "ER_evidence", "ER_rationale",
         "EX_score", "EX_evidence", "EX_rationale", "stance_relation", "evidence_alignment",
         "stance_preserved_vs_original", "facts_preserved", "advice_support_preserved",
         "unsupported_inference_or_agreement", "naturalness", "overall_rationale"]
ALLOWED = {"IP_score": {"0", "1", "2"}, "ER_score": {"0", "1", "2"}, "EX_score": {"0", "1", "2"},
           "naturalness": {"0", "1", "2"},
           "stance_relation": {"agree", "disagree", "neutral", "not_applicable"},
           "evidence_alignment": {"supported", "partially_supported", "unsupported",
                                  "not_applicable"},
           "stance_preserved_vs_original": {"yes", "no"}, "facts_preserved": {"yes", "no"},
           "advice_support_preserved": {"yes", "no"},
           "unsupported_inference_or_agreement": {"yes", "no"}}

GUIDE = """# Teacher-selection pilot: annotation guide (pilot codebook)

You will see 10 conversations (T01-T10). For each, the full dialogue, the user's current
message, the ORIGINAL supporter reply, and 4 rewritten replies labelled A-D. Labels are
shuffled per conversation; which model/condition produced each reply is hidden.
Score EVERY row on its own, in the context of the conversation, using the rules below.

## EPITOME (score each dimension separately, 0-2)
IP - Interpretations: 0 = no communicated understanding; 1 = generic understanding or vague
feeling reference; 2 = specific, context-supported reflection of the user's feeling/experience.
ER - Emotional Reactions: 0 = no warmth/compassion/concern; 1 = implicit or generic warmth;
2 = clear, proportionate warmth, compassion, or concern appropriate to the situation.
EX - Explorations: 0 = no exploration; 1 = generic question (e.g. "What happened?");
2 = gentle, specific question about a relevant feeling or experience not yet expressed.
Do NOT reward unsupported emotion inference, agreement, flattery, taking sides, or blanket
reassurance as empathy. For each score, paste the exact span from the reply as evidence
(leave empty for 0) and a one-line rationale.

## Content and stance checks (vs the ORIGINAL reply)
- stance_relation: agree / disagree / neutral / not_applicable, relative to the user's explicit
  claim when one exists.
- evidence_alignment: supported / partially_supported / unsupported / not_applicable, for the
  reply's emotional interpretation and factual/evaluative claims, given the dialogue.
- stance_preserved_vs_original: yes / no - same agreement/challenge/neutrality as the original?
- facts_preserved: yes / no - no facts changed, added, or lost.
- advice_support_preserved: yes / no - same advice, information, questions, support function.
- unsupported_inference_or_agreement: yes / no - adds an emotion, motive, blame, or agreement
  the dialogue does not support.
- naturalness: 0 = unnatural/robotic or formulaic, 1 = acceptable, 2 = natural.
- overall_rationale: one short evidence-based note (anything else worth knowing).

Use only the allowed values (lowercase). These are pilot labels, not a validated scale.
If a row's rewritten reply is a bracketed placeholder such as "[UNPAIRABLE: ...]", the
model declined to rewrite it: leave all score cells for that row empty.
"""


def render(ctx):
    return "\n".join(f"{LABEL[t['speaker']]}: {t['text']}" for t in ctx)


def build(a):
    picks = [json.loads(line) for line in open(a.contexts)]
    want = {p["example_id"] for p in picks}
    recs = {}
    for line in open(a.records, encoding="utf-8"):
        r = json.loads(line)
        if r["example_id"] in want:
            recs[r["example_id"]] = r
    outs, problems = {}, []
    for d in a.gen:
        for line in open(os.path.join(d, "raw_rewrites.jsonl"), encoding="utf-8"):
            r = json.loads(line)
            if r["example_id"] in want:
                outs[(r["example_id"], r["teacher_id"], r["condition"])] = r
    teachers = sorted({k[1] for k in outs})
    assert len(teachers) == 2, f"need exactly 2 teachers, found {teachers}"
    rng = random.Random(SEED)
    order = [p["example_id"] for p in picks]
    rng.shuffle(order)
    rows, key = [], {}
    for i, eid in enumerate(order, 1):
        cells = [(t, c) for t in teachers for c in ("neutral", "empathy")]
        rng.shuffle(cells)
        r = recs[eid]
        for lab, (t, c) in zip("ABCD", cells, strict=True):
            o = outs.get((eid, t, c))
            if not o or o["status"] != "OK":
                problems.append(f"{eid} {t}/{c}: {o['status'] if o else 'missing'}")
            row_id = f"T{i:02d}-{lab}"
            key[row_id] = {"example_id": eid, "teacher_id": t, "condition": c}
            rows.append({"row_id": row_id, "item": f"T{i:02d}", "label": lab,
                         "dialogue_history": render(r["dialogue_context"][:-1]) or "(none)",
                         "current_user_message": r["current_user_utterance"],
                         "original_reply": r["original_response"],
                         "rewritten_reply": (o or {}).get("rewritten_response")
                         or f"[{(o or {}).get('status', 'MISSING')}: "
                            f"{(o or {}).get('reason_code')}]",
                         **{k: "" for k in ANNOT}})
    os.makedirs(a.blind_dir, exist_ok=True)
    with open(f"{a.blind_dir}/teacher_pilot_blind.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    json.dump({"note": "UNBLINDING KEY - do not share with annotators until scores are frozen",
               "seed": SEED, "teachers": teachers, "rows": key},
              open(f"{a.blind_dir}/teacher_pilot_key.json", "w"), indent=2)
    open(f"{a.blind_dir}/annotation_guide.md", "w").write(GUIDE)
    print(f"Wrote {len(rows)} rows to {a.blind_dir}/teacher_pilot_blind.csv "
          f"(+ key + annotation_guide.md)")
    if problems:
        print("WARNING, not all outputs are OK:", *problems, sep="\n  ")


def score(a):
    key = json.load(open(a.key))["rows"]
    rows = list(csv.DictReader(open(a.filled, encoding="utf-8-sig", newline="")))
    errs, skipped = [], []
    for r in rows:
        if r["rewritten_reply"].startswith(("[UNPAIRABLE", "[INVALID_JSON", "[MISSING")):
            skipped.append(r["row_id"])
            continue
        for k, ok in ALLOWED.items():
            v = (r.get(k) or "").strip().lower()
            r[k] = v
            if v not in ok:
                errs.append(f"{r['row_id']}: {k}={v!r}")
    if errs:
        raise SystemExit("Fix these cells first:\n  " + "\n  ".join(errs[:40]))
    data = collections.defaultdict(dict)  # teacher -> example -> condition -> row
    for r in rows:
        if r["row_id"] in skipped:
            continue
        k = key[r["row_id"]]
        data[k["teacher_id"]].setdefault(k["example_id"], {})[k["condition"]] = r
    res = {}
    for t, ex in sorted(data.items()):
        out = {}
        n_contexts = len(ex)
        ex = {e: v for e, v in ex.items() if "neutral" in v and "empathy" in v}
        for c in ("neutral", "empathy"):
            rs = [e[c] for e in ex.values()]
            out[c] = {d: round(statistics.mean(int(x[f"{d}_score"]) for x in rs), 2)
                      for d in ("IP", "ER", "EX")}
            out[c]["naturalness"] = round(statistics.mean(int(x["naturalness"]) for x in rs), 2)
            out[c]["failures"] = {
                "facts_not_preserved": sum(x["facts_preserved"] == "no" for x in rs),
                "advice_support_not_preserved": sum(x["advice_support_preserved"] == "no"
                                                    for x in rs),
                "stance_not_preserved": sum(x["stance_preserved_vs_original"] == "no"
                                            for x in rs),
                "unsupported_inference_or_agreement": sum(
                    x["unsupported_inference_or_agreement"] == "yes" for x in rs)}
        diffs = {d: [int(e["empathy"][f"{d}_score"]) - int(e["neutral"][f"{d}_score"])
                     for e in ex.values()] for d in ("IP", "ER", "EX")}
        out["empathy_minus_neutral_mean"] = {d: round(statistics.mean(v), 2)
                                             for d, v in diffs.items()}
        out["share_empathy_gt_neutral_on_any_dim"] = round(statistics.mean(
            any(diffs[d][i] > 0 for d in diffs) for i in range(len(ex))), 2)
        out["n_contexts_scored_as_pairs"] = len(ex)
        out["n_contexts_dropped_unpairable"] = n_contexts - len(ex) + sum(
            key[s]["teacher_id"] == t and key[s]["example_id"] not in data[t] for s in skipped)
        res[t] = out
    base = os.path.splitext(a.results)[0]
    json.dump(res, open(base + ".json", "w"), indent=2)
    lines = ["# Teacher-selection pilot results (unblinded)", "",
             "| Teacher | Cond | IP | ER | EX | Natural | Facts✗ | Advice✗ | Stance✗ | "
             "Unsupported |", "|---|---|---|---|---|---|---|---|---|---|"]
    for t, o in res.items():
        for c in ("neutral", "empathy"):
            f = o[c]["failures"]
            lines.append(f"| {t} | {c} | {o[c]['IP']} | {o[c]['ER']} | {o[c]['EX']} | "
                         f"{o[c]['naturalness']} | {f['facts_not_preserved']} | "
                         f"{f['advice_support_not_preserved']} | {f['stance_not_preserved']} | "
                         f"{f['unsupported_inference_or_agreement']} |")
    lines += ["", "| Teacher | Empathy-Neutral IP | ER | EX | Share of contexts Empathy > "
              "Neutral on >=1 dim |", "|---|---|---|---|---|"]
    for t, o in res.items():
        d = o["empathy_minus_neutral_mean"]
        lines.append(f"| {t} | {d['IP']:+} | {d['ER']:+} | {d['EX']:+} | "
                     f"{o['share_empathy_gt_neutral_on_any_dim']} |")
    lines += ["", "Means and failure counts use only contexts where the teacher produced BOTH "
              "conditions. Rows skipped as UNPAIRABLE/invalid: " + (", ".join(
                  f"{s} ({key[s]['teacher_id']}/{key[s]['condition']})" for s in skipped)
                  or "none") + "."]
    lines += ["", "Decision rule (plan): choose ONE teacher with a clear, appropriate EPITOME "
              "contrast and the least content/stance drift. Record the decision and reason in "
              "formal/DECISIONS.md."]
    open(base + ".md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--gen", nargs=2, required=True, help="the two teacher output folders")
    b.add_argument("--contexts", default="formal/teacher_pilot/pilot_contexts.jsonl")
    b.add_argument("--records", default="formal/extract/records_base.jsonl")
    b.add_argument("--blind_dir", default="formal/teacher_pilot/blind")
    s = sub.add_parser("score")
    s.add_argument("--filled", required=True)
    s.add_argument("--key", default="formal/teacher_pilot/blind/teacher_pilot_key.json")
    s.add_argument("--results", default="formal/teacher_pilot/teacher_pilot_results.md")
    a = ap.parse_args()
    build(a) if a.cmd == "build" else score(a)


if __name__ == "__main__":
    main()

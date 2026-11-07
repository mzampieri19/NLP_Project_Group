"""Week 9 Step 3: choose the 10 teacher-selection pilot contexts (5 ESConv + 5 ED).

Usage:
  python3 src/pick_pilot_contexts.py --out formal/teacher_pilot/pilot_contexts.jsonl

ESConv: reuse 5 of the first 10 Week 5 pilot pairs (the plan says "reuse the same pilot
contexts"; it also lets us compare v2 outputs with the v4 Control/EV outputs). Chosen by hand
to cover different reply types; all PASS source QC:
  pair_001  restatement of the user's situation
  pair_002  clarifying question
  pair_003  information / practical advice
  pair_007  self-disclosure that already contains validation
  pair_201  suggestions + existing reflection of feelings, long context
ED: one PASS example per reply type, chosen at random (seed 42) from distinct conversations
with 4-40 word replies: question, advice, self_disclosure, already_empathic, short_comment.
The type is a rough regex bucket used only to spread the sample; it is not a label.
"""

import argparse
import csv
import json
import os
import random
import re

SEED = 42
ESCONV_PICKS = {"pair_001": "restatement", "pair_002": "question",
                "pair_003": "information_advice", "pair_007": "self_disclosure_with_validation",
                "pair_201": "suggestions_with_reflection_long_context"}
ED_BUCKETS = [
    ("question", lambda t: t.rstrip().endswith("?")),
    ("advice", lambda t: re.search(r"\b(you should|you could|maybe you|you might want|you need to|"
                                   r"why don't you|i'd recommend|i suggest)\b|(^|[.!] )try\b",
                                   t.lower())
     and not t.rstrip().endswith("?")),
    ("self_disclosure", lambda t: re.match(r"^i (had|have|was|used to|did|got|went|remember)\b",
                                           t.lower()) and "?" not in t),
    ("already_empathic", lambda t: re.search(r"\b(sorry|sounds|must be|must have been|"
                                             r"i understand|that's (awful|terrible|rough))\b",
                                             t.lower()) and "?" not in t),
    ("short_comment", lambda t: len(t.split()) <= 6 and "?" not in t),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", default="formal/extract/records_base.jsonl")
    ap.add_argument("--qc", default="formal/qc/source_qc.csv")
    ap.add_argument("--week5", default="work/selected_turns.jsonl")
    ap.add_argument("--out", default="formal/teacher_pilot/pilot_contexts.jsonl")
    a = ap.parse_args()

    qc = list(csv.DictReader(open(a.qc, encoding="utf-8")))
    status = {r["example_id"]: r["status"] for r in qc}
    reason = {r["example_id"]: r["reason_code"] for r in qc}
    recs = {}
    for line in open(a.records, encoding="utf-8"):
        r = json.loads(line)
        recs[r["example_id"]] = r

    out = []
    w5 = {json.loads(line)["example_id"]: json.loads(line) for line in open(a.week5)}
    for pid, kind in ESCONV_PICKS.items():
        t = w5[pid]
        eid = f"esc-tr-c{t['conversation_id']:04d}-b{t['turn_index']:03d}"
        # pair_001 was later removed from the formal data by a manual override (its reply
        # contradicts the user message; surfaced by this pilot). It stays in the pilot set so
        # the pilot that already ran is reproducible; it never enters training data.
        assert status[eid] == "PASS" or (status[eid] == "REMOVE" and reason[eid] ==
                                         "context_contradiction"), f"{pid} -> {eid} failed QC"
        assert recs[eid]["original_response"] == t["original_response"], f"{pid} text mismatch"
        out.append({"example_id": eid, "pilot_bucket": kind, "week5_pair_id": pid})

    rng = random.Random(SEED)
    ed = [r for r in recs.values() if r["source_dataset"] == "EmpatheticDialogues"
          and status[r["example_id"]] == "PASS" and 4 <= len(r["original_response"].split()) <= 40]
    rng.shuffle(ed)
    used_convs = set()
    for kind, test in ED_BUCKETS:
        r = next(r for r in ed if r["conversation_id"] not in used_convs
                 and test(r["original_response"]))
        used_convs.add(r["conversation_id"])
        out.append({"example_id": r["example_id"], "pilot_bucket": kind, "week5_pair_id": None})

    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        for o in out:
            f.write(json.dumps(o) + "\n")
    for o in out:
        r = recs[o["example_id"]]
        print(f"{o['example_id']:<32} {o['pilot_bucket']:<42} {r['original_response'][:70]}")
    print(f"Wrote {len(out)} pilot contexts to {a.out}")


if __name__ == "__main__":
    main()

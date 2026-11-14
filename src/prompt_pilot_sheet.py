"""Prompt-validation pilot (v2.1, one teacher): blind annotation sheet, and scoring after.

  build: python3 src/prompt_pilot_sheet.py build --gen formal/prompt_pilot_v2.1/gpt-5.6-sol-medium
         -> <blind_dir>/prompt_pilot_blind.csv   (send to Nikhil)
            <blind_dir>/prompt_pilot_key.json    (Michael keeps; do NOT send)
            <blind_dir>/annotation_guide.md      (send to Nikhil)
  score: python3 src/prompt_pilot_sheet.py score --filled <blind_dir>/prompt_pilot_blind_FILLED.csv
         -> <out>/prompt_pilot_results.md (+ .json)

Differences from the teacher pilot (src/teacher_pilot_sheet.py), following Rong (2026-11-14):
- One teacher, so each context has 2 rows (Neutral/Empathy) labelled A/B in random order.
- pair_001 (esc-tr-c0853-b003, source REMOVED) is left out of the sheet (--exclude).
- Context applicability: per context, IP/ER/EX are each labelled required / optional /
  not_indicated BEFORE scoring the replies. Scoring reports the Empathy-Neutral contrast per
  applicability level, so appropriate empathy can be told apart from simply adding more
  (e.g. EX added where no exploration is indicated).
- cold_or_dismissive (yes/no) on every row, to check that Neutral is not cold.
"""

import argparse
import collections
import csv
import json
import os
import random
import statistics

from teacher_pilot_sheet import ALLOWED as BASE_ALLOWED
from teacher_pilot_sheet import ANNOT as BASE_ANNOT
from teacher_pilot_sheet import render

SEED = 42
DIMS = ("IP", "ER", "EX")
APPLIC = [f"{d}_applicability" for d in DIMS]
APPLIC_VALUES = ("required", "optional", "not_indicated")
ANNOT = BASE_ANNOT[:-1] + ["cold_or_dismissive", BASE_ANNOT[-1]]
ALLOWED = {**BASE_ALLOWED, "cold_or_dismissive": {"yes", "no"}}
PLACEHOLDER = ("[UNPAIRABLE", "[INVALID_JSON", "[MISSING")

GUIDE = """# Prompt-validation pilot (v2.1): annotation guide

You will see 9 conversations (P01-P09). For each: the dialogue, the user's current message,
the ORIGINAL supporter reply, and 2 rewritten replies labelled A and B (random order; which
condition produced each is hidden). Same scoring rules as the teacher pilot, plus two things.

## Step 1 - context applicability (once per conversation, BEFORE reading A and B)
From the dialogue and the user's current message only, decide for each EPITOME dimension
whether this turn calls for it:
- required      - a good supportive reply here should clearly include it
- optional      - it would fit, but a good reply could reasonably leave it out
- not_indicated - it would be unnecessary, forced, or inappropriate here
Fill IP_applicability, ER_applicability, EX_applicability on the A row of each conversation
(leave them empty on the B row, or copy the same values).

## Step 2 - score each reply (both rows)
IP - Interpretations: 0 = no communicated understanding; 1 = generic understanding or vague
feeling reference; 2 = specific, context-supported reflection of the user's feeling/experience.
ER - Emotional Reactions: 0 = no warmth/compassion/concern; 1 = implicit or generic warmth;
2 = clear, proportionate warmth, compassion, or concern appropriate to the situation.
EX - Explorations: 0 = no exploration; 1 = generic question (e.g. "What happened?");
2 = gentle, specific question about a relevant feeling or experience not yet expressed.
Score what is in the reply, whatever you labelled in step 1. Do NOT reward unsupported emotion
inference, agreement, flattery, taking sides, or blanket reassurance as empathy. For each score,
paste the exact span as evidence (empty for 0) and a one-line rationale.

## Content and stance checks (vs the ORIGINAL reply)
- stance_relation: agree / disagree / neutral / not_applicable (to the user's explicit claim).
- evidence_alignment: supported / partially_supported / unsupported / not_applicable.
- stance_preserved_vs_original: yes / no.
- facts_preserved: yes / no - no facts changed, added, or lost.
- advice_support_preserved: yes / no - same advice, information, practical help, questions
  needed for the conversational goal.
- unsupported_inference_or_agreement: yes / no.
- naturalness: 0 = unnatural/robotic or formulaic, 1 = acceptable, 2 = natural.
- cold_or_dismissive: yes / no - would the user reasonably feel brushed off or treated coldly?
- overall_rationale: one short evidence-based note.

Use only the allowed values (lowercase). Save as UTF-8 CSV (Google Sheets -> Download -> CSV;
Excel can corrupt apostrophes). If a reply is a bracketed placeholder such as
"[UNPAIRABLE: ...]", leave that row's score cells empty.
"""


def build(a):
    picks = [json.loads(line)["example_id"] for line in open(a.contexts)]
    picks = [e for e in picks if e not in set(a.exclude)]
    recs = {}
    for line in open(a.records, encoding="utf-8"):
        r = json.loads(line)
        if r["example_id"] in picks:
            recs[r["example_id"]] = r
    outs = {}
    for line in open(os.path.join(a.gen, "raw_rewrites.jsonl"), encoding="utf-8"):
        r = json.loads(line)
        outs[(r["example_id"], r["condition"])] = r
    meta = json.load(open(os.path.join(a.gen, "generation_metadata.json")))
    rng = random.Random(SEED)
    rng.shuffle(picks)
    rows, key, problems = [], {}, []
    for i, eid in enumerate(picks, 1):
        conds = ["neutral", "empathy"]
        rng.shuffle(conds)
        r = recs[eid]
        for lab, c in zip("AB", conds, strict=True):
            o = outs.get((eid, c))
            if not o or o["status"] != "OK":
                problems.append(f"{eid} {c}: {o['status'] if o else 'missing'}")
            row_id = f"P{i:02d}-{lab}"
            key[row_id] = {"example_id": eid, "condition": c}
            rows.append({"row_id": row_id, "item": f"P{i:02d}", "label": lab,
                         "dialogue_history": render(r["dialogue_context"][:-1]) or "(none)",
                         "current_user_message": r["current_user_utterance"],
                         "original_reply": r["original_response"],
                         "rewritten_reply": (o or {}).get("rewritten_response")
                         or f"[{(o or {}).get('status', 'MISSING')}: "
                            f"{(o or {}).get('reason_code')}]",
                         **{k: "" for k in APPLIC + ANNOT}})
    os.makedirs(a.blind_dir, exist_ok=True)
    with open(f"{a.blind_dir}/prompt_pilot_blind.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    json.dump({"note": "UNBLINDING KEY - do not share with annotators until scores are frozen",
               "seed": SEED, "teacher_id": meta["teacher_id"],
               "prompt_version": meta["prompt_version"], "prompt_hash": meta["prompt_hash"],
               "excluded": a.exclude, "rows": key},
              open(f"{a.blind_dir}/prompt_pilot_key.json", "w"), indent=2)
    open(f"{a.blind_dir}/annotation_guide.md", "w").write(GUIDE)
    print(f"Wrote {len(rows)} rows ({len(picks)} contexts) to {a.blind_dir}/prompt_pilot_blind.csv"
          f" (+ key + annotation_guide.md); excluded {a.exclude}")
    if problems:
        print("WARNING, not all outputs are OK:", *problems, sep="\n  ")


def mean(xs):
    return round(statistics.mean(xs), 2) if xs else None


def score(a):
    k = json.load(open(a.key))
    key = k["rows"]
    rows = list(csv.DictReader(open(a.filled, encoding="utf-8-sig", newline="")))
    assert {r["row_id"] for r in rows} == set(key), "row_ids differ from the key"
    errs, skipped, applic = [], [], {}
    for r in rows:
        item = r["item"]
        for c in APPLIC:  # one value per context, taken from whichever row has it
            v = (r.get(c) or "").strip().lower()
            if v:
                if v not in APPLIC_VALUES:
                    errs.append(f"{r['row_id']}: {c}={v!r}")
                elif applic.setdefault(item, {}).setdefault(c, v) != v:
                    errs.append(f"{item}: conflicting {c} on A and B rows")
        if r["rewritten_reply"].startswith(PLACEHOLDER):
            skipped.append(r["row_id"])
            continue
        for c, ok in ALLOWED.items():
            v = (r.get(c) or "").strip().lower()
            r[c] = v
            if v not in ok:
                errs.append(f"{r['row_id']}: {c}={v!r}")
    for item in {r["item"] for r in rows}:
        for c in APPLIC:
            if c not in applic.get(item, {}):
                errs.append(f"{item}: {c} missing")
    if errs:
        raise SystemExit("Fix these cells first:\n  " + "\n  ".join(sorted(errs)[:40]))

    ex = collections.defaultdict(dict)  # example -> condition -> row
    for r in rows:
        if r["row_id"] not in skipped:
            ex[key[r["row_id"]]["example_id"]][key[r["row_id"]]["condition"]] = r
    item_of = {key[r["row_id"]]["example_id"]: r["item"] for r in rows}
    pairs = {e: v for e, v in ex.items() if "neutral" in v and "empathy" in v}
    res = {"teacher_id": k["teacher_id"], "prompt_version": k["prompt_version"],
           "prompt_hash": k["prompt_hash"], "n_contexts_compared": len(pairs),
           "excluded_contexts": k["excluded"], "unpairable_or_invalid_rows": skipped}
    for c in ("neutral", "empathy"):
        rs = [v[c] for v in pairs.values()]
        res[c] = {**{d: mean([int(x[f"{d}_score"]) for x in rs]) for d in DIMS},
                  "naturalness": mean([int(x["naturalness"]) for x in rs]),
                  "cold_or_dismissive": sum(x["cold_or_dismissive"] == "yes" for x in rs),
                  "facts_not_preserved": sum(x["facts_preserved"] == "no" for x in rs),
                  "advice_support_not_preserved": sum(x["advice_support_preserved"] == "no"
                                                      for x in rs),
                  "stance_not_preserved": sum(x["stance_preserved_vs_original"] == "no"
                                              for x in rs),
                  "unsupported_inference_or_agreement": sum(
                      x["unsupported_inference_or_agreement"] == "yes" for x in rs)}
    diff = {d: {e: int(v["empathy"][f"{d}_score"]) - int(v["neutral"][f"{d}_score"])
                for e, v in pairs.items()} for d in DIMS}
    res["empathy_minus_neutral_mean"] = {d: mean(list(diff[d].values())) for d in DIMS}
    res["share_empathy_gt_neutral_on_any_dim"] = mean(
        [any(diff[d][e] > 0 for d in DIMS) for e in pairs])
    by_app = {}
    for d in DIMS:
        for lvl in APPLIC_VALUES:
            es = [e for e in pairs if applic[item_of[e]][f"{d}_applicability"] == lvl]
            by_app[f"{d}/{lvl}"] = {
                "n": len(es),
                "neutral_mean": mean([int(pairs[e]["neutral"][f"{d}_score"]) for e in es]),
                "empathy_mean": mean([int(pairs[e]["empathy"][f"{d}_score"]) for e in es]),
                "share_empathy_gt_neutral": mean([diff[d][e] > 0 for e in es]),
                "share_empathy_zero": mean([pairs[e]["empathy"][f"{d}_score"] == "0"
                                            for e in es])}
    res["by_applicability"] = by_app

    os.makedirs(a.out, exist_ok=True)
    json.dump(res, open(f"{a.out}/prompt_pilot_results.json", "w"), indent=2)
    L = [f"# Prompt-validation pilot results ({res['prompt_version']}, {res['teacher_id']})", "",
         f"{len(pairs)} contexts with both conditions; excluded: {', '.join(k['excluded'])}; "
         f"skipped rows: {', '.join(skipped) or 'none'}.", "",
         "| Cond | IP | ER | EX | Natural | Cold | Facts✗ | Advice✗ | Stance✗ | Unsupported |",
         "|---|---|---|---|---|---|---|---|---|---|"]
    for c in ("neutral", "empathy"):
        o = res[c]
        L.append(f"| {c} | {o['IP']} | {o['ER']} | {o['EX']} | {o['naturalness']} | "
                 f"{o['cold_or_dismissive']} | {o['facts_not_preserved']} | "
                 f"{o['advice_support_not_preserved']} | {o['stance_not_preserved']} | "
                 f"{o['unsupported_inference_or_agreement']} |")
    d = res["empathy_minus_neutral_mean"]
    L += ["", f"Empathy-Neutral: IP {d['IP']:+}, ER {d['ER']:+}, EX {d['EX']:+}; Empathy > "
          f"Neutral on >=1 dimension in {res['share_empathy_gt_neutral_on_any_dim']} of contexts.",
          "", "## By context applicability", "",
          "| Dim / applicability | n | Neutral | Empathy | Share E>N | Share Empathy=0 |",
          "|---|---|---|---|---|---|"]
    for name, o in by_app.items():
        L.append(f"| {name} | {o['n']} | {o['neutral_mean']} | {o['empathy_mean']} | "
                 f"{o['share_empathy_gt_neutral']} | {o['share_empathy_zero']} |")
    L += ["", "Read: for *required* the Empathy condition should score > 0 and above Neutral; for "
          "*not_indicated* a high Share E>N means the dimension is being added where it is not "
          "called for. Only claim improvements on dimensions where a contrast is observed."]
    open(f"{a.out}/prompt_pilot_results.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--gen", required=True, help="teacher output folder")
    b.add_argument("--contexts", default="formal/teacher_pilot/pilot_contexts.jsonl")
    b.add_argument("--records", default="formal/extract/records_base.jsonl")
    b.add_argument("--exclude", nargs="*", default=["esc-tr-c0853-b003"])
    b.add_argument("--blind_dir", default="formal/prompt_pilot_v2.1/blind")
    s = sub.add_parser("score")
    s.add_argument("--filled", required=True)
    s.add_argument("--key", default="formal/prompt_pilot_v2.1/blind/prompt_pilot_key.json")
    s.add_argument("--out", default="formal/prompt_pilot_v2.1")
    a = ap.parse_args()
    build(a) if a.cmd == "build" else score(a)


if __name__ == "__main__":
    main()

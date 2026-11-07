"""Week 9 Step 2: source-turn QC. Marks every extracted example PASS or REMOVE.

Usage:
  python3 src/source_qc.py --extract formal/extract --out formal/qc \
      [--overrides formal/qc/source_qc_overrides.csv] [--min_words 3] [--max_words 200]

Nothing is rewritten or repaired: original_response stays exactly as extracted, and a REMOVE
drops the example from BOTH conditions (it simply never reaches generation).

REMOVE rules (reason_code; first matching rule is the primary reason, all are listed):
  structural          target role wrong, no user turn before it, or context does not end
                      with the current user turn (should never fire after extract_turns.py)
  no_letters          target has no letters (e.g. "4", "5?")
  garbled             mojibake, leftover "_comma_", HTML entities
  echo_of_user        target is identical to the user turn it answers (copy error)
  duplicated_raw_turn ESConv: the merged target contains the same raw turn twice verbatim
                      (an ESConv logging artifact; we do not repair source text)
  pleasantry_only     only greetings / farewells / thanks / "you too" with no other content
  too_short           fewer than --min_words words (default 3)
  too_long            more than --max_words words (default 200)
  exact_duplicate     same dataset, same context and same target as an earlier example
                      (the first occurrence is kept)
REVIEW flags (status stays PASS; listed in `flags` for the manual spot-check):
  repeats_own_earlier_turn  target equals an earlier same-role turn in the conversation
  question_only_short       3-4 word generic question ("What happened?"-style); kept, but it
                            leaves little to rewrite, so the generation subset may down-weight it

Manual decisions: put rows in --overrides (example_id,status,reason_code,note,decided_by).
They replace the automatic decision and are logged in the `override` column.

Outputs (in --out):
  source_qc.csv            example_id, source_dataset, status, reason_code, all_reasons,
                           flags, override, note
  source_qc_summary.json   counts per dataset and reason, parameters, input hash
  source_qc_spotcheck.csv  stratified random sample (PASS and REMOVE) with context, for a
                           human look; fill in agree_with_qc (y/n) and note
"""

import argparse
import collections
import csv
import datetime
import hashlib
import json
import os
import random
import re

SEED = 42
USER = {"ESConv": "seeker", "EmpatheticDialogues": "speaker"}
TARGET = {"ESConv": "supporter", "EmpatheticDialogues": "listener"}

PLEASANTRY = [
    r"good ?bye", r"bye( bye)?", r"take care( of yourself)?", r"see (you|ya)( later| soon)?",
    r"have an? (good|great|nice|wonderful|lovely|blessed|awesome) "
    r"(day|night|evening|weekend|one|time|afternoon|morning|holiday|christmas)",
    r"good (morning|afternoon|evening|night|luck)", r"merry christmas",
    r"happy (holidays|new year)",
    r"hi+", r"hello+", r"hey+", r"hiya", r"greetings",
    r"how (are|r) (you|u)( doing| today| tonight| this (morning|evening|afternoon))?",
    r"how is it going", r"how's it going", r"how are things",
    r"(it was )?nice (to )?(meet|talk(ing)?( to| with)?|chat(ting)?( with)?) you",
    r"thank (you|u)( so much| very much| again| for (your time|chatting|talking))?",
    r"thanks( a lot| so much| again)?", r"(you're|you are|your|ur|you r) (very |so |most )?welcome",
    r"no problem", r"(it was |it's |its )?(my|a) pleasure", r"any ?time", r"no worries",
    r"glad (i could|to) help", r"you too", r"(you|to you) as well", r"same to you", r"and you",
    r"same here",
]
PLEASANTRY_RE = re.compile(r"\b(" + "|".join(PLEASANTRY) + r")\b")
FILLER = set("ok okay sure well so and too again also oh yes yeah alright all as for the a an "
             "very much really to it was i am im i'm it's its great nice chatting talking with me "
             "you your today tonight there friend dear just hope good have bless god".split())
GENERIC_Q = re.compile(r"^(oh( no)?[,.!]* )?(what|why|how|when|where|who|really)\b.*\?$")
MOJIBAKE = re.compile(r"â€|Ã.|Â|_comma_|&[a-z]+;|&#\d+;")


def nwords(s):
    return len(s.split())


def is_pleasantry(text):
    t = text.lower().replace("’", "'")
    if not PLEASANTRY_RE.search(t):
        return False
    rest = PLEASANTRY_RE.sub(" ", t)
    toks = re.findall(r"[a-z']+", rest)
    return all(w in FILLER for w in toks)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def esconv_raw_repeats(meta, convs):
    """True if the merged ESConv target contains the same raw turn twice."""
    cid = int(meta["example_id"][8:12])
    raw = [" ".join(convs[cid]["dialog"][i]["content"].split())
           for i in meta["target_raw_turn_indices"]]
    return len(raw) != len(set(raw))


def qc_one(r, m, convs, a):
    ds, resp = r["source_dataset"], r["original_response"]
    ctx = r["dialogue_context"]
    reasons, flags = [], []
    if (r["target_role"] != TARGET[ds] or not ctx or ctx[-1]["speaker"] != USER[ds]
            or ctx[-1]["text"] != r["current_user_utterance"]
            or not r["current_user_utterance"].strip()):
        reasons.append("structural")
    if not re.search(r"[A-Za-z]", resp):
        reasons.append("no_letters")
    if MOJIBAKE.search(resp) or MOJIBAKE.search(r["current_user_utterance"]):
        reasons.append("garbled")
    if resp.strip().lower() == r["current_user_utterance"].strip().lower():
        reasons.append("echo_of_user")
    if ds == "ESConv" and m.get("n_raw_turns_merged", 1) > 1 and esconv_raw_repeats(m, convs):
        reasons.append("duplicated_raw_turn")
    if is_pleasantry(resp):
        reasons.append("pleasantry_only")
    n = nwords(resp)
    if n < a.min_words:
        reasons.append("too_short")
    if n > a.max_words:
        reasons.append("too_long")
    own = {x["text"] for x in ctx if x["speaker"] == TARGET[ds]}
    if resp in own:
        flags.append("repeats_own_earlier_turn")
    if n <= 4 and GENERIC_Q.match(resp.lower()):
        flags.append("question_only_short")
    return reasons, flags


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--extract", default="formal/extract")
    ap.add_argument("--esconv", default="data/ESConv.json")
    ap.add_argument("--out", default="formal/qc")
    ap.add_argument("--overrides")
    ap.add_argument("--min_words", type=int, default=3)
    ap.add_argument("--max_words", type=int, default=200)
    ap.add_argument("--spotcheck_n", type=int, default=50,
                    help="PASS rows per dataset in the spot-check sheet (plus REMOVE rows)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    rec_path = f"{a.extract}/records_base.jsonl"
    recs = [json.loads(l) for l in open(rec_path, encoding="utf-8")]
    metas = {json.loads(l)["example_id"]: json.loads(l)
             for l in open(f"{a.extract}/source_metadata.jsonl", encoding="utf-8")}
    convs = json.load(open(a.esconv, encoding="utf-8"))

    overrides = {}
    if a.overrides and os.path.exists(a.overrides):
        for o in csv.DictReader(open(a.overrides, encoding="utf-8-sig", newline="")):
            o = {k.strip(): (v or "").strip() for k, v in o.items()}
            assert o["status"] in ("PASS", "REMOVE"), f"bad override status: {o}"
            overrides[o["example_id"]] = o
        unknown = set(overrides) - {r["example_id"] for r in recs}
        assert not unknown, f"overrides for unknown example_ids: {sorted(unknown)[:5]}"

    seen = set()
    rows = []
    for r in recs:
        reasons, flags = qc_one(r, metas[r["example_id"]], convs, a)
        key = (r["source_dataset"], json.dumps(r["dialogue_context"]), r["original_response"])
        if key in seen:
            reasons.append("exact_duplicate")
        seen.add(key)
        status = "REMOVE" if reasons else "PASS"
        row = {"example_id": r["example_id"], "source_dataset": r["source_dataset"],
               "status": status, "reason_code": reasons[0] if reasons else "",
               "all_reasons": "|".join(reasons), "flags": "|".join(flags),
               "override": "", "note": ""}
        o = overrides.get(r["example_id"])
        if o:
            row["override"] = f"{status}->{o['status']} by {o.get('decided_by', '')}"
            row["status"], row["reason_code"] = o["status"], o.get("reason_code", "manual")
            row["note"] = o.get("note", "")
        rows.append(row)

    cols = ["example_id", "source_dataset", "status", "reason_code", "all_reasons", "flags",
            "override", "note"]
    with open(f"{a.out}/source_qc.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # summary
    summ = {"script": "src/source_qc.py",
            "run_utc": datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds"),
            "input": rec_path, "input_sha256": sha256(rec_path),
            "params": {"min_words": a.min_words, "max_words": a.max_words,
                       "overrides": a.overrides if overrides else None,
                       "n_overrides": len(overrides)},
            "datasets": {}}
    for ds in ("ESConv", "EmpatheticDialogues", None):
        rs = [x for x in rows if ds is None or x["source_dataset"] == ds]
        st = collections.Counter(x["status"] for x in rs)
        summ["datasets"][ds or "ALL"] = {
            "examples": len(rs), "PASS": st["PASS"], "REMOVE": st["REMOVE"],
            "pass_rate": round(st["PASS"] / len(rs), 4),
            "remove_by_primary_reason": dict(collections.Counter(
                x["reason_code"] for x in rs if x["status"] == "REMOVE").most_common()),
            "flags_on_pass": dict(collections.Counter(
                f for x in rs if x["status"] == "PASS" for f in x["flags"].split("|") if f
            ).most_common())}
    json.dump(summ, open(f"{a.out}/source_qc_summary.json", "w"), indent=2)

    # spot-check sheet: random PASS per dataset + up to 5 REMOVE per (dataset, reason)
    rng = random.Random(SEED)
    byid = {r["example_id"]: r for r in recs}
    pick = []
    for ds in ("ESConv", "EmpatheticDialogues"):
        p = [x for x in rows if x["source_dataset"] == ds and x["status"] == "PASS"]
        pick += rng.sample(p, min(a.spotcheck_n, len(p)))
        by_reason = collections.defaultdict(list)
        for x in rows:
            if x["source_dataset"] == ds and x["status"] == "REMOVE":
                by_reason[x["reason_code"]].append(x)
        for _, xs in sorted(by_reason.items()):
            pick += rng.sample(xs, min(5, len(xs)))
    with open(f"{a.out}/source_qc_spotcheck.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["example_id", "source_dataset", "status", "reason_code", "flags",
                    "context_last_4_turns", "current_user_utterance", "original_response",
                    "agree_with_qc (y/n)", "note"])
        for x in pick:
            r = byid[x["example_id"]]
            ctx = "\n".join(f"{t['speaker']}: {t['text']}" for t in r["dialogue_context"][-4:])
            w.writerow([x["example_id"], x["source_dataset"], x["status"], x["reason_code"],
                        x["flags"], ctx, r["current_user_utterance"], r["original_response"],
                        "", ""])

    for k, v in summ["datasets"].items():
        print(f"{k}: {v['PASS']}/{v['examples']} PASS ({v['pass_rate']:.1%}); "
              f"REMOVE by reason {v['remove_by_primary_reason']}; flags {v['flags_on_pass']}")
    print(f"Wrote {a.out}/source_qc.csv, source_qc_summary.json, "
          f"source_qc_spotcheck.csv ({len(pick)} rows)")


if __name__ == "__main__":
    main()

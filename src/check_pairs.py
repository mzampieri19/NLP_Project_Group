"""Flag problems in the generated pairs; writes a review sheet for you + Nikhil.

Usage: python check_pairs.py --work work/

The sheet now includes the conversation CONTEXT and the original ESConv strategy
label (joined from selected_turns.jsonl) so you can judge added details yourself.

Auto-flags (heuristics only. They never edit anything, and a clean row is NOT proof):
  missing/empty          output absent or blank
  format                 preamble, markdown, quotes, role labels
  facts_changed?         numbers/proper nouns from the original missing in the rewrite,
                         or very low content-word overlap (paraphrases can trip this)
  self_disclosure_dropped  original speaks in first person ("I...", "my...") but the
                         rewrite has no first person (the supporter's own experience got lost)
  len_vs_original        far from original length (Control may be much shorter: validation removed)
  ev_much_longer / control_much_longer   EV and Control differ by >20 words
  ev_no_ack?             EV has no feeling-acknowledgement language
  control_has_validation?  Control still has explicit validation phrases
Info columns (not flags):
  new_words_control / new_words_ev  content words in the rewrite that appear in neither the
                         original nor the context. Scan these for INVENTED details
                         (e.g. 'daughter', 'distance'). Noisy: synonyms show up too, and
                         EV's validation sentence will legitimately add words.
"""

import argparse
import csv
import json
import os
import re
import statistics as st

# explicit validation phrases (strict: used to flag Control)
VALID_PHRASES = [
    "that sounds",
    "it sounds like",
    "sounds really",
    "makes sense",
    "understandable",
    "i hear you",
    "i'm sorry",
    "i am sorry",
    "must be",
    "must feel",
    "no wonder",
    "can understand",
    "can imagine",
    "can see how",
    "it's okay to",
    "it is okay to",
    "your feelings",
    "anyone would",
    "completely natural",
    "that's so hard",
    "that's really hard",
]
# broader: acceptable evidence that EV acknowledges a feeling
EV_ACK = VALID_PHRASES + [
    "frustrat",
    "painful",
    "stress",
    "exhaust",
    "discourag",
    "overwhelm",
    "anxious",
    "worried",
    "scary",
    "lonely",
    "upset",
    "hurt",
    "tough",
    "difficult",
    "hard to",
]
STOP = set(
    "a an the and or but of to in on for with is are was were be been it this that "
    "i you your my me we they he she as at by from have has had do does did so not "
    "no if then than just very really can could would should".split()
)
JUNK = [
    r"^here('s| is)",
    r"^rewritten",
    r"^sure[,!]",
    r"\*\*",
    r"^#+ ",
    r"^[\"“]",
    r"^(control|ev|supporter|response)\s*:",
]
FIRST = re.compile(r"\b(i|i'm|i've|i'd|i'll|my|me|myself)\b")


def plain(s):
    return s.replace("’", "'").replace("“", '"').replace("”", '"')


def words(s):
    return s.split()


def stem(w):
    return re.sub(r"(ing|ed|es|s)$", "", w) if len(w) > 4 else w


def cw(s):
    return {stem(w) for w in re.findall(r"[a-z']+", plain(s).lower()) if w not in STOP}


def nums(s):
    return set(re.findall(r"\d+", s))


def caps(s):
    return set(re.findall(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]+", plain(s)))


# first-person phrases that are validation, not the supporter's own experience
VALIDATION_I = re.compile(
    r"\bi('m| am)( so| really)? sorry\b|\bi (hear|understand|feel for|"
    r"can (understand|see|imagine|relate))\b"
)


def has_first(s):
    return bool(FIRST.search(VALIDATION_I.sub(" ", plain(s).lower())))


def new_words(rewrite, original, context, k=10):
    return ", ".join(sorted(cw(rewrite) - cw(original) - cw(context))[:k])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    rows = [json.loads(loads) for loads in open(f"{a.work}/pilot_pairs_raw.jsonl")]
    strat = {}
    sp = f"{a.work}/selected_turns.jsonl"
    if os.path.exists(sp):
        strat = {
            json.loads(loads)["example_id"]: ", ".join(
                json.loads(loads).get("original_strategies", [])
            )
            for loads in open(sp)
        }

    out, counts, gaps = [], {}, []
    for r in rows:
        o, c, e, ctx = r["original_response"], r["control_response"], r["ev_response"], r["context"]
        flags = []
        for name, t in (("control", c), ("ev", e)):
            if not t.strip():
                flags.append(f"missing/empty:{name}")
                continue
            if any(re.search(p, t.strip().lower()) for p in JUNK):
                flags.append(f"format:{name}")
            if nums(o) - nums(t):
                flags.append(f"facts_changed?:{name}:numbers")
            if caps(o) - caps(t):
                flags.append(f"facts_changed?:{name}:names")
            ov = len(cw(o) & cw(t)) / max(1, len(cw(o) | cw(t)))
            if ov < 0.15:
                flags.append(f"facts_changed?:{name}:low_overlap({ov:.2f})")
            if has_first(o) and not has_first(t):
                flags.append(f"self_disclosure_dropped:{name}")
            lo, lt = len(words(o)), len(words(t))
            lower = 0.4 if name == "control" else 0.6  # Control shrinks when validation is removed
            if lt > lo * 1.3 + 25 or lt < lo * lower:
                flags.append(f"len_vs_original:{name}({lt} vs {lo})")
        if c.strip() and e.strip():
            lc, le = len(words(c)), len(words(e))
            gaps.append(le - lc)
            if le - lc > 20:
                flags.append(f"ev_much_longer({lc} vs {le})")
            elif lc - le > 20:
                flags.append(f"control_much_longer({lc} vs {le})")
            if not any(k in plain(e).lower() for k in EV_ACK):
                flags.append("ev_no_ack?")
            if any(k in plain(c).lower() for k in VALID_PHRASES):
                flags.append("control_has_validation?")
        for f in flags:
            key = re.split(r"[:(]", f)[0]
            counts[key] = counts.get(key, 0) + 1
        out.append(
            [
                r["example_id"],
                "; ".join(flags),
                strat.get(r["example_id"], ""),
                ctx,
                o,
                c,
                e,
                new_words(c, o, ctx),
                new_words(e, o, ctx),
                "",
                "",
                "",
            ]
        )

    with open(f"{a.work}/review_sheet.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "example_id",
                "auto_flags",
                "original_strategy",
                "context",
                "original",
                "control",
                "ev",
                "new_words_control",
                "new_words_ev",
                "facts_advice_preserved (y/n)",
                "needs_correction (y/n)",
                "notes",
            ]
        )
        w.writerows(out)
    print(f"{len(rows)} pairs checked. Flag counts: {counts or 'none'}")
    if gaps:
        print(
            f"EV minus Control length: mean {st.mean(gaps):+.1f} words, "
            f"EV longer in {sum(g > 0 for g in gaps)}/{len(gaps)} pairs"
        )
    print(f"Wrote {a.work}/review_sheet.csv")


if __name__ == "__main__":
    main()

"""Flag problems in the generated pairs; writes a review sheet.

Usage: python check_pairs.py --work work/

Flags (flag only, never auto-fixed; do not pad outputs to equalize length):
  missing/empty     output absent or blank
  format            preamble, markdown, quotes, or role label
  facts_changed?    numbers/proper nouns in original missing from rewrite, or very low overlap
  len_vs_original   rewrite far from original length (allowing one short sentence)
  len_control_vs_ev control and EV differ a lot in length
  ev_no_ack?        EV has no feeling-acknowledgement cue (rough proxy)
  control_has_validation?  Control should have NO validation; flagged if emotion cues remain
These are heuristics. The review is for you and Nikhil to read, not for the script to decide.
"""

import argparse
import csv
import json
import re
import statistics as st

CUES = [
    "sounds",
    "feel",
    "feeling",
    "understandable",
    "makes sense",
    "frustrat",
    "hard",
    "difficult",
    "stress",
    "overwhelm",
    "anxious",
    "worried",
    "sorry",
    "tough",
    "painful",
    "discourag",
    "upset",
    "scary",
    "lonely",
    "sad",
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


def words(s):
    return s.split()


def cw(s):
    return {w for w in re.findall(r"[a-z']+", s.lower()) if w not in STOP}


def nums(s):
    return set(re.findall(r"\d+", s))


def caps(s):  # capitalized words not at sentence start (rough proper-noun proxy)
    return set(re.findall(r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]+", s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--work", required=True)
    a = ap.parse_args()
    rows = [json.loads(loads) for loads in open(f"{a.work}/pilot_pairs_raw.jsonl")]
    out, counts = [], {}
    ratios_c, ratios_e = [], []
    for r in rows:
        o, c, e = r["original_response"], r["control_response"], r["ev_response"]
        flags = []
        for name, t in (("control", c), ("ev", e)):
            if not t.strip():
                flags.append(f"missing/empty:{name}")
                continue
            if any(re.search(p, t.strip().lower()) for p in JUNK):
                flags.append(f"format:{name}")
            if nums(o) - nums(t):
                flags.append(f"facts_changed?:{name}:numbers")
            if caps(o) - caps(t) and len(caps(o) - caps(t)) >= 1:
                flags.append(f"facts_changed?:{name}:names")
            ov = len(cw(o) & cw(t)) / max(1, len(cw(o) | cw(t)))
            if ov < 0.25:
                flags.append(f"facts_changed?:{name}:low_overlap({ov:.2f})")
            lo, lt = len(words(o)), len(words(t))
            if lt > lo * 1.3 + 25 or lt < lo * 0.6:
                flags.append(f"len_vs_original:{name}({lt} vs {lo})")
        lc, le = len(words(c)), len(words(e))
        if c.strip() and e.strip():
            ratios_c.append(lc / max(1, len(words(o))))
            ratios_e.append(le / max(1, len(words(o))))
            if abs(le - lc) > 30 or le > lc * 1.6:
                flags.append(f"len_control_vs_ev({lc} vs {le})")
            if not any(k in e.lower() for k in CUES):
                flags.append("ev_no_ack?")
            if any(k in c.lower() for k in CUES):
                flags.append("control_has_validation?")
        for f in flags:
            counts[f.split(":")[0].split("(")[0]] = counts.get(f.split(":")[0].split("(")[0], 0) + 1
        out.append([r["example_id"], "; ".join(flags), o, c, e, "", "", ""])

    with open(f"{a.work}/review_sheet.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "example_id",
                "auto_flags",
                "original",
                "control",
                "ev",
                "facts_advice_preserved (y/n)",
                "needs_correction (y/n)",
                "notes",
            ]
        )
        w.writerows(out)
    print(f"{len(rows)} pairs checked. Flag counts: {counts or 'none'}")
    if ratios_c:
        print(
            "Mean length vs original: "
            f"control {st.mean(ratios_c):.2f}x, "
            f"ev {st.mean(ratios_e):.2f}x"
        )
    print(f"Wrote {a.work}/review_sheet.csv")


if __name__ == "__main__":
    main()
